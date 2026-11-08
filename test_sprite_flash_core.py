import unittest

import numpy as np
from tools.export_soldier_robot_batch import emission_patch


class FlashCoreTests(unittest.TestCase):
    def test_white_core_is_not_used_as_backdrop_and_material_stays_protected(self):
        rgb = np.full((160, 240, 3), 125.)
        yy, xx = np.indices(rgb.shape[:2])
        flame = ((xx - 90) / 70) ** 2 + ((yy - 80) / 36) ** 2 < 1
        core = ((xx - 90) / 60) ** 2 + ((yy - 80) / 29) ** 2 < 1
        rgb[flame] = (255, 190, 50)
        rgb[core] = 255
        warm = flame & ~core
        semantic = np.zeros((160, 240), dtype=np.uint8)
        protect = np.zeros_like(semantic, dtype=bool)
        protect[70:90, 150:170] = True
        recover, alpha, foreground = emission_patch(rgb, semantic, protect, warm, np.ones_like(protect), np.array([125.] * 3))
        self.assertTrue(recover[80, 90])
        self.assertGreater(alpha[80, 90], .99)
        self.assertTrue(np.all(foreground[80, 90] > .99))
        self.assertFalse(np.any(recover[protect]))
        self.assertEqual(alpha[0, 0], 0)


if __name__ == '__main__':
    unittest.main()
