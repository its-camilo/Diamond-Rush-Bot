"""Tests del Nivel 6 segun la guia de Google AI Studio.

Fixture = make_new_level_grid() con el jugador en la posicion inicial real
(3,5) y la Llave 1 en la esquina superior derecha (4,8).
"""
import asyncio
import unittest

from cell import Cell
from game_action import GameAction
from game_state import GameState
from test_rock_simulation import make_new_level_grid


def rewire(grid):
    rows = len(grid)
    cols = len(grid[0])
    for r in range(rows):
        for c in range(cols):
            cell = grid[r][c]
            if cell is None:
                continue
            cell.neighbor_up = grid[r - 1][c] if r > 0 else None
            cell.neighbor_down = grid[r + 1][c] if r < rows - 1 else None
            cell.neighbor_left = grid[r][c - 1] if c > 0 else None
            cell.neighbor_right = grid[r][c + 1] if c < cols - 1 else None
    return grid


def make_ghost_grid():
    """Mapa ralo fiel al log en vivo: puerta izq ya abierta, jugador en
    (10,2), Llave 1 consumida, roca sin poner. La Llave 2 (13,4) queda tras
    tierra sin cavar: sin puente de roca es inalcanzable (A* inf)."""
    grid = make_new_level_grid()
    grid[9][5].cell_type = "terrain"  # quita el player del fixture
    grid[10][2].cell_type = "player"
    grid[4][8].cell_type = "terrain"  # Llave 1 ya usada
    for r, c in [(10, 3), (10, 4), (12, 4), (12, 5), (12, 6), (12, 7),
                 (9, 3), (9, 4), (8, 3), (8, 4), (11, 4)]:
        grid[r][c] = None
    return rewire(grid)


def make_level6_grid(player=(3, 5), key1=True):
    grid = make_new_level_grid()
    grid[9][5].cell_type = "terrain"
    grid[player[0]][player[1]].cell_type = "player"
    if key1:
        grid[4][8].cell_type = "key"
    return grid


def state_for(grid, player, has_key=False):
    return GameState(grid, list(player), 0, player_has_key=has_key)


def types(grid, kind):
    return sorted((r, c) for r, row in enumerate(grid) for c, cell in enumerate(row)
                  if cell is not None and cell.cell_type == kind)


class Level6FixtureTests(unittest.TestCase):
    def test_fixture_matches_guide(self):
        grid = make_level6_grid()
        self.assertEqual(types(grid, "player"), [(3, 5)])
        self.assertEqual(types(grid, "key"), [(4, 8), (13, 4)])
        self.assertEqual(types(grid, "rock"), [(4, 2), (4, 7)])
        self.assertEqual(types(grid, "door"), [(10, 2)])
        self.assertIn((11, 1), types(grid, "fall"))

    def test_signature_detected(self):
        self.assertTrue(state_for(make_level6_grid(), (3, 5))._is_level6())

    def test_other_levels_not_level6(self):
        from test_rock_simulation import make_key_door_level_grid
        grid = make_key_door_level_grid()
        self.assertFalse(state_for(grid, (4, 1))._is_level6())


class Level6RuleTests(unittest.TestCase):
    def test_key_pairs_follow_guide(self):
        state = state_for(make_level6_grid(), (3, 5))
        # Puerta izquierda cerrada: solo la llave de arriba cuenta.
        self.assertEqual(state.assign_keys_to_doors(), [((4, 8), (10, 2))])

    def test_phase1_takes_top_key_not_bottom(self):
        state = state_for(make_level6_grid(), (3, 5))
        key, path = state.find_assigned_key()
        self.assertIsNotNone(key)
        self.assertEqual(tuple(key.coordinates), (4, 8))

    def test_bottom_key_is_fallback_when_top_key_missing(self):
        # Sin Llave 1 visible, la inferior es la unica forma de abrir (10,2).
        grid = make_level6_grid(key1=False)
        state = state_for(grid, (3, 5))
        key, _ = state.find_assigned_key()
        self.assertEqual(tuple(key.coordinates), (13, 4))

    def test_right_rock_never_planned(self):
        state = state_for(make_level6_grid(), (3, 5))
        for sim in state.get_rock_simulations():
            self.assertNotEqual(tuple(sim.rock_start), (4, 7))
            self.assertEqual(tuple(sim.target_pos), (11, 1))
        for sim in state.get_shove_simulations():
            self.assertNotEqual(tuple(sim.rock_start), (4, 7))

    def test_forced_pairing_left_rock_to_bottom_hole(self):
        state = state_for(make_level6_grid(), (3, 5))
        forced = state._forced_rock_pair_targets(
            [(5, 1), (5, 8), (11, 1)], [(4, 2), (4, 7)])
        self.assertEqual(forced, {(4, 2): (11, 1), (4, 7): None})

    def test_door_order_left_first(self):
        grid = make_level6_grid(key1=False)
        grid[8][5].cell_type = "door"
        state = state_for(grid, (3, 5), has_key=True)
        state.actions = ["open_door"]
        action = state.get_next_action()
        if action.action == "open_door":
            self.assertEqual(tuple(action.coordinates), (10, 2))

    def test_after_left_door_open_bottom_key_waits_for_bridge(self):
        # Puerta abierta pero puente pendiente: la llave inferior espera (la
        # roca va al foso ANTES de bajar). Tras el puente, se permite.
        grid = make_level6_grid(key1=False)
        grid[10][2].cell_type = "terrain"
        state = state_for(grid, (3, 5))
        key, _ = state.find_assigned_key()
        self.assertIsNone(key)
        grid[11][1].cell_type = "rock-in-fall"
        state = state_for(grid, (3, 5))
        key, _ = state.find_assigned_key()
        self.assertIsNotNone(key)
        self.assertEqual(tuple(key.coordinates), (13, 4))


class Level6PhaseTests(unittest.TestCase):
    def test_phase_flow_offline(self):
        from smart_agent import SmartAgent
        agent = SmartAgent(make_level6_grid())
        self.assertIsNotNone(agent.game_state)
        winner = agent.simulate()
        self.assertIsNotNone(winner)
        history = winner.action_history
        self.assertTrue(history)
        names = [a.action for a in history]
        keys = [tuple(a.coordinates) for a in history if a.action == "get_key"]
        doors = [tuple(a.coordinates) for a in history if a.action == "open_door"]
        pushes = [a for a in history if a.action == "push_rock"]
        # Fase 1: la primera llave es la de arriba.
        self.assertTrue(keys)
        self.assertEqual(keys[0], (4, 8))
        # Fase 2: la primera puerta es la izquierda.
        self.assertTrue(doors)
        self.assertEqual(doors[0], (10, 2))
        # Fase 3: la roca derecha queda en su sitio; la izquierda rellena (11,1).
        self.assertEqual(winner.grid[4][7].cell_type, "rock")
        if pushes:
            self.assertIn((11, 1), [tuple(p.coordinates) for p in pushes])
        # Llave inferior solo tras abrir la puerta izquierda.
        if (13, 4) in keys:
            self.assertIn("open_door", names[:names.index("get_key", names.index("get_key") + 1)])


class GhostKeyTests(unittest.TestCase):
    """Correccion 1: jamas teletransportar a una llave inalcanzable.

    Escenario del log en vivo: puerta izquierda abierta, jugador en (10,2),
    Llave 2 en (13,4) tras tierra sin cavar. El planner viejo devolvia
    get_key camino [] y la marcaba como recogida sin moverse.
    """

    def test_unreachable_key_returns_no_target(self):
        state = state_for(make_ghost_grid(), (10, 2))
        key, path = state.find_assigned_key()
        self.assertIsNone(key)
        self.assertIsNone(path)

    def test_planner_prefers_bridge_over_ghost(self):
        state = state_for(make_ghost_grid(), (10, 2))
        action = state.get_next_action()
        self.assertNotEqual(
            (getattr(action, "action", ""), list(getattr(action, "path", None) or [])),
            ("get_key", []))
        if getattr(action, "action", "") == "get_key":
            self.assertTrue(action.path)
            self.assertNotEqual(tuple(action.coordinates), (13, 4))

    def test_simulate_never_teleports(self):
        from smart_agent import SmartAgent
        agent = SmartAgent(make_ghost_grid())
        self.assertIsNotNone(agent.game_state)
        winner = agent.simulate()
        self.assertIsNotNone(winner)
        anchor = [10, 2]
        for act in winner.action_history:
            name = getattr(act, "action", "")
            if name in ("get_key", "get_diamond", "open_door", "go_spike", "go_ladder"):
                self.assertTrue(getattr(act, "path", None),
                                f"teletransporte a {act.coordinates}")
                if anchor is not None:
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
            elif name == "push_rock":
                self.assertTrue(getattr(act, "path", None) or getattr(act, "directions", None))
                anchor = None  # el jugador queda junto a la roca: ancla desconocida

    def test_executor_refuses_empty_path(self):
        from keyboard_simulator import KeyboardSimulator
        grid = make_level6_grid()
        gs = state_for(grid, (3, 5))
        gs.action_history = [GameAction("get_key", coordinates=[13, 4], path=[])]
        sim = KeyboardSimulator(gs)
        done = asyncio.run(sim.execute_first_action())
        self.assertIsNone(done)

    def test_is_teleport_helper(self):
        from smart_agent import _is_teleport
        self.assertTrue(_is_teleport(GameAction("get_key", [13, 4], path=[]), [10, 2]))
        self.assertFalse(_is_teleport(GameAction("get_key", [13, 4], path=["down"]), [10, 2]))
        self.assertFalse(_is_teleport(GameAction("get_key", [10, 2], path=[]), [10, 2]))


class KeyPersistenceTests(unittest.TestCase):
    """Correccion 2: sin desplazamiento real no hay llave."""

    def test_resolve_held_key(self):
        from main import resolve_held_key
        # El HUD manda.
        self.assertTrue(resolve_held_key(False, True, None, False))
        # Llave con camino y movimiento real: se conserva aunque el sprite falle.
        acted = GameAction("get_key", [4, 8], path=["right"])
        self.assertTrue(resolve_held_key(True, False, acted, True))
        # Camino vacio = fantasma: jamas persistir.
        ghost = GameAction("get_key", [13, 4], path=[])
        self.assertFalse(resolve_held_key(True, False, ghost, False))
        self.assertFalse(resolve_held_key(False, False, ghost, False))
        # Choque contra puerta sin moverse: sin llave.
        door = GameAction("open_door", [8, 5], path=["down"])
        self.assertFalse(resolve_held_key(True, False, door, False))
        # Puerta abierta de verdad: llave consumida.
        self.assertFalse(resolve_held_key(True, False, door, True))
        # Cruzando con llave en mano: se conserva.
        dia = GameAction("get_diamond", [4, 4], path=["left"])
        self.assertTrue(resolve_held_key(True, False, dia, True))


class StuckDetectorTests(unittest.TestCase):
    """Correccion 3: mismo sitio tras actuar = choque, peso infinito."""

    def test_detect_stuck(self):
        from main import detect_stuck
        acted = GameAction("open_door", [8, 5], path=["down"])
        self.assertTrue(detect_stuck([7, 5], [7, 5], acted))
        self.assertFalse(detect_stuck([7, 5], [8, 5], acted))
        self.assertFalse(detect_stuck([7, 5], [7, 5], None))
        # Camino vacio es fallo del planner, no atasco del actuador.
        ghost = GameAction("get_key", [13, 4], path=[])
        self.assertFalse(detect_stuck([10, 2], [10, 2], ghost))

    def test_failed_target_skipped(self):
        # Vetada la unica llave valida por orden estricto, no hay llave: el
        # planner debe hacer otra cosa, jamas la llave inferior (13,4).
        state = state_for(make_level6_grid(), (3, 5))
        state.failed_targets = {("get_key", (4, 8))}
        key, path = state.find_assigned_key()
        self.assertIsNone(key)
        self.assertIsNone(path)
        action = state.get_next_action()
        self.assertNotEqual(getattr(action, "action", ""), "get_key")


class BridgeModelTests(unittest.TestCase):
    """Correccion 4 (Sokoban): roca + foso = terreno transitable."""

    def test_rock_into_fall_becomes_floor(self):
        from rock_simulation import RockSimulation
        grid = make_ghost_grid()
        sim = RockSimulation(grid=grid, player_pos=[10, 2], rock_pos=(4, 2),
                             target_pos=(11, 1), blocked=set())
        self.assertTrue(sim.simulate())
        cell = sim.grid[11][1]
        self.assertEqual(cell.cell_type, "rock-in-fall")
        self.assertTrue(cell.walkable)

    def test_fall_blocks_before_bridge_only(self):
        grid = make_ghost_grid()
        before = state_for(grid, (11, 2))
        blocked = before._astar_path([11, 2], [12, 1])
        blocked.search()
        self.assertEqual(blocked.total_weight, float("inf"))
        from rock_simulation import RockSimulation
        sim = RockSimulation(grid=grid, player_pos=[10, 2], rock_pos=(4, 2),
                             target_pos=(11, 1), blocked=set())
        self.assertTrue(sim.simulate())
        after = GameState(sim.grid, list(sim.player_pos), 0)
        opened = after._astar_path(list(sim.player_pos), [12, 1])
        opened.search()
        self.assertTrue(after._astar_reachable(list(sim.player_pos), [12, 1], opened))


class ExitGateTests(unittest.TestCase):
    """Anti-softlock: ningun parcial puede terminar sin retorno a la salida."""

    def make_end_state(self):
        grid = make_level6_grid()
        grid[9][5].cell_type = "terrain"
        grid[9][4].cell_type = "ladder-open"
        grid[8][5].cell_type = "door"
        grid[4][8].cell_type = "terrain"
        grid[4][2].cell_type = "terrain"
        grid[4][1].cell_type = "rock"
        return grid

    def test_exit_cells_found(self):
        state = state_for(self.make_end_state(), (13, 4), has_key=True)
        self.assertEqual(state.exit_cells(), [(9, 4)])

    def test_exit_reachable_with_key_from_bottom(self):
        # La corrida ganadora (abajo con llave2) siempre conserva retorno:
        # el gate no debe bloquearla.
        state = state_for(self.make_end_state(), (13, 4), has_key=True)
        self.assertTrue(state.exit_reachable_from([13, 4]))

    def test_exit_unreachable_when_walled_in(self):
        grid = self.make_end_state()
        for r, c in [(12, 4), (13, 3), (13, 5)]:
            grid[r][c] = None
        rewire(grid)
        state = state_for(grid, (13, 4), has_key=True)
        self.assertFalse(state.exit_reachable_from([13, 4]))

    def test_no_exit_means_accept(self):
        state = state_for(make_level6_grid(), (3, 5))
        self.assertEqual(state.exit_cells(), [])
        self.assertTrue(state.exit_reachable_from([3, 5]))


class BlueBarrierTests(unittest.TestCase):
    """Barrera azul del usuario: la roca solo puede ocupar el ducto izquierdo.

    La ruta geometrica del sim salia del ducto por celdas que ni existen en
    el juego real ((10,1) es None en vivo), y el shove a (4,1) varaba la roca
    para siempre. Con la barrera, el puente no se intenta y la roca no se toca.
    """

    def test_corridor_holds_start_target_and_detour(self):
        from game_state import GameState as _GS
        for inside in ((4, 2), (4, 3), (5, 3), (6, 3), (7, 3), (7, 2),
                       (9, 2), (10, 2), (11, 2), (11, 1)):
            self.assertIn(inside, _GS.LEVEL6_ROCK_CORRIDOR)
        for outside in ((4, 4), (5, 4), (7, 4), (10, 1), (4, 7), (11, 3)):
            self.assertNotIn(outside, _GS.LEVEL6_ROCK_CORRIDOR)

    def test_rock_untouched_from_start(self):
        # Puerta cerrada: el fill aun no es geometricamente posible y en este
        # nivel no hay shoves. Orden natural: llave1 -> puerta -> roca.
        state = state_for(make_level6_grid(), (3, 5))
        self.assertTrue(state._is_level6())
        self.assertEqual(state.get_rock_simulations(), [])
        self.assertEqual(state.get_shove_simulations(), [])

    def test_post_door_fill_routes_inside_corridor(self):
        from game_state import GameState as _GS
        grid = make_level6_grid()
        grid[9][5].cell_type = "terrain"
        grid[10][2].cell_type = "terrain"
        grid[4][8].cell_type = "terrain"
        state = state_for(grid, (8, 2))
        sims = state.get_rock_simulations()
        self.assertEqual([(tuple(s.rock_start), tuple(s.target_pos)) for s in sims],
                         [((4, 2), (11, 1))])
        blue = set(_GS.LEVEL6_ROCK_CORRIDOR)
        sim = sims[0]
        px, py = 8, 2
        rx, ry = (4, 2)
        traj = [(rx, ry)]
        for m in sim.directions:
            dx, dy = {"up": (-1, 0), "down": (1, 0),
                      "left": (0, -1), "right": (0, 1)}[m]
            nx, ny = px + dx, py + dy
            if (nx, ny) == (rx, ry):
                rx, ry = rx + dx, ry + dy
                px, py = nx, ny
                traj.append((rx, ry))
            else:
                px, py = nx, ny
        self.assertEqual((rx, ry), (11, 1))
        self.assertEqual([c for c in traj if c not in blue], [])

    def test_rock_before_going_down(self):
        # Puerta abierta, jugador arriba: ni llave2 ni diamantes de abajo;
        # lo primero es el puente (la roca sigue en su sitio).
        grid = make_level6_grid()
        grid[9][5].cell_type = "terrain"
        grid[10][2].cell_type = "terrain"
        grid[4][8].cell_type = "terrain"
        for r, c in [(4, 4), (4, 5), (9, 2), (9, 5), (9, 8)]:
            grid[r][c].cell_type = "terrain"
        state = state_for(grid, (8, 2))
        self.assertTrue(state._level6_bridge_pending())
        key, _ = state.find_assigned_key()
        self.assertIsNone(key)
        dia, _ = state.find_nearest_diamond()
        self.assertIsNone(dia)
        action = state.get_next_action()
        self.assertEqual(action.action, "push_rock")
        self.assertEqual(tuple(action.target_pos), (11, 1))

    def test_stranded_rock_has_no_future(self):
        # Roca ya varada en (4,1): ningun fill ni shove la mueve; el nivel
        # sigue jugable sin puente (ruta derecha, verificada en vivo: 10/8).
        grid = make_level6_grid()
        grid[4][2].cell_type = "terrain"
        grid[4][1].cell_type = "rock"
        state = state_for(grid, (4, 2))
        self.assertEqual(state.get_rock_simulations(), [])
        for sim in state.get_shove_simulations():
            self.assertNotEqual(tuple(sim.rock_start), (4, 1))

    def test_full_run_only_pushes_inside_corridor(self):
        from game_state import GameState as _GS
        from smart_agent import SmartAgent
        blue = set(_GS.LEVEL6_ROCK_CORRIDOR) | {(4, 7)}
        agent = SmartAgent(make_level6_grid())
        winner = agent.simulate()
        self.assertIsNotNone(winner)
        for act in winner.action_history:
            if getattr(act, "action", "") == "push_rock":
                self.assertIn(tuple(act.coordinates), blue)
        cells = sorted(tuple(c.coordinates) for row in winner.grid for c in row
                       if c is not None and c.cell_type in ("rock", "rock-in-fall"))
        self.assertTrue(cells)
        self.assertEqual([c for c in cells if c not in blue], [])
        self.assertEqual(winner.grid[4][7].cell_type, "rock")

    def _pocket_state(self):
        grid = [[None for _ in range(6)] for _ in range(4)]
        for r in range(4):
            for c in range(6):
                grid[r][c] = Cell((r, c), "terrain")
        grid[0][0] = None
        grid[0][2] = None
        grid[1][1].cell_type = "rock"
        grid[1][3].cell_type = "fall"
        for r in range(4):
            for c in range(6):
                cell = grid[r][c]
                if cell is None:
                    continue
                cell.neighbor_up = grid[r - 1][c] if r > 0 else None
                cell.neighbor_down = grid[r + 1][c] if r < 3 else None
                cell.neighbor_left = grid[r][c - 1] if c > 0 else None
                cell.neighbor_right = grid[r][c + 1] if c < 5 else None
        return grid

    def test_orphans_fill_detects_dead_pocket(self):
        from rock_simulation import RockSimulation as _RS
        grid = self._pocket_state()
        state = GameState(grid, [2, 1], 0)
        # Tras meterla en (0,1), la roca no sale ni rellena nada.
        end = [row[:] for row in grid]
        end[1][1] = Cell((1, 1), "terrain")
        end[0][1] = Cell((0, 1), "rock")
        sim = _RS(grid=grid, player_pos=[2, 1], rock_pos=(1, 1),
                  target_pos=(0, 1))
        sim.grid = end
        sim.player_pos = [1, 1]
        self.assertTrue(state._orphans_fill((1, 1), (0, 1), sim, set(), [(1, 3)]))
        # Control: empujon hacia el hueco conserva el fill.
        end2 = [row[:] for row in grid]
        end2[1][1] = Cell((1, 1), "terrain")
        end2[1][2] = Cell((1, 2), "rock")
        sim2 = _RS(grid=grid, player_pos=[2, 1], rock_pos=(1, 1),
                   target_pos=(1, 2))
        sim2.grid = end2
        sim2.player_pos = [1, 1]
        self.assertFalse(state._orphans_fill((1, 1), (1, 2), sim2, set(), [(1, 3)]))

    def test_orphan_shove_rejected(self):
        # Bolsillo sin salida: el shove mete la roca donde ningun fill futuro
        # la alcanza, aunque antes si tenia ruta. Se rechaza aunque abra suelo.
        grid = [[None for _ in range(6)] for _ in range(4)]
        for r in range(4):
            for c in range(6):
                grid[r][c] = Cell((r, c), "terrain")
        grid[0][0] = None
        grid[0][2] = None
        grid[1][1].cell_type = "rock"
        grid[1][3].cell_type = "fall"
        state = GameState(grid, [2, 1], 0)
        targets = [(1, 3)]
        self.assertTrue(
            __import__("rock_simulation").RockSimulation.can_reach_target_static(
                grid, (1, 1), (1, 3), set()))
        self.assertEqual(state.get_shove_simulations(), [])


class PlayerRescueTests(unittest.TestCase):
    """El jugador parado sobre llave/diamante no debe desaparecer."""

    def test_should_rescue_matrix(self):
        from diamond_rush_vision import DiamondRushVision as V
        for cur in ("key", "diamond", "terrain", None):
            self.assertTrue(V.should_rescue_player(cur, 0.75), cur)
            self.assertTrue(V.should_rescue_player(cur, 0.60), cur)
            self.assertFalse(V.should_rescue_player(cur, 0.59), cur)
        for cur in ("player", "player-with-key", "rock", "door", "metal-door",
                    "fall", "spike", "spike-up", "ladder", "ladder-open",
                    "rock-in-fall", "rock-in-button"):
            self.assertFalse(V.should_rescue_player(cur, 0.99), cur)

    def test_agent_accepts_rescued_types(self):
        from smart_agent import SmartAgent
        grid = make_level6_grid()
        grid[3][5].cell_type = "player-with-key"
        agent = SmartAgent(grid)
        self.assertIsNotNone(agent.game_state)
        self.assertTrue(agent.game_state.player_has_key)


class ScreenshotFlowTests(unittest.TestCase):
    """Flujo de las capturas en vivo: llave1 -> puerta izq -> roca al hueco
    (11,1) -> abajo -> llave2 -> puerta central -> jaula (9,4)."""

    def make_mid_bridge_state(self):
        # Imagen 7 del log: puente construido, jugador en (11,2), 3/8.
        grid = make_level6_grid()
        grid[9][5].cell_type = "terrain"
        grid[11][2].cell_type = "player"
        grid[4][2].cell_type = "terrain"
        grid[11][1].cell_type = "rock-in-fall"
        grid[4][8].cell_type = "terrain"
        grid[10][2].cell_type = "terrain"
        grid[4][4].cell_type = "terrain"
        grid[4][5].cell_type = "terrain"
        grid[9][2].cell_type = "terrain"
        return grid

    def test_bridge_mid_state_progresses(self):
        from smart_agent import SmartAgent
        agent = SmartAgent(self.make_mid_bridge_state())
        self.assertIsNotNone(agent.game_state)
        winner = agent.simulate()
        self.assertIsNotNone(winner)
        self.assertTrue(winner.action_history)
        # La roca derecha jamas se toca en ningun plan.
        for act in winner.action_history:
            if getattr(act, "action", "") == "push_rock":
                self.assertNotEqual(tuple(act.rock_start), (4, 7))
        self.assertEqual(winner.grid[4][7].cell_type, "rock")

    def test_finale_solves_to_ladder(self):
        # Final del log: abajo con llave2, jaula abierta, puerta central.
        from smart_agent import SmartAgent
        grid = make_level6_grid()
        grid[9][5].cell_type = "diamond"
        grid[9][4].cell_type = "ladder-open"
        grid[8][5].cell_type = "door"
        grid[4][8].cell_type = "terrain"
        grid[13][4].cell_type = "player-with-key"
        grid[13][5].cell_type = "terrain"
        # Calco del grid real del rescate: roca empujada a (4,1), puerta
        # izquierda abierta, spike (12,8) limpio, diamantes (4,4)/(4,5) hechos.
        grid[4][2].cell_type = "terrain"
        grid[4][1].cell_type = "rock"
        grid[10][2].cell_type = "terrain"
        grid[12][8].cell_type = "terrain"
        grid[4][4].cell_type = "terrain"
        grid[4][5].cell_type = "terrain"
        agent = SmartAgent(grid)
        self.assertIsNotNone(agent.game_state)
        self.assertTrue(agent.game_state.player_has_key)
        winner = agent.simulate()
        self.assertIsNotNone(winner)
        self.assertTrue(winner.action_history)
        first = winner.action_history[0]
        self.assertEqual(first.action, "open_door")
        self.assertEqual(tuple(first.coordinates), (8, 5))
        last = winner.action_history[-1]
        self.assertEqual(last.action, "go_ladder")
        self.assertEqual(tuple(last.coordinates), (9, 4))
        for act in winner.action_history:
            if getattr(act, "action", "") in ("get_key", "get_diamond", "open_door",
                                              "go_spike", "go_ladder"):
                self.assertTrue(getattr(act, "path", None))


class LastResortTests(unittest.TestCase):
    """Anti-paralisis: si todo lo demas falla o esta vetado, mejor un pincho
    con camino real que quedarse quieto para siempre (caso (9,8) en vivo)."""

    def _bare_state(self):
        grid = make_level6_grid()
        for r in range(15):
            for c in range(10):
                cell = grid[r][c]
                if cell is not None and cell.cell_type in ("key", "diamond"):
                    cell.cell_type = "terrain"
        grid[9][8].cell_type = "player"
        return state_for(grid, (9, 8))

    def test_spike_fallback_breaks_paralysis(self):
        state = self._bare_state()
        self.assertTrue(state._level6_upstream())
        action = state.get_next_action()
        self.assertEqual(action.action, "go_spike")
        self.assertTrue(action.path)

    def test_fallback_respects_failed_veto(self):
        # Cada veto descarta un pincho; al vetarlos todos vuelve el None.
        vetoed = set()
        seen = set()
        for _ in range(10):
            state = self._bare_state()
            state.failed_targets = set(vetoed)
            action = state.get_next_action()
            if action.action == "None":
                break
            self.assertEqual(action.action, "go_spike")
            coords = tuple(action.coordinates)
            self.assertNotIn(coords, seen)
            seen.add(coords)
            vetoed.add(("go_spike", coords))
        else:
            self.fail("el veto nunca agota los pinchos")
        self.assertEqual(action.action, "None")


if __name__ == "__main__":
    unittest.main()
