import unittest
import io
from idle_tool import prepare_reference_image
import numpy as np
from PIL import Image
from idle_tool import remove_flat_background


class BackgroundTests(unittest.TestCase):
    def test_motion_padding(self):
        source=io.BytesIO()
        Image.new('RGB',(100,100),'red').save(source,format='PNG')
        for padding in (0,10,20,30):
            # Transparent source exercises the gray matte.
            rgba=Image.new('RGBA',(100,100),'red')
            rgba.putpixel((0,0),(0,0,0,0))
            data=io.BytesIO();rgba.save(data,format='PNG')
            result=Image.open(io.BytesIO(prepare_reference_image(data.getvalue(),100,100,padding)))
            self.assertEqual(result.size,(100,100))
            self.assertEqual(result.getpixel((50,50)),(255,0,0,255))
            if padding:
                self.assertEqual(result.getpixel((0,50)),(128,128,128,255))
        with self.assertRaises(ValueError):
            prepare_reference_image(source.getvalue(),100,100,99)

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
