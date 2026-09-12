"""Isolated API tests: no model invocation or production accounts."""
import base64
from contextlib import closing
import io
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from pathlib import Path
from PIL import Image
import team_server as server

HEADERS={'X-Sprite-Request':'1'}

class TeamTests(unittest.TestCase):
    def test_video_poster_cached_and_deleted(self):
        jid=self.post(self.admin,'generate',**self.payload).json['jobId']
        root=self.data/'poster-results';folder=root/jid;folder.mkdir(parents=True)
        video=folder/'idle.mp4'
        with server.engine.av.open(str(video),mode='w') as container:
            stream=container.add_stream('libx264',rate=24)
            stream.width=640;stream.height=800;stream.pix_fmt='yuv420p'
            frame=server.engine.av.VideoFrame.from_image(Image.new('RGB',(640,800),'red'))
            for packet in stream.encode(frame): container.mux(packet)
            for packet in stream.encode(): container.mux(packet)
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            con.execute("UPDATE jobs SET state='complete',result=? WHERE id=?",
                        (json.dumps(dict(video=f'/outputs/results/{jid}/idle.mp4')),jid))
            con.commit()
        with patch.object(server.engine,'RESULT_ROOT',root):
            url=self.guest.get('/api/gallery').json['jobs'][0]['poster']
            response=self.guest.get(url)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.mimetype,'image/jpeg')
            with Image.open(io.BytesIO(response.data)) as image:
                self.assertEqual(image.size,(384,480))
            response.close()
            with patch.object(server.engine,'video_thumbnail',side_effect=AssertionError('cache missed')):
                cached=self.guest.get(url)
                self.assertEqual(cached.status_code,200)
                cached.close()
            self.post(self.admin,'jobs/'+jid+'/delete')
            self.assertEqual(self.guest.get(url).status_code,404)

    def test_gallery_pages(self):
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            uid=con.execute('SELECT id FROM users LIMIT 1').fetchone()[0]
            for i in range(8):
                con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',
                            (str(i),uid,'complete',i,i,'{}','{}'))
            con.commit()
        first=self.guest.get('/api/gallery').json
        second=self.guest.get('/api/gallery?page=2').json
        self.assertEqual((len(first['jobs']),first['total'],first['pages']),(6,8,2))
        self.assertEqual(len(second['jobs']),2)
        self.assertFalse({j['id'] for j in first['jobs']} & {j['id'] for j in second['jobs']})
        self.assertNotIn('userId',first['jobs'][0])
        self.assertIn('userId',self.admin.get('/api/gallery').json['jobs'][0])
        self.assertEqual(self.guest.get('/api/gallery?page=999').json['page'],2)

    def test_reextract_preserves_original(self):
        self.approve()
        jid=self.post(self.admin,'generate',**self.payload).json['jobId']
        endpoint='jobs/'+jid+'/extract'
        self.assertEqual(self.post(self.guest,endpoint,frameCount=64).status_code,401)
        self.assertEqual(self.post(self.member,endpoint,frameCount=64).status_code,403)
        self.assertEqual(self.post(self.admin,endpoint,frameCount=65).status_code,400)
        self.assertEqual(self.post(self.admin,endpoint,frameCount=64).status_code,409)
        root=self.data/'results';folder=root/jid;folder.mkdir(parents=True)
        (folder/'idle.mp4').touch()
        original=f'/outputs/results/{jid}/original.png'
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            con.execute("UPDATE jobs SET state='complete',result=? WHERE id=?",
                        (json.dumps(dict(video=f'/outputs/results/{jid}/idle.mp4',spriteSheet=original)),jid))
            con.commit()
        def fake_extract(video,output,count,loop):
            Image.new('RGBA',(count,1)).save(output)
        with patch.object(server.engine,'RESULT_ROOT',root),patch.object(server.engine,'make_sprite_sheet',side_effect=fake_extract) as extract:
            response=self.post(self.admin,endpoint,frameCount=64)
            self.assertEqual(response.status_code,200)
            self.assertEqual(extract.call_args.args[2],64)
            result=self.admin.get('/api/jobs/'+jid).json
            self.assertEqual(result['spriteSheet'],original)
            self.assertEqual(len(result['exportSheets']),1)
            exported=next(iter(self.guest.get('/api/gallery').json['jobs'][0]['exportSheets'].values()))
            media=self.guest.get(exported)
            self.assertEqual(media.status_code,200)
            media.close()
            self.post(self.admin,'jobs/'+jid+'/delete')
            self.assertEqual(self.guest.get(exported).status_code,404)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.data=Path(self.tmp.name)
        self.app=server.create_app(self.data,runner=lambda *_:None)
        self.admin=self.app.test_client()
        self.member=self.app.test_client()
        self.guest=self.app.test_client()
        code=(self.data/'admin-setup-code.txt').read_text()
        self.assertEqual(self.post(self.admin,'register',username='admin',name='관리자',password='long-password',setupCode=code).status_code,200)
        self.post(self.admin,'login',username='admin',password='long-password')
        self.post(self.member,'register',username='member',name='팀원',password='member-password')
        self.uid=self.admin.get('/api/users').json['users'][1]['id']
        buf=io.BytesIO();Image.new('RGB',(32,32)).save(buf,format='PNG')
        self.payload=dict(imageData=base64.b64encode(buf.getvalue()).decode(),width=352,height=608,animationType='idle')
        painted=Image.new('RGBA',(32,32),(0,0,0,0))
        for x in range(10,22):
            for y in range(13,19): painted.putpixel((x,y),(255,255,255,255))
        mask=io.BytesIO();painted.save(mask,format='PNG')
        self.mask_data=base64.b64encode(mask.getvalue()).decode()

    def tearDown(self):
        self.app.stop_worker()
        self.tmp.cleanup()

    def post(self,client,path,**body):
        return client.post('/api/'+path,json=body,headers=HEADERS)

    def approve(self):
        self.post(self.admin,'users/'+str(self.uid),state='approved')
        self.post(self.member,'login',username='member',password='member-password')

    def test_gallery_delete_permissions_and_archive(self):
        self.approve()
        jid=self.post(self.admin,'generate',**self.payload).json['jobId']
        endpoint='jobs/'+jid+'/delete'
        self.assertEqual(self.post(self.guest,endpoint).status_code,401)
        self.assertEqual(self.post(self.member,endpoint).status_code,403)
        self.assertEqual(self.post(self.admin,endpoint).status_code,409)
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            con.execute("UPDATE jobs SET state='complete' WHERE id=?",(jid,))
            con.commit()
        self.assertEqual(self.admin.post('/api/'+endpoint,json={}).status_code,403)
        self.assertEqual(self.post(self.admin,endpoint).status_code,200)
        self.assertEqual(self.guest.get('/api/gallery').json['jobs'],[])
        self.assertEqual(self.guest.get('/gallery-media/'+jid+'/spriteSheet').status_code,404)
        self.assertEqual(self.admin.get('/api/jobs').json['jobs'],[])
        self.assertEqual(self.post(self.admin,endpoint).status_code,404)
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            record=con.execute('SELECT record FROM deleted_jobs WHERE id=?',(jid,)).fetchone()
            self.assertEqual(json.loads(record[0])['state'],'complete')

    def test_auth_approval_revocation(self):
        for path in ['/studio','/api/jobs','/api/status','/outputs/results/x/sheet.png']:
            self.assertEqual(self.guest.get(path).status_code,401)
        self.assertEqual(self.post(self.member,'login',username='member',password='member-password').status_code,403)
        self.approve()
        self.assertEqual(self.member.get('/api/jobs').status_code,200)
        self.assertEqual(self.member.get('/api/users').status_code,403)
        self.assertEqual(self.post(self.member,'users/'+str(self.uid),state='approved').status_code,403)
        self.post(self.admin,'users/'+str(self.uid),state='rejected')
        self.assertEqual(self.member.get('/api/jobs').status_code,401)

    def test_setup_csrf_and_validation(self):
        with tempfile.TemporaryDirectory() as other:
            app=server.create_app(other)
            c=app.test_client()
            self.assertEqual(self.post(c,'register',username='admin',name='a',password='long-password').status_code,403)
        self.assertFalse((self.data/'admin-setup-code.txt').exists())
        response=self.guest.get('/')
        self.assertIn('TEAM WORKSPACE',response.text);response.close()
        studio=self.admin.get('/studio')
        self.assertIn('teamBase',studio.text)
        self.assertIn('X-Sprite-Request',studio.text)
        self.assertEqual(self.admin.post('/api/generate',json=self.payload).status_code,403)
        for change in [dict(subjectType='invalid'),dict(subjectType=[]),dict(width=999),dict(animationType='../bad'),dict(imageData='bad'),dict(prompt=[]),dict(width=None)]:
            self.assertEqual(self.post(self.admin,'generate',**(self.payload|change)).status_code,400)

    def test_custom_frames_private_preview_public_gallery(self):
        for value in (1,65,2.5,True,'8',None):
            self.assertEqual(self.post(self.admin,'generate',**(self.payload|{'frameCount':value})).status_code,400)
        result=self.post(self.admin,'generate',**(self.payload|{'frameCount':64}))
        self.assertEqual(result.status_code,202)
        jid=result.json['jobId']
        preview=self.admin.get('/api/jobs/'+jid).json['referencePreview']
        self.assertEqual(self.guest.get(preview).status_code,401)
        response=self.admin.get(preview)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.mimetype,'image/png')
        response.close()
        self.assertEqual(self.guest.get('/api/gallery').json['jobs'],[])
        self.assertEqual(self.guest.get('/gallery-media/'+jid+'/spriteSheet').status_code,404)
        self.post(self.admin,'jobs/'+jid+'/cancel')
        self.assertEqual(self.admin.get(preview).status_code,404)

    def test_queue_limits_ownership_and_restart(self):
        self.approve()
        ids=[self.post(self.admin,'generate',**self.payload).json['jobId'] for _ in range(3)]
        self.assertEqual(self.post(self.admin,'generate',**self.payload).status_code,429)
        self.assertEqual(self.post(self.member,'jobs/'+ids[0]+'/cancel').status_code,403)
        self.assertEqual(self.post(self.admin,'jobs/'+ids[0]+'/cancel').status_code,200)
        self.assertEqual(self.post(self.admin,'jobs/'+ids[0]+'/cancel').status_code,409)
        other=server.create_app(self.data)
        c=other.test_client();self.post(c,'login',username='admin',password='long-password')
        rows=c.get('/api/jobs').json['jobs']
        self.assertEqual(sum(j['state']=='queued' for j in rows),2)
        self.assertTrue(all(j['owner']=='관리자' for j in rows))
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            con.execute("UPDATE jobs SET state='generating' WHERE id=?",(ids[1],))
            con.commit()
        restarted=server.create_app(self.data)
        c=restarted.test_client();self.post(c,'login',username='admin',password='long-password')
        self.assertEqual(c.get('/api/jobs/'+ids[1]).json['state'],'error')

    def test_fifo_worker_and_protected_media(self):
        self.approve()
        ids=[self.post(c,'generate',**self.payload).json['jobId'] for c in [self.admin,self.member]]
        calls=[];finished=threading.Event()
        old_update=server.engine.update_job
        old_root=server.engine.RESULT_ROOT
        server.engine.RESULT_ROOT=self.data/'results'
        def runner(jid,p):
            calls.append(jid)
            server.engine.update_job(jid,state='generating')
            out=server.engine.RESULT_ROOT/jid;out.mkdir(parents=True)
            Image.new('RGB',(32,32)).save(out/'sheet.png')
            server.engine.update_job(jid,state='complete',spriteSheet=f'/outputs/results/{jid}/sheet.png')
            if len(calls)==2:finished.set()
        app=server.create_app(self.data,runner=runner)
        try:
            app.start_worker()
            self.assertTrue(finished.wait(5))
            app.stop_worker();time.sleep(.6)
            self.assertEqual(calls,ids)
            path=f'/outputs/results/{ids[0]}/sheet.png'
            self.assertEqual(self.guest.get(path).status_code,401)
            gallery=self.guest.get('/api/gallery').json['jobs']
            self.assertEqual(len(gallery),2)
            self.assertTrue(all(not {'owner','userId','imageData','referencePreview','rawVideo','prompt'} & set(j) for j in gallery))
            public=f'/gallery-media/{ids[0]}/spriteSheet'
            response=self.guest.get(public,headers={'Range':'bytes=0-9'})
            self.assertEqual(response.status_code,206);response.close()
            self.assertEqual(self.guest.get(f'/gallery-media/{ids[0]}/rawVideo').status_code,404)
            response=self.member.get(path)
            self.assertEqual(response.status_code,200);response.close()
            response=self.member.get(path,headers={'Range':'bytes=0-9'})
            self.assertEqual(response.status_code,206);response.close()
            self.assertEqual(self.member.get(path.replace('sheet.png','secret.txt')).status_code,404)
            with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
                self.assertTrue(all('imageData' not in json.loads(r[0]) for r in con.execute('SELECT payload FROM jobs')))
        finally:
            app.stop_worker();server.engine.update_job=old_update;server.engine.RESULT_ROOT=old_root

    def test_rigging_queue_result_and_private_player(self):
        valid=dict(imageData=self.payload['imageData'],eyeLeftMask=self.mask_data,eyeRightAbsent=True,
                   mouthMask=self.mask_data,resolution=768,steps=20,seed=7)
        for change in [dict(resolution=999),dict(steps=21),dict(seed=-1),dict(imageData='bad'),
                       dict(eyeLeftMask=''),dict(mouthMask=''),dict(eyeRightAbsent=False)]:
            response=self.post(self.admin,'rigging/generate',**(valid|change))
            self.assertEqual(response.status_code,400)
        response=self.post(self.admin,'rigging/generate',**valid)
        self.assertEqual(response.status_code,202)
        jid=response.json['jobId']
        queued=self.admin.get('/api/jobs/'+jid).json
        self.assertEqual((queued['jobType'],queued['animationType']),('rigging','2D 리깅'))
        self.assertEqual(self.guest.get('/rigging').status_code,401)
        rigging_page=self.admin.get('/rigging')
        self.assertEqual(rigging_page.status_code,200)
        rigging_page.close()
        self.assertEqual(self.guest.get('/rigging-player/index.html').status_code,401)

        old_root=server.rigging.RESULT_ROOT
        root=self.data/'rigging-results';server.rigging.RESULT_ROOT=root
        finished=threading.Event()
        def fake_rigging(job_id,payload):
            folder=root/job_id;folder.mkdir(parents=True)
            for name in ('character.psd','character-unity-parts.zip','composite.png','preview.png','manifest.json'):
                (folder/name).write_bytes(b'asset')
            base=f'/outputs/rigging/{job_id}'
            server.rigging.update_job(job_id,state='complete',message='done',qualityStatus='needs_review',
                partCount=20,expressionCount=2,psd=base+'/character.psd',package=base+'/character-unity-parts.zip',
                composite=base+'/composite.png',preview=base+'/preview.png',manifest=base+'/manifest.json',
                player=f'/rigging-player/index.html?model={base}/character.psd',warnings=[])
            finished.set()
        app=server.create_app(self.data,runner=lambda *_:None,rigging_runner=fake_rigging)
        client=app.test_client();self.post(client,'login',username='admin',password='long-password')
        try:
            app.start_worker();self.assertTrue(finished.wait(5));app.stop_worker();time.sleep(.6)
            job=client.get('/api/jobs/'+jid).json
            self.assertEqual((job['state'],job['partCount'],job['expressionCount']),('complete',20,2))
            asset=client.get(job['package']);self.assertEqual(asset.status_code,200);asset.close()
            self.assertEqual(self.guest.get(job['package']).status_code,401)
            self.assertEqual(client.get(job['package'].replace('.zip','.txt')).status_code,404)
            self.assertFalse(any(item['id']==jid for item in self.guest.get('/api/gallery').json['jobs']))
            internal=self.post(client,'jobs/'+jid+'/shares',kind='internal').json['url']
            external=self.post(client,'jobs/'+jid+'/shares',kind='external').json['url']
            self.assertEqual(self.guest.get(internal).status_code,200)
            internal_page=self.guest.get(internal)
            self.assertIn('/player',internal_page.text);self.assertNotIn('/player?model=',internal_page.text);internal_page.close()
            psd=self.guest.get(internal+'/asset/character.psd')
            self.assertEqual(psd.status_code,200);self.assertIn('attachment',psd.headers['Content-Disposition']);psd.close()
            player=self.guest.get(internal+'/player')
            self.assertEqual(player.status_code,200);self.assertIn('/shared-rig-player/',player.text);self.assertIn('SHARED_MODEL_URL',player.text);player.close()
            self.assertEqual(self.guest.get('/shared-rig-player/lib/app.js').status_code,200)
            self.assertEqual(self.guest.get('/shared-rig-player/sample.psd').status_code,404)
            self.assertEqual(self.guest.get(external).status_code,200)
            self.assertEqual(self.guest.get(external+'/asset/composite.png').status_code,200)
            self.assertEqual(self.guest.get(external+'/asset/character.psd').status_code,404)
            gallery=client.get('/api/gallery').json['jobs']
            self.assertTrue(any(item['id']==jid and item['jobType']=='rigging' for item in gallery))
        finally:
            app.stop_worker();server.rigging.RESULT_ROOT=old_root

if __name__=='__main__':unittest.main()
