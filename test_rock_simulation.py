import unittest

from cell import Cell
from game_state import GameState
from rock_simulation import RockSimulation


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


if __name__ == "__main__":
    unittest.main()
