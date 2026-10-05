

from typing import List
from cell import Cell
from rock_simulation import RockSimulation
from game_state import GameState
from game_action import GameAction
from collections import deque


def _is_teleport(action, player_pos):
    """Correccion 1 (defensa en simulacion): accion de movimiento con camino
    vacio hacia otra casilla = objetivo inalcanzable, no teletransporte."""
    try:
        if tuple(int(v) for v in action.coordinates) == tuple(int(v) for v in player_pos):
            return False
    except (TypeError, ValueError, IndexError):
        return True
    return not getattr(action, "path", None)


def state_hash_key(grid, player_pos, player_has_key):
    """Clave de estado para la busqueda del agente.

    Incluye rocas y huecos: sin ellos, empujar una roca generaba el mismo hash
    que antes del empuje y la busqueda se ciclaba entre push/backtrack hasta el
    limite de 300 pasos sin avanzar.
    """
    try:
        dd = tuple(sorted(tuple(c.coordinates) for row in grid for c in row if c is not None and c.cell_type == "diamond"))
        kk = tuple(sorted(tuple(c.coordinates) for row in grid for c in row if c is not None and c.cell_type == "key"))
        dr = tuple(sorted(tuple(c.coordinates) for row in grid for c in row if c is not None and c.cell_type in ("door", "metal-door")))
        sp = tuple(sorted(tuple(c.coordinates) for row in grid for c in row if c is not None and c.cell_type == "spike"))
        su = tuple(sorted(tuple(c.coordinates) for row in grid for c in row if c is not None and c.cell_type == "spike-up"))
        rk = tuple(sorted(tuple(c.coordinates) for row in grid for c in row if c is not None and c.cell_type == "rock"))
        rf = tuple(sorted(tuple(c.coordinates) for row in grid for c in row if c is not None and c.cell_type == "rock-in-fall"))
        rb = tuple(sorted(tuple(c.coordinates) for row in grid for c in row if c is not None and c.cell_type == "rock-in-button"))
        fl = tuple(sorted(tuple(c.coordinates) for row in grid for c in row if c is not None and c.cell_type == "fall"))
        bt = tuple(sorted(tuple(c.coordinates) for row in grid for c in row if c is not None and c.cell_type in ("button", "push_button", "push-button")))
        return (tuple(player_pos), dd, kk, dr, player_has_key, sp, su, rk, rf, rb, fl, bt)
    except Exception:
        return None


class SmartAgent:
    # El agente define la estrategia a seguir para resolver el juego
    def __init__(self, first_grid : List[List[Cell | None]]):
        player_pos = None
        has_key = False
        for row in range(0,len(first_grid)):
            for col in range(0,len(first_grid[row])):
                c = first_grid[row][col]
                if c is not None and c.cell_type in ("player", "player-with-key", "player-with-key1", "player-with-key2"):
                    player_pos = [row, col]
                    if "with-key" in c.cell_type:
                        has_key = True
        if player_pos is None:
            print("No se pudo encontrar la posicion del jugador en el grid inicial (ni player ni player-with-key)")
            game_state = None
            self.game_state = None
        else:
            game_state = GameState(first_grid, player_pos, 0, [], player_has_key=has_key)
            self.game_state = game_state
        

    def simulate(self):
        # Esta funcion se encarga de simular el juego con un loop
        # Se devuelve el estado del juego al lograr la meta
        # En cada paso se guarda la accion tomaada por cada estado de juego
        # Se tiene una pila de acciones en orden para ir de forma greedy a la solucion pero si no se puede hacer la accion
        # se hace la siguiente y asi, si no hay ninguna accion se considera unn camino bloqueado y se devuelve hasta el ultimo estado viable
        # Retorna el game state donde se gana junto con sus acciones
        if self.game_state is None:
            print("No se pudo encontrar la posicion del jugador en el grid inicial")
            return None
        state_stack : deque = []
        simulated_game_state : GameState = self.game_state
        simulated_action : GameAction = simulated_game_state.get_next_action()
        import time as _time
        steps = 0
        max_steps = 200
        t0 = _time.time()
        time_budget = 20.0
        found_ladder = False
        # Mejor progreso visto (los originales lo descartan al vaciar la pila y se quedan quietos)
        best_partial = None
        best_score = 0
        def _useful(st):
            # Progreso parcial: el diamante vale +2 aunque cueste pinchos.
            # go_spike puntua 0 (antes -1): limpiar el corredor del Nivel 2
            # para llegar al diamante es progreso, no perdida (con -1 el parcial
            # 3xspike+diamante daba -1 y se descartaba -> quieto para siempre).
            # go_button +1: pisar el boton post-botin abre la salida.
            try:
                score = 0
                for ac in st.action_history:
                    act = getattr(ac, "action", "")
                    if act in ("get_diamond", "get_key", "open_door"):
                        score += 2
                    elif act in ("push_rock", "go_button", "go_explore"):
                        score += 1
                    elif act == "go_spike":
                        score += 0
                return score
            except Exception:
                return -1
        seen = set()
        def _hash(st):
            return state_hash_key(st.grid, st.player_pos, st.player_has_key)
        seen.add(_hash(simulated_game_state))
        while True:
            steps += 1
            if steps > max_steps or (_time.time() - t0) > time_budget:
                print("Limite de simulacion alcanzado, devuelvo mejor estado")
                break
            if (simulated_action.action in ("get_diamond", "get_key", "open_door",
                                              "go_spike", "go_ladder", "go_button",
                                              "go_explore")
                    and _is_teleport(simulated_action, simulated_game_state.player_pos)):
                print(f"Objetivo inalcanzable (camino vacio): {simulated_action.action} "
                      f"{simulated_action.coordinates}, backtrack")
                simulated_action = GameAction("None", [0, 0], path=[])
            match simulated_action.action:
                case "get_diamond":
                    # Mover pj al diamante, quitar diamante de la grilla.
                    # Solo si no pasó por spikes
                    next_state : GameState = simulated_game_state.clone()
                    
                    next_state.game_state += 1
                    # TODO Puede que haga falta crear un estado de personaje in spike.. o manejar el player pos, sin ponerlo como cell.
                    
                    # Se borra el diamante y se cambia a terrain
                    new_terrain = Cell(
                        coordinates=simulated_action.coordinates, 
                        cell_type="terrain"
                    )

                    # Se colocan sus vecinos de nuevo manualmente
                    r, c = simulated_action.coordinates
                    neighbors = []
                    for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < len(next_state.grid) and 0 <= nc < len(next_state.grid[0]):
                            neighbors.append(next_state.grid[nr][nc])
                    new_terrain.set_neighbors(neighbors)

                    # Se coloca la nueva celda en la grilla
                    next_state.grid[r][c] = new_terrain

                    # Se borra el personaje y se cambia a terrain, debe hacerse solo si es la primera vez
                    pr, pc = simulated_game_state.player_pos
                    if next_state.grid[pr][pc].cell_type == "player":
                        player_replaced = Cell(
                            coordinates=simulated_game_state.player_pos, 
                            cell_type="terrain"
                        )

                        # Se colocan denuevo sus vecinos
                        player_neighbors = []
                        for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                            nr, nc = pr + dr, pc + dc
                            if 0 <= nr < len(next_state.grid) and 0 <= nc < len(next_state.grid[0]):
                                player_neighbors.append(next_state.grid[nr][nc])
                        player_replaced.set_neighbors(player_neighbors)

                        # Se actualiza en la grilla
                        next_state.grid[pr][pc] = player_replaced

                    # Se actualiza player pos
                    next_state.player_pos = simulated_action.coordinates

                    simulated_game_state = next_state
                    
                    # Añadir accion anterior
                    simulated_game_state.action_history.append(simulated_action)
                    # Actualizar lo que hay en exists
                    simulated_game_state.check_objects_in_grid()

                    state_stack.append(next_state)
                    print("Llego a nuevo estado get diamond")
                case "get_key":
                    # Mover pj al key, quitar key de la grilla.
                    next_state : GameState = simulated_game_state.clone()
                    
                    next_state.game_state += 1
                    next_state.player_has_key = True  # El jugador ahora tiene la llave
                    # Se borra el key y se cambia a terrain
                    new_terrain = Cell(
                        coordinates=simulated_action.coordinates, 
                        cell_type="terrain"
                    )

                    # Se colocan sus vecinos de nuevo manualmente
                    r, c = simulated_action.coordinates
                    neighbors = []
                    for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < len(next_state.grid) and 0 <= nc < len(next_state.grid[0]):
                            neighbors.append(next_state.grid[nr][nc])
                    new_terrain.set_neighbors(neighbors)

                    # Se coloca la nueva celda en la grilla
                    next_state.grid[r][c] = new_terrain

                    # Se borra el personaje y se cambia a terrain, debe hacerse solo si es la primera vez
                    pr, pc = simulated_game_state.player_pos
                    if next_state.grid[pr][pc].cell_type == "player":
                        player_replaced = Cell(
                            coordinates=simulated_game_state.player_pos, 
                            cell_type="terrain"
                        )

                        # Se colocan denuevo sus vecinos
                        player_neighbors = []
                        for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                            nr, nc = pr + dr, pc + dc
                            if 0 <= nr < len(next_state.grid) and 0 <= nc < len(next_state.grid[0]):
                                player_neighbors.append(next_state.grid[nr][nc])
                        player_replaced.set_neighbors(player_neighbors)

                        # Se actualiza en la grilla
                        next_state.grid[pr][pc] = player_replaced

                    # Se actualiza player pos
                    next_state.player_pos = simulated_action.coordinates

                    simulated_game_state = next_state
                    
                    # Añadir accion anterior
                    simulated_game_state.action_history.append(simulated_action)
                    # Actualizar lo que hay en exists
                    simulated_game_state.check_objects_in_grid()

                    state_stack.append(next_state)
                    print("Llego a nuevo estado get key")
                case "open_door":
                    # Mover pj al key, quitar key de la grilla.
                    next_state : GameState = simulated_game_state.clone()
                    
                    next_state.game_state += 1
                    next_state.player_has_key = False  # El jugador ahora no tiene la llave
                    # Se borra el key y se cambia a terrain
                    new_terrain = Cell(
                        coordinates=simulated_action.coordinates, 
                        cell_type="terrain"
                    )

                    # Se colocan sus vecinos de nuevo manualmente
                    r, c = simulated_action.coordinates
                    neighbors = []
                    for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < len(next_state.grid) and 0 <= nc < len(next_state.grid[0]):
                            neighbors.append(next_state.grid[nr][nc])
                    new_terrain.set_neighbors(neighbors)

                    # Se coloca la nueva celda en la grilla
                    next_state.grid[r][c] = new_terrain

                    # Se borra el personaje y se cambia a terrain, debe hacerse solo si es la primera vez
                    pr, pc = simulated_game_state.player_pos
                    if next_state.grid[pr][pc].cell_type == "player":
                        player_replaced = Cell(
                            coordinates=simulated_game_state.player_pos, 
                            cell_type="terrain"
                        )

                        # Se colocan denuevo sus vecinos
                        player_neighbors = []
                        for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                            nr, nc = pr + dr, pc + dc
                            if 0 <= nr < len(next_state.grid) and 0 <= nc < len(next_state.grid[0]):
                                player_neighbors.append(next_state.grid[nr][nc])
                        player_replaced.set_neighbors(player_neighbors)

                        # Se actualiza en la grilla
                        next_state.grid[pr][pc] = player_replaced

                    # Se actualiza player pos
                    next_state.player_pos = simulated_action.coordinates

                    simulated_game_state = next_state
                    
                    # Añadir accion anterior
                    simulated_game_state.action_history.append(simulated_action)
                    # Actualizar lo que hay en exists
                    simulated_game_state.check_objects_in_grid()

                    state_stack.append(next_state)
                    print("Llego a nuevo estado open door")
                case "push_rock":
                    # Actualizar el estado del juego con la simulacion de la roca
                    rock_simulation : RockSimulation = simulated_action
                    next_state : GameState = simulated_game_state.clone()
                    next_state.game_state += 1
                    # Actualizar la grilla con el estado de la roca
                    next_state.grid = rock_simulation.grid

                    # Se borra el personaje y se cambia a terrain, debe hacerse solo si es la primera vez
                    pr, pc = rock_simulation.player_pos
                    if next_state.grid[pr][pc].cell_type == "player":
                        player_replaced = Cell(
                            coordinates=rock_simulation.player_pos, 
                            cell_type="terrain"
                        )

                        # Se colocan denuevo sus vecinos
                        player_neighbors = []
                        for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                            nr, nc = pr + dr, pc + dc
                            if 0 <= nr < len(next_state.grid) and 0 <= nc < len(next_state.grid[0]):
                                player_neighbors.append(next_state.grid[nr][nc])
                        player_replaced.set_neighbors(player_neighbors)

                        # Se actualiza en la grilla
                        next_state.grid[pr][pc] = player_replaced
                    
                    next_state.player_pos = rock_simulation.player_pos
                    # Actualizar el estado del juego
                    next_state.check_objects_in_grid()
                    # Añadir acciones anteriores
                    for ac in simulated_action.action_history:
                        next_state.action_history.append(ac)
                    # Guardar nuevo estado en la pila
                    state_stack.append(next_state)

                    simulated_game_state = next_state
                    print("Llego a nuevo estado rock push")
            
                case "go_spike":
                    next_state: GameState = simulated_game_state.clone()
                    next_state.game_state += 1

                    r, c = simulated_action.coordinates
                    cell = next_state.grid[r][c]

                    # Activar spike (un solo uso): queda transitable peso 1
                    if cell and cell.cell_type == "spike":
                        cell.cell_type = "spike-up"
                        cell.weight = 1
                        cell.walkable = True

                    # Actualizar posición del jugador
                    next_state.player_pos = simulated_action.coordinates

                    # Añadir acción al historial
                    next_state.action_history.append(simulated_action)

                    # Actualizar objetos en el grid, si tienes esta función para actualizar estados
                    next_state.check_objects_in_grid()

                    # Guardar nuevo estado en la pila
                    state_stack.append(next_state)

                    simulated_game_state = next_state
                    print("Llego a nuevo estado go spike")
                case "go_button":
                    # Pisar boton (Valentina 'B'): mueve al jugador, el boton
                    # queda (abre puertas/salida en el juego real).
                    next_state: GameState = simulated_game_state.clone()
                    next_state.game_state += 1
                    next_state.player_pos = simulated_action.coordinates
                    next_state.action_history.append(simulated_action)
                    next_state.check_objects_in_grid()
                    state_stack.append(next_state)
                    simulated_game_state = next_state
                    print("Llego a nuevo estado go button")
                case "go_explore":
                    # Frontera segura: mueve al jugador sin mutar el grid.
                    next_state: GameState = simulated_game_state.clone()
                    next_state.game_state += 1
                    next_state.player_pos = simulated_action.coordinates
                    next_state.action_history.append(simulated_action)
                    next_state.check_objects_in_grid()
                    state_stack.append(next_state)
                    simulated_game_state = next_state
                    print("Llego a nuevo estado go explore")
                case "go_ladder":
                    next_state : GameState = simulated_game_state.clone()
                    next_state.game_state += 1
                    simulated_game_state = next_state
                    # Añadir accion anterior
                    simulated_game_state.action_history.append(simulated_action)
                    state_stack.append(next_state)
                    found_ladder = True
                    break
                case "None":
                    if len(state_stack) > 0:
                        simulated_game_state = state_stack.pop()
                        print("Me devolvi un estado")
                    else:
                        print("No hay mas game state, no encontre la solucion")
                        break
            try:
                _sc = _useful(simulated_game_state)
                if _sc > best_score:
                    best_score = _sc
                    best_partial = simulated_game_state
            except Exception:
                pass
            h = _hash(simulated_game_state)
            if h is not None:
                if h in seen:
                    simulated_action = GameAction("None", [0, 0], path=[])
                    # forzar backtrack sin reexpandir
                    if len(state_stack) > 0:
                        simulated_game_state = state_stack.pop()
                        print("Estado repetido, backtrack")
                    else:
                        print("No hay mas game state, no encontre la solucion")
                        break
                    simulated_action = simulated_game_state.get_next_action()
                    continue
                seen.add(h)
            simulated_action : GameAction | RockSimulation = simulated_game_state.get_next_action()
        if not found_ladder:
            # Sin ruta completa: mejor parcial VISTO (no solo lo que queda en la pila,
            # que al vaciarse pierde el progreso: era tu loop quieto en (12,1)).
            if best_partial is not None and best_score > 0:
                print(f"Sin ruta completa: ejecuto progreso parcial util ({len(best_partial.action_history)} acciones)")
                return best_partial
            print("Simulacion sin exito: no ejecutar movimientos, recapturar")
            return None
        print("Se encontró simulacion hasta go ladder")
        return simulated_game_state