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
from urllib.parse import urlsplit
import zipfile
from unittest.mock import patch
from pathlib import Path
from PIL import Image, ImageDraw
import team_server as server

HEADERS={'X-Sprite-Request':'1'}

class TeamTests(unittest.TestCase):
    def test_subtle_example_settings_are_saved_and_require_character_matte(self):
        settings=dict(combatEffect='subtle',effectStrength='low',effectDescription='',motionPadding=58,
            pixelOutput=False,removeBackground=True,backgroundRemoval='flat',animationType='custom',loop=False,
            motionSpeed=1.25,trimAction=False,frameCount=24)
        with patch.object(server.engine.image_background,'status',return_value=dict(ready=False)):
            rejected=self.post(self.admin,'generate',**(self.payload|settings))
            self.assertEqual(rejected.status_code,400)
            self.assertIn('작은 검기',rejected.json['error'])
        with patch.object(server.engine.image_background,'status',return_value=dict(ready=True)):
            response=self.post(self.admin,'generate',**(self.payload|settings))
            self.assertEqual(response.status_code,202,response.json)
            with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
                saved=json.loads(con.execute('SELECT payload FROM jobs WHERE id=?',(response.json['jobId'],)).fetchone()[0])
            for key,value in settings.items():self.assertEqual(saved[key],value)

    def test_joint_effect_validation_settings_and_reuse(self):
        for change in [dict(combatEffect='invalid'),dict(combatEffect='custom'),dict(effectDescription=[]),
                       dict(pixelOutput=1),dict(pixelOutput=True,removeBackground=True,backgroundRemoval='ai')]:
            result=self.post(self.admin,'generate',**(self.payload|change))
            self.assertEqual(result.status_code,400,result.json)
        settings=dict(combatEffect='blue_slash',effectStrength='high',effectDescription='gold sparks',
                      pixelOutput=True,pixelColorLock=False,removeBackground=True,backgroundRemoval='flat')
        result=self.post(self.admin,'generate',**(self.payload|settings))
        self.assertEqual(result.status_code,202,result.json)
        jid=result.json['jobId']
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            saved=json.loads(con.execute('SELECT payload FROM jobs WHERE id=?',(jid,)).fetchone()[0])
            con.execute("UPDATE jobs SET state='complete' WHERE id=?",(jid,));con.commit()
        for k,v in settings.items():self.assertEqual(saved[k],v)
        self.approve()
        reused=self.admin.get('/api/gallery/'+jid).json['job']['settings']
        for k,v in settings.items():self.assertEqual(reused[k],v)

    def test_image_poll_keeps_generation_settings_without_input_pixels(self):
        uid=self.admin.get('/api/me').json['user']['id']
        settings=dict(jobType='image',model='wai-cutscene-counter',prompt='navy coat',
                      denoise=.8,assetSpec=dict(type='side',facing='left',directionCount=1),
                      imageData='private pixels',maskData='private mask')
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',('image-poll',uid,'complete',1,1,json.dumps(settings),'{}'))
            con.commit()
        job=self.admin.get('/api/jobs/image-poll').json
        self.assertEqual(job['settings']['model'],'wai-cutscene-counter')
        self.assertEqual(job['settings']['assetSpec']['facing'],'left')
        self.assertFalse({'imageData','maskData'} & job['settings'].keys())
        self.assertEqual(self.guest.get('/api/jobs/image-poll').status_code,401)

    def test_reference_caption_auth_validation_and_local_result(self):
        buf=io.BytesIO();Image.new('RGB',(32,48),'red').save(buf,format='PNG')
        image='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()
        self.assertEqual(self.post(self.guest,'images/describe',imageData=image).status_code,401)
        self.assertEqual(self.post(self.admin,'images/describe',imageData='invalid').status_code,400)
        with patch.object(server.image_caption,'analyze',return_value=dict(prompt='black hood, long coat',summary='후드 확인',provider='local')) as analyze:
            response=self.post(self.admin,'images/describe',imageData=image)
            self.assertEqual(response.status_code,200);self.assertEqual(response.json['provider'],'local')
            self.assertEqual(analyze.call_args.args[0].size,(32,48))
        with patch.object(server.image_caption,'analyze',side_effect=server.image_caption.CaptionBusy('busy')):
            self.assertEqual(self.post(self.admin,'images/describe',imageData=image).status_code,429)


    def test_asset_direction_plan_is_saved_as_single_direction_job(self):
        bad=self.post(self.admin,'generate',**(self.payload|{'assetSpec':{'type':'side','directionCount':16}}))
        self.assertEqual(bad.status_code,400)
        response=self.post(self.admin,'generate',**(self.payload|{'assetSpec':{'type':'topdown','directionCount':8,'facing':'back'}}))
        self.assertEqual(response.status_code,202)
        job=self.admin.get('/api/jobs/'+response.json['jobId']).json
        self.assertEqual(job['assetSpec']['directionCount'],8)
        self.assertEqual(job['assetSpec']['outputMode'],'single-direction')
        self.assertEqual(job['assetSpec']['facing'],'back')

    def test_sprite_workflow_gating(self):
        invalid=self.post(self.admin,'generate',**(self.payload|{'workflowId':'unknown'}))
        self.assertEqual(invalid.status_code,400)
        p=self.payload|{'workflowId':'fasth3-sprite','width':512,'height':512}
        with patch.object(server.engine.sprite_workflows,'status',return_value=[dict(id='standard',ready=True),dict(id='fasth3-sprite',ready=False)]):
            self.assertEqual(self.post(self.admin,'generate',**p).status_code,400)
        with patch.object(server.engine.sprite_workflows,'status',return_value=[dict(id='standard',ready=True),dict(id='fasth3-sprite',ready=True)]):
            response=self.post(self.admin,'generate',**p)
            self.assertEqual(response.status_code,202)
            self.assertEqual(self.admin.get('/api/jobs/'+response.json['jobId']).json['workflowId'],'fasth3-sprite')

    def test_large_attack_padding_is_saved_and_bounded(self):
        for padding in (40,50,58):
            response=self.post(self.admin,'generate',**(self.payload|{'motionPadding':padding}))
            self.assertEqual(response.status_code,202,response.json)
            with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
                saved=json.loads(con.execute('SELECT payload FROM jobs WHERE id=?',(response.json['jobId'],)).fetchone()[0])
            self.assertEqual(saved['motionPadding'],padding)
        for padding in (True,45,60,'50'):
            self.assertEqual(self.post(self.admin,'generate',**(self.payload|{'motionPadding':padding})).status_code,400)

    def test_fast_one_shot_options_are_validated_and_saved(self):
        p=self.payload|dict(animationType='attack',loop=False,motionSpeed=2,trimAction=True)
        response=self.post(self.admin,'generate',**p)
        self.assertEqual(response.status_code,202,response.json)
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            saved=json.loads(con.execute('SELECT payload FROM jobs WHERE id=?',(response.json['jobId'],)).fetchone()[0])
        self.assertEqual(saved['motionSpeed'],2);self.assertTrue(saved['trimAction'])
        for change in (dict(motionSpeed=True),dict(motionSpeed=0),dict(trimAction=1),dict(loop=True),dict(animationType='run')):
            self.assertEqual(self.post(self.admin,'generate',**(p|change)).status_code,400)

    def test_loop_variant_permissions_preservation_and_public_assets(self):
        self.approve()
        jid=self.post(self.admin,'generate',**(self.payload|{'loop':True})).json['jobId']
        endpoint='jobs/'+jid+'/loop'
        self.assertEqual(self.post(self.guest,endpoint).status_code,401)
        self.assertEqual(self.post(self.member,endpoint).status_code,403)
        self.assertEqual(self.post(self.admin,endpoint).status_code,409)
        root=self.data/'loop-results';folder=root/jid;folder.mkdir(parents=True)
        video=folder/'idle.mp4';video.write_bytes(b'original-video')
        original=dict(video=f'/outputs/results/{jid}/idle.mp4',spriteSheet=f'/outputs/results/{jid}/original.png')
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            con.execute("UPDATE jobs SET state='complete',result=? WHERE id=?",(json.dumps(original),jid));con.commit()
        def optimize(source,output):
            output.write_bytes(b'corrected-video')
            return dict(method='trim',quality='good',version=1)
        def sheet(source,output,*args):Image.new('RGBA',(8,8)).save(output)
        with patch.object(server.engine,'RESULT_ROOT',root),patch.object(server.engine.sprite_loop,'optimize_video',side_effect=optimize),patch.object(server.engine,'make_sprite_sheet',side_effect=sheet):
            result=self.post(self.admin,endpoint)
            self.assertEqual(result.status_code,200)
            self.assertEqual(self.post(self.admin,endpoint).status_code,409)
            job=self.admin.get('/api/jobs/'+jid).json
            self.assertEqual(job['video'],original['video'])
            self.assertEqual(job['spriteSheet'],original['spriteSheet'])
            self.assertEqual(video.read_bytes(),b'original-video')
            self.assertEqual(self.guest.get(result.json['loopVideo']).status_code,401)
            gallery=next(j for j in self.guest.get('/api/gallery').json['jobs'] if j['id']==jid)
            self.assertEqual(gallery['loopReport']['quality'],'good')
            response=self.guest.get(gallery['loopVideo']);self.assertEqual(response.data,b'corrected-video');response.close()
            self.post(self.admin,'jobs/'+jid+'/delete')
            self.assertEqual(self.guest.get(gallery['loopVideo']).status_code,404)

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

    def test_ai_reextract_preserves_original_and_public_download(self):
        jid=self.post(self.admin,'generate',**self.payload).json['jobId']
        root=self.data/'results';folder=root/jid;folder.mkdir(parents=True)
        (folder/'idle.mp4').write_bytes(b'original-video')
        original=f'/outputs/results/{jid}/original.png'
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            con.execute("UPDATE jobs SET state='complete',result=? WHERE id=?",(json.dumps(dict(video=f'/outputs/results/{jid}/idle.mp4',spriteSheet=original)),jid));con.commit()
        def extract(video,output,count,loop,transparent,tolerance,method):
            self.assertEqual(method,'ai');Image.new('RGBA',(32,48),'red').save(output);Image.new('RGBA',(32,48),(255,0,0,50)).save(transparent)
        with patch.object(server.engine,'RESULT_ROOT',root),patch.object(server.engine.image_background,'status',return_value=dict(ready=True)),patch.object(server.engine,'make_sprite_sheet',side_effect=extract):
            response=self.post(self.admin,'jobs/'+jid+'/extract',frameCount=4,removeBackground=True,backgroundRemoval='ai')
            self.assertEqual(response.status_code,200)
            job=self.admin.get('/api/jobs/'+jid).json
            self.assertEqual(job['spriteSheet'],original);self.assertEqual(len(job['exportSheets']),2)
            public=self.guest.get('/api/gallery').json['jobs'][0]
            path=next(path for key,path in public['exportSheets'].items() if key.endswith('_transparent'))
            media=self.guest.get(path);self.assertEqual(media.status_code,200);media.close()
            self.assertEqual((folder/'idle.mp4').read_bytes(),b'original-video')
        with patch.object(server.engine.image_background,'status',return_value=dict(ready=False)):
            self.assertEqual(self.post(self.admin,'generate',**(self.payload|dict(removeBackground=True,backgroundRemoval='ai'))).status_code,400)
        self.assertEqual(self.post(self.admin,'generate',**(self.payload|dict(backgroundRemoval='unknown'))).status_code,400)

    def test_reextract_preserves_original(self):
        self.approve()
        jid=self.post(self.admin,'generate',**self.payload).json['jobId']
        endpoint='jobs/'+jid+'/extract'
        self.assertEqual(self.post(self.guest,endpoint,frameCount=64).status_code,401)
        self.assertEqual(self.post(self.member,endpoint,frameCount=64).status_code,403)
        self.assertEqual(self.post(self.admin,endpoint,frameCount=129).status_code,400)
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
        ImageDraw.Draw(painted).line((10,17,22,15),fill=(255,255,255,255),width=2)
        mask=io.BytesIO();painted.save(mask,format='PNG')
        self.mask_data=base64.b64encode(mask.getvalue()).decode()
        mouth=Image.new('RGBA',(32,32),(0,0,0,0))
        ImageDraw.Draw(mouth).rectangle((13,15,19,17),fill=(255,255,255,255))
        mouth_data=io.BytesIO();mouth.save(mouth_data,format='PNG')
        self.mouth_mask_data=base64.b64encode(mouth_data.getvalue()).decode()

    def tearDown(self):
        self.app.stop_worker()
        self.tmp.cleanup()

    def test_public_shells_render_from_templates_with_escaped_titles(self):
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            con.execute("INSERT INTO jobs VALUES('r9',1,'complete',1,1,?,'{}')",(json.dumps(dict(jobType='rigging')),))
            con.execute("INSERT INTO public_live2d VALUES('tok','r9','<b>x</b>',1,1,1,NULL)")
            con.execute("INSERT INTO rig_shares VALUES('share1','r9','internal',1,1,NULL)")
            con.commit()
        listing=self.guest.get('/live2d');self.assertIn('&lt;b&gt;x&lt;/b&gt;',listing.text);self.assertNotIn('{{',listing.text)
        work=self.guest.get('/live2d/tok');self.assertIn('/live2d/tok/player',work.text);self.assertNotIn('<b>x</b>',work.text)
        share=self.guest.get('/share/rig/share1');self.assertIn('/share/rig/share1/inspector',share.text);self.assertIn('/guide#rig-studio',share.text)

    def test_admin_public_list_reports_stale_snapshots(self):
        self.assertEqual(self.member.get('/api/admin/public-live2d').status_code,401)
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            con.execute("INSERT INTO jobs VALUES('r9',1,'complete',1,1,?,'{}')",(json.dumps(dict(jobType='rigging')),))
            con.execute("INSERT INTO public_live2d VALUES('tok','r9','캐릭터',1,1,1,NULL)")
            con.commit()
        snapshot=self.data/'public-live2d'/'tok';snapshot.mkdir(parents=True);(snapshot/'character.psd').write_bytes(b'8BPSold')
        with tempfile.TemporaryDirectory() as results:
            source=Path(results)/'r9';source.mkdir();(source/'character.psd').write_bytes(b'8BPSnew')
            with patch.object(server.rigging,'RESULT_ROOT',Path(results)):
                item=self.admin.get('/api/admin/public-live2d').json['items'][0]
                self.assertEqual((item['jobId'],item['stale'],item['title']),('r9',True,'캐릭터'))
                (snapshot/'character.psd').write_bytes(b'8BPSnew')
                self.assertFalse(self.admin.get('/api/admin/public-live2d').json['items'][0]['stale'])

    def test_unified_guide_is_public_and_old_address_redirects(self):
        page=self.guest.get('/guide')
        self.assertEqual(page.status_code,200)
        for anchor in ('getting-started','rig-studio-expressions','export-unity','sharing-who','troubleshooting'):
            self.assertIn(f'id="{anchor}"',page.text)
        old=self.guest.get('/layer-editing-guide')
        self.assertEqual(old.status_code,301)
        self.assertTrue(old.headers['Location'].endswith('guide#rig-studio'))

    def test_login_limit_is_scoped_to_failures_per_account(self):
        for _ in range(10):
            self.assertEqual(self.post(self.guest,'login',username='admin',password='wrong-password').status_code,401)
        self.assertEqual(self.post(self.guest,'login',username='admin',password='long-password').status_code,429)
        self.approve()
        for _ in range(35):
            self.assertEqual(self.post(self.member,'login',username='member',password='member-password').status_code,200,'successes are not counted')

    def test_login_limit_only_trusts_forwarded_address_when_enabled(self):
        def fail(client,address):
            return client.post('/api/login',json=dict(username='admin',password='wrong-password'),
                               headers={'X-Sprite-Request':'1','X-Forwarded-For':'6.6.6.6, '+address},environ_base={'REMOTE_ADDR':'127.0.0.1'}).status_code
        with patch.dict('os.environ',{'SPRITE_TRUST_PROXY':'1'}):
            self.assertEqual([fail(self.guest,'203.0.113.9') for _ in range(11)][-1],429)
            self.assertEqual(fail(self.guest,'203.0.113.10'),401,'another client is not locked out')
        with patch.dict('os.environ',{'SPRITE_TRUST_PROXY':'0'}):
            self.assertEqual([fail(self.guest,str(n)) for n in range(11)][-1],429,'header is ignored unless enabled')

    def test_gallery_filters_search_and_detail(self):
        self.approve()
        admin_id=self.admin.get('/api/me').json['user']['id']
        rows=[('v1',admin_id,'complete',{'animationType':'Idle Knight','prompt':'breathe','imageData':'secret'}),
              ('r1',self.uid,'complete',{'jobType':'rigging','animationType':'후드 캐릭터','rigMode':'illustration','mouthMask':'secret'}),
              ('m1',self.uid,'complete',{'jobType':'music','animationType':'50%_forest','title':'Forest'}),
              ('q1',admin_id,'queued',{'animationType':'Idle Knight'})]
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            for index,(jid,uid,state,payload) in enumerate(rows):
                con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(jid,uid,state,100+index,100+index,json.dumps(payload),'{}'))
            con.commit()
        ids=lambda client,query='':[job['id'] for job in client.get('/api/gallery'+query).json['jobs']]
        self.assertEqual(ids(self.guest),['v1'])
        self.assertEqual(ids(self.guest,'?type=music'),['v1'],'guests only ever see sprite videos')
        self.assertNotIn('owner',self.guest.get('/api/gallery').json['jobs'][0])
        self.assertEqual(ids(self.admin),['m1','r1','v1'])
        self.assertEqual(ids(self.admin,'?type=rigging'),['r1'])
        self.assertEqual(ids(self.admin,'?owner=me'),['v1'])
        self.assertEqual(ids(self.member,'?owner=me'),['m1','r1'])
        self.assertEqual(ids(self.admin,'?q=후드'),['r1'])
        self.assertEqual(ids(self.admin,'?q=Forest'),['m1'],'title is searchable')
        self.assertEqual(ids(self.admin,'?q=50%25_'),['m1'],'LIKE wildcards are matched literally')
        self.assertEqual(ids(self.admin,'?q=%25'),['m1'])
        self.assertEqual(ids(self.admin,'?q=관리자'),['v1'],'approved viewers can search by owner name')
        self.assertEqual(ids(self.guest,'?q=관리자'),[])
        paged=self.admin.get('/api/gallery?size=2&page=2').json
        self.assertEqual((paged['pages'],paged['total'],[job['id'] for job in paged['jobs']]),(2,3,['v1']))
        self.assertEqual(self.admin.get('/api/gallery?size=x').status_code,400)
        self.assertEqual(self.admin.get('/api/gallery?type=bad').status_code,400)
        detail=self.admin.get('/api/gallery/r1').json['job']
        self.assertEqual((detail['id'],detail['jobType'],detail['owner']),('r1','rigging','팀원'))
        self.assertEqual(detail['settings'],{'jobType':'rigging','animationType':'후드 캐릭터','rigMode':'illustration'})
        self.assertNotIn('imageData',self.admin.get('/api/gallery/v1').json['job']['settings'])
        guest_detail=self.guest.get('/api/gallery/v1').json['job']
        self.assertNotIn('settings',guest_detail);self.assertNotIn('owner',guest_detail)
        self.assertEqual(self.guest.get('/api/gallery/r1').status_code,404)
        self.assertEqual(self.admin.get('/api/gallery/q1').status_code,404)
        self.assertEqual(self.admin.get('/api/gallery/missing').status_code,404)

    def test_account_profile_password_and_sessions(self):
        self.approve()
        self.assertEqual(self.post(self.guest,'me/profile',name='x').status_code,401)
        self.assertEqual(self.post(self.member,'me/profile',name='').status_code,400)
        self.assertEqual(self.post(self.member,'me/profile',name='새 이름').json['user']['name'],'새 이름')
        self.assertEqual(self.member.get('/api/me').json['user']['name'],'새 이름')
        other=self.app.test_client();self.post(other,'login',username='member',password='member-password')
        legacy=self.app.test_client();self.post(legacy,'login',username='member',password='member-password')
        with legacy.session_transaction() as saved:
            del saved['pwv']  # a cookie issued before fingerprints existed
        self.assertEqual(legacy.get('/api/jobs').status_code,200,'legacy sessions adopt the current fingerprint')
        self.assertEqual(self.post(self.member,'me/password',currentPassword='wrong-password',newPassword='another-password').status_code,403)
        self.assertEqual(self.post(self.member,'me/password',currentPassword='member-password',newPassword='short').status_code,400)
        self.assertEqual(self.post(self.member,'me/password',currentPassword='member-password',newPassword='member-password').status_code,400)
        self.assertEqual(self.post(self.member,'me/password',currentPassword='member-password',newPassword='brand-new-password').status_code,200)
        self.assertEqual(self.member.get('/api/jobs').status_code,200,'the changing browser stays signed in')
        for client in (other,legacy):
            self.assertEqual(client.get('/api/jobs').status_code,401,'other sessions end after a password change')
            self.assertIsNone(client.get('/api/me').json['user'])
        fresh=self.app.test_client()
        self.assertEqual(self.post(fresh,'login',username='member',password='member-password').status_code,401)
        self.assertEqual(self.post(fresh,'login',username='member',password='brand-new-password').status_code,200)

    def test_summary_share_revoke_and_rename(self):
        self.approve()
        admin_id=self.admin.get('/api/me').json['user']['id']
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            for jid,uid,payload in [('rig-a',self.uid,{'jobType':'rigging','animationType':'2D 리깅'}),('vid-a',self.uid,{'animationType':'idle'}),('vid-b',admin_id,{'animationType':'walk'})]:
                con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(jid,uid,'complete',1,1,json.dumps(payload),json.dumps({'composite':'/c.png'})))
            con.commit()
        summary=self.member.get('/api/me/summary').json
        self.assertEqual((summary['counts'],summary['active'],summary['activeLimit'],summary['shares']),({'video':1,'rigging':1,'music':0,'image':0},0,3,[]))
        first=self.post(self.member,'jobs/rig-a/shares',kind='internal').json['url']
        shares=self.member.get('/api/me/summary').json['shares']
        self.assertEqual([(item['jobId'],item['url']) for item in shares],[('rig-a',first)])
        token=first.rsplit('/',1)[1]
        self.assertEqual(self.post(self.guest,f'shares/{token}/revoke').status_code,401)
        self.assertEqual(self.post(self.member,'shares/missing/revoke').status_code,404)
        self.assertEqual(self.post(self.member,f'shares/{token}/revoke').status_code,200)
        self.assertEqual(self.member.get('/api/me/summary').json['shares'],[])
        self.assertEqual(self.guest.get(first).status_code,404,'revoked links stop working')
        self.assertNotEqual(self.post(self.member,'jobs/rig-a/shares',kind='internal').json['url'],first,'a new link replaces the revoked one')

        self.assertEqual(self.post(self.member,'jobs/vid-b/title',title='남의 결과').status_code,403)
        self.assertEqual(self.post(self.member,'jobs/rig-a/title',title='x'*61).status_code,400)
        self.assertEqual(self.post(self.member,'jobs/missing/title',title='a').status_code,404)
        self.assertEqual(self.post(self.member,'jobs/rig-a/title',title='  후드   캐릭터 ').json['title'],'후드 캐릭터')
        detail=self.member.get('/api/gallery/rig-a').json['job']
        self.assertEqual(detail['title'],'후드 캐릭터');self.assertNotIn('resultTitle',detail['settings'])
        self.assertEqual([job['id'] for job in self.member.get('/api/gallery?q=후드').json['jobs']],['rig-a'])
        self.assertEqual(self.post(self.admin,'jobs/rig-a/title',title='').json['title'],None,'admins may rename; empty resets')
        self.assertIsNone(self.member.get('/api/gallery/rig-a').json['job']['title'])

    def test_ui_assets_are_public_with_cache_policy(self):
        css=self.guest.get('/assets/ui.css')
        self.assertEqual(css.status_code,200)
        self.assertIn('text/css',css.content_type)
        self.assertEqual(css.headers['Cache-Control'],'no-cache')
        self.assertTrue(css.headers.get('ETag'))
        css.close()
        font=self.guest.get('/assets/fonts/pretendard/pretendardvariable-dynamic-subset.css')
        self.assertEqual(font.status_code,200)
        self.assertIn('immutable',font.headers['Cache-Control'])
        font.close()
        self.assertEqual(self.guest.get('/assets/../team_server.py').status_code,404)
        self.assertEqual(self.guest.get('/assets/missing.css').status_code,404)

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
        self.assertIn('aria-label="작업 공간"',response.text)
        self.assertIn('assets/ui.css',response.text)
        self.assertIn('href="live2d"',response.text);response.close()  # the landing links the public Live2D list
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
        self.approve()
        valid=dict(imageData=self.payload['imageData'],eyeLeftMask=self.mask_data,eyeRightAbsent=True,
                   eyebrowLeftMask=self.mouth_mask_data,mouthMask=self.mouth_mask_data,mouthState='closed',resolution=768,steps=20,seed=7,
                   maskVersion=2,eyeInputMode='closed-stroke')
        for change in [dict(resolution=999),dict(steps=21),dict(seed=-1),dict(imageData='bad'),
                       dict(eyeLeftMask=''),dict(mouthMask=''),dict(eyeRightAbsent=False),dict(preserveOriginalEyes='yes'),dict(preserveOriginalEyebrows='yes'),dict(mouthState='unknown'),dict(rigMode='unknown'),dict(separationBackend='unknown')]:
            response=self.post(self.admin,'rigging/generate',**(valid|change))
            self.assertEqual(response.status_code,400)
        wide=Image.new('RGBA',(32,32),(0,0,0,0));ImageDraw.Draw(wide).rectangle((1,14,30,17),fill=(255,255,255,255))
        encoded=io.BytesIO();wide.save(encoded,format='PNG')
        too_wide='data:image/png;base64,'+base64.b64encode(encoded.getvalue()).decode()
        response=self.post(self.admin,'rigging/generate',**(valid|{'mouthMask':too_wide}))
        self.assertEqual(response.status_code,400)
        self.assertIn('입 마스크가 너무 넓습니다',response.json['error'])
        tall=Image.new('RGBA',(32,32),(0,0,0,0));ImageDraw.Draw(tall).line((15,5,16,26),fill=(255,255,255,255),width=2)
        encoded=io.BytesIO();tall.save(encoded,format='PNG')
        too_tall='data:image/png;base64,'+base64.b64encode(encoded.getvalue()).decode()
        response=self.post(self.admin,'rigging/generate',**(valid|{'eyeLeftMask':too_tall}))
        self.assertEqual(response.status_code,400)
        self.assertIn('감은 눈 선',response.json['error'])
        response=self.post(self.admin,'rigging/generate',**valid)
        self.assertEqual(response.status_code,202)
        jid=response.json['jobId']
        queued=self.admin.get('/api/jobs/'+jid).json
        self.assertEqual((queued['jobType'],queued['animationType']),('rigging','2D 리깅'))
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            stored=json.loads(con.execute('SELECT payload FROM jobs WHERE id=?',(jid,)).fetchone()[0])
        self.assertEqual((stored['maskVersion'],stored['eyeInputMode'],stored['preserveOriginalEyes'],stored['preserveOriginalEyebrows'],stored['mouthState'],stored['rigMode'],stored['separationBackend']),(2,'closed-stroke',True,True,'closed','illustration','standard'))
        self.assertIn('eyebrowLeftMask',stored)
        self.assertEqual(self.guest.get('/rigging').status_code,401)
        rigging_page=self.admin.get('/rigging')
        self.assertEqual(rigging_page.status_code,200)
        self.assertIn('눈 마스킹 가이드',rigging_page.text)
        self.assertIn('maskGuideTab',rigging_page.text)
        self.assertIn('preserveOriginalEyes',rigging_page.text)
        self.assertIn('eyebrowLeft',rigging_page.text)
        self.assertIn('preserveOriginalEyebrows',rigging_page.text)
        self.assertIn('mouthState',rigging_page.text)
        self.assertIn('qwen21-experimental',rigging_page.text)
        rigging_page.close()
        team_page=self.admin.get('/')
        self.assertIn('assets/results.js',team_page.text)
        team_page.close()
        results_script=self.admin.get('/assets/results.js')
        self.assertIn('갤러리에서 내리기',results_script.text)
        results_script.close()
        self.assertEqual(self.guest.get('/rigging-player/index.html').status_code,401)

        old_root=server.rigging.RESULT_ROOT
        root=self.data/'rigging-results';server.rigging.RESULT_ROOT=root
        finished=threading.Event()
        def fake_rigging(job_id,payload):
            folder=root/job_id;folder.mkdir(parents=True)
            for name in ('character.psd','character-unity-parts.zip','composite.png','preview.png','manifest.json'):
                (folder/name).write_bytes(b'asset')
            (folder/'character.psd').write_bytes(b'8BPS-public-snapshot-v1')
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
            self.assertEqual(self.post(client,'jobs/'+jid+'/shares',kind='external').status_code,410)
            with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
                con.execute('INSERT INTO rig_shares VALUES(?,?,?,?,?,NULL)',('legacy-external',jid,'external',time.time(),1));con.commit()
            external='/share/rig/legacy-external'
            self.assertEqual(self.guest.get(internal).status_code,200)
            internal_page=self.guest.get(internal)
            self.assertIn('/player',internal_page.text);self.assertIn('/inspector',internal_page.text);self.assertIn('레이어 편집',internal_page.text);self.assertNotIn('/player?model=',internal_page.text);internal_page.close()
            psd=self.guest.get(internal+'/asset/character.psd')
            self.assertEqual(psd.status_code,200);self.assertIn('attachment',psd.headers['Content-Disposition']);psd.close()
            player=self.guest.get(internal+'/player')
            self.assertEqual(player.status_code,200);self.assertIn('/shared-rig-player/',player.text);self.assertIn('SHARED_MODEL_URL',player.text);player.close()
            shared_app=self.guest.get('/shared-rig-player/lib/app.js')
            self.assertEqual(shared_app.status_code,200)
            self.assertIn("window.SHARED_MODEL_URL||QUERY.get('model')",shared_app.text)
            self.assertIn("bn!=='eye_open_original'",shared_app.text)
            shared_app.close()
            self.assertEqual(self.guest.get('/shared-rig-player/sample.psd').status_code,404)
            inspector=self.guest.get(internal+'/inspector');self.assertEqual(inspector.status_code,200);self.assertIn('moveTool',inspector.text);inspector.close()
            self.assertEqual(self.guest.get(external).status_code,410)
            self.assertEqual(self.post(self.guest,'jobs/'+jid+'/public-live2d',action='publish').status_code,401)
            self.assertEqual(self.post(self.member,'jobs/'+jid+'/public-live2d',action='publish').status_code,403)
            published=self.post(client,'jobs/'+jid+'/public-live2d',action='publish',title='공개 테스트').json['publicLive2d']
            public_url=published['url'];token=published['token']
            self.assertEqual(self.guest.get(external).status_code,302)
            public_page=self.guest.get(public_url);self.assertEqual(public_page.status_code,200);self.assertIn('공개 테스트',public_page.text);self.assertIn('메인 홈페이지',public_page.text);public_page.close()
            public_player=self.guest.get(public_url+'/player');self.assertEqual(public_player.status_code,200);self.assertIn('/character.psd',public_player.text);public_player.close()
            public_psd=self.guest.get(public_url+'/character.psd');self.assertEqual(public_psd.status_code,200);self.assertNotIn('attachment',public_psd.headers.get('Content-Disposition',''));self.assertEqual(public_psd.data,b'8BPS-public-snapshot-v1');public_psd.close()
            public_preview=self.guest.get(public_url+'/preview.png');self.assertEqual(public_preview.status_code,200);public_preview.close()
            self.assertEqual(self.guest.get(public_url+'/manifest.json').status_code,404)
            listing=self.guest.get('/api/public-live2d').json['items'];self.assertEqual((len(listing),listing[0]['token']),(1,token))
            index=self.guest.get('/live2d');self.assertIn('공개 테스트',index.text);self.assertIn('메인 홈페이지',index.text);index.close()
            (root/jid/'character.psd').write_bytes(b'8BPS-public-snapshot-v2')
            unchanged_psd=self.guest.get(public_url+'/character.psd');self.assertEqual(unchanged_psd.data,b'8BPS-public-snapshot-v1');unchanged_psd.close()
            refreshed=self.post(client,'jobs/'+jid+'/public-live2d',action='publish',title='갱신 테스트').json['publicLive2d']
            refreshed_psd=self.guest.get(public_url+'/character.psd');self.assertEqual(refreshed['token'],token);self.assertEqual(refreshed_psd.data,b'8BPS-public-snapshot-v2');refreshed_psd.close()
            self.assertEqual(self.post(client,'jobs/'+jid+'/public-live2d',action='unpublish').status_code,200)
            self.assertEqual(self.guest.get(public_url).status_code,404)
            self.assertTrue((self.data/'public-live2d'/token/'character.psd').is_file())
            republished=self.post(client,'jobs/'+jid+'/public-live2d',action='publish').json['publicLive2d'];self.assertEqual(republished['token'],token)
            self.assertEqual(self.guest.get(external+'/asset/character.psd').status_code,404)
            self.assertEqual(self.guest.get(external+'/inspector').status_code,404)
            self.assertEqual(self.guest.get(external+'/rig-edit').status_code,404)
            self.assertEqual(self.guest.get(external+'/layers/front_hair').status_code,404)
            self.assertEqual(self.guest.get(external+'/versions/0/composite.png').status_code,404)
            self.assertEqual(self.guest.post(external+'/rig-edit/revisions',json={'revision':0,'operations':[]},headers=HEADERS).status_code,404)
            self.assertEqual(self.guest.post(external+'/rig-edit/restore',json={'revision':0,'targetRevision':0},headers=HEADERS).status_code,404)
            gallery=client.get('/api/gallery').json['jobs']
            self.assertTrue(any(item['id']==jid and item['jobType']=='rigging' and item['publicLive2d']['token']==token for item in gallery))
            self.assertEqual(self.post(client,'jobs/'+jid+'/delete').status_code,200)
            self.assertEqual(self.guest.get(public_url).status_code,404)
        finally:
            app.stop_worker();server.rigging.RESULT_ROOT=old_root

    def test_qwen_rigging_requires_models_and_records_backend(self):
        self.approve()
        valid=dict(imageData=self.payload['imageData'],eyeLeftMask=self.mask_data,eyeRightAbsent=True,
                   mouthMask=self.mouth_mask_data,mouthState='closed',resolution=768,steps=20,
                   eyeInputMode='area',separationBackend='qwen21-experimental')
        with patch.object(server.rigging,'status_payload',return_value={'qwen21Ready':False}):
            response=self.post(self.admin,'rigging/generate',**valid)
        self.assertEqual(response.status_code,503)
        with patch.object(server.rigging,'status_payload',return_value={'qwen21Ready':True}):
            response=self.post(self.admin,'rigging/generate',**valid)
        self.assertEqual(response.status_code,202)
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            stored=json.loads(con.execute('SELECT payload FROM jobs WHERE id=?',(response.json['jobId'],)).fetchone()[0])
        self.assertEqual(stored['separationBackend'],'qwen21-experimental')

    def test_rigging_layer_editor_permissions_assets_and_revision(self):
        self.approve()
        jid='a'*32
        root=self.data/'edit-results';folder=root/jid;folder.mkdir(parents=True)
        layer=io.BytesIO();Image.new('RGBA',(12,10),(20,30,40,255)).save(layer,format='PNG')
        manifest={'schemaVersion':1,'status':'ready','canvas':{'width':32,'height':32,'origin':'top-left'},
                  'parts':[{'id':'headwear','runtimeName':'headwear','sourceLayerName':'headwear','file':'layers/headwear.png','left':5,'top':4,'width':12,'height':10}],
                  'expressions':[{'id':'eyebrow','runtimeName':'eyebrow','sourceLayerName':'eyebrow','file':'expressions/eyebrow.png','left':5,'top':4,'width':12,'height':10}],
                  'anchors':{},'warnings':[],'synthetic':{'eye':False,'mouth':False}}
        (folder/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
        with zipfile.ZipFile(folder/'character-unity-parts.zip','w') as archive:
            archive.writestr('layers/headwear.png',layer.getvalue())
            archive.writestr('expressions/eyebrow.png',layer.getvalue())
            archive.writestr('manifest.json',json.dumps(manifest))
        for name in ('character.psd','composite.png'):(folder/name).write_bytes(b'asset')
        (folder/'showcase.webp').write_bytes(b'old animation')
        result={'state':'complete','psd':f'/outputs/rigging/{jid}/character.psd','package':f'/outputs/rigging/{jid}/character-unity-parts.zip',
                'composite':f'/outputs/rigging/{jid}/composite.png','manifest':f'/outputs/rigging/{jid}/manifest.json'}
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(jid,1,'complete',time.time(),time.time(),json.dumps({'jobType':'rigging','animationType':'2D 리깅'}),json.dumps(result)))
            con.commit()
        old_root=server.rigging.RESULT_ROOT;server.rigging.RESULT_ROOT=root
        try:
            page=self.admin.get('/rigging-editor?job='+jid);self.assertEqual(page.status_code,200)
            self.assertIn('eraserTool',page.text);self.assertIn('brushTool',page.text);self.assertIn('sourceTool',page.text);self.assertIn('mergeLayer',page.text);page.close()
            self.assertEqual(self.guest.get('/api/jobs/'+jid+'/rig-edit').status_code,401)
            self.assertEqual(self.member.get('/api/jobs/'+jid+'/rig-edit').status_code,403)
            info=self.admin.get('/api/jobs/'+jid+'/rig-edit').json
            self.assertEqual((info['revision'],info['parts'][0]['id']),(0,'headwear'))
            self.assertIsNone(info['sourceReference'])
            self.assertIn('originalAsset',info['parts'][0])
            self.assertEqual([item['key'] for item in info['layers']],['part:headwear','expression:eyebrow'])
            eyebrow=self.admin.get(info['layers'][1]['asset']);self.assertEqual(eyebrow.status_code,200);eyebrow.close()
            self.assertEqual((info['versions'][0]['revision'],info['versions'][0]['label']),(0,'작업 버전 v1'))
            image=self.admin.get(info['parts'][0]['asset']);self.assertEqual(image.status_code,200);image.close()
            version_image=self.admin.get(info['versions'][0]['composite']);self.assertEqual(version_image.status_code,200);version_image.close()
            self.assertEqual(self.guest.get(info['versions'][0]['composite']).status_code,401)
            source=io.BytesIO();Image.new('RGBA',(16,24),(90,40,30,255)).save(source,format='PNG')
            source_data='data:image/png;base64,'+base64.b64encode(source.getvalue()).decode()
            self.assertEqual(self.post(self.member,'jobs/'+jid+'/rig-edit/source',imageData=source_data).status_code,403)
            attached=self.post(self.admin,'jobs/'+jid+'/rig-edit/source',imageData=source_data)
            self.assertEqual(attached.status_code,200)
            source_url=self.admin.get('/api/jobs/'+jid+'/rig-edit').json['sourceReference']
            source_response=self.admin.get(source_url);self.assertEqual(source_response.status_code,200);source_response.close()
            internal=self.post(self.admin,'jobs/'+jid+'/shares',kind='internal').json['url']
            inspect_info=self.guest.get(internal+'/rig-edit');self.assertEqual(inspect_info.status_code,200);self.assertFalse(inspect_info.json['readonly'])
            with patch.object(server.rigging_upscale,'export_layers',return_value=b'zip-export') as exporter:
                denied=self.guest.post('/api/jobs/'+jid+'/rig-edit/upscale',json={'revision':0,'scale':2},headers=HEADERS)
                self.assertEqual(denied.status_code,401)
                forbidden=self.post(self.member,'jobs/'+jid+'/rig-edit/upscale',revision=0,scale=2)
                self.assertEqual(forbidden.status_code,403)
                exported=self.post(self.admin,'jobs/'+jid+'/rig-edit/upscale',revision=0,scale=2)
                self.assertEqual((exported.status_code,exported.data),(200,b'zip-export'));exported.close()
                shared_export=self.guest.post(internal+'/rig-edit/upscale',json={'revision':0,'scale':4},headers=HEADERS)
                self.assertEqual((shared_export.status_code,shared_export.data),(200,b'zip-export'));shared_export.close()
                self.assertEqual(exporter.call_args.args[1],4)
                stale=self.post(self.admin,'jobs/'+jid+'/rig-edit/upscale',revision=99,scale=2)
                self.assertEqual(stale.status_code,409)
            self.assertTrue(inspect_info.json['sourceReference'].endswith('/source'))
            shared_source=self.guest.get(inspect_info.json['sourceReference']);self.assertEqual(shared_source.status_code,200);shared_source.close()
            self.assertEqual(inspect_info.json['versions'][0]['label'],'작업 버전 v1')
            inspect_layer=self.guest.get(inspect_info.json['parts'][0]['asset']);self.assertEqual(inspect_layer.status_code,200);inspect_layer.close()
            shared_version=self.guest.get(inspect_info.json['versions'][0]['composite']);self.assertEqual(shared_version.status_code,200);shared_version.close()
            saved={'revision':1,'editedParts':['headwear'],'manifest':manifest|{'editRevision':1,'editedParts':['headwear']}}
            with patch.object(server.rig_edit,'save_revision',return_value=saved):
                response=self.post(self.admin,'jobs/'+jid+'/rig-edit/revisions',revision=0,operations=[{'layerId':'headwear'}])
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json['revision'],1)
            self.assertFalse((folder/'showcase.webp').exists())
            shared_saved={'revision':2,'editedParts':['headwear'],'manifest':manifest|{'editRevision':2,'editedParts':['headwear']}}
            with patch.object(server.rig_edit,'save_revision',return_value=shared_saved):
                shared_response=self.guest.post(internal+'/rig-edit/revisions',json={'revision':1,'operations':[{'layerId':'headwear'}]},headers=HEADERS)
            self.assertEqual(shared_response.status_code,200)
            self.assertEqual(shared_response.json['revision'],2)
            (folder/'showcase.webp').write_bytes(b'old animation')
            restored={'revision':3,'targetRevision':0,'manifest':manifest|{'editRevision':3,'editedParts':[]}}
            self.assertEqual(self.guest.post('/api/jobs/'+jid+'/rig-edit/restore',json={'revision':2,'targetRevision':0},headers=HEADERS).status_code,401)
            self.assertEqual(self.post(self.member,'jobs/'+jid+'/rig-edit/restore',revision=2,targetRevision=0).status_code,403)
            with patch.object(server.rig_edit,'restore_version',return_value=restored):
                restored_response=self.post(self.admin,'jobs/'+jid+'/rig-edit/restore',revision=2,targetRevision=0)
            self.assertEqual((restored_response.status_code,restored_response.json['revision']),(200,3))
            self.assertFalse((folder/'showcase.webp').exists())
            self.assertEqual(self.post(self.admin,'jobs/'+jid+'/rig-edit/revisions',revision=0,operations=[]).status_code,409)
            gallery=next(item for item in self.admin.get('/api/gallery').json['jobs'] if item['id']==jid)
            self.assertEqual((gallery['rigRevision'],gallery['rigVersions'][-1]['label']),(3,'작업 버전 v4'))
        finally:
            server.rigging.RESULT_ROOT=old_root

    def test_expression_authoring_through_internal_share(self):
        self.approve()
        jid='c'*32
        root=self.data/'expression-results';folder=root/jid;folder.mkdir(parents=True)
        manifest={'canvas':{'width':64,'height':64},'parts':[], 'sourceMouthState':'closed',
                  'expressions':[{'id':'mouth_close','runtimeName':'mouth_close','file':'expressions/mouth.png',
                                  'left':25,'top':25,'width':8,'height':8}]}
        (folder/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
        Image.new('RGBA',(64,64)).save(folder/'composite.png');(folder/'character.psd').write_bytes(b'original')
        image=io.BytesIO();Image.new('RGBA',(8,8),(50,60,70,255)).save(image,'PNG')
        with zipfile.ZipFile(folder/'character-unity-parts.zip','w') as archive:
            archive.writestr('expressions/mouth.png',image.getvalue())
        result={'psd':f'/outputs/rigging/{jid}/character.psd','package':f'/outputs/rigging/{jid}/character-unity-parts.zip',
                'composite':f'/outputs/rigging/{jid}/composite.png'}
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(jid,1,'complete',time.time(),time.time(),json.dumps({'jobType':'rigging'}),json.dumps(result)));con.commit()
        with patch.object(server.rigging,'RESULT_ROOT',root):
            internal=self.post(self.admin,'jobs/'+jid+'/shares',kind='internal').json['url']
            script=self.guest.get('/rigging-expressions.js');self.assertEqual(script.status_code,200);self.assertIn('newExpression',script.text);script.close()
            operations=[{'kind':'variant_create','id':'variant_test','targetKey':'expression:mouth_close','name':'웃는 입'},
                        {'kind':'paint','layerKey':'expression:variant_test','color':'#112233','size':6,'points':[{'x':29,'y':29,'p':.5}]},
                        {'kind':'variant_apply','layerKey':'expression:variant_test'}]
            response=self.guest.post(internal+'/rig-edit/revisions',json={'revision':0,'operations':operations},headers=HEADERS)
            self.assertEqual(response.status_code,200,response.json)
            info=self.guest.get(internal+'/rig-edit').json
            variant=next(item for item in info['layers'] if item['id']=='variant_test')
            self.assertEqual(variant['variantOf'],'expression:mouth_close');self.assertFalse(variant['defaultVisible'])
            asset=self.guest.get(variant['asset']);self.assertEqual(asset.status_code,200);self.assertEqual(asset.mimetype,'image/png');asset.close()
            original=self.guest.get(variant['originalAsset']);self.assertEqual(original.status_code,200);original.close()
            self.assertEqual(info['revision'],1)
            stale=self.guest.post(internal+'/rig-edit/revisions',json={'revision':0,'operations':operations},headers=HEADERS)
            self.assertEqual(stale.status_code,409)

    def test_bone_editor_shared_revision_and_unity_v2(self):
        from test_rigging_bones import BoneTests
        self.approve();jid='d'*32;root=self.data/'bone-results';root.mkdir();folder=root/jid
        BoneTests().fixture(folder)
        result={'psd':f'/outputs/rigging/{jid}/character.psd','package':f'/outputs/rigging/{jid}/character-unity-parts.zip',
                'composite':f'/outputs/rigging/{jid}/composite.png'}
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(jid,1,'complete',time.time(),time.time(),json.dumps({'jobType':'rigging'}),json.dumps(result)));con.commit()
        with patch.object(server.rigging,'RESULT_ROOT',root):
            internal=self.post(self.admin,'jobs/'+jid+'/shares',kind='internal').json['url']
            external='/share/rig/legacy-external-test'
            with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
                con.execute('INSERT INTO rig_shares VALUES(?,?,?,?,?,NULL)',('legacy-external-test',jid,'external',time.time(),1));con.commit()
            info=self.guest.get(internal+'/rig-edit').json;config=info['rig']
            next(b for b in config['bones'] if b['name']=='head')['x']=145
            saved=self.guest.post(internal+'/rig-edit/revisions',json={'revision':0,'operations':[{'kind':'rig_config','config':config}]},headers=HEADERS)
            self.assertEqual(saved.status_code,200,saved.json)
            current=self.guest.get(internal+'/rig-edit').json
            self.assertEqual(next(b for b in current['rig']['bones'] if b['name']=='head')['x'],145)
            self.assertEqual(self.guest.post(external+'/rig-v2',json={'revision':1},headers=HEADERS).status_code,404)
            stale=self.guest.post(internal+'/rig-v2',json={'revision':0},headers=HEADERS)
            self.assertEqual(stale.status_code,409)
            built=self.guest.post(internal+'/rig-v2',json={'revision':1},headers=HEADERS)
            self.assertEqual(built.status_code,200,built.json)
            self.assertTrue(built.json['packageV2'].startswith(internal))
            package=self.guest.get(built.json['packageV2']);self.assertEqual(package.status_code,200)
            with zipfile.ZipFile(io.BytesIO(package.data)) as archive:
                rig=json.loads(archive.read('rig-v2.json'))
                self.assertEqual(next(b for b in rig['bones'] if b['name']=='head')['x'],145)
                self.assertIn('layerMeshes',rig)
            package.close()
            cached=self.guest.post(internal+'/rig-v2',json={'revision':1},headers=HEADERS)
            self.assertTrue(cached.json['cached'])

    def test_shared_timeline_persistence_invalid_pose_and_unity_clips(self):
        import test_rigging_bones as fixtures
        import test_rigging_animation as motion_fixtures
        self.approve();jid='e'*32;root=self.data/'animation-results';root.mkdir();folder=root/jid;fixtures.BoneTests().fixture(folder)
        result={'psd':f'/outputs/rigging/{jid}/character.psd','package':f'/outputs/rigging/{jid}/character-unity-parts.zip','composite':f'/outputs/rigging/{jid}/composite.png'}
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(jid,1,'complete',time.time(),time.time(),json.dumps({'jobType':'rigging'}),json.dumps(result)));con.commit()
        with patch.object(server.rigging,'RESULT_ROOT',root):
            internal=self.post(self.admin,'jobs/'+jid+'/shares',kind='internal').json['url']
            rig=self.guest.get(internal+'/rig-edit').json['rig'];config=motion_fixtures.AnimationTests().config()
            saved=self.guest.post(internal+'/rig-edit/revisions',json={'revision':0,'operations':[{'kind':'rig_animation','rig':rig,'config':config}]},headers=HEADERS)
            self.assertEqual(saved.status_code,200,saved.json)
            info=self.guest.get(internal+'/rig-edit').json;self.assertEqual(info['rigAnimations'],config)
            before=(folder/'manifest.json').read_bytes()
            bad=motion_fixtures.AnimationTests().config();bad['clips'][0]['keys'][0]['pose']={'unknown_bone':{'angle':10}}
            failed=self.guest.post(internal+'/rig-edit/revisions',json={'revision':1,'operations':[{'kind':'rig_animation','config':bad}]},headers=HEADERS)
            self.assertEqual(failed.status_code,400);self.assertEqual((folder/'manifest.json').read_bytes(),before)
            built=self.guest.post(internal+'/rig-v2',json={'revision':1},headers=HEADERS);self.assertEqual(built.status_code,200,built.json)
            package=self.guest.get(built.json['packageV2'])
            with zipfile.ZipFile(io.BytesIO(package.data)) as archive:
                exported=json.loads(archive.read('rig-v2.json'));self.assertEqual(exported['animations'][0]['name'],'Idle')
            package.close()
            importer=self.admin.get('/unity-importer.zip')
            with zipfile.ZipFile(io.BytesIO(importer.data)) as archive:
                self.assertIn('com.skylight.sprite-lab/Editor/RiggingV2AnimationBuilder.cs',archive.namelist())
                self.assertIn('com.skylight.sprite-lab/Runtime/RiggingV2ClipPlayer.cs',archive.namelist())
            importer.close()

    def test_rigging_upscale_apply_updates_gallery_and_share(self):
        self.approve()
        jid='e'*32
        root=self.data/'upscale-results';folder=root/jid;folder.mkdir(parents=True)
        manifest={'canvas':{'width':64,'height':64},'parts':[{'id':'face','runtimeName':'face',
                  'file':'layers/face.png','left':10,'top':10,'width':24,'height':30}],
                  'expressions':[],'anchors':{},'warnings':[]}
        raw=io.BytesIO();Image.new('RGBA',(24,30),(200,100,50,255)).save(raw,'PNG')
        (folder/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
        with zipfile.ZipFile(folder/'character-unity-parts.zip','w') as archive:
            archive.writestr('layers/face.png',raw.getvalue())
        (folder/'character.psd').write_bytes(b'original')
        Image.new('RGBA',(64,64)).save(folder/'composite.png')
        result={'psd':f'/outputs/rigging/{jid}/character.psd','package':f'/outputs/rigging/{jid}/character-unity-parts.zip',
                'composite':f'/outputs/rigging/{jid}/composite.png'}
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(jid,1,'complete',time.time(),time.time(),json.dumps({'jobType':'rigging'}),json.dumps(result)))
            con.commit()
        with patch.object(server.rigging,'RESULT_ROOT',root):
            internal=self.post(self.admin,'jobs/'+jid+'/shares',kind='internal').json['url']
            response=self.guest.post(internal+'/rig-edit/upscale',json={'action':'apply','revision':0,'scale':2},headers=HEADERS)
            self.assertEqual(response.status_code,200,response.json)
            self.assertEqual(response.json['revision'],1)
            info=self.guest.get(internal+'/rig-edit').json
            self.assertEqual(info['canvas']['width'],128)
            self.assertTrue(info['packageV2'].endswith('/asset/character-unity-skeleton.zip'))
            download=self.guest.get(info['packageV2']);self.assertEqual(download.status_code,200);download.close()
            gallery=next(item for item in self.admin.get('/api/gallery').json['jobs'] if item['id']==jid)
            self.assertEqual(gallery['rigRevision'],1)
            self.assertEqual(len(gallery['rigVersions']),2)
            self.assertTrue(gallery['packageV2'])
            stale=self.post(self.admin,'jobs/'+jid+'/rig-edit/upscale',action='apply',revision=0,scale=2)
            self.assertEqual(stale.status_code,409)

    def test_rigging_v2_generation_permissions_revision_and_download(self):
        self.approve()
        jid='b'*32
        root=self.data/'v2-results';folder=root/jid;folder.mkdir(parents=True)
        for name in ('character.psd','character-unity-parts.zip','composite.png','manifest.json'):(folder/name).write_bytes(b'asset')
        result={'state':'complete','rigRevision':2,'psd':f'/outputs/rigging/{jid}/character.psd','package':f'/outputs/rigging/{jid}/character-unity-parts.zip',
                'composite':f'/outputs/rigging/{jid}/composite.png','manifest':f'/outputs/rigging/{jid}/manifest.json'}
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(jid,1,'complete',time.time(),time.time(),json.dumps({'jobType':'rigging','animationType':'2D 리깅'}),json.dumps(result)))
            con.commit()
        old_root=server.rigging.RESULT_ROOT;server.rigging.RESULT_ROOT=root
        try:
            endpoint='jobs/'+jid+'/rig-v2'
            self.assertEqual(self.guest.post('/api/'+endpoint,json={'revision':2},headers={'X-Sprite-Request':'1'}).status_code,401)
            self.assertEqual(self.post(self.member,endpoint,revision=2).status_code,403)
            self.assertEqual(self.post(self.admin,endpoint,revision=1).status_code,409)
            package=folder/server.rig_v2.V2_FILENAME
            def build(*_):
                package.write_bytes(b'v2-package')
                return {'path':package,'bones':17,'sourceRevision':2,'warnings':['draft']}
            with patch.object(server.rig_v2,'build_package',side_effect=build):
                response=self.post(self.admin,endpoint,revision=2)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json['boneCount'],17)
            job=self.admin.get('/api/jobs/'+jid).json
            self.assertEqual((job['packageV2SourceRevision'],job['rigV2BoneCount']),(2,17))
            asset=self.admin.get(job['packageV2']);self.assertEqual(asset.status_code,200);asset.close()
            self.assertEqual(self.guest.get(job['packageV2']).status_code,401)
        finally:
            server.rigging.RESULT_ROOT=old_root

    def test_unity_importer_archive_and_signed_one_click_download(self):
        importer=self.admin.get('/unity-importer.zip')
        self.assertEqual(importer.status_code,200)
        with zipfile.ZipFile(io.BytesIO(importer.data)) as archive:
            names=set(archive.namelist())
        importer.close()
        self.assertIn('com.skylight.sprite-lab/package.json',names)
        self.assertIn('com.skylight.sprite-lab/Editor/SpriteLabUnityLink.cs',names)
        self.assertIn('com.skylight.sprite-lab/Editor/RiggingV2Importer.cs',names)
        self.assertIn('com.skylight.sprite-lab/Editor/SpriteSheetImporter.cs',names)
        self.assertIn('com.skylight.sprite-lab/Runtime/RiggingV2Portrait.cs',names)
        self.assertEqual(self.guest.get('/unity-importer.zip').status_code,401)

        self.approve()
        jid='c'*32
        root=self.data/'unity-link-results';folder=root/jid;folder.mkdir(parents=True)
        package=folder/server.rig_v2.V2_FILENAME
        package.write_bytes(b'signed-v2-package')
        result={'rigRevision':2,'packageV2SourceRevision':2,
                'packageV2':f'/outputs/rigging/{jid}/{server.rig_v2.V2_FILENAME}'}
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',
                        (jid,1,'complete',time.time(),time.time(),json.dumps({'jobType':'rigging','animationType':'2D 리깅'}),json.dumps(result)))
            con.commit()
        old_root=server.rigging.RESULT_ROOT;server.rigging.RESULT_ROOT=root
        try:
            endpoint='jobs/'+jid+'/unity-link'
            self.assertEqual(self.post(self.guest,endpoint).status_code,401)
            self.assertEqual(self.post(self.member,endpoint).status_code,403)
            with patch.dict(server.os.environ,{'SPRITE_HTTPS':'1'}):
                link=self.post(self.admin,endpoint)
            self.assertEqual(link.status_code,200)
            self.assertTrue(link.json['uri'].startswith('spritelab-unity://import?url='))
            self.assertTrue(link.json['downloadUrl'].startswith('https://localhost/'))
            self.assertEqual(link.json['expiresIn'],300)
            signed_path=urlsplit(link.json['downloadUrl']).path
            download=self.guest.get(signed_path)
            self.assertEqual((download.status_code,download.data),(200,b'signed-v2-package'))
            download.close()
            self.assertEqual(self.guest.get('/unity-import/not-a-token').status_code,404)
            result['packageV2SourceRevision']=3
            with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
                con.execute('UPDATE jobs SET result=? WHERE id=?',(json.dumps(result),jid));con.commit()
            self.assertEqual(self.guest.get(signed_path).status_code,410)
        finally:
            server.rigging.RESULT_ROOT=old_root

if __name__=='__main__':unittest.main()
