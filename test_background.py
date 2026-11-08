import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import av
import idle_tool as engine
import io
from idle_tool import prepare_reference_image
import numpy as np
from PIL import Image
from idle_tool import remove_flat_background


class BackgroundTests(unittest.TestCase):
    def test_sparks_mode_preserves_generated_gold_without_restoring_flat_background(self):
        raw=Image.new('RGBA',(48,48),(128,128,128,255))
        raw.putpixel((38,8),(220,192,132,255))
        semantic=raw.copy()
        mask=Image.new('L',raw.size,0)
        mask.paste(255,(10,20,25,40))
        semantic.putalpha(mask)
        before=raw.tobytes()
        with patch.object(engine.image_background,'remove_sprite',return_value=semantic):
            result=engine.image_background.remove_sprite_with_sparks(raw)
        self.assertGreater(result.getpixel((38,8))[3],128)
        self.assertEqual(result.getpixel((0,0))[3],0)
        self.assertEqual(result.getpixel((15,25)),semantic.getpixel((15,25)))
        self.assertEqual(raw.tobytes(),before)
        # The same colors in a non-neutral backdrop must not activate recovery.
        raw.paste((45,100,160,255),(0,0,48,2))
        with patch.object(engine.image_background,'remove_sprite',return_value=semantic):
            self.assertEqual(engine.image_background.remove_sprite_with_sparks(raw).tobytes(),semantic.tobytes())

    def test_sparks_mode_requires_ready_ai_model(self):
        with patch.object(engine.image_background,'status',return_value=dict(ready=False)):
            with self.assertRaises(ValueError):
                engine.background_options(dict(removeBackground=True,backgroundRemoval='ai-sparks'))
        with patch.object(engine.image_background,'status',return_value=dict(ready=True)):
            self.assertEqual(engine.background_options(dict(removeBackground=True,backgroundRemoval='ai-sparks')),'ai-sparks')

    def test_semantic_sprite_holes_keep_gray_costume(self):
        source=np.full((40,40,4),128,dtype=np.uint8);source[:,:,3]=255
        source[6:34,8:32,:3]=30
        source[12:17,12:17,:3]=128  # gray clothing: same color as background
        source[23:29,17:23,:3]=128  # enclosed leg gap
        semantic=Image.fromarray(source)
        mask=np.full((40,40),8,dtype=np.uint8)
        mask[6:34,8:32]=250;mask[23:29,17:23]=4
        semantic.putalpha(Image.fromarray(mask))
        with patch.object(engine.image_background,'remove',return_value=semantic):
            result=np.array(engine.image_background.remove_sprite(Image.fromarray(source)))
        self.assertEqual(result[25,20,3],0)
        self.assertEqual(result[14,14,3],255)
        self.assertEqual(result[0,0,3],0)
        np.testing.assert_array_equal(result[:,:,:3],source[:,:,:3])

    def test_flat_sprite_retains_thin_pale_weapon(self):
        source=Image.new('RGBA',(48,48),(128,128,128,255))
        from PIL import ImageDraw
        draw=ImageDraw.Draw(source);draw.rectangle((10,20,24,40),fill=(30,40,70,255));draw.line((24,22,42,4),fill='white',width=2)
        semantic=source.copy();mask=Image.new('L',source.size,0);d=ImageDraw.Draw(mask);d.rectangle((10,20,24,40),fill=255);d.line((24,22,42,4),fill=20,width=2);semantic.putalpha(mask)
        with patch.object(engine.image_background,'remove',return_value=semantic):result=engine.image_background.remove_sprite(source)
        self.assertEqual(result.getpixel((35,11))[3],255)
        self.assertEqual(result.getpixel((0,0))[3],0)

    def test_side_action_allows_joint_rotation_but_retains_direction(self):
        for action in ('walk','run','attack'):
            prompt=engine.animation_prompt('test',action,False,'right',3,True)
            self.assertIn('shoulder and pelvis counterrotation',prompt)
            self.assertNotIn('hips, feet and weapon remain oriented',prompt)
            self.assertIn('nose and gaze stay directed to screen right',prompt)
        prompt=engine.animation_prompt('test','attack',False,'right',3,True)
        self.assertNotIn('<Picture 2>',prompt)
    def test_motion_padding(self):
        source=io.BytesIO()
        Image.new('RGB',(100,100),'red').save(source,format='PNG')
        for padding in (0,10,20,30,40,50,58):
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

    def test_ai_sheet_preserves_grid_rgb_and_uses_sampled_frames(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);video=root/'source.mp4'
            with av.open(str(video),'w') as out:
                stream=out.add_stream('mpeg4',rate=4);stream.width=64;stream.height=64;stream.pix_fmt='yuv420p'
                for i in range(4):
                    frame=av.VideoFrame.from_image(Image.new('RGB',(64,64),(i*50,90,140)))
                    for packet in stream.encode(frame):out.mux(packet)
                for packet in stream.encode():out.mux(packet)
            original_bytes=video.read_bytes()
            def matte(image):
                cutout=image.copy();alpha=Image.new('L',image.size,0);alpha.paste(255,(10,10,54,54));cutout.putalpha(alpha);return cutout
            with patch.object(engine.image_background,'status',return_value=dict(ready=True)),patch.object(engine.image_background,'remove',side_effect=matte) as remove:
                engine.make_sprite_sheet(video,root/'sheet.png',3,True,root/'transparent.png',24,'ai')
                self.assertEqual(remove.call_count,3)
            with Image.open(root/'sheet.png') as original,Image.open(root/'transparent.png') as transparent:
                self.assertEqual(original.size,(192,64));self.assertEqual(original.size,transparent.size)
                np.testing.assert_array_equal(np.asarray(original)[:,:,:3],np.asarray(transparent)[:,:,:3])
                for x in [0,64,128]:self.assertEqual(transparent.getpixel((x+10,10))[3],255)
            self.assertEqual(video.read_bytes(),original_bytes)

    def test_tolerance(self):
        source = np.full((20, 20, 4), 128, dtype=np.uint8)
        source[:, :, 3] = 255
        source[1:10, 1:10, :3] = 148
        image = Image.fromarray(source)
        self.assertEqual(remove_flat_background(image, 10).getpixel((3, 3))[3], 255)
        self.assertEqual(remove_flat_background(image, 24).getpixel((3, 3))[3], 0)
