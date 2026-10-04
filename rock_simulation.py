
import copy
from game_action import GameAction
from collections import deque


class RockSimulation:
    _DIRECTIONS = (
        (-1, 0, "up"),
        (1, 0, "down"),
        (0, -1, "left"),
        (0, 1, "right"),
    )
    _BUTTON_TYPES = {"button", "push_button", "push-button"}
    _TARGET_TYPES = {"fall", "button", "push_button", "push-button", "terrain"}
    _PLAYER_BLOCKED_TYPES = {"fall", "key", "spike", "door", "metal-door", "rock-in-button"}

    def __init__(self, grid, player_pos, rock_pos, target_pos, blocked=None,
                 rock_allowed=None):
        self.grid = copy.deepcopy(grid)  # Esta grilla estara actualizada al finalizar la simulacion
        self.player_pos = player_pos
        self.path = []                # Path completo seguido por el jugador
        self.directions = []          # Direcciones seguidas por el jugador
        self.rock_start = rock_pos
        self.target_pos = target_pos
        self.blocked = {tuple(p) for p in (blocked or ())}
        # Hard limit (barrera azul del Nivel 6): celdas que la roca puede pisar.
        # None = sin restriccion (resto de niveles).
        self.rock_allowed = ({tuple(p) for p in rock_allowed}
                             if rock_allowed is not None else None)
        self.action_history = []  # Acciones tomadas durante la simulacion
        self.action = "push_rock"

    def is_in_bounds(self, pos):
        r, c = pos
        return 0 <= r < len(self.grid) and 0 <= c < len(self.grid[0])

    def _cell_type(self, pos):
        if not self.is_in_bounds(pos) or self.grid[pos[0]][pos[1]] is None:
            return None
        return self.grid[pos[0]][pos[1]].cell_type

    @classmethod
    def can_reach_target_static(cls, grid, rock_start, target_pos, blocked=None):
        """Valentina-style reverse flood-fill from a target.

        Other rocks are treated as temporarily movable here; the exact BFS in
        ``simulate`` accounts for their current positions and player reachability.
        """
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        start = (int(rock_start[0]), int(rock_start[1]))
        target = (int(target_pos[0]), int(target_pos[1]))
        blocked = {tuple(p) for p in (blocked or ())}

        def in_bounds(pos):
            return 0 <= pos[0] < rows and 0 <= pos[1] < cols

        def cell_at(pos):
            return grid[pos[0]][pos[1]] if in_bounds(pos) else None

        def player_can_stand(pos):
            cell = cell_at(pos)
            return (cell is not None and pos not in blocked
                    and cell.cell_type not in cls._PLAYER_BLOCKED_TYPES
                    and (cell.walkable or cell.cell_type == "rock"))

        def rock_can_occupy(pos):
            cell = cell_at(pos)
            if cell is None or pos in blocked:
                return False
            # Match Valentina's model: a rock can pass a diamond, which the
            # player collects when it steps onto the vacated square. It must
            # not pass through keys, hazards, or a different fall.
            return cell.cell_type in ("terrain", "rock", "player", "player-with-key", "diamond")

        target_cell = cell_at(target)
        if target_cell is None or target_cell.cell_type not in cls._TARGET_TYPES:
            return False

        reachable = {target}
        queue = deque([target])
        while queue:
            row, col = queue.popleft()
            for dr, dc, _ in cls._DIRECTIONS:
                previous_rock = (row - dr, col - dc)
                player_stand = (row - 2 * dr, col - 2 * dc)
                if previous_rock in reachable:
                    continue
                if not in_bounds(previous_rock) or not player_can_stand(player_stand):
                    continue
                if not rock_can_occupy(previous_rock):
                    continue
                reachable.add(previous_rock)
                queue.append(previous_rock)

        return start in reachable

    def _player_can_walk(self, pos, rock_pos, other_rocks):
        if not self.is_in_bounds(pos) or pos in self.blocked or pos in other_rocks or pos == rock_pos:
            return False
        cell = self.grid[pos[0]][pos[1]]
        if cell is None or cell.cell_type in self._PLAYER_BLOCKED_TYPES:
            return False
        if cell.cell_type == "rock":
            # The simulated rock has vacated its original square.
            return pos == self._rock_start_tuple and pos != rock_pos
        return cell.walkable

    def _reachable_player_paths(self, player_pos, rock_pos, other_rocks):
        """BFS over player-walkable cells, returning shortest paths to each tile."""
        start = (int(player_pos[0]), int(player_pos[1]))
        if not self._player_can_walk(start, rock_pos, other_rocks):
            return {}

        paths = {start: ([], [start])}
        queue = deque([start])
        while queue:
            pos = queue.popleft()
            directions, coordinates = paths[pos]
            for dr, dc, name in self._DIRECTIONS:
                nxt = (pos[0] + dr, pos[1] + dc)
                if nxt in paths or not self._player_can_walk(nxt, rock_pos, other_rocks):
                    continue
                paths[nxt] = (directions + [name], coordinates + [nxt])
                queue.append(nxt)
        return paths

    def _rock_can_move_to(self, pos, rock_pos, other_rocks):
        if not self.is_in_bounds(pos) or pos in other_rocks:
            return False
        if self.rock_allowed is not None and pos not in self.rock_allowed:
            return False
        cell_type = self._cell_type(pos)
        if pos == self._target_tuple:
            return cell_type in self._TARGET_TYPES
        if cell_type == "rock":
            # The original square is empty after the first push.
            return pos == self._rock_start_tuple and pos != rock_pos
        # Falls and buttons are stopping points, never intermediate tiles.
        return cell_type in ("terrain", "player", "player-with-key", "diamond")

    def update_grid(self, rock_pos):
        r, c = rock_pos
        # Actualizamos la celda de la roca a "rock-in-fall" si es que esta en una posicion de caida
        if self.grid[r][c].cell_type == "fall":
            self.grid[r][c].cell_type = "rock-in-fall"
            self.grid[r][c].weight = 1
            self.grid[r][c].walkable = True
        # Si la roca esta en un boton, se cambia el tipo de celda a "rock-in-button"
        elif self.grid[r][c].cell_type in self._BUTTON_TYPES:
            self.grid[r][c].cell_type = "rock-in-button"
            self.grid[r][c].weight = 200
            self.grid[r][c].walkable = False
        # Si la roca esta en una posicion de terreno, se cambia el tipo de celda a "rock"
        elif self.grid[r][c].cell_type in ("terrain", "player", "player-with-key"):
            self.grid[r][c].cell_type = "rock"
            self.grid[r][c].weight = 100000 - 100
            self.grid[r][c].walkable = False

        # Actualizamos la celda inicial de la roca volviendola a terreno
        start_r, start_c = self.rock_start
        if self.grid[start_r][start_c].cell_type == "rock":
            self.grid[start_r][start_c].cell_type = "terrain"
            self.grid[start_r][start_c].weight = 1
            self.grid[start_r][start_c].walkable = True

    def simulate(self):
        try:
            self._rock_start_tuple = (int(self.rock_start[0]), int(self.rock_start[1]))
            self._target_tuple = (int(self.target_pos[0]), int(self.target_pos[1]))
            player_start = (int(self.player_pos[0]), int(self.player_pos[1]))
        except (TypeError, ValueError, IndexError):
            return False

        if not self.is_in_bounds(self._rock_start_tuple) or not self.is_in_bounds(self._target_tuple):
            return False
        if (self.rock_allowed is not None
                and self._rock_start_tuple not in self.rock_allowed):
            return False
        if self._cell_type(self._rock_start_tuple) != "rock":
            return False
        if self._cell_type(self._target_tuple) not in self._TARGET_TYPES:
            return False
        if not self.can_reach_target_static(
                self.grid, self._rock_start_tuple, self._target_tuple, self.blocked):
            return False

        other_rocks = {
            (r, c)
            for r, row in enumerate(self.grid)
            for c, cell in enumerate(row)
            if cell is not None and cell.cell_type == "rock"
            and (r, c) != self._rock_start_tuple
        }

        # Estado: (posicion de roca, posicion del jugador, pasos y direcciones).
        # El BFS avanza entre empujes y comprueba que el jugador pueda llegar al
        # lado correcto de la roca sin atravesar paredes ni otras rocas.
        queue = deque([(self._rock_start_tuple, player_start, [], [])])
        visited = {(self._rock_start_tuple, player_start)}

        while queue:
            rock_pos, player_pos, path, directions = queue.popleft()
            reachable = self._reachable_player_paths(player_pos, rock_pos, other_rocks)

            for dr, dc, move in self._DIRECTIONS:
                push_from = (rock_pos[0] - dr, rock_pos[1] - dc)
                new_rock_pos = (rock_pos[0] + dr, rock_pos[1] + dc)
                player_path = reachable.get(push_from)
                if player_path is None or not self._rock_can_move_to(new_rock_pos, rock_pos, other_rocks):
                    continue

                push_dirs = directions + player_path[0] + [move]
                push_path = path + player_path[1][1:] + [rock_pos]
                next_state = (new_rock_pos, rock_pos)

                if new_rock_pos == self._target_tuple:
                    self.player_pos = list(rock_pos)
                    self.path = push_path
                    self.directions = push_dirs
                    self.rock_final = new_rock_pos
                    self.update_grid(new_rock_pos)
                    # The player can collect diamonds while walking to a push
                    # position and when stepping into each vacated rock square.
                    for row, col in push_path:
                        cell = self.grid[row][col]
                        if cell is not None and cell.cell_type == "diamond":
                            cell.cell_type = "terrain"
                            cell.weight = 1
                            cell.walkable = True
                    self.action_history.append(GameAction(
                        "push_rock", coordinates=list(new_rock_pos), path=list(push_dirs)))
                    return True

                if next_state in visited:
                    continue
                visited.add(next_state)
                queue.append((new_rock_pos, rock_pos, push_path, push_dirs))

        return False
