import unittest

import cv2
import numpy as np

from diamond_rush_vision import DiamondRushVision

CELL_SIZE = 56


def _cell(vision, name):
    # En runtime los templates ya vienen redimensionados a la celda.
    return vision.templates_raw[name]


class SpikeDetectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vision = DiamondRushVision()
        # Mismo orden que el runtime: primero resize, luego contornos.
        cls.vision.resize_templates(CELL_SIZE, CELL_SIZE)
        cls.vision.contours_spike = cls.vision._find_spike_contours()

    def _detected(self, roi):
        vision = self.vision
        return vision.detect_spike(roi) or vision._detect_spike_fallback(roi)

    def test_spike_template_detects(self):
        self.assertTrue(self._detected(_cell(self.vision, "spike")))

    def test_terrain_is_not_spike(self):
        # El detector primario dispara hasta en suelo plano (peculiaridad
        # preexistente, enmascarada porque el template de terreno gana antes).
        # Lo que importa del respaldo nuevo: debe rechazar el suelo.
        roi = _cell(self.vision, "terrain")
        self.assertFalse(self.vision._detect_spike_fallback(roi))

    def test_fall_is_not_spike(self):
        roi = _cell(self.vision, "fall")
        self.assertFalse(self.vision._detect_spike_fallback(roi))
        self.assertFalse(self._detected(roi))

    def test_spike_on_terrain_detects(self):
        roi = _cell(self.vision, "terrain").copy()
        self.assertFalse(self._detected(roi))
        spike = _cell(self.vision, "spike")
        y0 = (roi.shape[0] - spike.shape[0]) // 2
        x0 = (roi.shape[1] - spike.shape[1]) // 2
        roi[y0:y0 + spike.shape[0], x0:x0 + spike.shape[1]] = spike
        self.assertTrue(self._detected(roi))


class DiamondOverrideTests(unittest.TestCase):
    def _harness(self):
        from cell import Cell
        vision = DiamondRushVision()
        vision.resize_templates(120, 120)
        tile = cv2.resize(vision.templates_raw["terrain"], (120, 120),
                          interpolation=cv2.INTER_AREA)
        img = np.tile(tile, (5, 2, 1)).copy()
        grid = [[Cell([r, c], "terrain") for c in range(2)] for r in range(5)]
        vision.game_rectangle = (0, 0, 240, 600)
        vision.cell_width = 120
        vision.cell_height = 120
        return vision, img, grid

    def test_plain_floor_is_not_promoted_to_diamond(self):
        vision, img, grid = self._harness()

        vision._override_diamonds_full_image(img, img.copy(), grid, 5, 2)

        for row in grid:
            for cell in row:
                self.assertEqual(cell.cell_type, "terrain")

    def test_half_diamond_is_still_recovered(self):
        vision, img, grid = self._harness()
        diamond = cv2.resize(vision.templates_raw["diamond"], (120, 120),
                             interpolation=cv2.INTER_AREA)
        img[3 * 120:4 * 120, 1 * 120:2 * 120][:, :60] = diamond[:, :60]

        vision._override_diamonds_full_image(img, img.copy(), grid, 5, 2)

        self.assertEqual(grid[3][0].cell_type, "terrain")
        self.assertEqual(grid[3][1].cell_type, "diamond")


class KeyOverrideTests(unittest.TestCase):
    def _harness(self):
        from cell import Cell
        vision = DiamondRushVision()
        vision.resize_templates(120, 120)
        tile = cv2.resize(vision.templates_raw["terrain"], (120, 120),
                          interpolation=cv2.INTER_AREA)
        img = np.tile(tile, (5, 2, 1)).copy()
        grid = [[Cell([r, c], "terrain") for c in range(2)] for r in range(5)]
        vision.game_rectangle = (0, 0, 240, 600)
        vision.cell_width = 120
        vision.cell_height = 120
        return vision, img, grid

    def test_plain_floor_is_not_promoted_to_key(self):
        vision, img, grid = self._harness()

        vision._override_keys_full_image(img, img.copy(), grid, 5, 2)

        for row in grid:
            for cell in row:
                self.assertEqual(cell.cell_type, "terrain")

    def test_half_key_is_still_recovered(self):
        vision, img, grid = self._harness()
        key = cv2.resize(vision.templates_raw["key"], (120, 120),
                         interpolation=cv2.INTER_AREA)
        img[3 * 120:4 * 120, 1 * 120:2 * 120][:, :60] = key[:, :60]

        vision._override_keys_full_image(img, img.copy(), grid, 5, 2)

        self.assertEqual(grid[3][0].cell_type, "terrain")
        self.assertEqual(grid[3][1].cell_type, "key")


class SuppressionTests(unittest.TestCase):
    """Lo ya recogido no resucita por overrides (fantasmas tipo (6,5))."""

    def _harness(self):
        from cell import Cell
        vision = DiamondRushVision()
        vision.resize_templates(120, 120)
        tile = cv2.resize(vision.templates_raw["terrain"], (120, 120),
                          interpolation=cv2.INTER_AREA)
        img = np.tile(tile, (5, 2, 1)).copy()
        grid = [[Cell([r, c], "terrain") for c in range(2)] for r in range(5)]
        vision.game_rectangle = (0, 0, 240, 600)
        vision.cell_width = 120
        vision.cell_height = 120
        return vision, img, grid

    def _paste_half(self, vision, img, name):
        tpl = cv2.resize(vision.templates_raw[name], (120, 120),
                         interpolation=cv2.INTER_AREA)
        img[3 * 120:4 * 120, 1 * 120:2 * 120][:, :60] = tpl[:, :60]

    def test_collected_diamond_not_resurrected(self):
        from game_action import GameAction
        vision, img, grid = self._harness()
        self._paste_half(vision, img, "diamond")
        vision.mark_collected(GameAction("get_diamond", [3, 1], path=["left"]))

        vision._override_diamonds_full_image(img, img.copy(), grid, 5, 2)

        self.assertEqual(grid[3][1].cell_type, "terrain")

    def test_collected_key_not_resurrected(self):
        from game_action import GameAction
        vision, img, grid = self._harness()
        self._paste_half(vision, img, "key")
        vision.mark_collected(GameAction("get_key", [3, 1], path=["down"]))

        vision._override_keys_full_image(img, img.copy(), grid, 5, 2)

        self.assertEqual(grid[3][1].cell_type, "terrain")

    def test_unmark_reenables_override(self):
        from game_action import GameAction
        vision, img, grid = self._harness()
        self._paste_half(vision, img, "diamond")
        acted = GameAction("get_diamond", [3, 1], path=["left"])
        vision.mark_collected(acted)
        vision.unmark_collected(acted)

        vision._override_diamonds_full_image(img, img.copy(), grid, 5, 2)

        self.assertEqual(grid[3][1].cell_type, "diamond")

    def test_clear_suppressed_resets(self):
        from game_action import GameAction
        vision, _, _ = self._harness()
        vision.mark_collected(GameAction("get_key", [1, 1], path=["up"]))
        self.assertTrue(vision.suppressed_cells)
        vision.clear_suppressed()
        self.assertEqual(vision.suppressed_cells, set())


if __name__ == "__main__":
    unittest.main()
