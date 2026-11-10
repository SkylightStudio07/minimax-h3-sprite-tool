import unittest

import numpy as np
from PIL import Image

import sprite_breathe


def person(size=256):
    a = np.zeros((size, size, 4), np.uint8)
    a[40:80, 110:146] = (240, 200, 170, 255)
    a[80:180, 90:166] = (60, 90, 200, 255)
    a[100:104, 90:166] = (255, 255, 255, 255)
    a[180:240, 100:156] = (40, 40, 60, 255)
    return Image.fromarray(a, 'RGBA')


def frames(count=24):
    return sprite_breathe.loop(person(), 80, 128, 38, count)


def pixels(image):
    return np.asarray(image).astype(int)


class Loop(unittest.TestCase):
    def test_starts_on_the_untouched_still(self):
        result = frames()
        self.assertEqual(len(result), 24)
        self.assertTrue((pixels(result[0]) == pixels(person())).all())

    def test_chest_rises_and_comes_back(self):
        result = frames()
        moved = [int((np.abs(pixels(f) - pixels(person())).max(axis=2) > 8).sum()) for f in result]
        peak = int(np.argmax(moved))
        self.assertGreater(moved[peak], 50)
        self.assertLess(moved[-1], moved[peak] / 3)
        self.assertTrue(4 <= peak <= 14, peak)

    def test_head_and_legs_stay_exact(self):
        still = pixels(person())
        for frame in frames():
            a = pixels(frame)
            self.assertTrue((a[:80] == still[:80]).all())
            self.assertTrue((a[200:] == still[200:]).all())

    def test_transparent_surroundings_get_no_color(self):
        for frame in frames():
            a = pixels(frame)
            self.assertTrue((a[a[..., 3] == 0][:, :3] == 0).all())

    def test_refuses_marks_off_the_character(self):
        for neck, axis, half, count in ((9, 128, 38, 24), (250, 128, 38, 24), (80, 999, 38, 24), (80, 128, 1, 24), (80, 128, 38, 3), (80.5, 128, 38, 24)):
            with self.assertRaises(ValueError):
                sprite_breathe.loop(person(), neck, axis, half, count)

    def test_refuses_an_empty_frame(self):
        with self.assertRaises(ValueError):
            sprite_breathe.loop(Image.new('RGBA', (64, 64)), 20, 30, 8, 12)


if __name__ == '__main__':
    unittest.main()
