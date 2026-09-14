import importlib.util
import math
from pathlib import Path
import unittest

import numpy as np
from PIL import Image, ImageDraw


MODULE_PATH = Path(__file__).parent / "tools" / "build_rig_package.py"
SPEC = importlib.util.spec_from_file_location("build_rig_package", MODULE_PATH)
PACKAGER = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(PACKAGER)


class EyeAngleTests(unittest.TestCase):
    def make_eye(self, degrees: float):
        source = Image.new("RGBA", (120, 70), "white")
        mask = Image.new("L", source.size)
        ImageDraw.Draw(mask).ellipse((20, 15, 100, 55), fill=255)
        draw = ImageDraw.Draw(source)
        slope = math.tan(math.radians(degrees))
        y0 = 35 - slope * 32
        y1 = 35 + slope * 32
        draw.line((28, y0, 92, y1), fill=(45, 20, 35, 255), width=4)
        # A very dark iris should not turn the estimated eyelid vertical.
        draw.ellipse((54, 24, 66, 47), fill=(8, 8, 12, 255))
        return source, mask

    def test_horizontal_eye_stays_horizontal(self):
        source, mask = self.make_eye(0)
        angle = math.degrees(PACKAGER.eye_angle(source, mask))
        self.assertAlmostEqual(angle, 0, delta=2.5)

    def test_slanted_eyes_keep_their_own_angles(self):
        for expected in (-19, 21):
            with self.subTest(expected=expected):
                source, mask = self.make_eye(expected)
                angle = math.degrees(PACKAGER.eye_angle(source, mask))
                self.assertAlmostEqual(angle, expected, delta=4.0)

    def test_two_eye_masks_preserve_face_roll(self):
        source = Image.new("RGBA", (220, 100), "white")
        masks = []
        draw = ImageDraw.Draw(source)
        for box in ((25, 43, 85, 73), (135, 15, 195, 45)):
            mask = Image.new("L", source.size)
            ImageDraw.Draw(mask).ellipse(box, fill=255)
            masks.append(mask)
            draw.line((box[0] + 7, box[1] + 21, box[2] - 7, box[1] + 9), fill=(30, 20, 30, 255), width=4)
        angles = [math.degrees(value) for value in PACKAGER.eye_angles(source, masks)]
        self.assertTrue(all(-18 < value < -11 for value in angles), angles)


class AuthoredEyeStrokeTests(unittest.TestCase):
    def test_authored_curve_is_preserved_without_angle_inference(self):
        source = Image.new("RGBA", (96, 64), (235, 210, 200, 255))
        mask = Image.new("L", source.size)
        points = [(18, 31), (31, 36), (47, 38), (64, 35), (78, 29)]
        ImageDraw.Draw(mask).line(points, fill=255, width=4, joint="curve")
        ImageDraw.Draw(source).line(points, fill=(48, 25, 34, 255), width=4, joint="curve")

        image, left, top = PACKAGER.authored_closed_eye(source, [mask])

        self.assertEqual((left, top, left + image.width, top + image.height), mask.getbbox())
        expected = mask.crop(mask.getbbox())
        self.assertEqual(image.getchannel("A").tobytes(), expected.tobytes())
        visible = [pixel for pixel in np.asarray(image).reshape(-1, 4) if pixel[3]]
        self.assertTrue(visible)
        self.assertLess(sum(int(pixel[0]) for pixel in visible) / len(visible), 90)


if __name__ == "__main__":
    unittest.main()
