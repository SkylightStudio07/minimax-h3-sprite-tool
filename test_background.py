import unittest
import numpy as np
from PIL import Image
from idle_tool import remove_flat_background


class BackgroundTests(unittest.TestCase):
    def test_connected_background_and_enclosed_color(self):
        source = np.full((20, 20, 4), 128, dtype=np.uint8)
        source[:, :, 3] = 255
        source[5:15, 5:15, :3] = 0
        source[8:12, 8:12, :3] = 128
        original = source.copy()
        result = np.array(remove_flat_background(Image.fromarray(source)))
        self.assertEqual(result[0, 0, 3], 0)
        self.assertEqual(result[6, 6, 3], 255)
        self.assertEqual(result[9, 9, 3], 255)
        np.testing.assert_array_equal(source, original)

    def test_tolerance(self):
        source = np.full((20, 20, 4), 128, dtype=np.uint8)
        source[:, :, 3] = 255
        source[1:10, 1:10, :3] = 148
        image = Image.fromarray(source)
        self.assertEqual(remove_flat_background(image, 10).getpixel((3, 3))[3], 255)
        self.assertEqual(remove_flat_background(image, 24).getpixel((3, 3))[3], 0)
