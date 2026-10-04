import heapq


from cell import Cell


class AStar:
    def __init__(self, start: tuple[int, int], goal: tuple[int, int], grid: list[list['Cell']], blocked=None, allow=None):
        self.start = start
        self.goal = goal
        self.grid = grid
        self.rows = len(grid)
        self.cols = len(grid[0])
        # blocked: set de (r,c) intransitables extra (puertas sin llave, spikes).
        # Asi no se mutan celdas y el A* es thread-safe (multi-core real).
        self.blocked = blocked if blocked is not None else set()
        # allow: celdas 'rock' que en la simulacion ya quedaron vacias
        self.allow = allow if allow is not None else set()
        self._heap = []
        self._counter = 0
        self.open_set = set()
        self.closed_set = set()
        self.g_score = [[float('inf') for _ in range(self.cols)] for _ in range(self.rows)]
        self.f_score = [[float('inf') for _ in range(self.cols)] for _ in range(self.rows)]
        self.came_from = [[None for _ in range(self.cols)] for _ in range(self.rows)]
        self.total_weight = float('inf')
        self.directions = []
        self.path = []

    def heuristic(self, a, b) -> float:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def reconstruct_path(self, current):
        total_path = [current]
        while self.came_from[current[0]][current[1]] is not None:
            current = self.came_from[current[0]][current[1]]
            total_path.append(current)
        return total_path[::-1]

    def path_to_directions(self, path: list[tuple[int, int]]) -> list[str]:
        directions = []
        for i in range(1, len(path)):
            r1, c1 = path[i - 1]
            r2, c2 = path[i]
            if r2 < r1: directions.append("up")
            elif r2 > r1: directions.append("down")
            elif c2 < c1: directions.append("left")
            elif c2 > c1: directions.append("right")
        return directions

    def get_neighbors(self, node):
        row, col = node
        neighbors = []
        cell : Cell = self.grid[row][col]
        up : Cell = cell.neighbor_up
        down : Cell = cell.neighbor_down
        left : Cell = cell.neighbor_left
        right : Cell = cell.neighbor_right

        for nb in (up, down, left, right):
            if nb is None or not nb.walkable:
                continue
            nc = (int(nb.coordinates[0]), int(nb.coordinates[1]))
            if nc in self.blocked:
                continue
            if nb.cell_type == "rock" and nc not in self.allow and nc != (int(self.goal[0]), int(self.goal[1])):
                continue
            neighbors.append(nb.coordinates)

        return neighbors

    def search(self):
        sx, sy = int(self.start[0]), int(self.start[1])
        self.g_score[sx][sy] = 0
        f0 = self.heuristic(self.start, self.goal)
        self.f_score[sx][sy] = f0
        heapq.heappush(self._heap, (f0, self._counter, (sx, sy)))
        self._counter += 1
        self.open_set.add((sx, sy))

        while self._heap:
            _, _, current = heapq.heappop(self._heap)
            if current in self.closed_set:
                continue
            if current[0] == self.goal[0] and current[1] == self.goal[1]:
                self.path = self.reconstruct_path(current)
                self.total_weight = self.g_score[current[0]][current[1]]
                self.directions = self.path_to_directions(self.path)
                return {
                    "path": self.path,
                    "total_weight": self.total_weight,
                    "directions": self.directions
                }

            self.open_set.discard(current)
            self.closed_set.add(current)

            for neighbor in self.get_neighbors(current):
                neighbor = (int(neighbor[0]), int(neighbor[1]))
                if neighbor in self.closed_set:
                    continue

                ncell = self.grid[neighbor[0]][neighbor[1]]
                if ncell is None:
                    continue
                tentative_g = self.g_score[current[0]][current[1]] + ncell.weight

                if tentative_g >= self.g_score[neighbor[0]][neighbor[1]]:
                    continue

                self.came_from[neighbor[0]][neighbor[1]] = [current[0], current[1]]
                self.g_score[neighbor[0]][neighbor[1]] = tentative_g
                f = tentative_g + self.heuristic(neighbor, self.goal)
                self.f_score[neighbor[0]][neighbor[1]] = f
                heapq.heappush(self._heap, (f, self._counter, neighbor))
                self._counter += 1
                self.open_set.add(neighbor)

        return None
