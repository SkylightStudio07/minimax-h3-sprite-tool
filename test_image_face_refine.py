import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from PIL import Image,ImageChops,ImageDraw
import image_engine as engine
import image_face_refine as face
import team_server


class FaceRefineTests(unittest.TestCase):
    def test_saved_graph_has_no_body_generation_or_sprite_pose(self):
        for source_model in ('soya-anima-flanime','flanime-xl','wai-cutscene-counter','animagine-xl'):
            p=face.settings(dict(model=source_model,prompt='black hair, side view',pose={'points':[]}),{},'a'*32,0,(1536,2048))
            graph=face.build(p,'reference.png')
            self.assertFalse(any(n['class_type'] in ('KSampler','EmptyLatentImage','ControlNetLoader','ImageScale') for n in graph.values()))
            self.assertEqual(graph['23']['inputs']['image'],['30',0])
            self.assertNotIn('pose',p);self.assertEqual((p['width'],p['height']),(1536,2048))
            self.assertEqual(engine.backend_url(p),'http://127.0.0.1:8191')
        for strength in (True,float('nan'),.35,'0.12'):
            with self.assertRaises(ValueError):face.settings({},dict(strength=strength),'a'*32,0,(32,32))

    def test_face_composite_preserves_body_pixels_dimensions_and_exact_alpha(self):
        original=Image.new('RGBA',(160,240),(70,100,150,120));original.putpixel((70,70),(10,20,30,0))
        generated=Image.new('RGB',original.size,'red');mask=Image.new('L',original.size);ImageDraw.Draw(mask).rectangle((60,35,90,65),fill=255)
        out,box=face.composite(original,generated,mask)
        self.assertEqual(box,(60,35,91,66));self.assertEqual(out.size,original.size)
        self.assertEqual(out.getchannel('A').tobytes(),original.getchannel('A').tobytes())
        self.assertIsNone(ImageChops.difference(out.crop((0,120,160,240)).convert('RGB'),original.crop((0,120,160,240)).convert('RGB')).getbbox())
        self.assertNotEqual(out.getpixel((75,50)),original.getpixel((75,50)))
        same,box=face.composite(original,generated,Image.new('L',original.size))
        self.assertIsNone(box);self.assertEqual(same.tobytes(),original.tobytes())

    def test_authenticated_api_snapshots_candidate_and_enforces_limits(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(engine,'RESULT_ROOT',Path(tmp)/'images'):
            root=Path(tmp);app=team_server.create_app(root,image_runner=lambda *_:None)
            client=app.test_client();guest=app.test_client();headers={'X-Sprite-Request':'1'}
            client.post('/api/register',json=dict(username='admin',name='test',password='long-password',setupCode=(root/'admin-setup-code.txt').read_text()),headers=headers)
            client.post('/api/login',json=dict(username='admin',password='long-password'),headers=headers)
            uid=client.get('/api/me').json['user']['id'];jid='a'*32;folder=engine.RESULT_ROOT/jid;folder.mkdir(parents=True)
            Image.new('RGBA',(64,96),(30,80,120,100)).save(folder/'image-1.png');original=(folder/'image-1.png').read_bytes()
            p=dict(jobType='image',model='soya-anima-flanime',preset='illustration',mode='reference',prompt='navy coat',pose={'points':[]})
            result=dict(images=[dict(url=f'/api/images/{jid}/image-1.png',seed=1)])
            with closing(sqlite3.connect(root/'team.sqlite3')) as con:
                con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(jid,uid,'complete',1,1,json.dumps(p),json.dumps(result)))
                con.commit()
            route=f'/api/images/{jid}/face-refine'
            self.assertEqual(guest.post(route,json={},headers=headers).status_code,401)
            self.assertEqual(client.post(route,json={}).status_code,403)
            for body in (dict(image=True),dict(image=4),dict(image=1),dict(strength=.9)):
                self.assertEqual(client.post(route,json=body,headers=headers).status_code,400)
            created=[]
            for _ in range(3):
                r=client.post(route,json=dict(image=0,strength=.12),headers=headers);self.assertEqual(r.status_code,202)
                created.append(r.json['jobId'])
                self.assertEqual((engine.RESULT_ROOT/r.json['jobId']/'image-1-before-face.png').read_bytes(),original)
            self.assertEqual(client.post(route,json={},headers=headers).status_code,429)
            job=client.get('/api/jobs/'+created[0]).json
            self.assertEqual(job['settings']['model'],'flanime-xl');self.assertEqual(job['settings']['parentJob'],jid)
            self.assertNotIn('pose',job['settings']);self.assertNotIn('imageData',job['settings'])
            self.assertEqual((folder/'image-1.png').read_bytes(),original)
            (folder/'image-1.png').unlink()
            self.assertEqual((engine.RESULT_ROOT/created[0]/'image-1-before-face.png').read_bytes(),original)
            app.stop_worker()

    def test_worker_saves_comparison_and_honest_no_face_result(self):
        for detected in (True,False):
            with self.subTest(detected=detected),tempfile.TemporaryDirectory() as tmp,patch.object(engine,'RESULT_ROOT',Path(tmp)):
                p=face.settings(dict(model='flanime-xl',prompt='short black hair'),{},'b'*32,0,(64,96));folder=Path(tmp)/'test';folder.mkdir()
                original=Image.new('RGBA',(64,96),(40,90,120,110));original.save(folder/'image-1-before-face.png')
                mask=Image.new('L',original.size)
                if detected:ImageDraw.Draw(mask).rectangle((22,12,40,26),fill=255)
                def encoded(im):
                    b=io.BytesIO();im.save(b,format='PNG');return b.getvalue()
                class Response:
                    ok=True;text='';content=b''
                    def raise_for_status(self):pass
                    def json(self):return self.data
                def post(url,**kw):
                    r=Response();r.data={'name':'source.png'} if url.endswith('/upload/image') else {'prompt_id':'test'};return r
                def get(url,**kw):
                    r=Response()
                    if '/history/' in url:r.data={'test':dict(status=dict(status_str='success'),outputs={'9':dict(images=[dict(filename='output.png')]),'26':dict(images=[dict(filename='mask.png')])})}
                    else:r.content=encoded(mask if kw['params']['filename']=='mask.png' else Image.new('RGB',original.size,'red'))
                    return r
                with patch.object(face.requests,'post',side_effect=post),patch.object(face.requests,'get',side_effect=get),patch.object(engine,'update_job') as update:
                    face.run_job('test',p)
                result=update.call_args.kwargs;self.assertEqual(result['state'],'complete')
                self.assertEqual(result['images'][0]['faceDetailApplied'],detected)
                if not detected:self.assertIn('warning',result['images'][0])
                with Image.open(folder/'image-1.png') as output:
                    self.assertEqual(output.size,original.size);self.assertEqual(output.getchannel('A').tobytes(),original.getchannel('A').tobytes())
                    if not detected:self.assertEqual(output.tobytes(),original.tobytes())


if __name__=='__main__':unittest.main()
