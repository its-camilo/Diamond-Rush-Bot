from diamond_rush_vision import DiamondRushVision
from smart_agent import SmartAgent
from keyboard_simulator import KeyboardSimulator
from game_state import GameState
from cell import Cell
from level_route import (FiveRockLevelRoute, Level6CapturedRoute,
                         Level7CapturedRoute, Level8CapturedRoute,
                         Level9CapturedRoute, is_level9_captured_route,
                         Level10CapturedRoute, is_level10_captured_route,
                         Level11CapturedRoute, is_level11_captured_route,
                         Level12CapturedRoute, is_level12_captured_route,
                         Level13CapturedRoute, is_level13_captured_route,
                         Level14CapturedRoute, is_level14_captured_route,
                         Level15CapturedRoute, is_level15_captured_route,
                         is_level8_captured_route, is_five_rock_level,
                         is_level6_captured_route, is_level7_captured_route)
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

# Juego autónomo sin ventana de debug por defecto. Para revisar una captura
# supervisada con ENTER por vuelta: DIAMOND_DEBUG=1.
# DIAMOND_VERBOSE=1 imprime ademas el grid completo.
# El resumen del grid (conteos + jugador + salida) siempre se imprime.
# El click de foco previo a actuar mitiga el robo de foco de la ventana.
DEBUG_SHOW_IMAGE = os.environ.get("DIAMOND_DEBUG", "0") == "1"
VERBOSE_GRID = os.environ.get("DIAMOND_VERBOSE", "0") == "1"



def inject_route_player(grid, position, has_key=False):
    """Marca al jugador en `position` cuando la vision no lo detecta."""
    row, col = position
    if not (0 <= row < len(grid) and 0 <= col < len(grid[0])):
        return False
    kind = "player-with-key" if has_key else "player"
    cell = grid[row][col]
    if cell is not None:
        cell.cell_type = kind
        return True
    cell = Cell((row, col), kind)
    grid[row][col] = cell
    for dr, dc, mine, theirs in ((-1, 0, "neighbor_up", "neighbor_down"),
                                 (1, 0, "neighbor_down", "neighbor_up"),
                                 (0, -1, "neighbor_left", "neighbor_right"),
                                 (0, 1, "neighbor_right", "neighbor_left")):
        r, c = row + dr, col + dc
        if 0 <= r < len(grid) and 0 <= c < len(grid[0]) and grid[r][c] is not None:
            setattr(cell, mine, grid[r][c])
            setattr(grid[r][c], theirs, cell)
    return True

def log_grid_summary(grid, game_state=None):
    """Resumen de una linea por tipo + jugador + salida (debug sin foco)."""
    try:
        counts = {}
        for row in grid:
            for cell in row:
                if cell is None:
                    counts["None"] = counts.get("None", 0) + 1
                else:
                    t = cell.cell_type
                    counts[t] = counts.get(t, 0) + 1
        player = list(game_state.player_pos) if game_state is not None else None
        exits = game_state.exit_cells() if game_state is not None else None
        print(f"Grid resumen: {counts} jugador={player} salidas={exits}")
    except Exception as e:
        print(f"grid resumen omitido: {e}")

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
    level_route = None
    level_route_misses = 0
    route_fallback_logged = False
    vision = DiamondRushVision()
    while True:

        # first_grid = vision.debug_mode("screenshots/screenshot18.png")

        # Debug visible: ventana Resultado + ENTER por vuelta para revisar.
        first_grid = vision.realtime_mode(show_image=DEBUG_SHOW_IMAGE)
        # Area inestable (transicion/muerte/anuncio: una captura salio de
        # 561x452 en vez de 561x841): planificar sobre eso es basura
        # (grid de 80 terrains sin jugador). Recapturar sin mover.
        try:
            _x1, _y1, _x2, _y2 = (int(v) for v in vision.game_rectangle)
            _w, _h = _x2 - _x1, _y2 - _y1
        except (TypeError, ValueError):
            _w, _h = 0, 0
        if _w < 400 or _h < 700:
            print(f"Area inestable ({_w}x{_h}), recapturo sin planificar")
            continue
        # Simular desde la primera grilla hasta el final
        agent = SmartAgent(first_grid)
        if agent.game_state is None and level_route is not None:
            # Jugador oculto (HUD/animacion): seguir la ruta pregrabada
            # suponiendo que el ultimo tramo llego a su destino.
            blind = level_route.blind_expected()
            if blind is not None and inject_route_player(first_grid, *blind):
                print(f"Captura ciega: sigo ruta pregrabada desde {list(blind[0])}")
                agent = SmartAgent(first_grid)
        # Debug
        print("Grid inicial capturado, iniciando simulacion del agente...")
        log_grid_summary(first_grid, getattr(agent, "game_state", None))
        if VERBOSE_GRID:
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
        route_kind = (
            "level6_captured" if is_level6_captured_route(first_grid)
            else "level7_captured" if is_level7_captured_route(first_grid)
            else "level8_captured" if is_level8_captured_route(first_grid)
            else "level9_captured" if is_level9_captured_route(first_grid)
            else "level10_captured" if is_level10_captured_route(first_grid)
            else "level11_captured" if is_level11_captured_route(first_grid)
            else "level12_captured" if is_level12_captured_route(first_grid)
            else "level13_captured" if is_level13_captured_route(first_grid)
            else "level14_captured" if is_level14_captured_route(first_grid)
            else "level15_captured" if is_level15_captured_route(first_grid)
            else "five_rock" if is_five_rock_level(first_grid)
            else None
        )
        if (level_route is not None and route_kind is not None
                and route_kind != level_route.kind):
            level_route = None
            level_route_misses = 0
            route_fallback_logged = False
        if level_route is None and route_kind is not None:
            route_cls = {"level6_captured": Level6CapturedRoute,
                         "level7_captured": Level7CapturedRoute,
                         "level8_captured": Level8CapturedRoute,
                         "level9_captured": Level9CapturedRoute,
                         "level10_captured": Level10CapturedRoute,
                         "level11_captured": Level11CapturedRoute,
                         "level12_captured": Level12CapturedRoute,
                         "level13_captured": Level13CapturedRoute,
                         "level14_captured": Level14CapturedRoute,
                         "level15_captured": Level15CapturedRoute}.get(
                             route_kind, FiveRockLevelRoute)
            level_route = route_cls(
                first_grid, new_pos,
                has_key=agent.game_state.player_has_key)
            label = {"level6_captured": "ruta grabada de Nivel 6",
                     "level7_captured": "ruta grabada de Nivel 7",
                     "level8_captured": "ruta grabada de Nivel 8",
                     "level9_captured": "ruta grabada de Nivel 9",
                     "level10_captured": "ruta grabada de Nivel 10",
                     "level11_captured": "ruta grabada de Nivel 11",
                     "level12_captured": "ruta grabada de Nivel 12",
                     "level13_captured": "ruta grabada de Nivel 13",
                     "level14_captured": "ruta grabada de Nivel 14",
                     "level15_captured": "ruta grabada de Nivel 15"}.get(
                         route_kind, "ruta RRRR DD ... DDD")
            print(f"Nivel con ruta fija detectado: siguiendo {label}")
            route_fallback_logged = False
        if level_route is not None:
            if route_kind is not None:
                level_route_misses = 0
            elif level_route.completed or level_route.unusable:
                level_route_misses += 1
                if level_route_misses >= 2:
                    level_route = None
                    level_route_misses = 0
                    route_fallback_logged = False
            elif not level_route.completed and not level_route.unusable:
                # El inventario cambia durante la secuencia (llave/puerta,
                # fosos rellenados); una firma temporal distinta no la corta.
                level_route_misses = 0
            if level_route is not None and not level_route.completed and not level_route.unusable:
                level_route.observe(new_pos, last_action, first_grid)
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
        winner_state: GameState | None = None
        if (level_route is not None and not level_route.completed
                and not level_route.unusable):
            route_action = level_route.next_action(
                first_grid, new_pos,
                has_key=agent.game_state.player_has_key,
                failed_targets=failed_targets,
            )
            if route_action is not None:
                print(f"Ruta fija {level_route.kind}: {route_action.get_readable()}")
                winner_state = GameState(
                    first_grid, new_pos, 0, [route_action],
                    player_has_key=agent.game_state.player_has_key,
                )
            elif (level_route.completed or level_route.unusable) and not route_fallback_logged:
                print("Ruta fija finalizada/no reenganchable; planner general")
                route_fallback_logged = True
        if winner_state is None:
            if (level_route is not None and getattr(level_route, "rigid", False)
                    and not level_route.completed):
                # En el nivel 1/8 no mezclar acciones greedy con la secuencia
                # manual: esperar otra captura antes de volver a tocar teclas.
                print("Ruta rígida sin paso seguro; recapturo sin usar el planner general")
                last_action = None
                prev_pos = new_pos
                continue
            winner_state = agent.simulate()
        if winner_state is None:
            print("Sin ruta valida, recapturo pantalla sin mover")
            last_action = None
            prev_pos = new_pos
            continue
        first_planned = winner_state.action_history[0] if winner_state.action_history else None
        is_level_route_action = getattr(first_planned, "action", "") in (
            "level_route", "level_route_rejoin", "level_route_detour")
        if (not is_level_route_action and winner_state.exit_cells()
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
        elif getattr(done, "consumes_key", False):
            held_key = False
        else:
            held_key = winner_state.player_has_key



if __name__ == "__main__":
    main()
