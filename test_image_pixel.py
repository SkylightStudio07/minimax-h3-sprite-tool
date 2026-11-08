import base64
import io
import json
import tempfile
import unittest
import sqlite3
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import image_pixel as pixel
import image_engine as engine
import team_server

class PixelTests(unittest.TestCase):
    def test_recipe_uses_pinned_lora_no_refiner_and_low_resolution_metadata(self):
        for size in (64,96,128):
            p=engine.validate(dict(model=pixel.MODEL_ID,prompt='red knight',pixelSize=size,pixelColors=16))
            self.assertEqual((p['width'],p['height']),(pixel.generation_size(size),)*2)
            self.assertEqual((p['outputWidth'],p['outputHeight']),(size,size))
            graph=engine.build_workflow(p,42)
            self.assertEqual(graph['12']['inputs']['lora_name'],str(Path('pixel/pixel-art-xl.safetensors')))
            self.assertEqual(graph['7']['inputs']['model'],['12',0])
            self.assertEqual(graph['4']['inputs']['clip'],['12',1])
            self.assertTrue(graph['4']['inputs']['text'].startswith('pixel art,'))
            self.assertEqual(graph['9']['inputs']['images'],['8',0])
            self.assertFalse(p.get('faceDetail'));self.assertFalse(p.get('hiresFix'))
            self.assertEqual(engine.backend_url(p),engine.COMFY_URL)

    def test_reject_incompatible_or_fake_grid(self):
        for change in [dict(pixelSize=True),dict(pixelSize=256),dict(pixelColors=3),dict(pixelColors=False),dict(width=512,height=512),dict(mode='inpaint'),dict(styleId='flat-color'),dict(lookId='soya-cel-clean'),dict(faceDetail=True),dict(hiresFix=True),dict(pose={'points':[]}),dict(preset='rpg-sheet')]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                engine.validate(dict(model=pixel.MODEL_ID,prompt='knight')|change)

    def test_no_new_colors_from_resizing_or_soft_alpha(self):
        original=Image.new('RGBA',(512,512))
        original.paste((255,0,0,255),(0,0,256,256));original.paste((0,0,255,60),(256,0,512,256));original.paste((0,255,0,180),(0,256,256,512))
        out=pixel.finish(original,64,0)
        self.assertEqual(out.size,(64,64));self.assertEqual(set(out.getchannel('A').getdata()),{0,255})
        self.assertEqual(out.getpixel((0,0)),(255,0,0,255));self.assertEqual(out.getpixel((40,0))[3],0)
        self.assertEqual(out.getpixel((0,40)),(0,255,0,255))
        preview=out.resize((512,512),Image.Resampling.NEAREST)
        self.assertEqual(preview.crop((0,0,8,8)).getcolors(),[(64,(255,0,0,255))])

    def test_palette_counts_only_visible_pixels(self):
        original=Image.new('RGBA',(128,128))
        original.putdata([(x*2,y*2,(x+y)%256,0 if x<50 else 255) for y in range(128) for x in range(128)])
        for count in (16,32,64):
            out=pixel.finish(original,128,count)
            visible={p[:3] for p in out.getdata() if p[3]}
            self.assertLessEqual(len(visible),count)
            self.assertEqual(out.getchannel('A').tobytes(),original.getchannel('A').tobytes())

    def test_reference_preserves_aspect_ratio(self):
        source=Image.new('RGBA',(64,128),(255,0,0,255))
        out=pixel.prepare_reference(source,(1024,1024))
        self.assertEqual(out.getpixel((0,500)),(255,255,255));self.assertEqual(out.getpixel((512,500)),(255,0,0))

    def test_object_matte_keeps_subject_and_white_internal_pixels(self):
        original=Image.new('RGB',(128,128),'white');original.paste('red',(35,20,95,110));original.paste('white',(55,50,75,70))
        with patch('image_background.remove',side_effect=AssertionError('Object must not use anime detector')):
            cut,method=pixel.remove_background(original,'illustration',64)
        self.assertEqual(method,'border-connected-flat');self.assertEqual(cut.getpixel((0,0))[3],0)
        self.assertEqual(cut.getpixel((60,60)),(255,255,255,255))

    def test_empty_ai_matte_falls_back_and_bad_flat_matte_is_not_published(self):
        original=Image.new('RGB',(128,128),'white');original.paste('blue',(40,20,90,110))
        with patch('image_background.remove',return_value=Image.new('RGBA',original.size)):
            cut,method=pixel.remove_background(original,'sprite',64)
            self.assertEqual(method,'border-connected-flat');self.assertIsNotNone(cut.getbbox())
        with self.assertRaises(RuntimeError):pixel.remove_background(Image.new('RGB',(128,128),'white'),'illustration',64)

    def test_worker_exports_real_lowres_preview_and_records_dimensions(self):
        p=engine.validate(dict(model=pixel.MODEL_ID,prompt='knight',seed=42,pixelSize=64,pixelColors=16,background='keep'))
        im=Image.new('RGB',(1024,1024),'red');buf=io.BytesIO();im.save(buf,format='PNG')
        class Response:
            ok=True
            content=buf.getvalue()
            def raise_for_status(self):pass
            def json(self):return {'prompt_id':'mock','mock':{'outputs':{'9':{'images':[{'filename':'mock.png','type':'output','subfolder':''}]}},'status':{'status_str':'success'}}}
        with tempfile.TemporaryDirectory() as folder,patch.object(engine,'RESULT_ROOT',Path(folder)),patch.object(engine.requests,'post',return_value=Response()),patch.object(engine.requests,'get',return_value=Response()),patch.object(engine.time,'sleep'),patch.object(engine,'update_job') as update:
            engine.run_job('fixture',p)
            output=Path(folder)/'fixture'
            for name,size in [('image-1.png',(64,64)),('image-1-pixel-preview.png',(512,512)),('image-1-before-pixel.png',(1024,1024))]:
                with Image.open(output/name) as im:
                    self.assertEqual(im.size,size)
                    self.assertEqual(json.loads(im.info['sprite_lab'])['outputWidth'],64)
            self.assertTrue(update.call_args.kwargs['images'][0]['pixelArt'])
            self.assertEqual(update.call_args.kwargs['state'],'complete')

    def test_pixel_assets_require_login_and_listed_result_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);app=team_server.create_app(root,image_runner=lambda *args:None)
            client=app.test_client();guest=app.test_client()
            def post(path,data):return client.post('/api/'+path,json=data,headers={'X-Sprite-Request':'1'})
            post('register',dict(username='pixel-admin',name='test',password='long-password',setupCode=(root/'admin-setup-code.txt').read_text()))
            post('login',dict(username='pixel-admin',password='long-password'))
            response=post('images/generate',dict(model=pixel.MODEL_ID,prompt='knight',pixelSize=64))
            self.assertEqual(response.status_code,202);jid=response.json['jobId']
            media=root/'images'/jid;media.mkdir(parents=True)
            paths={}
            for key,name in [('url','image-1.png'),('pixelPreviewUrl','image-1-pixel-preview.png'),('beforePixelUrl','image-1-before-pixel.png')]:
                Image.new('RGBA',(64,64),'red').save(media/name);paths[key]=f'/api/images/{jid}/{name}'
            result=dict(images=[dict(paths,pixelArt=True)],image=paths['url'])
            with closing(sqlite3.connect(root/'team.sqlite3')) as db:
                db.execute('UPDATE jobs SET state=?,result=? WHERE id=?',('complete',json.dumps(result),jid));db.commit()
            with patch.object(engine,'RESULT_ROOT',root/'images'):
                for url in paths.values():
                    self.assertEqual(guest.get(url).status_code,401)
                    response=client.get(url);self.assertEqual(response.status_code,200);response.close()
                self.assertEqual(client.get(f'/api/images/{jid}/not-listed.png').status_code,404)
                self.assertEqual(post(f'images/{jid}/face-refine',dict(image=0,strength=.12)).status_code,400)

if __name__=='__main__':unittest.main()
