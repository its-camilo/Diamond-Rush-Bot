import unittest

from cell import Cell
from game_state import GameState
from rock_simulation import RockSimulation
from level_route import (FiveRockLevelRoute, Level6CapturedRoute,
                         Level7CapturedRoute, Level8CapturedRoute,
                         LEVEL8_CAPTURE_GROUPS, is_level8_captured_route,
                         LEVEL6_CAPTURE_GROUPS,
                         LEVEL7_CAPTURE_GROUPS, ROUTE_GROUPS,
                         is_five_rock_level, is_level6_captured_route,
                         is_level7_captured_route, Level9CapturedRoute,
                         LEVEL9_CAPTURE_GROUPS, is_level9_captured_route,
                         Level10CapturedRoute, is_level10_captured_route,
                         Level11CapturedRoute, is_level11_captured_route,
                         Level12CapturedRoute, is_level12_captured_route,
                         Level13CapturedRoute, is_level13_captured_route,
                         Level14CapturedRoute, is_level14_captured_route)


def make_level_four_grid():
    grid = [[None for _ in range(10)] for _ in range(15)]

    def put(row, col, cell_type="terrain"):
        grid[row][col] = Cell((row, col), cell_type)

    for col in range(9):
        put(0, col)
    for col in range(2, 8):
        put(1, col)
    for col in range(1, 9):
        put(3, col)
    put(3, 2, "player")

    put(4, 6, "rock")
    for col in range(1, 9):
        put(5, col)
    put(5, 3, "diamond")
    put(5, 4, "diamond")
    put(5, 6, "fall")

    put(6, 1, "rock")
    put(7, 1, "fall")
    for col in range(2, 9):
        put(7, col)
    put(7, 5, "rock")
    put(7, 7, "diamond")
    put(8, 6, "diamond")

    for col in range(1, 9):
        put(9, col)
    for col in range(1, 9):
        put(10, col)
    put(10, 2, "rock")

    put(11, 2)
    put(11, 3)
    put(11, 4, "rock")
    put(11, 6, "fall")
    put(11, 8)

    put(12, 3, "fall")
    put(12, 4, "diamond")
    put(12, 6)
    put(12, 8)
    put(13, 4, "diamond")
    put(13, 8)

    for row in range(15):
        for col in range(10):
            cell = grid[row][col]
            if cell is None:
                continue
            cell.neighbor_up = grid[row - 1][col] if row > 0 else None
            cell.neighbor_down = grid[row + 1][col] if row < 14 else None
            cell.neighbor_left = grid[row][col - 1] if col > 0 else None
            cell.neighbor_right = grid[row][col + 1] if col < 9 else None
    return grid


class RockSimulationTests(unittest.TestCase):
    def test_replays_the_required_level_four_fill_order(self):
        grid = make_level_four_grid()
        player = [3, 2]
        first_fills = (
            ((4, 6), (5, 6)),
            ((6, 1), (7, 1)),
        )
        for rock, target in first_fills:
            with self.subTest(rock=rock, target=target):
                sim = RockSimulation(grid, player, rock, target)
                self.assertTrue(sim.simulate())
                self.assertEqual(sim.grid[target[0]][target[1]].cell_type, "rock-in-fall")
                self.assertEqual(sim.grid[rock[0]][rock[1]].cell_type, "terrain")
                grid = sim.grid
                player = sim.player_pos

        # The rock in the narrow row blocks access to the lower half. Use the
        # same one-step shove then diamond-clearing shove that a live replan uses.
        # The two reachable left-side diamonds were collected on the approach.
        for row, col in ((5, 3), (5, 4)):
            grid[row][col].cell_type = "terrain"
            grid[row][col].weight = 1
            grid[row][col].walkable = True
        state = GameState(grid, player, 2)
        action = state.get_next_action()
        self.assertEqual(action.action, "push_rock")
        self.assertEqual(tuple(action.target_pos), (7, 6))

        shoves = state.get_shove_simulations()
        self.assertTrue(shoves)
        self.assertEqual(tuple(shoves[0].rock_start), (7, 5))
        self.assertEqual(tuple(shoves[0].target_pos), (7, 6))
        grid = shoves[0].grid
        player = shoves[0].player_pos

        state = GameState(grid, player, 3)
        shoves = state.get_shove_simulations()
        self.assertTrue(shoves)
        self.assertEqual(tuple(shoves[0].rock_start), (7, 6))
        self.assertEqual(tuple(shoves[0].target_pos), (7, 8))
        self.assertIn("right", shoves[0].directions)
        grid = shoves[0].grid
        player = shoves[0].player_pos

        last_fills = (
            ((10, 2), (12, 3)),
            ((11, 4), (11, 6)),
        )
        for rock, target in last_fills:
            with self.subTest(rock=rock, target=target):
                sim = RockSimulation(grid, player, rock, target)
                self.assertTrue(sim.simulate())
                self.assertEqual(sim.grid[target[0]][target[1]].cell_type, "rock-in-fall")
                self.assertEqual(sim.grid[rock[0]][rock[1]].cell_type, "terrain")
                self.assertTrue(sim.directions)
                grid = sim.grid
                player = sim.player_pos

    def test_initial_assignment_uses_the_reachable_near_hole(self):
        state = GameState(make_level_four_grid(), [3, 2], 0)

        simulations = state.get_rock_simulations()

        self.assertTrue(simulations)
        self.assertEqual(tuple(simulations[0].rock_start), (4, 6))
        self.assertEqual(tuple(simulations[0].target_pos), (5, 6))
        # The matching is one-to-one: no returned plan repeats a rock or target.
        self.assertEqual(
            len({tuple(sim.rock_start) for sim in simulations}), len(simulations))
        self.assertEqual(
            len({tuple(sim.target_pos) for sim in simulations}), len(simulations))

    def test_a_rock_cannot_cross_another_unfilled_fall(self):
        grid = [[None for _ in range(5)] for _ in range(3)]
        for col in range(5):
            grid[1][col] = Cell((1, col), "terrain")
        grid[1][0] = Cell((1, 0), "player")
        grid[1][1] = Cell((1, 1), "rock")
        grid[1][2] = Cell((1, 2), "fall")
        grid[1][4] = Cell((1, 4), "fall")

        sim = RockSimulation(grid, [1, 0], (1, 1), (1, 4))

        self.assertFalse(sim.simulate())

    def test_spike_up_is_walkable_after_activation(self):
        # Pincho ya pisado/desactivado: transitable barato. Verificado en vivo
        # (el bot lo cruza repetidas veces) y el solve offline lo necesita.
        cell = Cell((0, 0), "spike-up")
        self.assertTrue(cell.walkable)
        self.assertEqual(cell.weight, 1)

    def test_can_backtrack_through_an_activated_spike(self):
        grid = [[Cell((r, 0), "terrain")] for r in range(3)]
        grid[0][0] = Cell((0, 0), "diamond")
        grid[1][0] = Cell((1, 0), "spike-up")
        grid[2][0] = Cell((2, 0), "player")
        for r in range(3):
            for c in range(1):
                cell = grid[r][c]
                cell.neighbor_up = grid[r - 1][c] if r > 0 else None
                cell.neighbor_down = grid[r + 1][c] if r < 2 else None

        state = GameState(grid, [2, 0], 0)

        nearest, path = state.find_nearest_diamond()

        self.assertIsNotNone(nearest)
        self.assertEqual(path, ["up", "up"])

def make_key_door_level_grid():
    """Tablero inicial del nivel llave/puerta (walkthrough 0/8).

    Reconstruido de la captura del log: jugador (4,1), llave (4,5),
    puerta (5,8), rocas (5,4)/(11,8), huecos (6,8)/(8,1).
    """
    grid = [[None for _ in range(10)] for _ in range(15)]

    def put(row, col, cell_type="terrain"):
        grid[row][col] = Cell((row, col), cell_type)

    for col in range(9):
        put(0, col)
    for col in range(2, 8):
        put(1, col)
    put(3, 1, "ladder")
    put(3, 7, "diamond")
    put(3, 8, "diamond")
    put(4, 1, "player")
    put(4, 2, "spike")
    put(4, 3)
    put(4, 4)
    put(4, 5, "key")
    put(4, 7, "diamond")
    put(4, 8, "diamond")
    put(5, 1, "spike")
    put(5, 4, "rock")
    put(5, 8, "door")
    put(6, 1, "diamond")
    put(6, 3)
    put(6, 4)
    put(6, 5)
    put(6, 8, "fall")
    put(7, 1, "diamond")
    for col in range(3, 9):
        put(7, col)
    put(8, 1, "fall")
    for col in range(3, 9):
        put(8, col)
    for col in (1, 2, 3, 4, 5):
        put(9, col)
    put(9, 7)
    put(9, 8)
    for col in (1, 2, 3, 4):
        put(10, col)
    put(10, 8)
    put(11, 1)
    put(11, 3)
    put(11, 4)
    put(11, 8, "rock")
    put(12, 4)
    put(12, 5, "spike")
    put(12, 6, "spike")
    put(12, 7)
    put(12, 8)
    put(13, 5, "diamond")
    put(13, 6, "diamond")

    for row in range(15):
        for col in range(10):
            cell = grid[row][col]
            if cell is None:
                continue
            cell.neighbor_up = grid[row - 1][col] if row > 0 else None
            cell.neighbor_down = grid[row + 1][col] if row < 14 else None
            cell.neighbor_left = grid[row][col - 1] if col > 0 else None
            cell.neighbor_right = grid[row][col + 1] if col < 9 else None
    return grid


def make_mid_stuck_grid():
    """Estado trabado en vivo: jugador con llave en (4,3), (8,1) relleno.

    Diamantes restantes: 4 arriba-derecha + 2 abajo. Rocas: (11,8).
    Puerta (5,8) cerrada, pinchos (5,1)/(12,5)/(12,6) activos.
    """
    grid = [[None for _ in range(10)] for _ in range(15)]

    def put(row, col, cell_type="terrain"):
        grid[row][col] = Cell((row, col), cell_type)

    for col in range(9):
        put(0, col)
    for col in range(2, 8):
        put(1, col)
    put(3, 1, "ladder")
    put(3, 7, "diamond")
    put(3, 8, "diamond")
    put(4, 1)
    put(4, 2, "spike-up")
    put(4, 3, "player-with-key")
    put(4, 4)
    put(4, 5)
    put(4, 7, "diamond")
    put(4, 8, "diamond")
    put(5, 1, "spike")
    put(5, 4)
    put(5, 8, "door")
    put(6, 1)
    put(6, 3)
    put(6, 4)
    put(6, 5)
    put(6, 8, "fall")
    put(7, 1)
    for col in range(3, 9):
        put(7, col)
    put(8, 1, "rock-in-fall")
    for col in range(3, 9):
        put(8, col)
    for col in (1, 2, 3, 4, 5):
        put(9, col)
    put(9, 7)
    put(9, 8)
    for col in (1, 2, 3, 4):
        put(10, col)
    put(10, 8)
    put(11, 1)
    put(11, 3)
    put(11, 4)
    put(11, 8, "rock")
    put(12, 4)
    put(12, 5, "spike")
    put(12, 6, "spike")
    put(12, 7)
    put(12, 8)
    put(13, 5, "diamond")
    put(13, 6, "diamond")

    for row in range(15):
        for col in range(10):
            cell = grid[row][col]
            if cell is None:
                continue
            cell.neighbor_up = grid[row - 1][col] if row > 0 else None
            cell.neighbor_down = grid[row + 1][col] if row < 14 else None
            cell.neighbor_left = grid[row][col - 1] if col > 0 else None
            cell.neighbor_right = grid[row][col + 1] if col < 9 else None
    return grid


def make_after_left_diamonds_grid():
    """Estado tras recoger (7,1) y (6,1): jugador con llave en (6,1).

    (8,1) ya relleno, puerta cerrada, pinchos (5,1)/(12,5)/(12,6) activos.
    Lo correcto es BAJAR hacia abajo, nunca subir a (5,1).
    """
    grid = [[None for _ in range(10)] for _ in range(15)]

    def put(row, col, cell_type="terrain"):
        grid[row][col] = Cell((row, col), cell_type)

    for col in range(9):
        put(0, col)
    for col in range(2, 8):
        put(1, col)
    put(3, 1, "ladder")
    put(3, 7, "diamond")
    put(3, 8, "diamond")
    put(4, 1)
    put(4, 2, "spike-up")
    put(4, 3)
    put(4, 4)
    put(4, 5)
    put(4, 7, "diamond")
    put(4, 8, "diamond")
    put(5, 1, "spike")
    put(5, 4)
    put(5, 8, "door")
    put(6, 1, "player-with-key")
    put(6, 3)
    put(6, 4)
    put(6, 5)
    put(6, 8, "fall")
    put(7, 1)
    for col in range(3, 9):
        put(7, col)
    put(8, 1, "rock-in-fall")
    for col in range(3, 9):
        put(8, col)
    for col in (1, 2, 3, 4, 5):
        put(9, col)
    put(9, 7)
    put(9, 8)
    for col in (1, 2, 3, 4):
        put(10, col)
    put(10, 8)
    put(11, 1)
    put(11, 3)
    put(11, 4)
    put(11, 8, "rock")
    put(12, 4)
    put(12, 5, "spike")
    put(12, 6, "spike")
    put(12, 7)
    put(12, 8)
    put(13, 5, "diamond")
    put(13, 6, "diamond")

    for row in range(15):
        for col in range(10):
            cell = grid[row][col]
            if cell is None:
                continue
            cell.neighbor_up = grid[row - 1][col] if row > 0 else None
            cell.neighbor_down = grid[row + 1][col] if row < 14 else None
            cell.neighbor_left = grid[row][col - 1] if col > 0 else None
            cell.neighbor_right = grid[row][col + 1] if col < 9 else None
    return grid


def make_endgame_grid():
    """Estado final: todo recogido, escalera abierta en (3,1).

    Jugador en (4,7), pincho (5,1) vivo, (4,2) aplanado, rellenos listos,
    puerta abierta. La ruta a la escalera debe bajar primero (no subir a la
    esquina de pinchos) y jamas pisar (5,1).
    """
    grid = [[None for _ in range(10)] for _ in range(15)]

    def put(row, col, cell_type="terrain"):
        grid[row][col] = Cell((row, col), cell_type)

    for col in range(9):
        put(0, col)
    for col in range(2, 8):
        put(1, col)
    put(3, 1, "ladder-open")
    put(4, 1)
    put(4, 2, "spike-up")
    put(4, 3)
    put(4, 4)
    put(4, 5)
    put(4, 7, "player")
    put(4, 8)
    put(5, 1, "spike")
    put(5, 4)
    put(5, 8)
    put(6, 1)
    put(6, 3)
    put(6, 4)
    put(6, 5)
    put(6, 8, "rock-in-fall")
    put(7, 1)
    for col in range(3, 9):
        put(7, col)
    put(8, 1, "rock-in-fall")
    for col in range(3, 9):
        put(8, col)
    for col in (1, 2, 3, 4, 5):
        put(9, col)
    put(9, 7)
    put(9, 8)
    for col in (1, 2, 3, 4):
        put(10, col)
    put(10, 8)
    put(11, 1)
    put(11, 3)
    put(11, 4)
    put(11, 8)
    put(12, 4)
    put(12, 5)
    put(12, 6)
    put(12, 7)
    put(12, 8)
    put(13, 5)
    put(13, 6)

    for row in range(15):
        for col in range(10):
            cell = grid[row][col]
            if cell is None:
                continue
            cell.neighbor_up = grid[row - 1][col] if row > 0 else None
            cell.neighbor_down = grid[row + 1][col] if row < 14 else None
            cell.neighbor_left = grid[row][col - 1] if col > 0 else None
            cell.neighbor_right = grid[row][col + 1] if col < 9 else None
    return grid


def make_new_level_grid():
    """Tablero inicial del nivel nuevo (jugador en (9,5), sin escalera visible).

    Rocas (4,2)/(4,7), huecos (5,1)/(5,8)/(11,1), puerta (10,2), llave (13,4).
    """
    grid = [[None for _ in range(10)] for _ in range(15)]

    def put(row, col, cell_type="terrain"):
        grid[row][col] = Cell((row, col), cell_type)

    for col in range(10):
        put(0, col)
    for col in range(1, 10):
        put(1, col)
    for col in range(2, 8):
        put(2, col)
    for col in range(1, 9):
        put(3, col)
    put(4, 1)
    put(4, 2, "rock")
    put(4, 3)
    put(4, 4, "diamond")
    put(4, 5, "diamond")
    put(4, 6)
    put(4, 7, "rock")
    put(4, 8)
    put(5, 1, "fall")
    put(5, 3)
    put(5, 4)
    put(5, 6)
    put(5, 8, "fall")
    for col in range(1, 9):
        put(6, col)
    for col in range(1, 9):
        put(7, col)
    put(8, 1)
    put(8, 2)
    put(8, 5)
    put(8, 7)
    put(8, 8)
    put(9, 1)
    put(9, 2, "diamond")
    put(9, 4)
    put(9, 5, "player")
    put(9, 7)
    put(9, 8, "diamond")
    put(10, 1)
    put(10, 2, "door")
    put(10, 3)
    put(10, 4)
    put(10, 7, "spike")
    put(10, 8)
    put(11, 1, "fall")
    put(11, 2)
    put(11, 3, "diamond")
    put(11, 4, "diamond")
    put(11, 5, "diamond")
    put(11, 6)
    put(11, 7)
    put(11, 8)
    put(12, 1)
    put(12, 4)
    put(12, 5)
    put(12, 6)
    put(12, 7)
    put(12, 8, "spike")
    put(13, 1, "spike")
    put(13, 2)
    put(13, 3, "diamond")
    put(13, 4, "key")
    put(13, 5, "diamond")
    put(13, 6)
    put(13, 7)
    put(13, 8)

    for row in range(15):
        for col in range(10):
            cell = grid[row][col]
            if cell is None:
                continue
            cell.neighbor_up = grid[row - 1][col] if row > 0 else None
            cell.neighbor_down = grid[row + 1][col] if row < 14 else None
            cell.neighbor_left = grid[row][col - 1] if col > 0 else None
            cell.neighbor_right = grid[row][col + 1] if col < 9 else None
    return grid


class KeyDoorLevelTests(unittest.TestCase):
    def test_key_door_level_fixture_matches_initial_capture(self):
        from smart_agent import SmartAgent
        agent = SmartAgent(make_key_door_level_grid())

        self.assertIsNotNone(agent.game_state)
        self.assertEqual(list(agent.game_state.player_pos), [4, 1])
        rocks = sorted(tuple(c.coordinates) for row in agent.game_state.grid
                       for c in row if c is not None and c.cell_type == "rock")
        falls = sorted(tuple(c.coordinates) for row in agent.game_state.grid
                       for c in row if c is not None and c.cell_type == "fall")
        self.assertEqual(rocks, [(5, 4), (11, 8)])
        self.assertEqual(falls, [(6, 8), (8, 1)])

    def test_full_key_door_level_solves_offline(self):
        from smart_agent import SmartAgent
        agent = SmartAgent(make_key_door_level_grid())
        self.assertIsNotNone(agent.game_state)

        winner = agent.simulate()

        self.assertIsNotNone(winner)
        self.assertTrue(winner.action_history)
        self.assertEqual(winner.action_history[-1].action, "go_ladder")

    def test_mid_state_flow_down_left_then_rock_up(self):
        # Flujo pedido: desde (4,3) con llave, BAJAR a los pinchos de abajo
        # (12,5)/(12,6) en vez de subir a (5,1) y levantar los pinchos del
        # corredor final; luego subir la roca (11,8) hasta (6,8).
        from smart_agent import SmartAgent
        agent = SmartAgent(make_mid_stuck_grid())
        self.assertIsNotNone(agent.game_state)
        self.assertTrue(agent.game_state.player_has_key)

        winner = agent.simulate()

        self.assertIsNotNone(winner)
        self.assertTrue(winner.action_history)
        first = winner.action_history[0]
        self.assertEqual(first.action, "go_spike")
        self.assertIn(tuple(first.coordinates), ((12, 5), (12, 6)))
        # Rumbo abajo (derecha y luego centro, o columna izquierda): jamas
        # subir a (5,1).
        self.assertIn(first.path[0], ("right", "down"))
        self.assertEqual(winner.action_history[-1].action, "go_ladder")
        pushes = [tuple(a.coordinates) for a in winner.action_history
                  if getattr(a, "action", "") == "push_rock"]
        self.assertIn((6, 8), pushes)
        diamonds = [a for a in winner.action_history
                    if getattr(a, "action", "") == "get_diamond"]
        self.assertEqual(len(diamonds), 6)
        doors = [a for a in winner.action_history
                 if getattr(a, "action", "") == "open_door"]
        self.assertEqual(len(doors), 1)

    def test_endgame_ladder_uses_lower_route(self):
        # Flujo final: con todo recogido, a la escalera (3,1) se va por abajo,
        # nunca por arriba hacia la esquina del (5,1) vivo. La ruta jamas pisa
        # (5,1) y solo usa celdas libres (suelo, pincho desactivado, hueco
        # relleno, escalera).
        from smart_agent import SmartAgent
        grid = make_endgame_grid()
        agent = SmartAgent(grid)
        self.assertIsNotNone(agent.game_state)

        action = agent.game_state.get_next_action()

        self.assertEqual(action.action, "go_ladder")
        self.assertEqual(tuple(action.coordinates), (3, 1))
        self.assertIn(action.path[0], ("right", "down"))
        pos = [4, 7]
        visited = [tuple(pos)]
        for step in action.path:
            if step == "up":
                pos[0] -= 1
            elif step == "down":
                pos[0] += 1
            elif step == "left":
                pos[1] -= 1
            elif step == "right":
                pos[1] += 1
            visited.append(tuple(pos))
        self.assertEqual(tuple(pos), (3, 1))
        self.assertNotIn((5, 1), visited)
        for r, c in visited:
            cell = grid[r][c]
            self.assertIsNotNone(cell)
            self.assertNotIn(cell.cell_type, ("spike", "fall", "door",
                                              "metal-door", "rock",
                                              "rock-in-button"))

    def test_endgame_hard_fallback_fixed_flow(self):
        grid = make_endgame_grid()
        grid[4][7].cell_type = "terrain"
        state = GameState(grid, [4, 3], 0)

        action = state.get_next_action()

        self.assertEqual(action.action, "go_ladder")
        self.assertEqual(list(action.coordinates), [3, 1])
        self.assertEqual(list(action.path), ["right", "down", "down", "left",
                                             "down", "down", "down", "left", "left",
                                             "up", "up", "up", "up", "up", "up"])
        pos = [4, 3]
        visited = []
        for step in action.path:
            if step == "up":
                pos[0] -= 1
            elif step == "down":
                pos[0] += 1
            elif step == "left":
                pos[1] -= 1
            elif step == "right":
                pos[1] += 1
            visited.append(tuple(pos))
        self.assertEqual(tuple(pos), (3, 1))
        self.assertIn((5, 1), visited)
        self.assertNotIn((4, 2), visited)

    def test_new_level_hacks_stay_off(self):
        # Ningun hardcode del nivel anterior debe dispararse aqui.
        state = GameState(make_new_level_grid(), [9, 5], 0)

        self.assertIsNone(state._opening_right_move())
        self.assertIsNone(state._endgame_ladder_fallback())
        # Guia Nivel 6: roca izquierda -> (11,1), roca (4,7) vetada.
        self.assertEqual(state._forced_rock_pair_targets(
            [(5, 1), (5, 8), (11, 1)], [(4, 2), (4, 7)]),
            {(4, 2): (11, 1), (4, 7): None})

    def test_new_level_first_action_is_sane(self):
        from smart_agent import SmartAgent
        agent = SmartAgent(make_new_level_grid())
        self.assertIsNotNone(agent.game_state)

        action = agent.game_state.get_next_action()

        self.assertEqual(action.action, "get_key")
        self.assertEqual(tuple(action.coordinates), (13, 4))
        self.assertTrue(action.path)

    def test_keys_pair_with_nearest_door_one_to_one(self):
        grid = [[None for _ in range(10)] for _ in range(2)]
        for c in range(10):
            grid[1][c] = Cell((1, c), "terrain")
        grid[1][0] = Cell((1, 0), "player")
        grid[1][1] = Cell((1, 1), "key")
        grid[1][2] = Cell((1, 2), "door")
        grid[1][7] = Cell((1, 7), "door")
        grid[1][8] = Cell((1, 8), "key")

        state = GameState(grid, [1, 0], 0)

        self.assertEqual(state.assign_keys_to_doors(),
                         [((1, 1), (1, 2)), ((1, 8), (1, 7))])

    def test_assigned_key_preferred_over_nearer_unassigned(self):
        grid = [[None for _ in range(10)] for _ in range(2)]
        for c in range(10):
            grid[1][c] = Cell((1, c), "terrain")
        grid[1][0] = Cell((1, 0), "player")
        grid[1][1] = Cell((1, 1), "key")
        grid[1][8] = Cell((1, 8), "key")
        grid[1][9] = Cell((1, 9), "door")
        for c in range(10):
            cell = grid[1][c]
            cell.neighbor_left = grid[1][c - 1] if c > 0 else None
            cell.neighbor_right = grid[1][c + 1] if c < 9 else None

        state = GameState(grid, [1, 0], 0)

        nearest, _ = state.find_assigned_key()

        self.assertEqual(tuple(nearest.coordinates), (1, 8))

    def test_new_level_left_rock_goes_to_fall(self):
        # Barrera azul: la unica ruta geometrica (4,2)->(11,1) sale del ducto
        # (pasa por (4,3)/(5,3)/(10,1), que ni existe en el juego real), asi
        # que no se planifica ningun fill y la roca jamas se toca.
        state = GameState(make_new_level_grid(), [9, 5], 0)

        pairs = {(tuple(s.rock_start), tuple(s.target_pos))
                 for s in state.get_rock_simulations()}

        self.assertEqual(pairs, set())

    def test_new_level_planner_makes_progress(self):
        # Sin escalera visible no puede terminar, pero debe avanzar sin
        # trabarse: devuelve progreso parcial no vacio en tiempo acotado.
        from smart_agent import SmartAgent
        agent = SmartAgent(make_new_level_grid())
        self.assertIsNotNone(agent.game_state)

        winner = agent.simulate()

        self.assertIsNotNone(winner)
        self.assertTrue(winner.action_history)

    def test_endgame_fallback_only_at_stuck_spot(self):
        grid = make_endgame_grid()
        state = GameState(grid, [4, 7], 0)

        action = state.get_next_action()

        self.assertFalse(list(action.path) == list(GameState.ENDGAME_LADDER_PATH))

    def test_endgame_fallback_needs_flat_spike(self):
        grid = make_endgame_grid()
        grid[4][7].cell_type = "terrain"
        grid[5][1].cell_type = "spike-up"
        grid[5][1].weight = 100000
        grid[5][1].walkable = False
        state = GameState(grid, [4, 3], 0)

        action = state.get_next_action()

        self.assertFalse(list(action.path) == list(GameState.ENDGAME_LADDER_PATH))

    def test_after_left_diamonds_goes_down_never_up_to_spike(self):
        # Tras (7,1)+(6,1) el jugador queda en (6,1): debe BAJAR hacia abajo
        # (pinchos/diamantes de abajo) y jamas subir a (5,1), que levanta los
        # pinchos por donde pasara a las escaleras al final.
        from smart_agent import SmartAgent
        agent = SmartAgent(make_after_left_diamonds_grid())
        self.assertIsNotNone(agent.game_state)

        action = agent.game_state.get_next_action()

        self.assertEqual(action.action, "go_spike")
        self.assertIn(tuple(action.coordinates), ((12, 5), (12, 6)))
        self.assertEqual(action.path[0], "down")

    def _make_opening_level_grid(self):
        grid = [[None for _ in range(10)] for _ in range(15)]
        grid[3][1] = Cell((3, 1), "ladder")
        grid[4][1] = Cell((4, 1), "player")
        grid[4][2] = Cell((4, 2), "spike")
        grid[4][5] = Cell((4, 5), "key")
        grid[5][1] = Cell((5, 1), "spike")
        grid[5][4] = Cell((5, 4), "rock")
        grid[5][8] = Cell((5, 8), "door")
        grid[6][1] = Cell((6, 1), "diamond")
        grid[6][8] = Cell((6, 8), "fall")
        grid[7][1] = Cell((7, 1), "diamond")
        grid[8][1] = Cell((8, 1), "fall")
        grid[11][8] = Cell((11, 8), "rock")
        return grid

    def test_opening_forces_right_never_down(self):
        state = GameState(self._make_opening_level_grid(), [4, 1], 0)

        action = state.get_next_action()

        self.assertEqual(action.action, "go_spike")
        self.assertEqual(list(action.coordinates), [4, 2])
        self.assertEqual(list(action.path), ["right"])

    def test_opening_override_only_at_start(self):
        state = GameState(self._make_opening_level_grid(), [4, 3], 0)

        self.assertIsNone(state._opening_right_move())

    def test_opening_override_ignores_other_levels(self):
        state = GameState(make_level_four_grid(), [3, 2], 0)

        self.assertIsNone(state._opening_right_move())

    def test_forced_pairing_straight_up_right_column(self):
        # Nivel de la llave/puerta: la roca de la columna 8 sube recto a (6,8)
        # y la otra va a (8,1). Sin esto el matching por distancia los cruza.
        grid = [[Cell((r, c), "terrain") for c in range(10)] for r in range(15)]
        grid[4][1] = Cell((4, 1), "player")
        grid[5][4] = Cell((5, 4), "rock")
        grid[11][8] = Cell((11, 8), "rock")
        grid[6][8] = Cell((6, 8), "fall")
        grid[8][1] = Cell((8, 1), "fall")

        state = GameState(grid, [4, 1], 0)

        pairs = {(tuple(s.rock_start), tuple(s.target_pos))
                 for s in state.get_rock_simulations()}

        self.assertTrue(pairs)
        self.assertIn(((11, 8), (6, 8)), pairs)
        self.assertIn(((5, 4), (8, 1)), pairs)
        self.assertNotIn(((5, 4), (6, 8)), pairs)
        self.assertNotIn(((11, 8), (8, 1)), pairs)

    def test_state_hash_distinguishes_rock_positions(self):
        from smart_agent import state_hash_key
        grid = [[Cell((r, c), "terrain") for c in range(3)] for r in range(3)]
        grid[0][0] = Cell((0, 0), "player")
        grid[1][1] = Cell((1, 1), "rock")
        moved = [[Cell((r, c), "terrain") for c in range(3)] for r in range(3)]
        moved[0][0] = Cell((0, 0), "player")
        moved[1][2] = Cell((1, 2), "rock")

        self.assertEqual(
            state_hash_key(grid, [0, 0], False),
            state_hash_key(grid, [0, 0], False))
        self.assertNotEqual(
            state_hash_key(grid, [0, 0], False),
            state_hash_key(moved, [0, 0], False))

    def test_go_spike_clears_nearest_first(self):
        # El camino al pincho lejano no debe pisar el pincho vivo cercano
        # cuando hay rodeo libre: se limpia el mas cercano primero.
        grid = [[None for _ in range(3)] for _ in range(3)]
        for r in range(3):
            for c in range(3):
                grid[r][c] = Cell((r, c), "terrain")
        grid[1][1] = Cell((1, 1), "player")
        grid[1][2] = Cell((1, 2), "spike")
        grid[2][2] = Cell((2, 2), "spike")
        for r in range(3):
            for c in range(3):
                cell = grid[r][c]
                cell.neighbor_up = grid[r - 1][c] if r > 0 else None
                cell.neighbor_down = grid[r + 1][c] if r < 2 else None
                cell.neighbor_left = grid[r][c - 1] if c > 0 else None
                cell.neighbor_right = grid[r][c + 1] if c < 2 else None

        state = GameState(grid, [1, 1], 0)

        action = state.get_next_action()

        self.assertEqual(action.action, "go_spike")
        self.assertEqual(list(action.coordinates), [1, 2])
        self.assertEqual(list(action.path), ["right"])

    def test_dead_corner_shove_without_gain_is_rejected(self):
        # Nivel nuevo: roca en (2,2) con unico empuje hacia (3,2), una esquina
        # sin salida (abajo y derecha son muro) que no abre terreno nuevo.
        # Seb (solo fills) y Valentina (solo planes a hueco) nunca harian ese
        # empuje: el bot debe quedarse quieto y usar otra accion (go_spike).
        grid = [[None for _ in range(5)] for _ in range(5)]
        for row, col in ((0, 0), (0, 1), (0, 2), (1, 2), (3, 2), (3, 1)):
            grid[row][col] = Cell((row, col), "terrain")
        grid[0][0] = Cell((0, 0), "player")
        grid[2][2] = Cell((2, 2), "rock")

        state = GameState(grid, [0, 0], 0)

        self.assertEqual(state.get_rock_simulations(), [])
        self.assertEqual(state.get_shove_simulations(), [])


def make_level2_corridor_grid(post_diamond=False):
    """Corredor de pinchos del Nivel 2 (log en vivo + Imagen 1).

    Jugador (6,7), diamante (9,4) tras pinchos verticales (8,5)/(9,5)/(10,5),
    foso (12,7), sin escalera/llave/puerta/roca. Tras el diamante el jugador
    queda en (9,4) con pinchos ya planos y sin salida visible.
    """
    grid = [[None for _ in range(10)] for _ in range(15)]

    def put(row, col, cell_type="terrain"):
        grid[row][col] = Cell((row, col), cell_type)

    for col in range(1, 9):
        put(0, col)
    for col in range(2, 8):
        put(1, col)
    for col in range(1, 6):
        put(3, col)
    for col in range(1, 6):
        put(4, col)
    put(5, 1, "spike-up")
    put(5, 5)
    put(5, 8)
    put(6, 1)
    put(6, 2)
    put(6, 3)
    put(6, 5)
    put(6, 6)
    put(6, 8)
    put(7, 1)
    put(7, 5)
    put(7, 6)
    put(7, 7)
    put(7, 8)
    put(8, 1)
    put(8, 7)
    put(8, 8)
    put(9, 1)
    put(9, 3)
    put(10, 1)
    put(10, 3)
    put(11, 1)
    put(11, 5)
    put(11, 6)
    put(11, 7)
    put(11, 8)
    for col in range(1, 7):
        put(12, col)
    put(12, 7, "fall")
    put(12, 8)
    put(13, 1)
    put(13, 2)
    put(13, 5)
    put(13, 6)
    put(13, 7)
    put(13, 8)
    if not post_diamond:
        put(6, 7, "player")
        put(8, 5, "spike")
        put(9, 4, "diamond")
        put(9, 5, "spike")
        put(10, 5, "spike")
    else:
        put(9, 4, "player")
        put(8, 5, "spike-up")
        put(9, 5, "spike-up")
        put(10, 5, "spike-up")

    for row in range(15):
        for col in range(10):
            cell = grid[row][col]
            if cell is None:
                continue
            cell.neighbor_up = grid[row - 1][col] if row > 0 else None
            cell.neighbor_down = grid[row + 1][col] if row < 14 else None
            cell.neighbor_left = grid[row][col - 1] if col > 0 else None
            cell.neighbor_right = grid[row][col + 1] if col < 9 else None
    return grid


class Level2CorridorTests(unittest.TestCase):
    def test_signature_detected(self):
        state = GameState(make_level2_corridor_grid(), [6, 7], 0)

        self.assertTrue(state._is_spike_corridor())
        self.assertFalse(state._is_level6())

    def test_initial_plan_reaches_diamond(self):
        # Regresion del atasco en vivo: el parcial 3xspike+diamante daba
        # score -1 y se descartaba -> "Simulacion sin exito" quieto.
        # Ahora go_spike puntua 0 y el parcial vuelve con 4 acciones.
        from smart_agent import SmartAgent
        agent = SmartAgent(make_level2_corridor_grid())
        self.assertIsNotNone(agent.game_state)

        winner = agent.simulate()

        self.assertIsNotNone(winner)
        self.assertTrue(winner.action_history)
        first = winner.action_history[0]
        self.assertEqual(first.action, "go_spike")
        self.assertTrue(first.path)
        diamonds = [a for a in winner.action_history
                    if getattr(a, "action", "") == "get_diamond"]
        self.assertEqual(len(diamonds), 1)
        self.assertEqual(tuple(diamonds[0].coordinates), (9, 4))
        # Sin teletransportes en el parcial.
        anchor = [6, 7]
        for act in winner.action_history:
            name = getattr(act, "action", "")
            if name in ("get_diamond", "get_key", "open_door", "go_spike",
                        "go_ladder", "go_button", "go_explore"):
                self.assertTrue(getattr(act, "path", None))
                pos = list(anchor)
                for step in act.path:
                    if step == "up":
                        pos[0] -= 1
                    elif step == "down":
                        pos[0] += 1
                    elif step == "left":
                        pos[1] -= 1
                    elif step == "right":
                        pos[1] += 1
                self.assertEqual(tuple(pos), tuple(act.coordinates))
                anchor = list(act.coordinates)

    def test_post_diamond_explores_to_fall_edge(self):
        # Tras el diamante no hay salida visible: un paso a la frontera
        # junto al foso (12,6) en vez de quedarse quieto.
        from smart_agent import SmartAgent
        agent = SmartAgent(make_level2_corridor_grid(post_diamond=True))
        self.assertIsNotNone(agent.game_state)

        winner = agent.simulate()

        self.assertIsNotNone(winner)
        self.assertTrue(winner.action_history)
        self.assertEqual(winner.action_history[0].action, "go_explore")
        self.assertEqual(tuple(winner.action_history[0].coordinates), (12, 6))

    def test_metal_door_counts_as_door(self):
        grid = [[Cell((0, c), "terrain") for c in range(3)]]
        grid[0][0] = Cell((0, 0), "player")
        grid[0][2] = Cell((0, 2), "metal-door")
        for c in range(3):
            cell = grid[0][c]
            cell.neighbor_left = grid[0][c - 1] if c > 0 else None
            cell.neighbor_right = grid[0][c + 1] if c < 2 else None

        state = GameState(grid, [0, 0], 0)

        self.assertTrue(state.doorExist)
        self.assertIn((0, 2), state.get_possible_doors())

    def test_button_is_post_loot_only(self):
        grid = [[Cell((0, c), "terrain") for c in range(3)]]
        grid[0][0] = Cell((0, 0), "player")
        grid[0][1] = Cell((0, 1), "diamond")
        grid[0][2] = Cell((0, 2), "push_button")
        for c in range(3):
            cell = grid[0][c]
            cell.neighbor_left = grid[0][c - 1] if c > 0 else None
            cell.neighbor_right = grid[0][c + 1] if c < 2 else None

        state = GameState(grid, [0, 0], 0)
        self.assertTrue(state.buttonExist)
        # Con diamante pendiente no se desvia al boton.
        self.assertEqual(state.get_next_action().action, "get_diamond")

        grid[0][1] = Cell((0, 1), "terrain")
        grid[0][1].neighbor_left = grid[0][0]
        grid[0][1].neighbor_right = grid[0][2]
        grid[0][0].neighbor_right = grid[0][1]
        grid[0][2].neighbor_left = grid[0][1]
        state = GameState(grid, [0, 0], 0)
        action = state.get_next_action()
        self.assertEqual(action.action, "go_button")
        self.assertEqual(tuple(action.coordinates), (0, 2))

    def test_spike_alternative_skipped_when_loot_reachable(self):
        # Nivel spikes (Seb original): con diamante alcanzable, una
        # alternativa go_spike valida por replay se descarta igual.
        grid = [[Cell((0, c), "terrain") for c in range(3)]]
        grid[0][0] = Cell((0, 0), "player")
        grid[0][1] = Cell((0, 1), "diamond")
        grid[0][2] = Cell((0, 2), "spike")
        for c in range(3):
            cell = grid[0][c]
            cell.neighbor_left = grid[0][c - 1] if c > 0 else None
            cell.neighbor_right = grid[0][c + 1] if c < 2 else None

        state = GameState(grid, [0, 0], 0)
        state.alternative_stack.append(
            ("go_spike", (0, 2), ["right", "right"]))

        action = state.get_next_action()

        self.assertEqual(action.action, "get_diamond")
        self.assertEqual(tuple(action.coordinates), (0, 1))

    def test_stale_alternative_path_is_discarded(self):
        # Fantasma (11,5)->(10,7) reutilizado desde (12,8): el replay termina
        # en (11,10), no en (10,7), asi que debe descartarse.
        grid = make_level2_corridor_grid()
        state = GameState(grid, [12, 8], 0)
        state.alternative_stack.append(
            ("go_spike", (10, 7), ["right", "right", "up"]))

        action = state.get_next_action()

        if action.action == "go_spike":
            self.assertNotEqual(
                (tuple(action.coordinates), list(action.path)),
                ((10, 7), ["right", "right", "up"]))


class FiveRockLevelRouteTests(unittest.TestCase):
    def test_detector_matches_level_four_not_other_known_map(self):
        from test_level6_guide import make_new_level_grid

        self.assertTrue(is_five_rock_level(make_level_four_grid()))
        self.assertFalse(is_five_rock_level(make_new_level_grid()))

    @staticmethod
    def _apply_live_path(grid, player, path, has_key=False, allow_bumps=False):
        """Apply the route's one-tile moves, including pushing rocks into pits."""
        pos = tuple(player)
        held_key = bool(has_key)
        deltas = {"up": (-1, 0), "down": (1, 0),
                  "left": (0, -1), "right": (0, 1)}
        for step in path:
            dr, dc = deltas[step]
            nxt = (pos[0] + dr, pos[1] + dc)
            if not (0 <= nxt[0] < len(grid) and 0 <= nxt[1] < len(grid[0])):
                if allow_bumps:
                    continue
                raise AssertionError(f"route went out of bounds at {nxt}")
            cell = grid[nxt[0]][nxt[1]]
            if cell is None:
                if allow_bumps:
                    continue
                raise AssertionError(f"route hit unknown/wall at {nxt}")
            old_cell = grid[pos[0]][pos[1]]
            if old_cell is not None and old_cell.cell_type in (
                    "player", "player-with-key"):
                grid[pos[0]][pos[1]] = Cell(pos, "terrain")
            if cell.cell_type in ("rock", "rock-in-button"):
                dest = (nxt[0] + dr, nxt[1] + dc)
                if not (0 <= dest[0] < len(grid) and 0 <= dest[1] < len(grid[0])):
                    if allow_bumps:
                        continue
                    raise AssertionError(f"rock push out of bounds at {dest}")
                pushed = grid[dest[0]][dest[1]]
                if pushed is None or pushed.cell_type not in (
                        "terrain", "diamond", "fall", "push_button"):
                    if allow_bumps:
                        continue
                    raise AssertionError(f"rock push blocked at {dest}")
                grid[nxt[0]][nxt[1]] = Cell(
                    nxt, "push_button" if cell.cell_type == "rock-in-button"
                    else "terrain")
                grid[dest[0]][dest[1]] = Cell(
                    dest, "rock-in-fall" if pushed.cell_type == "fall"
                    else "rock-in-button" if pushed.cell_type == "push_button"
                    else "rock")
            elif cell.cell_type == "diamond":
                grid[nxt[0]][nxt[1]] = Cell(nxt, "terrain")
            elif cell.cell_type == "key":
                held_key = True
                grid[nxt[0]][nxt[1]] = Cell(nxt, "terrain")
            elif cell.cell_type in ("door", "metal-door"):
                pressed = any(c is not None and c.cell_type == "rock-in-button"
                              for r in grid for c in r)
                if cell.cell_type == "metal-door" and pressed:
                    grid[nxt[0]][nxt[1]] = Cell(nxt, "terrain")
                elif not held_key:
                    if allow_bumps:
                        continue
                    raise AssertionError(f"route hit locked door at {nxt}")
                else:
                    held_key = False
                    grid[nxt[0]][nxt[1]] = Cell(nxt, "terrain")
            elif cell.cell_type == "spike":
                grid[nxt[0]][nxt[1]] = Cell(nxt, "spike-up")
            elif cell.cell_type not in ("terrain", "spike-up", "rock-in-fall",
                                        "push_button", "ladder", "ladder-open"):
                if allow_bumps:
                    continue
                raise AssertionError(f"route entered {cell.cell_type} at {nxt}")
            pos = nxt
        return pos, held_key

    def test_initial_position_follows_exact_groups_with_recapture(self):
        grid = make_level_four_grid()
        pos = (3, 2)
        has_key = False
        route = FiveRockLevelRoute(grid, pos)
        observed_groups = []

        while True:
            action = route.next_action(grid, pos)
            if action is None:
                break
            self.assertEqual(action.action, "level_route")
            observed_groups.append("".join({
                "up": "U", "down": "D", "left": "L", "right": "R"}[d]
                for d in action.path))
            pos, has_key = self._apply_live_path(
                grid, pos, action.path, has_key=has_key)
            route.observe(pos, action, grid)
            self.assertTrue(is_five_rock_level(grid))

        self.assertEqual(tuple(observed_groups), ROUTE_GROUPS)
        self.assertEqual(pos, (12, 6))
        self.assertTrue(route.completed)
        for hole in ((5, 6), (7, 1), (11, 6), (12, 3)):
            self.assertEqual(grid[hole[0]][hole[1]].cell_type, "rock-in-fall")

    def test_non_initial_position_rejoins_nearest_route_waypoint(self):
        grid = make_level_four_grid()
        grid[3][2] = Cell((3, 2), "terrain")
        grid[8][2] = Cell((8, 2), "player")
        route = FiveRockLevelRoute(grid, (8, 2))

        action = route.next_action(grid, (8, 2))

        self.assertIsNotNone(action)
        self.assertEqual(action.action, "level_route_rejoin")
        self.assertEqual(action.path, ["up"])
        self.assertEqual(tuple(action.coordinates), (7, 2))
        route.observe((7, 2), action, grid)

        next_action = route.next_action(grid, (7, 2))
        self.assertEqual(next_action.action, "level_route")
        self.assertEqual(next_action.path, ["right"] * 5)

    def test_zero_movement_retries_same_route_segment(self):
        grid = make_level_four_grid()
        route = FiveRockLevelRoute(grid, (3, 2))

        first = route.next_action(grid, (3, 2))
        route.observe((3, 2), first, grid)
        retry = route.next_action(grid, (3, 2))

        self.assertEqual(first.path, ["right"] * 4)
        self.assertEqual(retry.action, "level_route")
        self.assertEqual(retry.path, ["right"] * 4)
        route.observe((3, 2), retry, grid)
        self.assertTrue(route.unusable)
        self.assertIsNone(route.next_action(grid, (3, 2)))


class Level6CapturedRouteTests(unittest.TestCase):
    @staticmethod
    def _grid():
        from test_level6_guide import make_level6_grid
        return make_level6_grid(player=(3, 5), key1=True)

    def test_signature_matches_level6_initial_not_generic_key_level(self):
        self.assertTrue(is_level6_captured_route(self._grid()))
        self.assertFalse(is_level6_captured_route(make_new_level_grid()))

    def test_route_starts_with_recorded_right_triple_and_is_rigid(self):
        grid = self._grid()
        route = Level6CapturedRoute(grid, (3, 5))

        action = route.next_action(grid, (3, 5))

        self.assertTrue(route.rigid)
        self.assertEqual(action.action, "level_route")
        self.assertEqual(action.path, ["right", "right", "right"])

    def test_full_recorded_route_runs_in_capture_groups(self):
        grid = self._grid()
        position = (3, 5)
        has_key = False
        route = Level6CapturedRoute(grid, position)
        observed = []

        for _ in range(len(LEVEL6_CAPTURE_GROUPS) + 2):
            action = route.next_action(grid, position, has_key=has_key)
            if action is None:
                break
            self.assertEqual(action.action, "level_route")
            observed.append("".join({
                "up": "U", "down": "D", "left": "L", "right": "R"}[d]
                for d in action.path))
            position, has_key = FiveRockLevelRouteTests._apply_live_path(
                grid, position, action.path, has_key=has_key, allow_bumps=True)
            route.observe(position, action, grid)

        self.assertEqual(tuple(observed), LEVEL6_CAPTURE_GROUPS)
        self.assertTrue(route.completed)


class Level7CapturedRouteTests(unittest.TestCase):
    @staticmethod
    def _grid(pit_type="fall"):
        grid = [[None for _ in range(10)] for _ in range(15)]
        for row in range(1, 14):
            for col in range(1, 9):
                grid[row][col] = Cell((row, col), "terrain")
        for pos in ((7, 4), (10, 1), (10, 7)):
            grid[pos[0]][pos[1]] = Cell(pos, pit_type)
        grid[7][7] = Cell((7, 7), "key")
        grid[11][5] = Cell((11, 5), "door")
        grid[4][2] = Cell((4, 2), "player")
        for row in range(15):
            for col in range(10):
                cell = grid[row][col]
                if cell is None:
                    continue
                cell.neighbor_up = grid[row - 1][col] if row > 0 else None
                cell.neighbor_down = grid[row + 1][col] if row < 14 else None
                cell.neighbor_left = grid[row][col - 1] if col > 0 else None
                cell.neighbor_right = grid[row][col + 1] if col < 9 else None
        return grid

    def test_detector_and_first_group(self):
        grid = self._grid()
        self.assertTrue(is_level7_captured_route(grid))
        self.assertFalse(is_level7_captured_route(make_new_level_grid()))
        route = Level7CapturedRoute(grid, (4, 2))
        action = route.next_action(grid, (4, 2))
        self.assertTrue(route.rigid)
        self.assertEqual(action.path, ["right"])

    def test_full_recorded_route_reaches_cage(self):
        grid = self._grid("rock-in-fall")
        position, has_key = (4, 2), False
        route = Level7CapturedRoute(grid, position)
        observed = []
        for _ in range(len(LEVEL7_CAPTURE_GROUPS) + 2):
            action = route.next_action(grid, position, has_key=has_key)
            if action is None:
                break
            observed.append("".join({
                "up": "U", "down": "D", "left": "L", "right": "R"}[d]
                for d in action.path))
            position, has_key = FiveRockLevelRouteTests._apply_live_path(
                grid, position, action.path, has_key=has_key, allow_bumps=True)
            route.observe(position, action, grid)
        self.assertEqual(tuple(observed), LEVEL7_CAPTURE_GROUPS)
        self.assertEqual(position, (13, 5))
        self.assertTrue(route.completed)



class Level8CapturedRouteTests(unittest.TestCase):
    @staticmethod
    def _grid(player=(7, 5)):
        grid = [[None for _ in range(10)] for _ in range(15)]
        for row in range(1, 14):
            for col in range(1, 9):
                grid[row][col] = Cell((row, col), "terrain")
        spec = {(9, 2): "fall", (12, 2): "fall", (7, 2): "push_button",
                (12, 6): "push_button", (7, 4): "rock", (9, 3): "rock",
                (11, 2): "rock", (12, 3): "rock", (8, 7): "metal-door",
                (9, 6): "metal-door", (10, 2): "key", (6, 7): "door",
                (4, 5): "ladder", player: "player"}
        for pos, kind in spec.items():
            grid[pos[0]][pos[1]] = Cell(pos, kind)
        return grid

    def test_detector_accepts_any_player_position_and_rejects_others(self):
        self.assertTrue(is_level8_captured_route(self._grid()))
        self.assertTrue(is_level8_captured_route(self._grid((7, 3))))
        self.assertFalse(is_level8_captured_route(make_new_level_grid()))

    def test_full_route_with_trapdoors_reaches_cage(self):
        grid = self._grid()
        position, has_key = (7, 5), False
        route = Level8CapturedRoute(grid, position)
        observed = []
        for _ in range(len(LEVEL8_CAPTURE_GROUPS) + 2):
            action = route.next_action(grid, position, has_key=has_key)
            if action is None:
                break
            observed.append("".join({
                "up": "U", "down": "D", "left": "L", "right": "R"}[d]
                for d in action.path))
            position, has_key = FiveRockLevelRouteTests._apply_live_path(
                grid, position, action.path, has_key=has_key, allow_bumps=True)
            route.observe(position, action, grid)
        self.assertEqual(tuple(observed), LEVEL8_CAPTURE_GROUPS)
        self.assertEqual(position, (4, 5))

    def test_blind_capture_assumes_group_arrived_and_continues(self):
        from main import inject_route_player
        grid = self._grid()
        position, has_key = (7, 5), False
        route = Level8CapturedRoute(grid, position)
        last = None
        for _ in range(12):  # hasta emitir UUUUUUU (grupo 12)
            action = route.next_action(grid, position, has_key=has_key)
            last = action
            if len(action.path) == 7:
                break
            position, has_key = FiveRockLevelRouteTests._apply_live_path(
                grid, position, action.path, has_key=has_key, allow_bumps=True)
            route.observe(position, action, grid)
        self.assertEqual(len(last.path), 7)
        expected, key = route.blind_expected()
        self.assertEqual(expected, (2, 7))
        self.assertFalse(key)  # la llave se gasta en la puerta (6,7)
        # Jugador oculto bajo el HUD: se inyecta y la ruta avanza.
        FiveRockLevelRouteTests._apply_live_path(
            grid, position, last.path, has_key=has_key, allow_bumps=True)
        grid[2][7] = None
        self.assertTrue(inject_route_player(grid, expected, key))
        route.observe(expected, last, grid)
        nxt = route.next_action(grid, expected, has_key=key)
        self.assertEqual(nxt.path, ["left"] * 5)
        # Siguiente tramo por la fila 2 (HUD): el simulador lo cruza.
        self.assertEqual(route.blind_expected()[0], (2, 2))
        FiveRockLevelRouteTests._apply_live_path(
            grid, expected, nxt.path, has_key=key, allow_bumps=True)
        self.assertEqual(Level8CapturedRoute(grid, (7, 5)).blind_expected()[0],
                         (7, 5))


    def test_off_route_start_rejoins_instead_of_giving_up(self):
        grid = self._grid((7, 6))
        route = Level8CapturedRoute(grid, (7, 6))
        action = route.next_action(grid, (7, 6))
        self.assertIsNotNone(action)
        self.assertFalse(route.unusable)



class Level9CapturedRouteTests(unittest.TestCase):
    @staticmethod
    def _grid(player=(3, 5)):
        grid = [[None for _ in range(10)] for _ in range(15)]
        for row in range(1, 14):
            for col in range(1, 9):
                grid[row][col] = Cell((row, col), "terrain")
        spec = {(5, 1): "push_button", (7, 8): "push_button",
                (12, 5): "push_button", (4, 2): "rock", (6, 4): "rock",
                (12, 2): "rock", (5, 4): "metal-door", (8, 2): "metal-door",
                (11, 7): "metal-door", (13, 8): "ladder", player: "player"}
        for pos, kind in spec.items():
            grid[pos[0]][pos[1]] = Cell(pos, kind)
        return grid

    def test_detector_any_position_and_not_other_levels(self):
        self.assertTrue(is_level9_captured_route(self._grid()))
        self.assertTrue(is_level9_captured_route(self._grid((6, 6))))
        self.assertFalse(is_level9_captured_route(make_new_level_grid()))

    def test_first_group_and_off_route_rejoin(self):
        grid = self._grid()
        route = Level9CapturedRoute(grid, (3, 5))
        self.assertEqual(route.next_action(grid, (3, 5)).path, ["down"])
        off = self._grid((6, 6))
        route = Level9CapturedRoute(off, (6, 6))
        self.assertIsNotNone(route.next_action(off, (6, 6)))
        self.assertFalse(route.unusable)

    def test_first_groups_press_button_and_open_gate(self):
        grid = self._grid()
        position, has_key = (3, 5), False
        route = Level9CapturedRoute(grid, position)
        for _ in range(7):  # D LLL U L D RRR DD
            action = route.next_action(grid, position, has_key=has_key)
            position, has_key = FiveRockLevelRouteTests._apply_live_path(
                grid, position, action.path, has_key=has_key, allow_bumps=True)
            route.observe(position, action, grid)
        # tras RRR el jugador esta en (4,4); DD cruza la reja (5,4) abierta
        self.assertEqual(position, (6, 4))
        self.assertEqual(grid[5][1].cell_type, "rock-in-button")



class Level10CapturedRouteTests(unittest.TestCase):
    @staticmethod
    def _grid(player=(6, 5)):
        grid = [[None for _ in range(10)] for _ in range(15)]
        for row in range(1, 14):
            for col in range(1, 9):
                grid[row][col] = Cell((row, col), "terrain")
        for pos, kind in {(8, 2): "fall", (8, 7): "fall", (5, 4): "ladder",
                          player: "player"}.items():
            grid[pos[0]][pos[1]] = Cell(pos, kind)
        return grid

    def test_detectors(self):
        self.assertTrue(is_level10_captured_route(self._grid()))
        self.assertFalse(is_level10_captured_route(make_new_level_grid()))
        # Nivel 9 sin escalera visible: firma por trampillas
        grid = Level9CapturedRouteTests._grid()
        grid[13][8] = Cell((13, 8), "terrain")
        self.assertTrue(is_level9_captured_route(grid))

    def test_first_group_and_rejoin(self):
        grid = self._grid()
        self.assertEqual(Level10CapturedRoute(grid, (6, 5)).next_action(
            grid, (6, 5)).path, ["down"] * 4)
        off = self._grid((3, 3))
        route = Level10CapturedRoute(off, (3, 3))
        self.assertIsNotNone(route.next_action(off, (3, 3)))



class Level11CapturedRouteTests(unittest.TestCase):
    def test_detector_and_first_group(self):
        grid = Level10CapturedRouteTests._grid((4, 2))
        for pos in ((8, 2), (8, 7)):
            grid[pos[0]][pos[1]] = Cell(pos, "terrain")
        for pos in ((5, 7), (9, 5), (12, 1)):
            grid[pos[0]][pos[1]] = Cell(pos, "fall")
        self.assertTrue(is_level11_captured_route(grid))
        self.assertFalse(is_level11_captured_route(make_new_level_grid()))
        route = Level11CapturedRoute(grid, (4, 2))
        self.assertEqual(route.next_action(grid, (4, 2)).path, ["up"])



class Level12CapturedRouteTests(unittest.TestCase):
    def test_signature_needs_door_and_terrain_pattern(self):
        grid = Level10CapturedRouteTests._grid((3, 3))
        grid[5][3] = Cell((5, 3), "door")
        self.assertTrue(is_level12_captured_route(grid))
        route = Level12CapturedRoute(grid, (3, 3))
        self.assertEqual(route.next_action(grid, (3, 3)).path, ["left"])
        # sin patron de terreno (mapa casi vacio) no es el nivel
        empty = [[None] * 10 for _ in range(15)]
        empty[3][3] = Cell((3, 3), "player")
        empty[5][3] = Cell((5, 3), "door")
        self.assertFalse(is_level12_captured_route(empty))
        self.assertFalse(is_level12_captured_route(make_new_level_grid()))



class Level13CapturedRouteTests(unittest.TestCase):
    def test_signature_two_doors_and_first_group(self):
        grid = Level10CapturedRouteTests._grid((12, 4))
        for pos in ((8, 2), (8, 7)):
            grid[pos[0]][pos[1]] = Cell(pos, "terrain")
        for pos in ((4, 6), (11, 1)):
            grid[pos[0]][pos[1]] = Cell(pos, "door")
        self.assertTrue(is_level13_captured_route(grid))
        self.assertFalse(is_level13_captured_route(make_new_level_grid()))
        route = Level13CapturedRoute(grid, (12, 4))
        self.assertEqual(route.next_action(grid, (12, 4)).path, ["left"])



class Level14CapturedRouteTests(unittest.TestCase):
    def test_signature_door_buttons_and_first_group(self):
        grid = Level10CapturedRouteTests._grid((13, 4))
        grid[10][2] = Cell((10, 2), "door")
        grid[11][1] = Cell((11, 1), "push_button")
        grid[11][4] = Cell((11, 4), "push_button")
        self.assertTrue(is_level14_captured_route(grid))
        self.assertFalse(is_level14_captured_route(make_new_level_grid()))
        route = Level14CapturedRoute(grid, (13, 4))
        self.assertEqual(route.next_action(grid, (13, 4)).path, ["up"])


if __name__ == "__main__":
    unittest.main()
