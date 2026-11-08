"""Joint prompt and real video postprocess checks without GPU generation."""
import io
import tempfile
import unittest
from pathlib import Path
import av
import numpy as np
from PIL import Image, ImageDraw
import idle_tool
import sprite_combat
import sprite_pixel_export
import sprite_gif


class CombatTests(unittest.TestCase):
    def test_small_trail_uses_concise_conditioning_and_allows_body_turn(self):
        settings=dict(combatEffect='subtle',effectStrength='low',effectDescription='a red tip glint')
        graph=idle_tool.build_workflow('reference.png',sprite_combat.SUBTLE_MOTIONS['spin'],3,768,768,73,
            animation_type='custom',loop=False,facing='right',flat_background=True,combat_settings=settings)
        text=graph['6']['inputs']['prompt']
        self.assertIn('Show the back of the head',text)
        self.assertIn('red tip glint',text)
        self.assertIn('forearm-length',text)
        self.assertNotIn('No complete turn',text)
        for term in ('energy crescent','starburst','auburn','cream jacket','teal skirt','Never rotate'):
            self.assertNotIn(term,text)
        self.assertNotIn('last_frame',graph['6']['inputs'])
        self.assertEqual(graph['10']['inputs']['steps'],20)
        self.assertNotIn('14',graph)
        loop=idle_tool.build_workflow('reference.png','one cut',3,768,768,73,loop=True,combat_settings=settings)
        self.assertIn('<Picture 2>',loop['6']['inputs']['prompt'])
        self.assertEqual(loop['6']['inputs']['last_frame'],['1',0])

    def test_small_trail_matte_protects_costume_and_unmixes_faint_glow(self):
        from unittest.mock import patch
        import image_background,sprite_vfx_matte
        raw=Image.new('RGBA',(96,96),(128,128,128,255));draw=ImageDraw.Draw(raw)
        draw.rectangle((20,16,45,80),fill=(35,40,60));draw.rectangle((26,35,38,48),fill=(128,128,128))
        draw.rectangle((54,20,76,30),fill=(30,200,235));draw.rectangle((54,40,76,50),fill=(176,176,176))
        semantic=raw.copy();alpha=Image.new('L',raw.size,0);ImageDraw.Draw(alpha).rectangle((20,16,45,80),fill=255);semantic.putalpha(alpha)
        with patch.object(image_background,'remove',return_value=semantic):cut,_=sprite_vfx_matte.remove(raw)
        self.assertEqual(cut.getpixel((30,40)),(128,128,128,255))
        self.assertEqual(cut.getpixel((0,0))[3],0)
        self.assertGreater(cut.getpixel((60,24))[3],0)
        self.assertGreater(cut.getpixel((60,45))[3],0);self.assertLess(cut.getpixel((60,45))[3],255)
        combined=Image.new('RGBA',raw.size,(128,128,128,255));combined.alpha_composite(cut)
        self.assertLessEqual(max(abs(a-b) for a,b in zip(combined.getpixel((60,45)),raw.getpixel((60,45)))),1)

    def test_graph_keeps_native_model_and_integrates_effect_in_positive_prompt(self):
        old = idle_tool.build_workflow('ref.png', 'one cut', 3, 768, 640, 73, animation_type='attack', loop=True)
        same = idle_tool.build_workflow('ref.png', 'one cut', 3, 768, 640, 73, animation_type='attack', loop=True, combat_settings={})
        self.assertEqual(old, same)
        new = idle_tool.build_workflow('ref.png', 'one cut', 3, 768, 640, 73, animation_type='attack', loop=True,
            combat_settings=dict(combatEffect='blue_slash',effectDescription='gold stars'))
        self.assertEqual(new['10'], old['10'])
        self.assertEqual(new['8'], old['8'])
        self.assertEqual(new['6']['inputs']['last_frame'], ['1',0])
        self.assertIn('gold stars', new['6']['inputs']['prompt'])
        self.assertIn('cyan-blue energy crescent', new['6']['inputs']['prompt'])
        self.assertIn('8 percent', new['6']['inputs']['prompt'])
        self.assertNotIn('Subject movement only:', new['6']['inputs']['prompt'])

    def test_validation_and_compatibility(self):
        self.assertEqual(sprite_combat.options({})['combatEffect'], 'none')
        for value in [dict(combatEffect=[]),dict(effectStrength=4),dict(combatEffect='custom'),
                      dict(effectDescription='x'*1801),dict(pixelOutput=1),dict(pixelColorLock='true'),
                      dict(combatEffect='blue_slash',removeBackground=True,backgroundRemoval='ai'),
                      dict(pixelOutput=True,removeBackground=True,backgroundRemoval='ai')]:
            with self.subTest(value=value),self.assertRaises(ValueError):sprite_combat.options(value)
        for kind in sprite_combat.EFFECTS:
            sprite_combat.options(dict(combatEffect=kind,effectDescription='violet sparks'))

    def test_real_video_export_preserves_new_effect_colors_and_gif_timing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);source=Image.new('RGBA',(96,96));ImageDraw.Draw(source).rectangle((28,20,51,75),fill=(170,55,35))
            buf=io.BytesIO();source.save(buf,format='PNG')
            video=av.open(str(tmp/'raw.mp4'),'w');stream=video.add_stream('libx264',rate=24)
            stream.width=stream.height=96;stream.pix_fmt='yuv420p';stream.options={'crf':'10'}
            for i in range(12):
                im=Image.new('RGB',(96,96),(128,128,128));im.paste(source,mask=source.getchannel('A'))
                if 3<=i<=8:ImageDraw.Draw(im).rectangle((56,32,79,59),fill=(10,210,245))
                for packet in stream.encode(av.VideoFrame.from_image(im)):video.mux(packet)
            for packet in stream.encode():video.mux(packet)
            video.close()
            for lock in (False,True):
                report=sprite_pixel_export.export(tmp/'raw.mp4',buf.getvalue(),tmp/'sheet.png',tmp/'alpha.png',6,False,lock)
                self.assertEqual((report['width'],report['height'],report['frameCount']),(24,24,6))
                self.assertLessEqual(report['colors'],48)
                self.assertEqual(sum(report['durationMs']),500)
                self.assertTrue(any(c[1]>150 and c[2]>180 and c[0]<80 for c in report['palette']))
                with Image.open(tmp/'alpha.png') as sheet:
                    a=np.array(sheet);self.assertEqual(set(np.unique(a[:,:,3])),{0,255})
                    self.assertTrue(np.any((a[:,:,1]>150)&(a[:,:,2]>180)&(a[:,:,3]>0)))
                    images=sprite_gif.split_sheet(sheet,6,1,6)
                data,meta=sprite_gif.encode(images,report['durationMs'])
                self.assertEqual(meta['totalMs'],500)
                with Image.open(io.BytesIO(data)) as gif:
                    self.assertGreater(gif.n_frames,1)
                    self.assertLessEqual(gif.n_frames,6)
                    duration=0
                    for i in range(gif.n_frames):gif.seek(i);duration+=gif.info['duration']
                    self.assertEqual(duration,500)


if __name__=='__main__':unittest.main()
