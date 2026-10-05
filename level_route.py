"""Closed-loop route for the five-rock/four-fall level.

The route is deliberately level-specific. Each straight run is issued as one
action, then the normal screen capture confirms where the player actually is
before the next run is sent.
"""
from collections import deque

from game_action import GameAction


ROUTE_START = (3, 2)
ROUTE_GROUPS = (
    "RRRR", "DD", "LLLLL", "DD", "RRRRRR", "LDD", "LLLLL",
    "DR", "UR", "DDD", "RD", "UU", "LURRUR", "DDD",
)
ROUTE_DIRECTIONS = tuple(step for group in ROUTE_GROUPS for step in group)
_ROUTE_SEGMENT_ENDS = []
_route_offset = 0
for _route_group in ROUTE_GROUPS:
    _route_offset += len(_route_group)
    _ROUTE_SEGMENT_ENDS.append(_route_offset)
_ROUTE_SEGMENT_ENDS = tuple(_ROUTE_SEGMENT_ENDS)
_DELTAS = {
    "U": (-1, 0),
    "D": (1, 0),
    "L": (0, -1),
    "R": (0, 1),
}
_NAMES = {"U": "up", "D": "down", "L": "left", "R": "right"}

# The four permanent pit locations uniquely identify the fixture/live map.
_HOLES = ((5, 6), (7, 1), (11, 6), (12, 3))
_DIAMOND_ROUTE_INDEX = {
    (5, 4): 8,
    (5, 3): 9,
    (7, 7): 19,
    (8, 6): 21,
    (12, 4): 35,
    (13, 4): 36,
}
LEVEL6_CAPTURE_START = (3, 5)
LEVEL6_CAPTURE_GROUPS = (
    "RRR", "D", "U", "LLL", "D", "LL", "U", "LL", "D", "R",
    "U", "R", "DDD", "R", "D", "L", "U", "LL", "DD", "R",
    "DD", "UU", "L", "UU", "R", "DDDD", "UUU", "RRRRRR", "DD",
    "L", "DD", "LLLLLL", "DD", "RRRRRRR", "UU", "LLLLLL", "UUUU",
    "RRR", "DD", "L",
)
LEVEL6_CAPTURE_DIRECTIONS = tuple(
    step for group in LEVEL6_CAPTURE_GROUPS for step in group)
LEVEL8_CAPTURE_START = (7, 5)
LEVEL8_CAPTURE_GROUPS = (
    "RR", "LLLL", "RRRR", "DDDDD", "LLL", "UUU", "LL", "DDD", "RRR",
    "UUU", "RR", "UUUUUUU", "LLLLL", "DDD", "RRR", "U",
)
LEVEL8_CAPTURE_DIRECTIONS = tuple(
    step for group in LEVEL8_CAPTURE_GROUPS for step in group)
_LEVEL8_HOLES = ((9, 2), (12, 2))
LEVEL9_CAPTURE_START = (3, 5)
LEVEL9_CAPTURE_GROUPS = (
    "D", "LLL", "U", "L", "D", "RRR", "DD", "L", "D", "RRRR", "U",
    "LLLLLL", "R", "DDDD", "L", "DDD", "RR", "LL", "U", "R", "D", "R",
    "UU", "D", "LL", "UU", "RRR", "U", "D", "R", "DDD", "UUUU", "RR",
    "D", "L", "U", "L", "DD", "U", "RR", "DDD", "R",
)
LEVEL9_CAPTURE_DIRECTIONS = tuple(
    step for group in LEVEL9_CAPTURE_GROUPS for step in group)
LEVEL10_CAPTURE_START = (6, 5)
LEVEL10_CAPTURE_GROUPS = tuple(
    "DDDD LLLL D R L DD RR UU R U L D L UUU L R UUU L UU RRRR DDDD L DDD "
    "RRRR D L R DD LL UU DD LLL UUU RRR D R UUU R L UUU R UU LLL DD L".split())
LEVEL10_CAPTURE_DIRECTIONS = tuple(
    step for group in LEVEL10_CAPTURE_GROUPS for step in group)
LEVEL11_CAPTURE_START = (4, 2)
LEVEL11_CAPTURE_GROUPS = tuple(
    "U L DDDD RRR U R DD RR UU DDD U LL U LLLL DDDD RRRR LLLL DD RRRR UUUU "
    "R D R UUUU DDD R LLL DD R L DD RRR L UUUUUUUUU LLL".split())
LEVEL11_CAPTURE_DIRECTIONS = tuple(
    step for group in LEVEL11_CAPTURE_GROUPS for step in group)
LEVEL12_CAPTURE_START = (3, 2)
LEVEL12_CAPTURE_GROUPS = tuple(
    "L RRR D RR U D R DDDDDDD L R UU LL DD R D LLL UUU LLL DDD RRR UUU LL "
    "UUU L R U RR D RRRR DDDDDD".split())
LEVEL12_CAPTURE_DIRECTIONS = tuple(
    step for group in LEVEL12_CAPTURE_GROUPS for step in group)
LEVEL7_CAPTURE_START = (4, 2)
LEVEL7_CAPTURE_GROUPS = (
    "R", "U", "R", "DDDD", "L", "D", "LL", "DDDD", "UU", "RRRRRR",
    "U", "R", "L", "UU", "R", "UU", "DD", "L", "DDD", "LL", "DDD",
)
LEVEL7_CAPTURE_DIRECTIONS = tuple(
    step for group in LEVEL7_CAPTURE_GROUPS for step in group)
_LEVEL7_HOLES = ((7, 4), (10, 1), (10, 7))
_BUTTON_KINDS = ("push_button", "push-button", "button")
_SAFE_ROUTE_TILE_TYPES = {
    "push_button", "push-button", "button",
    "terrain", "diamond", "player", "player-with-key", "spike-up",
    "rock-in-fall", "ladder", "ladder-open",
}


def route_positions(start=ROUTE_START, directions=ROUTE_DIRECTIONS):
    """Return the player coordinate after every individual route keypress."""
    positions = [tuple(start)]
    row, col = start
    for direction in directions:
        dr, dc = _DELTAS[direction]
        row += dr
        col += dc
        positions.append((row, col))
    return tuple(positions)


ROUTE_POSITIONS = route_positions()


def _simulate_route_positions(grid, start, directions, has_key=False,
                              return_key=False, open_hud=False):
    """Predict player positions, including wall bumps, door/key use and pushes."""
    types = [[None if cell is None else cell.cell_type for cell in row]
             for row in grid]
    position = tuple(start)
    positions = [position]
    held_key = bool(has_key or _cell_type(grid, position) in
                    ("player-with-key", "player-with-key1", "player-with-key2"))
    rows = len(types)
    cols = len(types[0]) if rows else 0
    passable = {"terrain", "diamond", "key", "player", "player-with-key",
                "spike-up", "rock-in-fall", "ladder", "ladder-open",
                "button", "push_button", "push-button"}

    for direction in directions:
        dr, dc = _DELTAS[direction]
        nxt = (position[0] + dr, position[1] + dc)
        if not (0 <= nxt[0] < rows and 0 <= nxt[1] < cols):
            positions.append(position)
            continue
        kind = types[nxt[0]][nxt[1]]
        if kind is None and open_hud and nxt[0] <= 2 and 2 <= nxt[1] <= 7:
            # Filas 0-2: el HUD tapa el tablero y la vision las deja vacias.
            kind = "terrain"
        if kind is None:
            positions.append(position)
            continue
        if kind in ("rock", "rock-in-button"):
            dest = (nxt[0] + dr, nxt[1] + dc)
            if not (0 <= dest[0] < rows and 0 <= dest[1] < cols):
                positions.append(position)
                continue
            dest_kind = types[dest[0]][dest[1]]
            if dest_kind not in ("terrain", "diamond", "fall") + _BUTTON_KINDS:
                positions.append(position)
                continue
            # Una roca sobre trampilla se empuja igual; la trampilla queda.
            types[nxt[0]][nxt[1]] = ("push_button" if kind == "rock-in-button"
                                     else "terrain")
            types[dest[0]][dest[1]] = (
                "rock-in-fall" if dest_kind == "fall"
                else "rock-in-button" if dest_kind in _BUTTON_KINDS
                else "rock")
            position = nxt
        elif kind == "fall":
            positions.append(position)
            continue
        elif kind in ("door", "metal-door"):
            gate_open = kind == "metal-door" and (
                types[position[0]][position[1]] in _BUTTON_KINDS
                or any(k == "rock-in-button" for r in types for k in r))
            if gate_open:
                types[nxt[0]][nxt[1]] = "terrain"
                position = nxt
            elif not held_key:
                positions.append(position)
                continue
            else:
                held_key = False
                types[nxt[0]][nxt[1]] = "terrain"
                position = nxt
        elif kind == "spike":
            # El juego activa el pincho al pisarlo; luego es transitable.
            types[nxt[0]][nxt[1]] = "spike-up"
            position = nxt
        elif kind in passable:
            if kind == "key":
                held_key = True
            if kind == "diamond":
                types[nxt[0]][nxt[1]] = "terrain"
            position = nxt
        else:
            positions.append(position)
            continue
        positions.append(position)
    trace = tuple(positions)
    return (trace, held_key) if return_key else trace


def is_five_rock_level(grid):
    """Recognize this map using its four fixed pits and rock inventory.

    Filled pits remain ``rock-in-fall``, so the signature continues to match
    after the route has started or when the bot is resumed mid-level.
    """
    if not grid or len(grid) != 15 or len(grid[0]) != 10:
        return False

    def cell_type_at(position):
        row, col = position
        cell = grid[row][col]
        return None if cell is None else cell.cell_type

    matching_holes = sum(
        cell_type_at(position) in ("fall", "rock-in-fall")
        for position in _HOLES)
    if matching_holes < 3:
        return False

    rocks_and_fills = sum(
        cell is not None and cell.cell_type in ("rock", "rock-in-fall")
        for row in grid for cell in row)
    if rocks_and_fills < 4:
        return False

    diamond_count = sum(
        cell is not None and cell.cell_type == "diamond"
        for row in grid for cell in row)
    return diamond_count <= len(_DIAMOND_ROUTE_INDEX)


def is_level6_captured_route(grid):
    """Recognize the Level 6 board used to record the rigid route.

    The exact start is player (3,5), keys (4,8)/(13,4), rocks (4,2)/(4,7),
    and pits (5,1)/(5,8)/(11,1). A resume is allowed only on a coordinate in
    the captured route with the same pit/rock family and key state.
    """
    if not grid or len(grid) != 15 or len(grid[0]) != 10:
        return False
    holes = ((5, 1), (5, 8), (11, 1))
    hole_hits = sum(
        _cell_type(grid, position) in ("fall", "rock-in-fall")
        for position in holes)
    if hole_hits < 3:
        return False
    rock_mass = sum(
        cell is not None and cell.cell_type in ("rock", "rock-in-fall")
        for row in grid for cell in row)
    if rock_mass < 2:
        return False
    players = [(int(cell.coordinates[0]), int(cell.coordinates[1]), cell.cell_type)
               for row in grid for cell in row if cell is not None and
               cell.cell_type in ("player", "player-with-key", "player-with-key1",
                                  "player-with-key2")]
    if not players:
        return False
    player = players[0][:2]
    has_key = any("with-key" in p[2] for p in players)
    top_key = _cell_type(grid, (4, 8)) == "key"
    bottom_key = _cell_type(grid, (13, 4)) == "key"
    initial = (player == LEVEL6_CAPTURE_START
               and top_key and bottom_key
               and _cell_type(grid, (4, 2)) == "rock"
               and _cell_type(grid, (4, 7)) == "rock")
    on_route = player in set(route_positions(LEVEL6_CAPTURE_START,
                                             LEVEL6_CAPTURE_DIRECTIONS))
    resumed = on_route and (top_key or has_key)
    return initial or resumed


def is_level7_captured_route(grid):
    """Recognize the pit/key board recorded after Level 6.

    Start: player (4,2), key (7,7), door (11,5), pits (7,4)/(10,1)/(10,7).
    A resume is accepted only on a coordinate of the recorded route.
    """
    if not grid or len(grid) != 15 or len(grid[0]) != 10:
        return False
    hole_hits = sum(
        _cell_type(grid, position) in ("fall", "rock-in-fall")
        for position in _LEVEL7_HOLES)
    if hole_hits < 3:
        return False
    players = [(int(cell.coordinates[0]), int(cell.coordinates[1]), cell.cell_type)
               for row in grid for cell in row if cell is not None and
               cell.cell_type in ("player", "player-with-key", "player-with-key1",
                                  "player-with-key2")]
    if not players:
        return False
    player = players[0][:2]
    has_key = any("with-key" in p[2] for p in players)
    key_present = _cell_type(grid, (7, 7)) == "key"
    door_present = _cell_type(grid, (11, 5)) in ("door", "metal-door")
    initial = (player == LEVEL7_CAPTURE_START and key_present and door_present)
    on_route = player in set(route_positions(LEVEL7_CAPTURE_START,
                                             LEVEL7_CAPTURE_DIRECTIONS))
    resumed = on_route and (key_present or has_key or door_present)
    return (initial or resumed) and _terrain_fits(
        grid, LEVEL7_CAPTURE_START, LEVEL7_CAPTURE_DIRECTIONS)


def is_level8_captured_route(grid):
    """Pit/key/trapdoor board: start (7,5), key (10,2), door (6,7), cage (4,5).

    Con la firma del mapa basta cualquier posicion del jugador: el reenganche
    BFS de la ruta lo devuelve al waypoint alcanzable mas cercano.
    """
    if not grid or len(grid) != 15 or len(grid[0]) != 10:
        return False
    if sum(_cell_type(grid, p) in ("fall", "rock-in-fall")
           for p in _LEVEL8_HOLES) < 2:
        return False
    players = [cell.cell_type for row in grid for cell in row
               if cell is not None and cell.cell_type in (
                   "player", "player-with-key", "player-with-key1",
                   "player-with-key2")]
    if not players:
        return False
    has_key = any("with-key" in p for p in players)
    key_present = _cell_type(grid, (10, 2)) == "key"
    door_present = _cell_type(grid, (6, 7)) in ("door", "metal-door")
    return key_present or has_key or door_present


def is_level9_captured_route(grid):
    """Trapdoor board #2. Firma: escalera/jaula en (13,8) O las trampillas
    (5,1),(7,8),(12,5) (al inicio la escalera aun no se lee en vivo).
    Cualquier posicion del jugador vale; el reenganche BFS la devuelve a la ruta.
    """
    if not grid or len(grid) != 15 or len(grid[0]) != 10:
        return False
    if not any(cell is not None and cell.cell_type in (
            "player", "player-with-key", "player-with-key1", "player-with-key2")
            for row in grid for cell in row):
        return False
    if _cell_type(grid, (13, 8)) in ("ladder", "ladder-open"):
        return True
    buttons = sum(_cell_type(grid, p) in (
        "push_button", "push-button", "rock-in-button")
        for p in ((5, 1), (7, 8), (12, 5)))
    return buttons >= 2


def _terrain_fits(grid, start, directions, minimum=0.85):
    """Patron de terreno: casi todas las celdas de la ruta deben existir
    (no ser None/pared) en el mapa capturado. Endurece las firmas."""
    cells = route_positions(start, directions)
    ok = sum(_cell_type(grid, p) is not None for p in cells)
    return ok / len(cells) >= minimum


def is_level12_captured_route(grid):
    """Lava/key level: door (5,3), start (3,2). Firma = puerta + terreno."""
    if not grid or len(grid) != 15 or len(grid[0]) != 10:
        return False
    if _cell_type(grid, (5, 3)) not in ("door", "metal-door"):
        return False
    if not any(c is not None and c.cell_type in (
            "player", "player-with-key", "player-with-key1", "player-with-key2")
            for row in grid for c in row):
        return False
    return _terrain_fits(grid, LEVEL12_CAPTURE_START,
                         LEVEL12_CAPTURE_DIRECTIONS)


def is_level11_captured_route(grid):
    """Key/trapdoor board: pits (5,7),(9,5),(12,1), cage (4,4), start (4,2)."""
    if not grid or len(grid) != 15 or len(grid[0]) != 10:
        return False
    if sum(_cell_type(grid, p) in ("fall", "rock-in-fall")
           for p in ((5, 7), (9, 5), (12, 1))) < 2:
        return False
    if not _terrain_fits(grid, LEVEL11_CAPTURE_START, LEVEL11_CAPTURE_DIRECTIONS):
        return False
    return any(cell is not None and cell.cell_type in (
        "player", "player-with-key", "player-with-key1", "player-with-key2")
        for row in grid for cell in row)

def is_level10_captured_route(grid):
    """Pit/spike board: pits (8,2),(8,7), cage (5,4), start (6,5)."""
    if not grid or len(grid) != 15 or len(grid[0]) != 10:
        return False
    if sum(_cell_type(grid, p) in ("fall", "rock-in-fall")
           for p in ((8, 2), (8, 7))) < 2:
        return False
    if not _terrain_fits(grid, LEVEL10_CAPTURE_START, LEVEL10_CAPTURE_DIRECTIONS):
        return False
    return any(cell is not None and cell.cell_type in (
        "player", "player-with-key", "player-with-key1", "player-with-key2")
        for row in grid for cell in row)

def _cell_type(grid, position):
    row, col = position
    if not (0 <= row < len(grid) and 0 <= col < len(grid[0])):
        return None
    cell = grid[row][col]
    return None if cell is None else cell.cell_type


def _shortest_safe_path(grid, start, goal, has_key=False):
    """Unweighted BFS used only to rejoin the scripted route safely."""
    start = tuple(start)
    goal = tuple(goal)
    if start == goal:
        return []
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    queue = deque([start])
    came_from = {start: None}
    came_step = {}
    moves = ((-1, 0, "up"), (1, 0, "down"),
             (0, -1, "left"), (0, 1, "right"))

    while queue:
        row, col = queue.popleft()
        for dr, dc, name in moves:
            nxt = (row + dr, col + dc)
            if nxt in came_from or not (0 <= nxt[0] < rows and 0 <= nxt[1] < cols):
                continue
            kind = _cell_type(grid, nxt)
            if (kind not in _SAFE_ROUTE_TILE_TYPES
                    and not (has_key and kind in ("door", "metal-door"))):
                continue
            came_from[nxt] = (row, col)
            came_step[nxt] = name
            if nxt == goal:
                path = []
                current = goal
                while current != start:
                    path.append(came_step[current])
                    current = came_from[current]
                return list(reversed(path))
            queue.append(nxt)
    return None


class FiveRockLevelRoute:
    """Follower for the supplied route, with capture-based progress/rejoin."""

    kind = "five_rock"
    open_hud = False

    def __init__(self, grid, player_pos, has_key=False, *, route_start=ROUTE_START,
                 route_groups=ROUTE_GROUPS, diamond_route_index=None,
                 simulate_map=True):
        self.route_start = tuple(route_start)
        self.route_groups = tuple(route_groups)
        self.directions = tuple(step for group in self.route_groups for step in group)
        self.simulate_map = bool(simulate_map)
        segment_ends = []
        segment_offset = 0
        for group in self.route_groups:
            segment_offset += len(group)
            segment_ends.append(segment_offset)
        self.segment_ends = tuple(segment_ends)
        self.diamond_route_index = (dict(diamond_route_index)
                                    if diamond_route_index is not None else
                                    dict(_DIAMOND_ROUTE_INDEX))
        self.step_index = None
        self.rejoin_index = None
        self.pending = None
        self.failed_route_segments = {}
        self.has_key = bool(has_key)
        self.completed = False
        self.unusable = False

        start = tuple(int(v) for v in player_pos)
        # Build the coordinate trace from the level map so wall bumps and
        # rock-to-pit pushes keep subsequent waypoints aligned with the game.
        self.positions = (
            _simulate_route_positions(
                grid, self.route_start, self.directions, self.has_key,
                open_hud=self.open_hud)
            if simulate_map else route_positions(self.route_start, self.directions)
        )
        if start == self.route_start:
            self.step_index = 0
            return

        floor = self._progress_floor(grid)
        candidate = self._nearest_route_index(grid, start, floor)
        if candidate is None:
            self.unusable = True
        elif self.positions[candidate] == start:
            self.step_index = candidate
        else:
            self.rejoin_index = candidate

    def _progress_floor(self, grid):
        floor = 0
        for coordinate, index in self.diamond_route_index.items():
            if _cell_type(grid, coordinate) != "diamond":
                floor = max(floor, index)
        return floor

    def _nearest_route_index(self, grid, start, minimum_index):
        best = None
        best_score = None
        has_key = any(
            cell is not None and cell.cell_type in
            ("player-with-key", "player-with-key1", "player-with-key2")
            for row in grid for cell in row)
        for index in range(max(0, minimum_index), len(self.positions)):
            target = self.positions[index]
            if _cell_type(grid, target) not in _SAFE_ROUTE_TILE_TYPES:
                continue
            path = _shortest_safe_path(grid, start, target, has_key)
            if path is None:
                continue
            score = (len(path), index)
            if best_score is None or score < best_score:
                best = index
                best_score = score
        return best

    def blind_expected(self):
        """(posicion, llave) esperadas si la captura no ve al jugador.

        Con el sprite oculto (p. ej. bajo el HUD en las filas 0-2) se asume que
        el ultimo tramo enviado llego a su destino y la ruta sigue desde ahi.
        """
        if self.completed or self.unusable:
            return None
        if self.pending is None:
            # Sin tramo en vuelo (p. ej. tras un falso atasco): seguir la
            # secuencia desde donde el simulador la dejo.
            if self.step_index is None or self.rejoin_index is not None:
                return None
            if self.step_index >= len(self.positions):
                return None
            return tuple(self.positions[self.step_index]), self.has_key
        kind, data = self.pending
        if kind == "route":
            expected = data[3][-1] if data[3] else data[2]
            return tuple(expected), getattr(self, "_pending_final_key", self.has_key)
        return tuple(data[1]), self.has_key

    def observe(self, player_pos, last_action, grid=None):
        """Advance only after the capture confirms the requested movement."""
        if self.pending is None:
            return
        try:
            position = tuple(int(v) for v in player_pos)
        except (TypeError, ValueError):
            return

        kind, data = self.pending
        action_name = getattr(last_action, "action", "")
        expected_action = "level_route" if kind == "route" else "level_route_rejoin"
        if action_name != expected_action:
            self.pending = None
            if kind == "route" and position != data[2]:
                candidate = self._nearest_route_index(
                    grid if grid is not None else getattr(self, "_last_grid", []),
                    position, data[1])
                self.rejoin_index = candidate
                if candidate is None:
                    self.unusable = True
            return

        if kind == "route":
            start_index, end_index, start_position, expected_positions = data
            reached = [index for index, expected in enumerate(expected_positions, 1)
                       if expected == position]
            if reached:
                self.step_index = start_index + max(reached)
                self.failed_route_segments.pop((start_index, end_index), None)
            elif position == start_position:
                # Ningun input llegó al juego: conservar el mismo tramo para
                # un reintento; tras un segundo fallo, reenganchar si se puede.
                self.step_index = start_index
                segment = (start_index, end_index)
                self.failed_route_segments[segment] = (
                    self.failed_route_segments.get(segment, 0) + 1)
                if self.failed_route_segments[segment] >= 2:
                    self.rejoin_index = self._nearest_route_index(
                        grid if grid is not None else getattr(self, "_last_grid", []),
                        position, end_index + 1)
                    if self.rejoin_index is None:
                        self.unusable = True
            else:
                # El juego pudo aceptar el grupo aunque la predicción de una
                # puerta/pared no coincida. Las pulsaciones están consumidas;
                # continuar el flujo desde la posición real recapturada.
                self.step_index = end_index
                self.failed_route_segments.pop((start_index, end_index), None)
        else:
            target_index, expected_position = data
            if position == expected_position and position == self.positions[target_index]:
                self.step_index = target_index
                self.rejoin_index = None
        self.pending = None

    def _choose_rejoin(self, grid, player_pos, minimum_index, has_key):
        best = None
        best_score = None
        for index in range(max(0, minimum_index), len(self.positions)):
            target = self.positions[index]
            if _cell_type(grid, target) not in _SAFE_ROUTE_TILE_TYPES:
                continue
            path = _shortest_safe_path(grid, player_pos, target, has_key)
            if path is None:
                continue
            score = (len(path), index)
            if best_score is None or score < best_score:
                best = (index, path)
                best_score = score
        return best

    def next_action(self, grid, player_pos, has_key=False, failed_targets=None):
        if self.completed or self.unusable:
            return None
        self._last_grid = grid
        self.has_key = bool(has_key)
        failed_targets = failed_targets or set()
        position = tuple(int(v) for v in player_pos)

        if self.rejoin_index is not None:
            target_index = self.rejoin_index
            target = self.positions[target_index]
            if position == target:
                self.step_index = target_index
                self.rejoin_index = None
            else:
                path = _shortest_safe_path(grid, position, target, self.has_key)
                if not path:
                    next_rejoin = self._choose_rejoin(
                        grid, position, target_index + 1, self.has_key)
                    if next_rejoin is None:
                        self.unusable = True
                        return None
                    self.rejoin_index = next_rejoin[0]
                    target_index = self.rejoin_index
                    target = self.positions[target_index]
                    path = next_rejoin[1]
                direction = path[0]
                dr, dc = {
                    "up": (-1, 0), "down": (1, 0),
                    "left": (0, -1), "right": (0, 1),
                }[direction]
                one_step = (position[0] + dr, position[1] + dc)
                if ("level_route_rejoin", one_step) in failed_targets:
                    next_rejoin = self._choose_rejoin(
                        grid, position, target_index + 1, self.has_key)
                    if next_rejoin is None:
                        self.unusable = True
                        return None
                    self.rejoin_index = next_rejoin[0]
                    return self.next_action(grid, player_pos, has_key, failed_targets)
                self.pending = ("rejoin", (target_index, one_step))
                return GameAction("level_route_rejoin", coordinates=list(one_step),
                                  path=[direction])

        if self.step_index is None:
            candidate = self._nearest_route_index(
                grid, position, self._progress_floor(grid))
            if candidate is None:
                self.unusable = True
                return None
            if self.positions[candidate] == position:
                self.step_index = candidate
            else:
                self.rejoin_index = candidate
                return self.next_action(grid, player_pos, has_key, failed_targets)

        if self.step_index >= len(self.directions):
            self.completed = True
            return None

        end_index = next(
            (end for end in self.segment_ends if end > self.step_index),
            len(self.directions),
        )
        path = [_NAMES[d] for d in self.directions[self.step_index:end_index]]
        if self.simulate_map:
            expected_positions, final_key = _simulate_route_positions(
                grid, position, self.directions[self.step_index:end_index],
                self.has_key, return_key=True, open_hud=self.open_hud)
            expected_positions = expected_positions[1:]
        else:
            expected_positions = route_positions(position, self.directions[self.step_index:end_index])[1:]
            final_key = self.has_key
        endpoint = expected_positions[-1] if expected_positions else position
        if ("level_route", endpoint) in failed_targets:
            next_rejoin = self._choose_rejoin(
                grid, position, end_index + 1, self.has_key)
            if next_rejoin is None:
                self.unusable = True
                return None
            self.rejoin_index = next_rejoin[0]
            return self.next_action(grid, player_pos, has_key, failed_targets)

        self.pending = ("route", (self.step_index, end_index, position,
                                   tuple(expected_positions)))
        self._pending_final_key = final_key
        action = GameAction("level_route", coordinates=list(endpoint), path=path)
        action.consumes_key = self.has_key and not final_key
        return action


class Level6CapturedRoute(FiveRockLevelRoute):
    """Rigid Level 6 route recorded from the user's manual playthrough."""

    kind = "level6_captured"
    rigid = True

    def __init__(self, grid, player_pos, has_key=False):
        super().__init__(
            grid, player_pos, has_key,
            route_start=LEVEL6_CAPTURE_START,
            route_groups=LEVEL6_CAPTURE_GROUPS,
            diamond_route_index={},
            simulate_map=True,
        )


class Level7CapturedRoute(FiveRockLevelRoute):
    """Rigid route recorded from the user's manual playthrough (pit/key level)."""

    kind = "level7_captured"
    rigid = True

    def __init__(self, grid, player_pos, has_key=False):
        super().__init__(
            grid, player_pos, has_key,
            route_start=LEVEL7_CAPTURE_START,
            route_groups=LEVEL7_CAPTURE_GROUPS,
            diamond_route_index={},
            simulate_map=True,
        )


class Level8CapturedRoute(FiveRockLevelRoute):
    """Rigid route recorded manually for the trapdoor (push_button) level."""

    kind = "level8_captured"
    rigid = True
    open_hud = True

    def __init__(self, grid, player_pos, has_key=False):
        super().__init__(
            grid, player_pos, has_key,
            route_start=LEVEL8_CAPTURE_START,
            route_groups=LEVEL8_CAPTURE_GROUPS,
            diamond_route_index={},
            simulate_map=True,
        )


class Level9CapturedRoute(FiveRockLevelRoute):
    """Rigid route recorded manually for the second trapdoor level."""

    kind = "level9_captured"
    rigid = True

    def __init__(self, grid, player_pos, has_key=False):
        super().__init__(
            grid, player_pos, has_key,
            route_start=LEVEL9_CAPTURE_START,
            route_groups=LEVEL9_CAPTURE_GROUPS,
            diamond_route_index={},
            simulate_map=True,
        )


class Level10CapturedRoute(FiveRockLevelRoute):
    """Rigid route recorded manually for the pit/spike level."""

    kind = "level10_captured"
    rigid = True

    def __init__(self, grid, player_pos, has_key=False):
        super().__init__(
            grid, player_pos, has_key,
            route_start=LEVEL10_CAPTURE_START,
            route_groups=LEVEL10_CAPTURE_GROUPS,
            diamond_route_index={},
            simulate_map=True,
        )


class Level11CapturedRoute(FiveRockLevelRoute):
    """Rigid route recorded manually for the key/trapdoor level."""

    kind = "level11_captured"
    rigid = True

    def __init__(self, grid, player_pos, has_key=False):
        super().__init__(
            grid, player_pos, has_key,
            route_start=LEVEL11_CAPTURE_START,
            route_groups=LEVEL11_CAPTURE_GROUPS,
            diamond_route_index={},
            simulate_map=True,
        )


class Level12CapturedRoute(FiveRockLevelRoute):
    """Rigid route recorded manually for the lava/key level."""

    kind = "level12_captured"
    rigid = True

    def __init__(self, grid, player_pos, has_key=False):
        super().__init__(
            grid, player_pos, has_key,
            route_start=LEVEL12_CAPTURE_START,
            route_groups=LEVEL12_CAPTURE_GROUPS,
            diamond_route_index={},
            simulate_map=True,
        )
