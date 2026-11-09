import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

import idle_tool
import image_background
import sprite_combat

GRAY = (128, 128, 128)


def scene(size=200):
    a = np.full((size, size, 3), GRAY, np.float32)
    a[60:160, 70:130] = (200, 40, 40)
    return a


def cut(rgb, body):
    """Run the soft matte with a stand-in for the semantic cutout."""
    image = Image.fromarray(rgb.round().astype(np.uint8))
    mask = Image.fromarray((body * 255).astype(np.uint8))
    plain = image.convert('RGBA')
    plain.putalpha(mask)
    with patch.object(image_background, 'remove_sprite', return_value=plain):
        return np.asarray(image_background.remove_sprite_soft(image.convert('RGBA')), np.float32)


def body_mask(size=200):
    m = np.zeros((size, size), bool)
    m[60:160, 70:130] = True
    return m


class SoftMatte(unittest.TestCase):
    def test_blast_keeps_a_soft_edge_and_loses_the_backdrop(self):
        rgb = scene()
        y, x = np.ogrid[:200, :200]
        glow = np.clip(1 - np.hypot(y - 30, x - 40) / 28, 0, 1)[..., None]
        rgb = rgb * (1 - glow) + np.array((255, 200, 60), np.float32) * glow
        out = cut(rgb, body_mask())
        self.assertGreater(out[30, 40, 3], 200)
        mid = out[30, 54, 3]
        self.assertTrue(40 < mid < 200, mid)
        self.assertGreater(out[30, 54, 0], 200, 'Color is unmixed instead of keeping the gray backdrop')
        self.assertEqual(out[5, 5, 3], 0)

    def test_body_pixels_are_untouched(self):
        out = cut(scene(), body_mask())
        self.assertTrue(np.all(out[70:150, 80:120, 3] == 255))
        self.assertTrue(np.all(out[70:150, 80:120, 0] == 200))

    def test_small_backdrop_hole_is_opened(self):
        rgb = scene()
        rgb[100:106, 90:96] = GRAY
        self.assertEqual(cut(rgb, body_mask())[103, 93, 3], 0)

    def test_shaded_armor_near_the_backdrop_color_is_not_opened(self):
        rgb = scene()
        rgb[100:106, 90:96] = (136, 136, 136)
        self.assertEqual(cut(rgb, body_mask())[103, 93, 3], 255)

    def test_large_gray_panel_stays_as_clothing(self):
        rgb = scene()
        rgb[80:140, 80:120] = GRAY
        self.assertEqual(cut(rgb, body_mask())[110, 100, 3], 255)

    def test_faint_haze_is_not_kept(self):
        rgb = scene()
        rgb[170:195, 20:180] = (140, 140, 140)
        self.assertEqual(cut(rgb, body_mask())[180, 100, 3], 0)

    def blob(self, rgb, cy, cx, color, reach=24):
        y, x = np.ogrid[:200, :200]
        amount = np.clip(1 - np.hypot(y - cy, x - cx) / reach, 0, 1)[..., None]
        return rgb * (1 - amount) + np.array(color, np.float32) * amount

    def test_light_on_the_floor_is_not_kept(self):
        rgb = self.blob(scene(), 172, 40, (175, 140, 115))
        self.assertEqual(cut(rgb, body_mask())[172, 40, 3], 0)

    def test_a_strong_blast_near_the_feet_is_kept(self):
        rgb = self.blob(scene(), 172, 40, (255, 240, 120))
        self.assertGreater(cut(rgb, body_mask())[172, 40, 3], 200)

    def test_soft_glow_beside_the_body_is_kept(self):
        rgb = self.blob(scene(), 90, 40, (175, 140, 115))
        self.assertGreater(cut(rgb, body_mask())[90, 40, 3], 40)

    def test_tiny_specks_are_not_kept(self):
        rgb = scene()
        rgb[20:23, 20:23] = (255, 255, 255)
        self.assertEqual(cut(rgb, body_mask())[21, 21, 3], 0)

    def test_blast_touching_the_edge_still_counts_as_flat(self):
        rgb = scene()
        rgb[:40, :40] = (255, 220, 120)
        self.assertGreater(cut(rgb, body_mask())[5, 5, 3], 200)

    def test_textured_backdrop_returns_the_plain_cutout(self):
        rgb = scene()
        noise = np.random.default_rng(1).integers(0, 255, rgb.shape, dtype=np.uint8).astype(np.float32)
        mask = body_mask()
        rgb[~mask] = noise[~mask]
        out = cut(rgb, mask)
        self.assertEqual(out[5, 5, 3], 0)


class Options(unittest.TestCase):
    def test_mode_is_accepted(self):
        with patch.object(image_background, 'status', return_value=dict(ready=True)):
            self.assertEqual(idle_tool.background_options(dict(removeBackground=True, backgroundRemoval='ai-soft')), 'ai-soft')

    def test_needs_the_cutout_model(self):
        with patch.object(image_background, 'status', return_value=dict(ready=False)), self.assertRaises(ValueError):
            idle_tool.background_options(dict(removeBackground=True, backgroundRemoval='ai-soft'))

    def test_generated_effect_setting_still_requires_flat(self):
        with self.assertRaises(ValueError):
            sprite_combat.options(dict(combatEffect='fire', removeBackground=True, backgroundRemoval='ai-soft'))


if __name__ == '__main__':
    unittest.main()
