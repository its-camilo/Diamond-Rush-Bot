
from game_action import GameAction
from game_state import GameState
import pyautogui
from pyKey import pressKey, releaseKey, press, sendSequence, showKeys

class KeyboardSimulator:
    # Esta clase se encarga de simular el teclado para enviar acciones al juego
    def __init__(self, game_state: GameState):
        self.game_state = game_state
        self.actions = game_state.action_history

    async def execute_actions(self):
        total_path = []
        # Ejecutar las acciones en la lista de acciones
        for action in self.actions:
            for th in action.path:
                total_path.append(th)
        # Limpiar la lista de acciones
        self.actions = []
        print("Lista completa de pasos a seguir")
        print(total_path)
        for step in total_path:
            # Simular el movimiento en el juego
            self.simulate_move(step)
            # Esperar un tiempo para que el juego procese el movimiento
            pyautogui.sleep(0.20)

    async def execute_first_action(self):
        # Closed-loop estilo Valentina+Seb: ejecuta SOLO el primer objetivo y recaptura.
        # Los 94 pasos ciegos se desincronizan (un input perdido = resto basura).
        if not self.actions:
            print("Sin acciones para ejecutar")
            return None
        action = self.actions[0]
        # Correccion 1 (accion fantasma): camino vacio hacia otra casilla =
        # objetivo inalcanzable. No ejecutar ni marcar como hecho.
        try:
            at_target = (tuple(int(v) for v in action.coordinates)
                         == tuple(int(v) for v in self.game_state.player_pos))
        except (TypeError, ValueError, IndexError):
            at_target = False
        if getattr(action, "action", "") != "push_rock" and not at_target and not getattr(action, "path", None):
            print(f"Objetivo inalcanzable (camino vacio): {action.get_readable()}, no ejecuto")
            self.actions = []
            return None
        print(f"Ejecuto solo: {action.get_readable()}")
        for step in action.path:
            self.simulate_move(step)
            pyautogui.sleep(0.20)
        self.actions = []
        return action

    # Dado que cada accion es un ir a x,y o empujar a alguna direccion, se debe hacer un A* para encontrar el camino
    # luego simular cada movimiento del A * en el juego
    def execute_action(self, action: GameAction):
        path = action.path
        # Simular el movimiento en el juego
        for step in path:
            # Simular el movimiento en el juego
            self.simulate_move(step)
            # Esperar un tiempo para que el juego procese el movimiento
            pyautogui.sleep(0.20)

    def simulate_move(self, step: str):
        # Simular el movimiento en el juego
        # Esto se hace enviando las teclas de movimiento al juego
        # Se puede usar pyautogui o pynput para simular el teclado
        # Hold 0.20 (Seb usaba 0.15; subir a 0.20 evita inputs tragados por el navegador)
        if step == "up":
            press("UP",0.20)
        elif step == "down":
            press("DOWN",0.20)
        elif step == "left":
            press("LEFT",0.20)
        elif step == "right":
            press("RIGHT",0.20)
