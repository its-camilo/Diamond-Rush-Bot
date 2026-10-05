"""Tests de los helpers del loop principal: foco, rachas y veto.

El log en vivo mostro dos ejecuciones de 20 pasos con cero movimiento
(open_door [8,5] desde (13,5)): los inputs caian fuera del juego por foco
perdido. El click de foco + el veto solo-tras-repeticion lo cubren.
"""
import unittest

from game_action import GameAction
from record_route import format_sequence
from main import (DEBUG_SHOW_IMAGE, detect_stuck, focus_center,
                  register_repeat, resolve_held_key)


class DebugModeTests(unittest.TestCase):
    def test_debug_window_off_by_default(self):
        # Juego autónomo por defecto; para supervisar: DIAMOND_DEBUG=1.
        self.assertFalse(DEBUG_SHOW_IMAGE)


class FocusTests(unittest.TestCase):
    def test_center_of_game_rectangle(self):
        self.assertEqual(focus_center((705, 101, 1266, 942)), (985, 521))

    def test_invalid_rect_is_none(self):
        self.assertIsNone(focus_center(None))
        self.assertIsNone(focus_center("no-rect"))


class RepeatTests(unittest.TestCase):
    def test_first_time_never_vetoes(self):
        streak, target, veto = register_repeat(0, None, ("open_door", (8, 5)))
        self.assertEqual((streak, target, veto), (1, ("open_door", (8, 5)), False))

    def test_second_repeat_vetoes_and_resets(self):
        streak, target, veto = register_repeat(1, ("open_door", (8, 5)), ("open_door", (8, 5)))
        self.assertTrue(veto)
        self.assertEqual(target, ("open_door", (8, 5)))
        # Tras vetar, la racha reinicia: el siguiente fallo cuenta como primero.
        streak2, _, veto2 = register_repeat(streak, target, ("open_door", (8, 5)))
        self.assertEqual((streak2, veto2), (1, False))

    def test_other_target_resets_streak(self):
        streak, target, veto = register_repeat(1, ("open_door", (8, 5)), ("get_key", (13, 4)))
        self.assertEqual((streak, target, veto), (1, ("get_key", (13, 4)), False))

    def test_none_target_never_vetoes(self):
        self.assertEqual(register_repeat(5, ("a", (1, 1)), None), (0, None, False))


class StuckKeyTests(unittest.TestCase):
    def test_stuck_open_door_drops_key(self):
        acted = GameAction("open_door", [8, 5], path=["down"])
        self.assertTrue(detect_stuck([13, 5], [13, 5], acted))
        self.assertFalse(resolve_held_key(True, False, acted, False))

    def test_real_walk_keeps_key(self):
        acted = GameAction("get_key", [13, 4], path=["down", "left"])
        self.assertFalse(detect_stuck([12, 8], [13, 4], acted))
        self.assertTrue(resolve_held_key(False, False, acted, True))


class RouteRecorderTests(unittest.TestCase):
    def test_compacts_arrow_events_into_route_groups(self):
        events = [
            {"direction": "up"}, {"direction": "up"},
            {"direction": "left"}, {"direction": "down"},
            {"direction": "down"}, {"direction": "down"},
            {"direction": "right"},
        ]

        self.assertEqual(format_sequence(events), "UU L DDD R")

    def test_empty_or_non_arrow_events_are_ignored(self):
        self.assertEqual(format_sequence([]), "")
        self.assertEqual(format_sequence([{"direction": "space"}]), "")


if __name__ == "__main__":
    unittest.main()
