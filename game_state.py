
from collections import deque
import copy
from functools import lru_cache
from typing import List, Tuple


from cell import Cell
from game_action import GameAction
from a_star import AStar
from rock_simulation import RockSimulation


class GameState:
    # Esta clase se encarga de guardar el estado del juego junto ccon la lista de acciones que lo llevaron a ese estado
    # Se considera un estado ganador si el jugador llega a la escalera abierta. (el agente revisa esta condicion para romper la simulacion)
    # con player pos y ladder pos
    # Las acciones son ir a x,y o empujar a alguna direccion
    def __init__(self, grid: List[List[Cell | None]], player_pos: tuple[int, int], game_state: int, action_history: list[GameAction] | None = None, player_has_key: bool = False):
        self.grid = grid
        self.player_pos = player_pos
        self.player_has_key = player_has_key
        self.game_state = game_state
        self.action_history = list(action_history) if action_history is not None else []
        self.check_objects_in_grid()
        # Las acciones van en orden de peso. go_button (Valentina 'B') va antes
        # que go_spike: pisar el boton abre la salida y no mata. go_explore es
        # red de seguridad post-botin (Nivel 2 sin salida visible).
        self.actions = ["go_ladder", "get_key", "open_door", "get_diamond", "push_rock", "shove_rock", "go_button", "go_explore", "go_spike"]
        self.alternative_stack: list[tuple[str, tuple[int, int], list]] = []  # Lista de tuplas (action_type, coordinates, path)

        # Correccion 3 (stuck detector): objetivos penalizados con peso
        # infinito tras chocar sin moverse. main.py los inyecta entre vueltas.
        self.failed_targets: set = set()
    
    def check_objects_in_grid(self):
        doorExists, keyExists, diamondExists, rockExists = False, False, False, False
        buttonExists = False
        for row in self.grid:
            for cell in row:
                if cell != None:
                    if cell.cell_type in ("door", "metal-door"):
                        doorExists = True
                    elif cell.cell_type == "key":
                        keyExists = True
                    elif cell.cell_type == "diamond":
                        diamondExists = True
                    elif cell.cell_type == "rock":
                        rockExists = True
                    elif cell.cell_type in ("button", "push_button", "push-button"):
                        buttonExists = True
        self.doorExist, self.keyExist, self.diamondExist, self.rockExist = doorExists, keyExists, diamondExists, rockExists
        self.buttonExist = buttonExists

    def _astar_path(self, start, goal):
        # Principio Valentina: los caminos a diamante/llave/escalera no pueden
        # atravesar puertas cerradas ni pinchos activos (el pincho se limpia
        # primero con go_spike explicito, de un solo uso). Antes A* los cruzaba
        # por coste alto y el parcial iba por donde no era (ej. (5,2)->(6,2) spike).
        # Set bloqueado (sin mutar celdas: thread-safe).
        blocked = set()
        for row in self.grid:
            for cell in row:
                if cell is None:
                    continue
                if cell.cell_type == "spike":
                    blocked.add((int(cell.coordinates[0]), int(cell.coordinates[1])))
                elif cell.cell_type in ("door", "metal-door"):
                    if not self.player_has_key:
                        blocked.add((int(cell.coordinates[0]), int(cell.coordinates[1])))
        astar = AStar(start=start, goal=goal, grid=self.grid, blocked=blocked)
        astar.search()
        return astar

    def _astar_reachable(self, start, goal, astar):
        """Correccion 1 (camino vacio): un objetivo solo vale si A* llego.

        A* fallido deja total_weight=inf y directions=[]. Sin este filtro el
        planner "teletransportaba" al jugador (ej. get_key [13,4] camino [])
        y marcaba la llave como recogida sin moverse.
        """
        try:
            if tuple(int(v) for v in start) == tuple(int(v) for v in goal):
                return True
        except (TypeError, ValueError):
            pass
        try:
            weight = float(astar.total_weight)
        except (TypeError, ValueError):
            return False
        # Solo se rechaza lo inalcanzable (peso inf + sin direcciones). Una
        # ruta que cruza diamantes/llaves pesa ~99900 por casilla pero es
        # valida: se recogen al pasar.
        if weight == float("inf"):
            return False
        return bool(getattr(astar, "directions", None))

    def _failed(self, action, coords):
        try:
            return (action, (int(coords[0]), int(coords[1]))) in self.failed_targets
        except (TypeError, ValueError, IndexError):
            return False

    def exit_cells(self):
        out = []
        for row in self.grid:
            for cell in row:
                if cell is not None and cell.cell_type in ("ladder", "ladder-open"):
                    out.append((int(cell.coordinates[0]), int(cell.coordinates[1])))
        return out

    def exit_reachable_from(self, pos):
        """Anti-softlock (meta global reversible): si la salida se conoce, debe
        existir camino desde pos hasta ella (con la llave en mano las puertas
        cuentan como abiertas). Sin salida conocida no se puede juzgar."""
        exits = self.exit_cells()
        if not exits:
            return True
        for goal in exits:
            astar = self._astar_path(pos, goal)
            astar.search()
            if self._astar_reachable(pos, goal, astar):
                return True
        return False

    def find_nearest_diamond(self):
        # Esta funcion se encarga de encontrar el diamante mas cercano al jugador, si no hay
        # diamantes alcanzables (peso infinito) o no hay vecinos caminables, no se realiza
        # esta accion. Sin umbral finito: cruzar otros diamantes/llaves (99900) es valido
        # porque se recogen al pasar; solo los pinchos/puertas bloquean (van en `blocked`).
        # Se usa el algoritmo A* para encontrar el camino mas corto entre el jugador y el diamante
        # Debe decir si se pasa encima de un spike (o tomar el spike como otra accion)
        best = None
        best_score = float("inf")
        path = None
        player_position = self.player_pos
        # Orden del Nivel 6: roca al foso ANTES de bajar (filas 11+ vetadas
        # mientras el puente este pendiente y sea viable).
        down_blocked = self._level6_bridge_pending()
        for row in self.grid:
            for cell in row:
                if cell != None:
                    if cell.cell_type == "diamond":
                        coord = (int(cell.coordinates[0]), int(cell.coordinates[1]))
                        if down_blocked and coord[0] >= 11:
                            continue
                        if self._failed("get_diamond", coord):
                            continue
                        Astar = self._astar_path(player_position, cell.coordinates)
                        # Si el peso es el minimo, actualizar mejor, si es inwalkeable, none
                        if (Astar.total_weight < best_score
                                and self._astar_reachable(player_position, cell.coordinates, Astar)):
                            best_score = Astar.total_weight
                            best = cell
                            path = Astar.directions
        return best, path

    def go_ladder(self):
        best = None
        best_score = float("inf")
        path = None
        player_position = self.player_pos
        for row in self.grid:
            for cell in row:
                if cell != None:
                    if cell.cell_type == "ladder" or cell.cell_type == "ladder-open":
                        Astar = self._astar_path(player_position, cell.coordinates)
                        # Si el peso es el minimo, actualizar mejor, si es inwalkeable, none
                        if (Astar.total_weight < best_score
                                and self._astar_reachable(player_position, cell.coordinates, Astar)):
                            best_score = Astar.total_weight
                            best = cell
                            path = Astar.directions
        return best, path

    def find_nearest_key(self):
        best = None
        best_score = float("inf")
        path = None
        player_position = self.player_pos
        down_blocked = self._level6_bridge_pending()
        for row in self.grid:
            for cell in row:
                if cell != None:
                    if cell.cell_type == "key":
                        coord = (int(cell.coordinates[0]), int(cell.coordinates[1]))
                        if down_blocked and coord[0] >= 11:
                            continue
                        if self._failed("get_key", coord):
                            continue
                        Astar = self._astar_path(player_position, cell.coordinates)
                        # Si el peso es el minimo, actualizar mejor, si es inwalkeable, none
                        if (Astar.total_weight < best_score
                                and self._astar_reachable(player_position, cell.coordinates, Astar)):
                            best_score = Astar.total_weight
                            best = cell
                            path = Astar.directions
        return best, path

    def assign_keys_to_doors(self):
        """Empareja cada llave con su puerta mas cercana, uno a uno.

        Como Valentina: cada puerta toma su llave libre mas cercana por
        distancia Manhattan. Asi una llave persigue su puerta y no una ajena.
        """
        keys = []
        doors = []
        for row in self.grid:
            for cell in row:
                if cell is None:
                    continue
                if cell.cell_type == "key":
                    keys.append((int(cell.coordinates[0]), int(cell.coordinates[1])))
                elif cell.cell_type in ("door", "metal-door"):
                    doors.append((int(cell.coordinates[0]), int(cell.coordinates[1])))
        if self._is_level6():
            # Guia: llave arriba (4,8) -> puerta izquierda (10,2); llave
            # inferior (13,4) -> puerta central. Orden estricto: mientras la
            # puerta izquierda siga cerrada solo cuenta su llave.
            pairs = []
            for key in keys:
                door = self.LEVEL6_KEY_PAIRS.get(key)
                if door in doors:
                    pairs.append((key, door))
                elif door is not None and doors and not self._level6_left_door_closed():
                    others = [d for d in doors if d != self.LEVEL6_LEFT_DOOR] or doors
                    pairs.append((key, others[0]))
            if self._level6_left_door_closed():
                pairs = [p for p in pairs if p[1] == self.LEVEL6_LEFT_DOOR]
            if pairs:
                return pairs
        pairs = []
        used_keys = set()
        for door in doors:
            best_key = None
            best_dist = None
            for key in keys:
                if key in used_keys:
                    continue
                dist = abs(door[0] - key[0]) + abs(door[1] - key[1])
                if best_dist is None or dist < best_dist:
                    best_dist = dist
                    best_key = key
            if best_key is not None:
                pairs.append((best_key, door))
                used_keys.add(best_key)
        return pairs

    def find_assigned_key(self):
        """Llave mas cercana entre las emparejadas a una puerta.

        Si ninguna emparejada es alcanzable, se acepta cualquier llave (las
        llaves abren cualquier puerta); sin puertas, todas valen.
        """
        pairs = self.assign_keys_to_doors()
        targets = {key for key, _ in pairs} if pairs else None
        best = None
        best_score = float("inf")
        path = None
        # La llave inferior (13,4) espera al puente, igual que los diamantes.
        down_blocked = self._level6_bridge_pending()
        for row in self.grid:
            for cell in row:
                if cell is not None and cell.cell_type == "key":
                    coord = (int(cell.coordinates[0]), int(cell.coordinates[1]))
                    if targets is not None and coord not in targets:
                        continue
                    if down_blocked and coord[0] >= 11:
                        continue
                    if self._failed("get_key", coord):
                        continue
                    Astar = self._astar_path(self.player_pos, cell.coordinates)
                    if (Astar.total_weight < best_score
                            and self._astar_reachable(self.player_pos, cell.coordinates, Astar)):
                        best_score = Astar.total_weight
                        best = cell
                        path = Astar.directions
        if best is None:
            if self._level6_left_door_closed() and targets:
                # No coger la llave inferior antes de abrir la puerta izquierda.
                return None, None
            return self.find_nearest_key()
        return best, path

    def find_nearest_button(self):
        """Boton mas cercano (Valentina 'B'): pisarlo abre la salida.

        Los botones son transitables (peso 2), asi que A* los alcanza sin
        limpiar pinchos extra. Solo se usa cuando ya no hay diamantes ni
        llaves pendientes: es exploracion post-botín, no botín.
        """
        best = None
        best_score = float("inf")
        path = None
        for row in self.grid:
            for cell in row:
                if cell is not None and cell.cell_type in ("button", "push_button", "push-button"):
                    coord = (int(cell.coordinates[0]), int(cell.coordinates[1]))
                    if self._failed("go_button", coord):
                        continue
                    Astar = self._astar_path(self.player_pos, cell.coordinates)
                    if (Astar.total_weight < best_score
                            and self._astar_reachable(self.player_pos, cell.coordinates, Astar)):
                        best_score = Astar.total_weight
                        best = cell
                        path = Astar.directions
        return best, path

    def _safe_loot_reachable(self):
        """¿Hay diamante o llave alcanzable ahora mismo?

        Guardia anti-pinchos (Nivel spikes Imagen 1, logica Seb original):
        con botin seguro a la vista jamas se pisa un pincho. Las
        alternativas go_spike guardadas de un estado viejo (sin botin) se
        descartan al reventar contra botin fresco en vez de desviar al bot.
        """
        try:
            if self.diamondExist:
                best, path = self.find_nearest_diamond()
                if best is not None and path:
                    return True
            if self.keyExist and not self.player_has_key:
                best, path = self.find_assigned_key()
                if best is not None and path:
                    return True
        except Exception:
            pass
        return False

    def find_nearest_frontier(self):
        """Exploracion post-botin: celda segura junto a lo desconocido.

        Solo se usa cuando ya no hay diamantes/llaves/rocas/botones ni
        pinchos vivos ni salida visible (Nivel 2 tras el diamante con la
        salida aun tapada por vision). Mueve al borde del mapa conocido para
        revelar la escalera/boton en la proxima captura en vez de quedarse
        quieto. Nunca pisa fosos/pinchos/rocas/puertas.
        """
        try:
            if self.diamondExist or self.keyExist or self.rockExist or self.buttonExist:
                return None, None
            spikes = sum(1 for row in self.grid for c in row
                         if c is not None and c.cell_type == "spike")
            if spikes:
                return None, None
            reachable = self._bfs_reachable_cells(self.grid, self.player_pos, set())
            if not reachable:
                return None, None
            rows = len(self.grid)
            cols = len(self.grid[0]) if rows else 0
            interesting = {"fall", "button", "push_button", "push-button",
                           "metal-door", "door", "ladder", "ladder-open"}
            best = None
            best_path = None
            best_score = float("inf")
            start = (int(self.player_pos[0]), int(self.player_pos[1]))
            for (r, c) in reachable:
                if (r, c) == start:
                    continue
                if self._failed("go_explore", (r, c)):
                    continue
                # Frontera util: junto a foso/boton/puerta/salida (no a None:
                # el None local haria rebotar (9,5)<->(8,5) 200 pasos).
                is_frontier = False
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nr, nc = r + dr, c + dc
                    if not (0 <= nr < rows and 0 <= nc < cols):
                        continue
                    nb = self.grid[nr][nc]
                    if nb is not None and nb.cell_type in interesting:
                        is_frontier = True
                        break
                if not is_frontier:
                    continue
                Astar = self._astar_path(self.player_pos, (r, c))
                if not self._astar_reachable(self.player_pos, (r, c), Astar):
                    continue
                if Astar.total_weight < best_score:
                    best_score = Astar.total_weight
                    best = (r, c)
                    best_path = Astar.directions
            if best is None:
                return None, None
            from cell import Cell as _Cell
            # Celda virtual: no existe en el grid, solo lleva coordenadas.
            probe = _Cell(list(best), "terrain")
            return probe, best_path
        except (TypeError, ValueError, IndexError, AttributeError):
            return None, None

    def _is_spike_corridor(self):
        """Nivel 2 (corredor de pinchos): 1 diamante tras pinchos verticales,
        sin escalera/llave/puerta/roca visible y con foso.

        Logica separada por nivel (pedido): aqui Seb cruzaba pinchos por peso
        y Valentina iba al goal; nosotros limpiamos pinchos en orden y luego
        exploramos el boton/salida en vez de quedarnos quietos.
        """
        try:
            if self.exit_cells() or self.keyExist or self.doorExist or self.rockExist:
                return False
            if not self.diamondExist:
                return False
            spikes = [(int(c.coordinates[0]), int(c.coordinates[1]))
                      for row in self.grid for c in row
                      if c is not None and c.cell_type == "spike"]
            falls = [c for row in self.grid for c in row
                     if c is not None and c.cell_type == "fall"]
            # Columna vertical de >=2 pinchos + foso = firma del corredor.
            if len(spikes) < 2 or not falls:
                return False
            cols = [c for _, c in spikes]
            return max(cols) - min(cols) <= 1
        except (TypeError, ValueError, AttributeError):
            return False

    def get_possible_spikes(self) -> List[Tuple[int, int]]:
        possible_spikes = []
        visited : list = []
        queue = deque()
        queue.append((self.player_pos, []))  # (posición actual, lista de spikes vistos)

        while queue:
            current_pos, spikes_seen = queue.popleft()
            r, c = current_pos
            current_cell = self.grid[r][c]

            if current_pos in visited:
                continue
            visited.append(current_pos)

            # Si llegamos a un spike y no hemos visto otros antes, es válido
            if current_cell.cell_type == "spike":
                if len(spikes_seen) <= 1:
                    possible_spikes.append(current_pos)
                continue  # no seguimos más allá del spike

            for neighbor in [current_cell.neighbor_up, current_cell.neighbor_down,
                            current_cell.neighbor_left, current_cell.neighbor_right]:
                if neighbor and neighbor.walkable:
                    new_pos = neighbor.coordinates
                    new_spikes = spikes_seen[:]
                    if neighbor.cell_type == "spike":
                        new_spikes.append(new_pos)
                    queue.append((new_pos, new_spikes))

        return possible_spikes
    
    def get_possible_doors(self) -> List[Tuple[int, int]]:
        # Puertas abribles: door y metal-door (la jaula del Nivel 2 es
        # metal-door; antes se ignoraba y la jaula jamas se abria).
        possible_spikes = []
        visited : list = []
        queue = deque()
        queue.append((self.player_pos, []))  # (posición actual, lista de spikes vistos)

        while queue:
            current_pos, spikes_seen = queue.popleft()
            r, c = current_pos
            current_cell = self.grid[r][c]

            if current_pos in visited:
                continue
            visited.append(current_pos)

            # Si llegamos a un spike y no hemos visto otros antes, es válido
            if current_cell.cell_type in ("door", "metal-door"):
                if len(spikes_seen) <= 1:
                    possible_spikes.append(current_pos)
                continue  # no seguimos más allá del spike

            for neighbor in [current_cell.neighbor_up, current_cell.neighbor_down,
                            current_cell.neighbor_left, current_cell.neighbor_right]:
                if neighbor and neighbor.walkable:
                    new_pos = neighbor.coordinates
                    new_spikes = spikes_seen[:]
                    if neighbor.cell_type in ("door", "metal-door"):
                        new_spikes.append(new_pos)
                    queue.append((new_pos, new_spikes))

        return possible_spikes
    
    # ---- Nivel 6 (guia Google AI Studio) ----
    LEVEL6_BANNED_ROCK = (4, 7)
    LEVEL6_LEFT_DOOR = (10, 2)
    LEVEL6_KEY_PAIRS = {(4, 8): (10, 2), (13, 4): (8, 5)}
    # Barrera azul dibujada por el usuario: la roca no puede salir de este
    # espacio. El ducto directo es intransitable con nuestra fisica (el foso
    # intermedio (5,1) se tragaria la roca), asi que el corredor incluye el
    # unico rodeo fisico: bajar por la columna 3 hasta la fila 7, cortar a la
    # izquierda y bajar por el ducto hasta el hueco. La roca nunca pisa la
    # mitad derecha ni se aparca muerta (regla anti-huerfanos).
    LEVEL6_ROCK_CORRIDOR = frozenset({
        (3, 1), (3, 2), (3, 3),
        (4, 1), (4, 2), (4, 3),
        (5, 1), (5, 3),
        (6, 1), (6, 2), (6, 3),
        (7, 1), (7, 2), (7, 3),
        (8, 1), (8, 2),
        (9, 1), (9, 2),
        (10, 2),
        (11, 1), (11, 2),
        (12, 1),
    })

    def _level6_bridge_open(self):
        """True si el puente del Nivel 6 ya esta construido."""
        return (self._is_level6()
                and self._cell_type_at(11, 1) == "rock-in-fall")

    def _level6_upstream(self):
        """True si el jugador aun no ha bajado (fila <= 10) en el Nivel 6
        con el puente sin construir: hay que poner la roca ANTES de bajar."""
        if not self._is_level6():
            return False
        if self._cell_type_at(11, 1) == "rock-in-fall":
            return False
        try:
            return int(self.player_pos[0]) <= 10
        except (TypeError, ValueError, IndexError):
            return False

    def _level6_bridge_pending(self):
        """Puente pendiente y viable: prohibido bajar (objetivos de filas
        11+). Si el fill deja de ser viable (roca varada), se libera para
        jugar sin puente en vez de bloquearse."""
        return self._level6_upstream() and bool(self.get_rock_simulations())

    def _cell_type_at(self, r, c):
        try:
            cell = self.grid[r][c]
        except (IndexError, TypeError):
            return None
        return None if cell is None else cell.cell_type

    def _is_level6(self):
        """Firma del Nivel 6: roca derecha (4,7) intacta, huecos (5,8) y
        (11,1) (vacio o ya rellenado) y la columna izquierda del nivel."""
        if self._cell_type_at(4, 7) != "rock":
            return False
        if self._cell_type_at(5, 8) != "fall":
            return False
        if self._cell_type_at(11, 1) not in ("fall", "rock-in-fall"):
            return False
        return self._cell_type_at(5, 1) in ("fall", "rock-in-fall")

    def _level6_left_door_closed(self):
        return (self._is_level6()
                and self._cell_type_at(*self.LEVEL6_LEFT_DOOR) in ("door", "metal-door"))

    def _forced_rock_pair_targets(self, targets, rocks):
        """Asignacion fija roca->hueco para el nivel de la llave/puerta.

        La roca de la columna derecha sube en linea recta a (6,8) junto a la
        puerta; la otra roca va al hueco (8,1) bajo los diamantes. El matching
        por distancia minima los empareja al reves y el nivel se vuelve
        imposible, asi que aqui se impone el emparejamiento correcto. Solo se
        activa con ambos huecos sin rellenar y una roca en la columna 8; si el
        par forzado no es viable aun, se devuelve lista vacia para que el bot
        avance con pinchos/diamantes en vez de rellenar el hueco equivocado.
        """
        if self._is_level6():
            # Guia Nivel 6: solo la roca izquierda va al hueco (11,1) como
            # puente; la roca (4,7) nunca se usa (softlock).
            if (11, 1) not in targets:
                return {}
            return {rock: (None if rock == self.LEVEL6_BANNED_ROCK else (11, 1))
                    for rock in rocks}
        if set(targets) != {(6, 8), (8, 1)}:
            return None
        if not any(c == 8 for _, c in rocks):
            return None
        return {rock: ((6, 8) if rock[1] == 8 else (8, 1)) for rock in rocks}

    def get_rock_simulations(self) -> List[RockSimulation]:
        targets = []
        # Cada hueco/boton es un objetivo independiente; los ya llenos quedan
        # como rock-in-fall / rock-in-button y no se vuelven a planificar.
        for row in self.grid:
            for cell in row:
                if cell is not None and cell.cell_type in ("fall", "button", "push_button", "push-button"):
                    targets.append((int(cell.coordinates[0]), int(cell.coordinates[1])))

        rocks = []
        for row in self.grid:
            for cell in row:
                if cell is not None and cell.cell_type == "rock":
                    rocks.append((int(cell.coordinates[0]), int(cell.coordinates[1])))

        if not rocks or not targets:
            return []

        # No caminar a traves de peligros ni de puertas que aun no se han
        # abierto durante un plan de empuje.
        blocked = set()
        for row in self.grid:
            for cell in row:
                if cell is not None and cell.cell_type in ("spike", "door", "metal-door"):
                    blocked.add((int(cell.coordinates[0]), int(cell.coordinates[1])))

        # Primero, flood-fill inverso desde cada objetivo (como Valentina) para
        # descartar pares sin una geometria de empuje posible. Luego, el BFS
        # exacto comprueba accesibilidad del jugador y las otras rocas.
        corridor = self.LEVEL6_ROCK_CORRIDOR if self._is_level6() else None
        simulations = []
        for target in targets:
            for rock in rocks:
                if not RockSimulation.can_reach_target_static(
                        self.grid, rock, target, blocked):
                    continue
                sim = RockSimulation(
                    grid=self.grid,
                    player_pos=self.player_pos,
                    rock_pos=rock,
                    target_pos=target,
                    blocked=blocked,
                    rock_allowed=corridor,
                )
                if sim.simulate():
                    sim.kind = "fill"
                    simulations.append(sim)

        forced = self._forced_rock_pair_targets(targets, rocks)
        if forced is not None:
            simulations = [s for s in simulations
                           if forced.get(tuple(s.rock_start)) == tuple(s.target_pos)]

        if not simulations:
            return []

        # Matching bipartito: cada roca y cada objetivo aparece como maximo una
        # vez. Se maximiza el numero de objetivos asignables y, despues, se
        # minimiza la longitud de los recorridos. Esto evita que varias rocas
        # compitan por el mismo hueco por tener menor distancia Manhattan.
        rock_ids = {rock: i for i, rock in enumerate(rocks)}
        sim_by_target = {target: [] for target in targets}
        for sim_index, sim in enumerate(simulations):
            target = tuple(sim.target_pos)
            rock = tuple(sim.rock_start)
            sim_by_target[target].append((rock_ids[rock], len(sim.directions), sim_index))

        @lru_cache(maxsize=None)
        def choose(target_index, used_rocks):
            if target_index == len(targets):
                return 0, 0, ()

            # Omitir un objetivo es válido: puede depender de que otra roca se
            # mueva antes y se reconsiderará al recapturar el tablero.
            best = choose(target_index + 1, used_rocks)
            target = targets[target_index]
            for rock_index, cost, sim_index in sorted(sim_by_target[target], key=lambda item: (item[1], item[0])):
                bit = 1 << rock_index
                if used_rocks & bit:
                    continue
                matched, total_cost, selected = choose(target_index + 1, used_rocks | bit)
                candidate = (matched + 1, total_cost + cost,
                             ((target_index, sim_index),) + selected)
                if (candidate[0] > best[0]
                        or (candidate[0] == best[0] and candidate[1] < best[1])
                        or (candidate[0] == best[0] and candidate[1] == best[1]
                            and candidate[2] < best[2])):
                    best = candidate
            return best

        _, _, selected_pairs = choose(0, 0)
        selected = [simulations[sim_index] for _, sim_index in selected_pairs]
        selected.sort(key=lambda sim: (
            len(sim.directions), tuple(sim.target_pos), tuple(sim.rock_start)))
        return selected

    def _bfs_reachable_cells(self, grid, player_pos, blocked, treat_as_floor=()):
        """Celdas a las que el jugador puede caminar sin empujar nada.

        treat_as_floor: celdas que se cuentan como transitables aunque su tipo
        las bloquee (sirve para medir cuantas celdas NUEVAS abriria limpiar un
        pincho objetivo).
        """
        try:
            start = (int(player_pos[0]), int(player_pos[1]))
        except (TypeError, ValueError, IndexError):
            return set()
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if not (0 <= start[0] < rows and 0 <= start[1] < cols):
            return set()
        start_cell = grid[start[0]][start[1]]
        if start_cell is None or not start_cell.walkable:
            return set()
        treat_set = {tuple(p) for p in (treat_as_floor or ())}
        seen = {start}
        queue = deque([start])
        while queue:
            r, c = queue.popleft()
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                if (nr, nc) in seen or (nr, nc) in blocked:
                    continue
                if not (0 <= nr < rows and 0 <= nc < cols):
                    continue
                cell = grid[nr][nc]
                if cell is None:
                    continue
                if (nr, nc) not in treat_set:
                    if not cell.walkable:
                        continue
                    if cell.cell_type in ("fall", "spike", "door", "metal-door", "rock", "rock-in-button"):
                        continue
                seen.add((nr, nc))
                queue.append((nr, nc))
        return seen

    def _future_rock_pushes(self, grid, rock_pos, reachable):
        """Cuenta empujes legales que le quedarian a la roca tras un shove."""
        moves = 0
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            dest = (rock_pos[0] + dr, rock_pos[1] + dc)
            stand = (rock_pos[0] - dr, rock_pos[1] - dc)
            if stand not in reachable:
                continue
            if not (0 <= dest[0] < rows and 0 <= dest[1] < cols):
                continue
            cell = grid[dest[0]][dest[1]]
            if cell is None or cell.cell_type == "rock":
                continue
            if cell.cell_type in ("terrain", "diamond", "player", "player-with-key",
                                  "fall", "button", "push_button", "push-button"):
                moves += 1
        return moves

    def _orphans_fill(self, rock_start, final_rock, sim, blocked, fill_targets):
        """True si el shove deja a la roca movida sin ningun fill viable
        cuando antes tenia potencial geometrico.

        Es la barrera azul en forma general: mover (4,2)->(4,1) no sale del
        ducto pero mata el unico fill futuro (el foso intermedio no es
        transitable), asi que equivale a perder la run. La comprobacion se
        hace sobre el tablero resultante con las mismas reglas (incluido el
        corredor del Nivel 6).
        """
        try:
            rock_start = (int(rock_start[0]), int(rock_start[1]))
            final_rock = (int(final_rock[0]), int(final_rock[1]))
        except (TypeError, ValueError, IndexError):
            return False
        if rock_start == final_rock:
            return False
        had_potential = any(
            RockSimulation.can_reach_target_static(self.grid, rock_start, t, blocked)
            for t in fill_targets)
        if not had_potential:
            return False
        probe = GameState(sim.grid, list(sim.player_pos), 0,
                          player_has_key=self.player_has_key)
        for s in probe.get_rock_simulations():
            if tuple(s.rock_start) == final_rock:
                return False
        return True

    def get_shove_simulations(self):
        """Move a corridor-blocking rock when no fill assignment is reachable.

        Most pushes are one tile. If a diamond blocks the corridor, plan through
        it to the next floor tile; the player follows into the vacated diamond
        square and collects it, matching Valentina's tile-validity model.
        Unlike Seb (fill-only) and Valentina (hole-only plans), this shove is
        an exception: it is rejected when the rock would end with no legal
        push left and open no new ground (e.g. parking in a corner).
        """
        from rock_simulation import RockSimulation as _RS
        # Fill objectives always take precedence over shoves.
        if self.get_rock_simulations():
            return []

        blocked = set()
        for row in self.grid:
            for cell in row:
                if cell is not None and cell.cell_type in ("spike", "door", "metal-door"):
                    blocked.add((int(cell.coordinates[0]), int(cell.coordinates[1])))

        sims = []
        rocks = []
        for row in self.grid:
            for cell in row:
                if cell is not None and cell.cell_type == "rock":
                    rocks.append((int(cell.coordinates[0]), int(cell.coordinates[1])))
        corridor = self.LEVEL6_ROCK_CORRIDOR if self._is_level6() else None
        if self._is_level6():
            # Nivel 6: la roca puente ((4,2)) solo se mueve via fill al hueco;
            # cualquier push a terreno la vara (caso (4,2)->(4,1) en vivo).
            # La (4,7) ni se toca. Sin shoves en este nivel.
            return []
        
        # Objetivos de fill para la regla anti-huerfanos (ver abajo).
        fill_targets = []
        for row in self.grid:
            for cell in row:
                if cell is not None and cell.cell_type in ("fall", "button",
                                                           "push_button", "push-button"):
                    fill_targets.append((int(cell.coordinates[0]),
                                         int(cell.coordinates[1])))
        reachable_before = self._bfs_reachable_cells(self.grid, self.player_pos, blocked)
        for rock in rocks:
            r, c = int(rock[0]), int(rock[1])
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                crossed_diamond = False
                for distance in range(1, 5):
                    tgt = (r + dr * distance, c + dc * distance)
                    if not (0 <= tgt[0] < len(self.grid) and 0 <= tgt[1] < len(self.grid[0])):
                        break
                    cell = self.grid[tgt[0]][tgt[1]]
                    if cell is None:
                        break
                    if cell.cell_type == "diamond":
                        crossed_diamond = True
                        continue
                    if cell.cell_type != "terrain":
                        break
                    # Permit a long shove only when it clears a diamond from
                    # the corridor. Otherwise prefer one-step, reversible moves.
                    if distance > 1 and not crossed_diamond:
                        continue

                    free_neighbors = 0
                    for ddr, ddc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        neighbor_pos = (tgt[0] + ddr, tgt[1] + ddc)
                        if neighbor_pos == (r, c):
                            free_neighbors += 1
                            continue
                        nr, nc = neighbor_pos
                        if not (0 <= nr < len(self.grid) and 0 <= nc < len(self.grid[0])):
                            continue
                        neighbor = self.grid[nr][nc]
                        if (neighbor is not None and neighbor.walkable
                                and neighbor.cell_type not in ("rock", "rock-in-button")):
                            free_neighbors += 1
                    # Dead-end parking is allowed only when this push is needed
                    # to get past an intervening diamond.
                    if free_neighbors < 2 and not crossed_diamond:
                        continue

                    sim = _RS(grid=self.grid, player_pos=self.player_pos,
                              rock_pos=rock, target_pos=tgt, blocked=blocked,
                              rock_allowed=corridor)
                    if sim.simulate() and len(sim.directions) <= 25:
                        # Seb nunca empujaba a terreno y Valentina solo hacia huecos:
                        # un shove solo vale si no deja la roca muerta sin abrir nada.
                        sim.kind = "shove"
                        try:
                            final_rock = tuple(sim.rock_final)
                        except AttributeError:
                            final_rock = tuple(sim.target_pos)
                        if self._orphans_fill(rock, final_rock, sim, blocked,
                                              fill_targets):
                            # El shove mataria el unico fill futuro de la roca
                            # (caso (4,2)->(4,1) del Nivel 6): run perdida.
                            continue
                        reachable_after = self._bfs_reachable_cells(
                            sim.grid, sim.player_pos, blocked)
                        gain = len(reachable_after - reachable_before)
                        mobility = self._future_rock_pushes(sim.grid, final_rock, reachable_after)
                        if mobility == 0 and gain < 2:
                            continue
                        sims.append(sim)
        sims.sort(key=lambda sim: (len(sim.directions), tuple(sim.rock_start), tuple(sim.target_pos)))
        return sims[:2]

    def _opening_right_move(self):
        """Hard limit de apertura: en este nivel, al inicio siempre a la derecha.

        El planner prefiere bajar por (5,1)->(6,1)->(7,1) y termina en el callejon
        de la columna izquierda. Aqui se fuerza el primer paso a la derecha
        (pisar el spike (4,2)) y nunca hacia abajo. Solo se activa con la firma
        del tablero (ladder/llave/puerta/rocas/huecos en su sitio), el jugador en
        (4,1) y sin llave. Tras dar el paso, la firma deja de coincidir y el
        planner normal retoma.
        """
        try:
            pp = (int(self.player_pos[0]), int(self.player_pos[1]))
        except (TypeError, ValueError, IndexError):
            return None
        if pp != (4, 1) or self.player_has_key:
            return None
        signature = [(3, 1, "ladder"), (4, 5, "key"), (5, 8, "door"),
                     (5, 4, "rock"), (6, 8, "fall"), (11, 8, "rock")]
        hits = 0
        for r, c, want in signature:
            try:
                cell = self.grid[r][c]
            except IndexError:
                cell = None
            if cell is not None and cell.cell_type == want:
                hits += 1
        if hits < 5:
            return None
        try:
            spike = self.grid[4][2]
        except IndexError:
            return None
        # Solo con el pincho aun plano: pisarlo lo levanta y quemaria el puente
        # de vuelta antes de tiempo.
        if spike is None or spike.cell_type != "spike":
            return None
        return GameAction("go_spike", coordinates=[4, 2], path=["right"])

    # Flujo final fijado: derecha, abajo, abajo, izquierda, abajo x3,
    # izquierda x2, arriba x6 hasta la escalera (3,1), pasando por el (5,1)
    # plano una sola vez al salir (nunca por el (4,2)).
    ENDGAME_LADDER_PATH = ["right", "down", "down", "left",
                           "down", "down", "down", "left", "left",
                           "up", "up", "up", "up", "up", "up"]

    def _endgame_ladder_fallback(self):
        """Hard fallback del tramo final a la escalera.

        Solo se activa en el punto de atasco (jugador en (4,3)) con todo
        resuelto: sin diamantes ni rocas, escalera abierta en (3,1), (8,1)
        relleno y (5,1) aun plano. Ademas se verifica que cada casilla de la
        ruta exista y sea transitable; si algo no coincide, no se activa y
        decide el planner normal.
        """
        try:
            pp = (int(self.player_pos[0]), int(self.player_pos[1]))
        except (TypeError, ValueError, IndexError):
            return None
        if pp != (4, 3):
            return None
        if self.diamondExist or self.rockExist:
            return None
        try:
            ladder = self.grid[3][1]
            hole = self.grid[8][1]
            spike = self.grid[5][1]
        except IndexError:
            return None
        if ladder is None or ladder.cell_type != "ladder-open":
            return None
        if hole is None or hole.cell_type != "rock-in-fall":
            return None
        if spike is None or spike.cell_type != "spike":
            return None
        r, c = pp
        for step in self.ENDGAME_LADDER_PATH:
            if step == "up":
                r -= 1
            elif step == "down":
                r += 1
            elif step == "left":
                c -= 1
            elif step == "right":
                c += 1
            if not (0 <= r < len(self.grid) and 0 <= c < len(self.grid[0])):
                return None
            cell = self.grid[r][c]
            if cell is None or not cell.walkable:
                return None
        if (r, c) != (3, 1):
            return None
        return GameAction("go_ladder", coordinates=[3, 1],
                          path=list(self.ENDGAME_LADDER_PATH))

    def get_next_action(self):
        opening = self._opening_right_move()
        if opening is not None:
            return opening
        endgame = self._endgame_ladder_fallback()
        if endgame is not None:
            return endgame
        # Primero intentamos las alternativas guardadas (backtracking) validando precondiciones
        while self.alternative_stack:
            alt = self.alternative_stack.pop()
            if len(alt) == 2:
                # Alternativa de push_rock malformada vieja: (tipo, sim) -> descartar
                continue
            alt_action, coords, path = alt
            if alt_action == "open_door":
                if not (self.doorExist and self.player_has_key):
                    continue
                r, c = coords
                if not (0 <= r < len(self.grid) and 0 <= c < len(self.grid[0])):
                    continue
                cell = self.grid[r][c]
                if cell is None or cell.cell_type not in ("door", "metal-door"):
                    continue
            if alt_action == "get_key":
                if not (self.keyExist and not self.player_has_key):
                    continue
            if alt_action == "get_diamond":
                if not self.diamondExist:
                    continue
            if alt_action in ("get_key", "get_diamond", "open_door", "go_spike", "go_button", "go_explore"):
                if self._failed(alt_action, coords):
                    continue
                # Correccion 1: alternativa con camino vacio = inalcanzable.
                try:
                    if not path and tuple(coords) != tuple(int(v) for v in self.player_pos):
                        continue
                except (TypeError, ValueError):
                    continue
                # Alternativa rancia ( Seb heredado ): el path se calculo desde
                # otra casilla y tras el backtrack ya no llega (caso fantasma
                # (11,5)->(10,7) reutilizado desde (12,8) = (11,10)). Se
                # descarta si al replay no termina en coords.
                try:
                    pos = [int(self.player_pos[0]), int(self.player_pos[1])]
                    for step in (path or []):
                        if step == "up":
                            pos[0] -= 1
                        elif step == "down":
                            pos[0] += 1
                        elif step == "left":
                            pos[1] -= 1
                        elif step == "right":
                            pos[1] += 1
                        else:
                            raise ValueError(step)
                    if tuple(pos) != (int(coords[0]), int(coords[1])):
                        continue
                except (TypeError, ValueError, IndexError):
                    continue
                # Con botin fresco a la vista, jamas desvio a un pincho viejo
                # (Nivel spikes: con 13 diamantes alcanzables, limpiar pinchos
                # mata/atrapa; Seb solo los cruzaba por peso sin rodeo).
                if alt_action == "go_spike" and self._safe_loot_reachable():
                    continue
            return GameAction(alt_action, coordinates=coords, path=list(path) if path is not None else [])

        # Si no hay alternativas, seguimos con las acciones normales
        last_resort_spike = None
        while len(self.actions) > 0:
            next_action = self.actions.pop(0)
            match next_action:
                case "get_key":
                    if self.keyExist and not self.player_has_key:
                        nearest, path = self.find_assigned_key()
                        if nearest is not None and path:
                            return GameAction(next_action, coordinates=nearest.coordinates, path=path)

                case "push_rock":
                    if self.rockExist:
                        simulations = [s for s in self.get_rock_simulations()
                                       if not self._failed("push_rock", s.target_pos)]
                        if simulations:
                            # Las otras simulaciones se calcularon sobre esta
                            # misma captura y quedan obsoletas tras cualquier
                            # empuje. Se elige la mejor del matching y se
                            # recalcula con la siguiente captura del tablero.
                            best : RockSimulation = simulations[0]
                            return best

                case "open_door":
                    if self.doorExist and self.player_has_key:
                        spike_coords = self.get_possible_doors()
                        if self._level6_left_door_closed():
                            # Orden estricto de puertas del Nivel 6.
                            spike_coords = [d for d in spike_coords
                                            if tuple(d) == self.LEVEL6_LEFT_DOOR]
                        best = None
                        best_score = 100000
                        best_path = None
                        alternatives = []
                        for coord in spike_coords:
                            if self._failed("open_door", coord):
                                continue
                            Astar = AStar(start=self.player_pos, goal=coord, grid=self.grid)
                            Astar.search()
                            if Astar.total_weight < best_score:
                                if best != None:
                                    alternatives.append((best, best_path))  # Guardar la anterior mejor como alternativa
                                best_score = Astar.total_weight
                                best = coord
                                best_path = Astar.directions
                            else:
                                if Astar.total_weight < 100000:
                                    alternatives.append((coord, Astar.directions))
                        for alt in alternatives:
                            self.alternative_stack.append(("open_door", alt[0], alt[1]))
                        if best is not None and best_path:
                            return GameAction("open_door", coordinates=best, path=best_path)

                case "get_diamond":
                    if self.diamondExist:
                        nearest, path = self.find_nearest_diamond()
                        if nearest is not None and path:
                            return GameAction(next_action, coordinates=nearest.coordinates, path=path)
                case "go_ladder":
                    if not self.diamondExist:
                        nearest, path = self.go_ladder()
                        if nearest is not None and path:
                            return GameAction(next_action, coordinates=nearest.coordinates, path=path)
                case "shove_rock":
                    if self.rockExist:
                        simulations = self.get_shove_simulations()
                        if simulations:
                            return simulations[0]

                case "go_button":
                    # Valentina 'B': tras el botin, pisar el boton abre la salida.
                    # Solo cuando no hay diamantes/llaves/rocas pendientes para
                    # no desviar el flujo normal (tests sin botones intactos).
                    # Un solo uso por simulacion (no muta el grid: repetir seria
                    # rebotar hasta max_steps).
                    if self.buttonExist and not self.diamondExist and not self.keyExist and not self.rockExist:
                        if not any(getattr(a, "action", "") == "go_button" for a in self.action_history):
                            nearest, path = self.find_nearest_button()
                            if nearest is not None and path:
                                return GameAction(next_action, coordinates=nearest.coordinates, path=path)

                case "go_explore":
                    # Red post-botin (Nivel 2): sin botin ni pinchos ni salida,
                    # un paso a la frontera en vez de quedarse quieto.
                    # Un solo uso por simulacion (no muta el grid).
                    if not any(getattr(a, "action", "") == "go_explore" for a in self.action_history):
                        nearest, path = self.find_nearest_frontier()
                        if nearest is not None and path:
                            return GameAction(next_action, coordinates=nearest.coordinates, path=path)

                case "go_spike":
                    vetoed = self._level6_upstream()
                    # Puente primero (guia Nivel 6 + barrera azul): sin
                    # puente y sin haber bajado, los pinchos son el atajo
                    # suicida (bajar por la derecha dejando el foso sin
                    # tapar). Ya abajo o con puente, se permiten. Vetado se
                    # guarda como ultimo recurso anti-paralisis (ver abajo).
                    spike_coords = self.get_possible_spikes()
                    spike_cells = set()
                    for row in self.grid:
                        for cell in row:
                            if cell is not None and cell.cell_type == "spike":
                                spike_cells.add((int(cell.coordinates[0]), int(cell.coordinates[1])))
                    # El pincho que mas terreno nuevo abre va primero (flujo del nivel):
                    # limpiar (5,1) no abre nada y subir levanta los pinchos del
                    # corredor final; limpiar abajo abre diamantes. A igual
                    # ganancia, el camino mas corto (comportamiento anterior).
                    base_reachable = self._bfs_reachable_cells(self.grid, self.player_pos, set())
                    evaluated = []
                    for coord in spike_coords:
                        # No cruzar otros pinchos vivos de paso hacia el objetivo:
                        # el camino debe limpiar el mas cercano primero. El objetivo
                        # queda exento del bloqueo.
                        goal = (int(coord[0]), int(coord[1]))
                        if self._failed("go_spike", goal):
                            continue
                        Astar = AStar(start=self.player_pos, goal=coord, grid=self.grid,
                                      blocked=spike_cells - {goal})
                        Astar.search()
                        if Astar.total_weight >= 100000:
                            continue
                        after = self._bfs_reachable_cells(
                            self.grid, self.player_pos, set(), treat_as_floor={goal})
                        gain = len(after - base_reachable)
                        evaluated.append((goal, Astar.directions, Astar.total_weight, gain))
                    evaluated.sort(key=lambda item: (-item[3], item[2], item[0]))
                    best = None
                    best_path = None
                    for index, (goal, path, weight, gain) in enumerate(evaluated):
                        if index == 0:
                            best, best_path = goal, path
                        elif not vetoed:
                            self.alternative_stack.append(("go_spike", goal, path))
                    try:
                        at_goal = tuple(int(v) for v in self.player_pos) == tuple(best) if best is not None else False
                    except (TypeError, ValueError):
                        at_goal = False
                    if best is not None and (best_path or at_goal):
                        if vetoed:
                            last_resort_spike = (best, best_path)
                            continue
                        return GameAction("go_spike", coordinates=best, path=best_path)

            # Si esta acción no produjo una acción válida, sigue con la siguiente
        if last_resort_spike is not None:
            # Anti-paralisis: todo lo demas fallo o esta vetado; mejor un
            # pincho con camino real que quedarse quieto para siempre. Si
            # tambien falla, el detector de atascos lo veta y se replanifica.
            best, best_path = last_resort_spike
            print(f"Paralisis total: go_spike de ultimo recurso en {tuple(best)}")
            return GameAction("go_spike", coordinates=best, path=best_path)
        print(f"sin accion desde {list(self.player_pos)}: "
              f"llave={self.keyExist}/{self.player_has_key} "
              f"puerta={self.doorExist} diamante={self.diamondExist} "
              f"roca={self.rockExist} boton={self.buttonExist} "
              f"spikes={sum(1 for row in self.grid for c in row if c is not None and c.cell_type == 'spike')} "
              f"salidas={self.exit_cells()} upstream={self._level6_upstream()} "
              f"corredor2={self._is_spike_corridor()}")
        return GameAction("None", [0, 0], path=[])




    def clone(self):
        grid_clone = copy.deepcopy(self.grid)
        player_pos_clone = copy.deepcopy(self.player_pos)
        game_state_clone = self.game_state  # int, no necesita deepcopy
        actions_clone = copy.deepcopy(self.action_history)
        player_key = self.player_has_key

        new_state = GameState(grid_clone, player_pos_clone, game_state_clone, actions_clone, player_has_key = player_key)
        # Acciones frescas para decidir desde el nuevo estado (original Seb); conservar
        # alternativas para backtracking (el original las perdia).
        new_state.alternative_stack = copy.deepcopy(self.alternative_stack)
        new_state.failed_targets = set(self.failed_targets)
        return new_state


    def __repr__(self):
        return f"GameState({self.grid}, {self.player_pos}, {self.game_state})"
