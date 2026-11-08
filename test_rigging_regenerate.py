"""Isolated candidate/apply tests. Production jobs and GPU are not used here."""
import io
import json
import sqlite3
from contextlib import closing
import time
import unittest
import zipfile
from unittest.mock import patch
from PIL import Image
import test_rigging_expressions as fixtures
import test_team_server as api_fixtures
import rigging_editor as editor
import rigging_regenerate as regeneration
import team_server as server


class ReplacementTests(unittest.TestCase):
    def setUp(self):
        fixtures.ExpressionTests.setUp(self)

    def replacement(self):
        image=Image.new('RGBA',(16,12),(20,40,60,255))
        return dict(kind='layer_png',layerKey='expression:mouth_close',left=36,top=38,width=16,height=12,imageData=regeneration.image_data(image))

    def test_save_replaces_only_slot_and_retains_version(self):
        self.manifest['parts']=[dict(id='hair',file='layers/hair.png',left=1,top=2,width=8,height=8)]
        (self.folder/'manifest.json').write_text(json.dumps(self.manifest))
        with zipfile.ZipFile(self.folder/'character-unity-parts.zip','a') as z:
            z.writestr('layers/hair.png',ImageBytes(Image.new('RGBA',(8,8),'blue')))
        with zipfile.ZipFile(self.folder/'character-unity-parts.zip') as z: before=z.read('layers/hair.png')
        result=editor.save_revision(self.folder,[self.replacement()],0,self.writer)
        record=dict(editor.layer_records(result['manifest']))['expression:mouth_close']
        self.assertEqual((record['left'],record['top'],record['width'],record['height']),(36,38,16,12))
        with zipfile.ZipFile(self.folder/'character-unity-parts.zip') as z:
            self.assertEqual(z.read('layers/hair.png'),before)
            self.assertEqual(Image.open(io.BytesIO(z.read(record['file']))).size,(16,12))
        self.assertEqual((self.folder/'revisions/0000/character.psd').read_bytes(),b'original')
        self.assertTrue((self.folder/'character.psd').read_bytes().startswith(b'8BPS'))

    def test_invalid_geometry_empty_and_wrong_slot(self):
        for change in [dict(left=-1),dict(width=97),dict(width=True),dict(layerKey='part:face'),
                       dict(imageData=regeneration.image_data(Image.new('RGBA',(16,12))))]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                editor.validate_operations(self.manifest,[self.replacement()|change])
        editor.validate_operations(self.manifest,[self.replacement()])
        self.assertEqual(self.manifest['expressions'][0]['width'],8,'validation must not mutate manifest')

    def test_candidate_generation_keeps_package_untouched(self):
        self.manifest['sourceReference']=editor.SOURCE_REFERENCE
        (self.folder/'manifest.json').write_text(json.dumps(self.manifest))
        Image.new('RGBA',(96,96),'white').save(self.folder/editor.SOURCE_REFERENCE)
        original=(self.folder/'character-unity-parts.zip').read_bytes()
        generated=self.folder/'generated.png';Image.new('RGB',(80,80),'pink').save(generated)
        p=dict(parentJob='job',revision=0,layerKey='expression:mouth_close',hint='')
        status=[]
        with patch.object(regeneration.rigging,'RESULT_ROOT',self.folder.parent),patch.object(regeneration,'ROOT',self.folder/'candidates'),\
             patch.object(regeneration.rigging,'INPUT_ROOT',self.folder),patch.object(regeneration.rigging,'QWEN_MODEL_PATHS',[]),\
             patch.object(regeneration.requests,'post') as post,patch.object(regeneration.rigging,'_wait_for_prompt',return_value={}),\
             patch.object(regeneration.rigging,'_saved_image',return_value=generated),\
             patch.object(regeneration,'update_job',side_effect=lambda jid,**kw:status.append(kw)):
            post.return_value.json.return_value={'prompt_id':'test'}
            regeneration.run_job('candidate',p)
        self.assertEqual(status[-1]['state'],'complete')
        self.assertEqual((self.folder/'character-unity-parts.zip').read_bytes(),original)

    def test_object_candidate_scales_coordinates_and_keeps_other_objects_out(self):
        manifest=dict(sourceReference=editor.SOURCE_REFERENCE,canvas=dict(width=96,height=96),
                      parts=[dict(id='objects',runtimeName='objects',file='layers/objects.png',left=30,top=30,width=20,height=20)])
        (self.folder/'manifest.json').write_text(json.dumps(manifest))
        Image.new('RGBA',(96,96),'white').save(self.folder/editor.SOURCE_REFERENCE)
        from PIL import ImageDraw
        layer=Image.new('RGBA',(48,48));draw=ImageDraw.Draw(layer)
        draw.rectangle((15,15,24,24),fill='red');draw.rectangle((0,0,2,2),fill='blue')
        layer.save(self.folder/'objects.png')
        info=self.folder/'layers.json';info.write_text(json.dumps(dict(width=48,height=48,layers=[dict(name='objects',filename='objects.png',left=0,top=0)])))
        with patch.object(regeneration.rigging,'RESULT_ROOT',self.folder.parent),patch.object(regeneration,'ROOT',self.folder/'candidates'),\
             patch.object(regeneration.rigging,'INPUT_ROOT',self.folder),patch.object(regeneration.rigging,'COMFY_OUTPUT',self.folder),\
             patch.object(regeneration.requests,'post') as post,patch.object(regeneration.rigging,'_wait_for_prompt',return_value={}),\
             patch.object(regeneration.rigging,'_latest_layers',return_value=info):
            post.return_value.json.return_value={'prompt_id':'test'}
            regeneration.run_job('object',dict(parentJob='job',revision=0,layerKey='part:objects',hint=''))
        metadata=json.loads((self.folder/'candidates/object/candidate.json').read_text())
        self.assertGreater(metadata['left'],14)
        with Image.open(self.folder/'candidates/object/candidate.png') as candidate:
            self.assertGreater(candidate.getchannel('A').getextrema()[1],0)



def ImageBytes(image):
    output=io.BytesIO();image.save(output,'PNG');return output.getvalue()


class RegenerationAPITests(unittest.TestCase):
    setUp=api_fixtures.TeamTests.setUp
    tearDown=api_fixtures.TeamTests.tearDown
    post=api_fixtures.TeamTests.post
    approve=api_fixtures.TeamTests.approve

    def test_permissions_queue_share_candidate_and_gallery(self):
        self.approve()
        root=self.data/'rigs';folder=root/'parent';folder.mkdir(parents=True)
        manifest=dict(sourceReference=editor.SOURCE_REFERENCE,canvas=dict(width=96,height=96),expressions=[dict(id='mouth_close',file='expressions/mouth.png',left=40,top=40,width=8,height=8)])
        (folder/'manifest.json').write_text(json.dumps(manifest))
        Image.new('RGBA',(96,96),'white').save(folder/editor.SOURCE_REFERENCE)
        uid=self.admin.get('/api/me').json['user']['id']
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',('parent',uid,'complete',1,1,json.dumps(dict(jobType='rigging')),'{}'))
            con.execute('INSERT INTO rig_shares VALUES(?,?,?,?,?,?)',('internal','parent','internal',1,uid,None))
            con.execute('INSERT INTO rig_shares VALUES(?,?,?,?,?,?)',('external','parent','showcase',1,uid,None))
            con.commit()
        body=dict(revision=0,layerKey='expression:mouth_close')
        with patch.object(server.rigging,'RESULT_ROOT',root),patch.object(server.rigging,'QWEN_MODEL_PATHS',[]),patch.object(regeneration,'ROOT',self.data/'candidates'):
            route='/api/jobs/parent/rig-edit/regenerate'
            self.assertEqual(self.guest.post(route,json=body,headers=api_fixtures.HEADERS).status_code,401)
            self.assertEqual(self.member.post(route,json=body,headers=api_fixtures.HEADERS).status_code,403)
            self.assertEqual(self.admin.post(route,json=body|dict(revision=1),headers=api_fixtures.HEADERS).status_code,400)
            self.assertEqual(self.admin.post(route,json=body|dict(layerKey='part:face'),headers=api_fixtures.HEADERS).status_code,400)
            response=self.admin.post(route,json=body,headers=api_fixtures.HEADERS)
            self.assertEqual(response.status_code,202,response.json)
            task=response.json['taskId']
            self.assertEqual(self.admin.get(route+'/'+task).json['state'],'queued')
            self.assertEqual(self.admin.get(route+'/missing').status_code,404)
            share='/share/rig/internal/rig-edit/regenerate'
            self.assertEqual(self.guest.get(share+'/'+task).status_code,200)
            self.assertEqual(self.guest.post('/share/rig/external/rig-edit/regenerate',json=body,headers=api_fixtures.HEADERS).status_code,404)
            self.assertEqual(self.guest.post(share,json=body,headers=api_fixtures.HEADERS).status_code,202)
            target=regeneration.ROOT/task;target.mkdir(parents=True)
            (target/'candidate.json').write_text(json.dumps(body|dict(left=40,top=40,width=8,height=8)))
            Image.new('RGBA',(8,8),'red').save(target/'candidate.png')
            with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
                con.execute("UPDATE jobs SET state='complete' WHERE id=?",(task,));con.commit()
            self.assertTrue(self.guest.get(share+'/'+task).json['imageData'].startswith('data:image/png;base64,'))
            self.assertEqual([r['id'] for r in self.admin.get('/api/gallery').json['jobs']],['parent'])
            self.assertEqual([r['id'] for r in self.admin.get('/api/jobs').json['jobs']],['parent'])
            # Verify the real FIFO dispatcher calls the part runner, rather than the video engine.
            def fake_run(jid,p):regeneration.update_job(jid,state='complete',message='test')
            with patch.object(regeneration,'run_job',side_effect=fake_run) as runner,\
                 patch.object(regeneration,'update_job'),\
                 patch.object(server.rigging,'comfy_ready',return_value=True),\
                 patch.object(server.engine.requests,'get') as get:
                get.return_value.json.return_value={'queue_running':[],'queue_pending':[]}
                self.app.start_worker()
                for _ in range(40):
                    if runner.called:break
                    time.sleep(.05)
                self.app.stop_worker()
                time.sleep(.6)
                self.assertTrue(runner.called)
                self.assertEqual(runner.call_args.args[1]['jobType'],'rig-part')
