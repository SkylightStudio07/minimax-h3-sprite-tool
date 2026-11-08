import base64
import io
import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import image_engine as image
import team_server

def encoded(im):
    buf=io.BytesIO();im.save(buf,format='PNG');return base64.b64encode(buf.getvalue()).decode()

class ImageTests(unittest.TestCase):
    def test_native_face_pass_preserves_output_size_and_excludes_sprite_lora(self):
        import image_face_detail
        with patch.object(image_face_detail,'ready',return_value=True):
            p=image.validate(dict(model='flanime-xl',prompt='adult knight, side view',faceDetail=True,faceDetailDenoise=.9))
        self.assertEqual((p['outputWidth'],p['outputHeight']),(1024,1536))
        self.assertEqual(p['faceDetailDenoise'],.15)
        graph=image.build_workflow(p,42)
        self.assertEqual(graph['23']['inputs']['image'],['8',0])
        self.assertEqual(graph['23']['inputs']['model'],['1',0])
        self.assertEqual(graph['23']['inputs']['denoise'],.15)
        self.assertEqual(graph['24']['inputs']['images'],['8',0])
        self.assertNotIn('28',graph);self.assertNotIn('27',graph)
        self.assertIn('side profile',graph['21']['inputs']['text'])
        self.assertEqual(p['faceDetailVersion'],image_face_detail.NATIVE_VERSION)

    def test_native_rpg_defaults_use_full_resolution_without_second_pass(self):
        p=image.validate(dict(model='flanime-xl',prompt='adult knight',seed=42))
        self.assertEqual((p['width'],p['height'],p['steps']),(1024,1536,40))
        self.assertFalse(p.get('hiresFix',False));self.assertFalse(p.get('faceDetail',False))
        graph=image.build_workflow(p,42)
        self.assertEqual(graph['6']['inputs']['width'],1024)
        self.assertEqual(graph['6']['inputs']['height'],1536)
        self.assertIn('rinFlanime',graph['1']['inputs']['ckpt_name'])
        self.assertEqual(graph['9']['inputs']['images'],['8',0])
        self.assertNotIn('23',graph);self.assertNotIn('44',graph)
        self.assertEqual(image.DEFAULT_MODEL,'soya-anima-flanime')

    def test_hires_second_pass_then_face_does_not_upscale_twice(self):
        import image_hires
        import image_face_detail
        with patch.object(image_hires,'ready',return_value=True),patch.object(image_face_detail,'ready',return_value=True):
            p=image.validate(dict(model='illustrious-xl',prompt='adult knight',hiresFix=True,faceDetail=True,width=896,height=1152,hiresDenoise=.9))
            with self.assertRaises(ValueError):image.validate(dict(model='anima-turbo',prompt='knight',hiresFix=True))
            with self.assertRaises(ValueError):image.validate(dict(model='illustrious-xl',prompt='knight',hiresFix=1))
            with self.assertRaises(ValueError):image.validate(dict(model='illustrious-xl',prompt='knight',hiresFix=True,mode='reference'))
        graph=image.build_workflow(p,42)
        self.assertEqual(p['hiresDenoise'],.2)
        self.assertEqual((p['outputWidth'],p['outputHeight']),(1792,2304))
        self.assertEqual(graph['44']['inputs']['latent_image'],['43',0])
        self.assertEqual(graph['44']['inputs']['denoise'],.2)
        self.assertEqual(graph['43']['inputs']['pixels'],['42',0])
        self.assertEqual(graph['23']['inputs']['image'],['45',0])
        self.assertNotIn('28',graph)
        self.assertEqual(graph['9']['inputs']['images'],['23',0])
        self.assertEqual(image.backend_url(p),image.image_soya.URL)
        without_face=image.build_workflow(p|dict(faceDetail=False),42)
        self.assertEqual(without_face['9']['inputs']['images'],['45',0])

    def test_face_detail_is_optional_family_scoped_and_routes_to_workflow_backend(self):
        import image_face_detail
        self.assertFalse(image.validate(dict(model='illustrious-xl',prompt='knight')).get('faceDetail',False))
        for model in ('soya-anima-flanime','anima-turbo'):
            with self.assertRaises(ValueError):image.validate(dict(model=model,prompt='knight',faceDetail=True))
        with self.assertRaises(ValueError):image.validate(dict(model='illustrious-xl',prompt='knight',faceDetail='true'))
        with patch.object(image_face_detail,'ready',return_value=False):
            with self.assertRaises(ValueError):image.validate(dict(model='illustrious-xl',prompt='knight',faceDetail=True))
        with patch.object(image_face_detail,'ready',return_value=True):
            p=image.validate(dict(model='illustrious-xl',prompt='knight, full body, standing',faceDetail=True))
            with self.assertRaises(ValueError):image.validate(dict(model='illustrious-xl',prompt='knight',mode='inpaint',faceDetail=True))
        graph=image.build_workflow(p,12)
        self.assertEqual(image.backend_url(p),image.image_soya.URL)
        self.assertEqual(graph['9']['inputs']['images'],['23',0])
        self.assertEqual(graph['24']['inputs']['images'],['28',0])
        self.assertEqual(graph['28']['inputs']['image'],['8',0])
        self.assertEqual((p['outputWidth'],p['outputHeight']),(1792,2304))
        self.assertNotIn('full body',graph['21']['inputs']['text'])
        self.assertEqual(graph['23']['inputs']['bbox_detector'],['20',0])
        self.assertEqual(graph['23']['inputs']['denoise'],.35)
        self.assertEqual(p['faceDetailVersion'],image_face_detail.VERSION)

    def test_illustrious_sprite_lora_patches_model_and_clip(self):
        import image_styles
        sample=next(dict(s,enabled=True) for s in image_styles.catalog() if s['id']=='epic-seven-sprites')
        with tempfile.TemporaryDirectory() as temp,patch.object(image_styles,'catalog',return_value=[sample]),patch.object(image.engine,'COMFY_ROOT',Path(temp)):
            target=Path(temp)/'models/loras'/sample['filename'];target.parent.mkdir(parents=True);target.write_bytes(b'fixture')
            for model in ('anima-turbo','animagine-xl','soya-anima-flanime'):
                with self.assertRaises(ValueError):
                    image.validate(dict(prompt='rapi (nikke)',model=model,styleId=sample['id']))
            p=image.validate(dict(prompt='rapi (nikke), full body',model='illustrious-xl',styleId=sample['id'],styleStrength=.6,width=896,height=1152))
            graph=image.build_workflow(p,42)
            self.assertEqual(graph['11']['class_type'],'LoraLoader')
            self.assertEqual(graph['11']['inputs']['strength_clip'],.6)
            self.assertEqual(graph['4']['inputs']['clip'],['11',1])
            self.assertEqual(graph['5']['inputs']['clip'],['11',1])
            self.assertEqual(graph['7']['inputs']['model'],['11',0])
            self.assertEqual(graph['8']['inputs']['vae'],['3',0])
            self.assertIn('illustriousXL10',graph['1']['inputs']['ckpt_name'])
            self.assertIn('rapi (nikke)',p['resolvedPrompt'])
            self.assertIn('e7sprites',p['resolvedPrompt'])

    def test_soya_looks_refine_style_without_replacing_subject(self):
        import image_looks
        new=[x for x in image_looks.catalog()['looks'] if x['model']=='soya-anima-flanime']
        self.assertEqual(len(new),36)
        request=dict(prompt='adult knight, navy coat',model='soya-anima-flanime',seed=42)
        a=image.validate(request|dict(lookId='soya-cel-clean',lookWorkflow={'refineDenoise':1}))
        b=image.validate(request|dict(lookId='soya-cel-soft'))
        line=image.validate(request|dict(lookId='soya-line-ink'))
        ga=image.build_workflow(a,42);gb=image.build_workflow(b,42)
        self.assertEqual(ga['125']['inputs']['value'],gb['125']['inputs']['value'])
        self.assertEqual(ga['126']['inputs']['value'],gb['126']['inputs']['value'])
        self.assertIn('navy coat',ga['125']['inputs']['value'])
        self.assertNotEqual(ga['415']['inputs']['value'],gb['415']['inputs']['value'])
        self.assertLess(ga['80']['inputs']['denoise'],.6)
        self.assertIn('monochrome',image.build_workflow(line,42)['125']['inputs']['value'])
        self.assertEqual(image.build_workflow(line,42)['283:7']['inputs']['value'],-100)
        self.assertEqual(a['lookWorkflow']['refineDenoise'],.25)

    def test_soya_random_and_batch_seeds_stay_within_rgthree_limit(self):
        limit=2**50
        for count in (1,4):
            with patch.object(image.secrets,'randbelow',side_effect=lambda stop:stop-1) as random:
                p=image.validate(dict(prompt='adult knight',count=count))
            self.assertLessEqual(p['seed']+count-1,limit)
            self.assertEqual(random.call_args.args[0],limit-count+2)
            for i in range(count):
                graph=image.build_workflow(p,p['seed']+i)
                self.assertLessEqual(graph['290']['inputs']['seed'],limit)
                self.assertEqual(graph['290']['inputs']['seed'],graph['291']['inputs']['seed'])
        with self.assertRaises(ValueError):image.validate(dict(prompt='adult knight',seed=limit+1))
        with self.assertRaises(ValueError):image.validate(dict(prompt='adult knight',seed=limit,count=4))
        self.assertEqual(image.validate(dict(prompt='adult knight',seed=limit))['seed'],limit)
        self.assertEqual(image.validate(dict(model='flanime-xl',prompt='adult knight',seed=limit+1))['seed'],limit+1)

    def test_soya_default_profile_and_routing(self):
        p=image.validate(dict(prompt='adult knight',seed=42,preset='live2d'))
        self.assertEqual(p['model'],'soya-anima-flanime')
        self.assertEqual((p['width'],p['height'],p['outputWidth'],p['outputHeight']),(768,768,1536,1536))
        self.assertEqual(image.backend_url(p),'http://127.0.0.1:8191')
        graph=image.build_workflow(p,42)
        self.assertEqual(graph['9']['inputs']['images'],['79',0])
        self.assertEqual(graph['386']['inputs']['strength_model'],.3)
        self.assertIn('soya-candidates',graph['184']['inputs']['lora_name'])
        self.assertIn('front view',graph['125']['inputs']['value'])
        self.assertEqual(graph['290']['inputs']['seed'],42)
        self.assertEqual(graph['182']['inputs']['scale_by'],1)
        for n in graph.values():
            for v in n['inputs'].values():
                if isinstance(v,list) and len(v)==2 and isinstance(v[0],str):self.assertIn(v[0],graph)
        for extra in (dict(mode='inpaint'),dict(width=1024,height=1024)):
            with self.assertRaises(ValueError):image.validate(dict(prompt='knight')|extra)
        classic=image.validate(dict(prompt='knight',model='anima-turbo'))
        self.assertEqual(image.backend_url(classic),image.COMFY_URL)

    def test_visual_presets_and_nonaccumulating_prompts(self):
        import image_looks
        import image_styles
        looks=image_looks.catalog()['looks']
        self.assertEqual(len({x['id'] for x in looks}),len(looks))
        artists=[x for x in looks if x['group']=='artist']
        self.assertEqual(len(artists),3)
        self.assertTrue(all('@' in x['prompt'] and not x['styleId'] for x in artists))
        for look in looks:
            request=dict(prompt='adult knight',model=look['model'],lookId=look['id'],styleId=look['styleId'],styleStrength=look['styleStrength'],steps=look['steps'],cfg=look['cfg'])
            style=next((s for s in image_styles.catalog() if s['id']==look['styleId']),None)
            if look.get('recipePreset'):continue
            if style and not style['enabled']:
                with self.assertRaises(ValueError):image.validate(request)
                continue
            with patch.object(image_styles.engine.COMFY_ROOT.__class__,'is_file',return_value=True):
                p=image.validate(request)
                twice=image.validate(p)
            self.assertEqual(p['resolvedPrompt'],twice['resolvedPrompt'])
            self.assertEqual(p['lookVersion'],image_looks.catalog()['version'])
            self.assertIn(look['prompt'],p['resolvedPrompt'])
            if look['styleId']=='flat-color' and 'no lineart' not in look['triggers']:
                self.assertNotIn('no lineart',p['resolvedPrompt'])
        with self.assertRaises(ValueError):image.validate(dict(prompt='knight',lookId='../unknown'))
        with self.assertRaises(ValueError):image.validate(dict(prompt='knight',lookId='flat-paper',model='animagine-xl'))
        p=image.validate(dict(prompt='knight',model='anima-turbo',lookId='flat-paper',steps=12,cfg=1.5))
        self.assertEqual((p['steps'],p['cfg']),(12,1.5))

    def test_background_validation_and_originals(self):
        with patch.object(image.image_background,'status',return_value={'ready':False}):
            with self.assertRaises(ValueError):image.validate(dict(prompt='knight',background='transparent'))
        with patch.object(image.image_background,'status',return_value={'ready':True}):
            p=image.validate(dict(prompt='knight',background='transparent',width=512,height=512,seed=11))
        self.assertIn('plain white background',p['resolvedPrompt'])
        class Response:
            ok=True
            def raise_for_status(self):pass
            def json(self):return {'prompt_id':'test','test':{'outputs':{'9':{'images':[{'filename':'test.png','type':'output','subfolder':''}]}},'status':{'status_str':'success'}}}
            @property
            def content(self):return base64.b64decode(encoded(Image.new('RGB',(512,512),'blue')))
        for fail in (False,True):
            with tempfile.TemporaryDirectory() as temp,patch.object(image,'RESULT_ROOT',Path(temp)),patch.object(image.requests,'post',return_value=Response()),patch.object(image.requests,'get',return_value=Response()),patch.object(image.time,'sleep'),patch.object(image,'update_job') as update,patch.object(image.image_background,'remove') as remove:
                if fail:remove.side_effect=RuntimeError('inference failure')
                else:remove.return_value=Image.new('RGBA',(512,512),(0,0,255,0))
                image.run_job('test',p)
                with Image.open(Path(temp)/'test/image-1-original.png') as original:
                    self.assertEqual(original.getpixel((0,0)),(0,0,255))
                item=update.call_args.kwargs['images'][0]
                self.assertEqual(item['originalUrl'],'/api/images/test/image-1-original.png')
                self.assertEqual(item['background'],'keep' if fail else 'transparent')
                self.assertEqual(bool(item.get('warning')),fail)

    def test_style_allowlist_and_model_patch(self):
        import image_styles
        disabled=dict(image_styles.catalog()[0],enabled=False)
        with patch.object(image_styles,'catalog',return_value=[disabled]):
            with self.assertRaises(ValueError):image.validate(dict(prompt='knight',styleId=disabled['id']))
        with self.assertRaises(ValueError):image.validate(dict(prompt='knight',styleId='../unsafe'))
        sample=dict(image_styles.catalog()[0],enabled=True)
        with tempfile.TemporaryDirectory() as temp,patch.object(image_styles,'catalog',return_value=[sample]),patch.object(image.engine,'COMFY_ROOT',Path(temp)):
            target=Path(temp)/'models/loras'/sample['filename'];target.parent.mkdir(parents=True);target.write_bytes(b'fixture')
            with self.assertRaises(ValueError):image.validate(dict(prompt='knight',model='animagine-xl',styleId=sample['id']))
            with self.assertRaises(ValueError):image.validate(dict(prompt='knight',styleId=sample['id'],styleStrength=float('nan')))
            p=image.validate(dict(prompt='knight',model='anima-turbo',styleId=sample['id'],styleStrength=.65))
            graph=image.build_workflow(p,12)
            self.assertEqual(graph['7']['inputs']['model'],['11',0])
            self.assertEqual(graph['11']['inputs']['strength_model'],.65)
            self.assertEqual(graph['11']['inputs']['lora_name'],str(Path(sample['filename'])))
            self.assertIn(sample['triggers'][0],p['resolvedPrompt'])
            self.assertEqual(p['styleSha256'],sample['sha256'])

    def test_validation_and_workflows(self):
        for model in ('anima-turbo','animagine-xl'):
            p=image.validate(dict(model=model,prompt='adult knight',preset='live2d',seed=12))
            w=image.build_workflow(p,12)
            self.assertIn('front view',w['4']['inputs']['text'])
            self.assertEqual(w['7']['inputs']['seed'],12)
            self.assertEqual(w['6']['inputs']['batch_size'],1)
            for value in [dict(width=513),dict(count=9),dict(seed=True),dict(cfg=float('nan')),dict(mode='oops'),dict(model='../oops')]:
                with self.assertRaises(ValueError):image.validate(dict(prompt='knight')|value)
        source=encoded(Image.new('RGB',(32,32),'red'))
        with self.assertRaises(ValueError):image.validate(dict(prompt='knight',model='anima-turbo',mode='inpaint',imageData=source,maskData=encoded(Image.new('RGB',(32,32),'black'))))
        p=image.validate(dict(prompt='knight',model='anima-turbo',mode='inpaint',imageData=source,maskData=encoded(Image.new('RGB',(32,32),'white'))))
        self.assertEqual(image.build_workflow(p,1,'test.png')['6']['class_type'],'VAEEncodeForInpaint')

    def test_mask_preserves_outside_and_png_metadata(self):
        source=Image.new('RGBA',(512,512),(255,0,0,80));mask=Image.new('RGB',source.size,'black');mask.paste('white',(100,100,200,200))
        p=image.validate(dict(prompt='knight',model='anima-turbo',width=512,height=512,seed=11,mode='inpaint',background='transparent',imageData=encoded(source),maskData=encoded(mask)))
        self.assertEqual(p['background'],'keep')
        class Response:
            ok=True
            def raise_for_status(self): pass
            def json(self):return {'prompt_id':'test','test':{'outputs':{'9':{'images':[{'filename':'test.png','type':'output','subfolder':''}]}},'status':{'status_str':'success'}}}
            @property
            def content(self):return base64.b64decode(encoded(Image.new('RGB',(512,512),'blue')))
        with tempfile.TemporaryDirectory() as temp,patch.object(image,'RESULT_ROOT',Path(temp)),patch.object(image.engine,'upload_image',return_value='test.png'),patch.object(image.requests,'post',return_value=Response()),patch.object(image.requests,'get',return_value=Response()),patch.object(image.time,'sleep'),patch.object(image,'update_job') as update:
            image.run_job('test',p)
            with Image.open(Path(temp)/'test/image-1.png') as output:
                self.assertEqual(output.getpixel((0,0)),(255,0,0,80));self.assertEqual(output.getpixel((150,150)),(0,0,255,255))
                self.assertEqual(json.loads(output.info['sprite_lab'])['seed'],11)
                self.assertNotIn('imageData',output.info['sprite_lab'])
            self.assertEqual(update.call_args.kwargs['state'],'complete')

    def test_authenticated_queue_gallery_and_delete(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            def run(jid,p):
                folder=root/'images'/jid;folder.mkdir(parents=True);Image.new('RGB',(8,8)).save(folder/'image-1.png');Image.new('RGB',(8,8)).save(folder/'image-1-original.png');Image.new('RGB',(8,8)).save(folder/'image-1-before-face.png');Image.new('RGB',(8,8)).save(folder/'image-1-before-hires.png')
                image.update_job(jid,state='complete',image=f'/api/images/{jid}/image-1.png',images=[dict(url=f'/api/images/{jid}/image-1.png',originalUrl=f'/api/images/{jid}/image-1-original.png',beforeFaceUrl=f'/api/images/{jid}/image-1-before-face.png',beforeHiresUrl=f'/api/images/{jid}/image-1-before-hires.png',seed=p['seed'])])
            app=team_server.create_app(root,image_runner=run);client=app.test_client();guest=app.test_client()
            response=guest.get('/assets/image-look-previews/flat-paper.webp')
            self.assertEqual(response.status_code,200);self.assertEqual(response.mimetype,'image/webp');response.close()
            def post(path,p):return client.post('/api/'+path,json=p,headers={'X-Sprite-Request':'1'})
            post('register',dict(username='admin',name='test',password='long-password',setupCode=(root/'admin-setup-code.txt').read_text()))
            post('login',dict(username='admin',password='long-password'))
            self.assertEqual(guest.get('/image-studio').status_code,401)
            self.assertEqual(client.post('/api/images/generate',json={'prompt':'knight'}).status_code,403)
            p=dict(prompt='knight',model='anima-turbo')
            ids=[post('images/generate',p).json['jobId'] for _ in range(3)]
            self.assertEqual(post('images/generate',p).status_code,429)
            with patch.object(image,'RESULT_ROOT',root/'images'):
                app.start_worker()
                try:
                    for _ in range(60):
                        if all(client.get('/api/jobs/'+jid).json['state']=='complete' for jid in ids):break
                        time.sleep(.1)
                    gallery=client.get('/api/gallery?type=image').json
                    self.assertEqual(gallery['total'],3)
                    self.assertEqual(guest.get('/api/gallery').json['total'],0)
                    asset=gallery['jobs'][0]['image'];jid=gallery['jobs'][0]['id']
                    self.assertEqual(guest.get(asset).status_code,401)
                    response=client.get(asset);self.assertEqual(response.status_code,200);response.close()
                    original=f'/api/images/{jid}/image-1-original.png'
                    self.assertEqual(guest.get(original).status_code,401)
                    response=client.get(original);self.assertEqual(response.status_code,200);response.close()
                    before=f'/api/images/{jid}/image-1-before-face.png'
                    self.assertEqual(guest.get(before).status_code,401)
                    response=client.get(before);self.assertEqual(response.status_code,200);response.close()
                    hires=f'/api/images/{jid}/image-1-before-hires.png'
                    self.assertEqual(guest.get(hires).status_code,401)
                    response=client.get(hires);self.assertEqual(response.status_code,200);response.close()
                    self.assertEqual(client.get(f'/api/images/{jid}/secret.txt').status_code,404)
                    self.assertEqual(post('jobs/'+jid+'/delete',{}).status_code,200)
                    self.assertEqual(client.get(asset).status_code,404)
                finally:app.stop_worker();time.sleep(.6)

if __name__=='__main__':unittest.main()
