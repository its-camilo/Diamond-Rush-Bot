from diamond_rush_vision import DiamondRushVision
from smart_agent import SmartAgent
from keyboard_simulator import KeyboardSimulator
from game_state import GameState
import asyncio
import os
# Usar todos los nucleos: OpenCV/numpy en multihilo y pool de procesos en rocas.
os.environ.setdefault("OMP_NUM_THREADS", str(os.cpu_count() or 4))
os.environ.setdefault("MKL_NUM_THREADS", str(os.cpu_count() or 4))
os.environ.setdefault("OPENBLAS_NUM_THREADS", str(os.cpu_count() or 4))
try:
    import cv2
    cv2.setNumThreads(max(4, (os.cpu_count() or 4) // 2))
except Exception:
    pass
try:
    # Prioridad alta en Windows para que el planificador no recorte CPU.
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(
        ctypes.windll.kernel32.GetCurrentProcess(), 0x00000080)
    print(f"CPU: {os.cpu_count()} hilos logicos, prioridad alta activada")
except Exception as e:
    print(f"Prioridad normal ({e})")

# TODO recortar assets en resolucion de portatil 1366x768

# Sin ventana de debug: el juego conserva el foco y los inputs llegan.
DEBUG_SHOW_IMAGE = False

def focus_center(rect):
    """Centro del area de juego para el click de foco.

    El juego solo responde al teclado y el click en el canvas no hace nada,
    pero si la ventana Resultado u otra app roba el foco, los 20 pasos del
    plan caen al vacio (cero movimiento, como en el log de (13,5)->(8,5)).
    """
    try:
        x1, y1, x2, y2 = (int(v) for v in rect)
        return ((x1 + x2) // 2, (y1 + y2) // 2)
    except (TypeError, ValueError):
        return None


def register_repeat(streak, last_target, target, veto_after=2):
    """Racha del mismo objetivo fallido: veta al repetirse veto_after veces.

    Un solo fallo no veta nada (input tragado por foco, captura con tierra
    sin cavar). Tras vetar, la racha se reinicia.
    """
    if target is None:
        return 0, None, False
    streak = streak + 1 if target == last_target else 1
    if streak >= veto_after:
        return 0, target, True
    return streak, target, False


def detect_stuck(prev_pos, new_pos, action):
    """Correccion 3 (stuck/deadlock): comando con pasos reales que deja al
    jugador en la misma casilla = la accion fallo (choque con puerta/muro).
    Camino vacio no cuenta como atasco: es fallo del planner (correccion 1).
    """
    if action is None or not getattr(action, "path", None):
        return False
    try:
        return tuple(int(v) for v in prev_pos) == tuple(int(v) for v in new_pos)
    except (TypeError, ValueError, IndexError):
        return False


def resolve_held_key(held_key, vision_has_key, last_action, player_moved):
    """Correccion 2 (persistencia mentirosa): solo se cree la llave si el HUD
    la muestra o si se camino de verdad hacia su celda. Intentar abrir sin
    moverse (choque) fuerza has_key=False.
    """
    if vision_has_key:
        return True
    if last_action is None:
        return held_key
    act = getattr(last_action, "action", "")
    path = getattr(last_action, "path", None) or []
    if act == "get_key":
        return bool(path and player_moved)
    if act == "open_door":
        return False
    return held_key


def main():
    # Principio Valentina: el inventario no depende solo del sprite (fragil).
    # Se persiste entre capturas y se combina (OR) con lo que ve la vision.
    held_key = False
    last_action = None
    prev_pos = None
    failed_targets = set()
    stuck_streak = 0
    stuck_target = None
    blind_streak = 0
    exit_reject_streak = 0
    exit_reject_target = None
    vision = DiamondRushVision()
    while True:

        # first_grid = vision.debug_mode("screenshots/screenshot18.png")

        # Debug visible: ventana Resultado + ENTER por vuelta para revisar.
        first_grid = vision.realtime_mode(show_image=DEBUG_SHOW_IMAGE)
        # Simular desde la primera grilla hasta el final
        agent = SmartAgent(first_grid)
        # Debug
        print("Grid inicial capturado, iniciando simulacion del agente...")
        print(first_grid)
        if agent.game_state is None:
            # Sin jugador visible (muerte o sprite tapado): no mover. Tras
            # varios ciegos seguidos el estado heredado caduca (nivel nuevo).
            blind_streak += 1
            if blind_streak >= 4:
                print("4 capturas ciegas: reseteo llave/vetos (nivel nuevo o muerte)")
                held_key = False
                vision.clear_suppressed()
                failed_targets.clear()
                stuck_streak = 0
                stuck_target = None
                last_action = None
                prev_pos = None
            continue
        blind_streak = 0
        new_pos = list(agent.game_state.player_pos)
        player_moved = (prev_pos is not None and prev_pos != new_pos)
        if last_action is not None and prev_pos is not None:
            if detect_stuck(prev_pos, new_pos, last_action):
                # La llave fantasma cae aqui: choque contra puerta = sin llave.
                try:
                    target = (last_action.action,
                              (int(last_action.coordinates[0]),
                               int(last_action.coordinates[1])))
                except (TypeError, ValueError, IndexError, AttributeError):
                    target = None
                stuck_streak, stuck_target, veto = register_repeat(
                    stuck_streak, stuck_target, target)
                if veto:
                    # Peso infinito al nodo tras choques repetidos (un solo
                    # input tragado por foco perdido no veta nada).
                    failed_targets.add(target)
                    print(f"Atasco x2: {last_action.action} "
                          f"{getattr(last_action, 'coordinates', None)} sin moverse, "
                          f"penalizado y sin llave")
                else:
                    print(f"Atasco: {last_action.action} "
                          f"{getattr(last_action, 'coordinates', None)} sin moverse, "
                          f"replanifico y sin llave")
                held_key = False
                vision.unmark_collected(last_action)
                last_action = None
                prev_pos = new_pos
                continue
        else:
            stuck_streak = 0
            stuck_target = None
            if player_moved:
                # Hubo progreso real: las penalizaciones viejas caducan (evita
                # vetos heredados de otro nivel o de un atasco ya resuelto).
                failed_targets.clear()
        vision_has_key = agent.game_state.player_has_key
        held_key = resolve_held_key(held_key, vision_has_key, last_action, player_moved)
        if held_key and not vision_has_key:
            print("Llave persistida de la vuelta anterior (hubo desplazamiento real)")
            agent.game_state.player_has_key = True
        agent.game_state.failed_targets = set(failed_targets)
        winner_state : GameState = agent.simulate()
        if winner_state is None:
            print("Sin ruta valida, recapturo pantalla sin mover")
            last_action = None
            prev_pos = new_pos
            continue
        if (winner_state.exit_cells()
                and not winner_state.exit_reachable_from(winner_state.player_pos)):
            # Anti-softlock: el parcial termina sin retorno a la salida
            # conocida. No ejecutar; vetar el primer objetivo solo si se
            # repite (una captura con tierra sin cavar no veta nada).
            first = winner_state.action_history[0] if winner_state.action_history else None
            try:
                target = (first.action, (int(first.coordinates[0]),
                                         int(first.coordinates[1]))) if first is not None else None
            except (TypeError, ValueError, IndexError, AttributeError):
                target = None
            exit_reject_streak, exit_reject_target, veto = register_repeat(
                exit_reject_streak, exit_reject_target, target)
            if veto:
                failed_targets.add(target)
                print(f"Parcial sin salida x2: {target} vetado, replanifico")
            else:
                print(f"Parcial sin salida a {winner_state.exit_cells()}: no ejecuto, replanifico")
            last_action = None
            prev_pos = new_pos
            continue
        exit_reject_streak = 0
        exit_reject_target = None
        #for i in winner_state.action_history:
        #    print(i.get_readable())
        key_simulator = KeyboardSimulator(winner_state)

        # Foco antes de actuar: si otra ventana lo robo, los pasos caen al
        # vacio y el jugador no se mueve (doble open_door [8,5] quieto).
        fxy = focus_center(vision.game_rectangle)
        if fxy is not None:
            try:
                import pyautogui as _pg
                _pg.click(fxy[0], fxy[1])
                _pg.sleep(0.15)
            except Exception as e:
                print(f"foco omitido: {e}")

        # Paso a paso: solo el primer objetivo, luego recapturar (closed-loop).
        # Ejecutar los 94 pasos ciegos se desincronizan (un input perdido = resto basura).
        done = asyncio.run(key_simulator.execute_first_action())
        last_action = done
        prev_pos = new_pos
        vision.mark_collected(done)
        if done is None:
            # Camino vacio (correccion 1): nada se marco como hecho.
            held_key = winner_state.player_has_key
            continue
        if getattr(done, "action", "") == "get_key":
            held_key = bool(getattr(done, "path", None))
        elif getattr(done, "action", "") == "open_door":
            held_key = False
        else:
            held_key = winner_state.player_has_key



if __name__ == "__main__":
    main()
