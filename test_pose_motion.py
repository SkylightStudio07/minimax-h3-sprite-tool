"""Walking control and all-or-nothing publication, with isolated files/SQLite."""
from contextlib import closing
import copy
import io
import zipfile
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

import pose_motion as motion
import character_studio
import test_team_server as fixtures
import team_server as server
import motion_identity


class MotionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def payload(self):return dict(poses=motion.walking(),prompt='purple bob, black coat',model='wai-cutscene-counter',facing='right',size='512x768')

    def test_template_and_input_validation(self):
        with patch.object(motion.image_pose,'status',return_value=dict(ready=True)):
            clean=motion.validate(self.payload());self.assertEqual(len(clean['poses']),4)
            self.assertEqual(clean['consistency'],'reference-edit');self.assertEqual(clean['action'],'walk');self.assertEqual(clean['fps'],4)
            self.assertEqual(motion.validate(self.payload()|dict(action='run'))['fps'],6)
            for change in [dict(action='fly'),dict(action=[]),dict(action={}),dict(consistency='invalid'),dict(poses=[]),dict(poses=[{}]*4),dict(poses=[None]*4),dict(model='anima-base'),dict(fps=True),dict(size='10x10'),dict(denoise=float('nan')),dict(prompt='')]:
                with self.subTest(change=change),self.assertRaises(ValueError):motion.validate(self.payload()|change)
        right=motion.walking(8);left=motion.walking(8,'left');self.assertNotEqual(right[0]['points'][10],right[4]['points'][10])
        for r,l in zip(right,left):
            for a,b in zip(r['points'],l['points']):self.assertAlmostEqual(a[0]+b[0],1);self.assertEqual(a[1],b[1])
        with patch.object(motion.image_pose,'status',return_value=dict(ready=False)):
            motion.validate(self.payload()|dict(consistency='reference-edit'))
            with self.assertRaises(ValueError):motion.validate(self.payload()|dict(consistency='independent'))

    def run_fixture(self,fail=False):
        folder=self.root/'motion'/'task';folder.mkdir(parents=True)
        source=Image.new('RGBA',(80,120),'blue');source.save(folder/'reference.png')
        p=dict(self.payload(),_motionRoot=str(folder.parent),_frameRoot=str(self.root/'frames'),workspaceId='set',fps=8,denoise=.8,seed=123)
        calls=[]
        def fake(child,settings):
            calls.append(copy.deepcopy(settings))
            if fail and len(calls)==2:raise RuntimeError('frame failed')
            out=motion.image_engine.RESULT_ROOT/child;out.mkdir(parents=True);Image.new('RGBA',(512,768),(100,50,len(calls),255)).save(out/'image-1.png')
            motion.image_engine.update_job(child,state='complete',images=[dict(background='transparent')])
        with patch.object(motion.image_engine,'RESULT_ROOT',self.root/'images'),patch.object(motion.image_pose,'status',return_value=dict(ready=True)),patch.object(motion.image_background,'status',return_value=dict(ready=True)),patch.object(motion.image_engine,'run_job',side_effect=fake),patch.object(motion,'update_job'),patch.object(motion.image_engine,'update_job') as callback:
            if fail:
                with self.assertRaises(RuntimeError):motion.run_job('task',p)
                self.assertFalse((self.root/'frames/set').exists())
            else:
                doc=motion.run_job('task',p);self.assertEqual(len(doc['frames']),4)
                self.assertEqual({x['seed'] for x in calls},{123});self.assertEqual(len({x['imageData'] for x in calls}),1);self.assertNotEqual(calls[0]['pose'],calls[1]['pose'])
                self.assertEqual(doc['motion']['poses'],p['poses']);self.assertTrue((folder/'motion.json').is_file())
            self.assertIs(motion.image_engine.update_job,callback)
        self.assertEqual(len(list((self.root/'images').glob('*'))),0)

    def test_generate_uses_one_reference_seed_and_preserves_authored_poses(self):self.run_fixture()
    def test_failed_frame_does_not_publish_partial_workspace(self):self.run_fixture(True)

    def test_alignment_uses_common_floor_and_preserves_aspect(self):
        from PIL import ImageDraw
        source=Image.new('RGBA',(100,200));ImageDraw.Draw(source).rectangle((20,30,59,149),fill=(180,80,100,255))
        image,info=motion.align_frame(source,(512,768))
        box=image.getchannel('A').point(lambda a:255 if a>=24 else 0).getbbox()
        self.assertAlmostEqual(box[3],round(768*.95),delta=2)
        self.assertAlmostEqual((box[2]-box[0])/(box[3]-box[1]),40/120,delta=.01)
        self.assertEqual(image.size,(512,768))

    def test_full_body_gaits_have_distinct_support_and_upper_body_motion(self):
        walk=motion.gait('walk',8);run=motion.gait('run',8)
        for action,poses in [('walk',walk),('run',run)]:
            for joint in (1,2,3,4,5,6,7,8,11):
                self.assertGreater(len({tuple(p['points'][joint]) for p in poses}),2,(action,joint))
            for p in poses:
                self.assertTrue(all(0<x<1 and 0<y<1 for x,y in p['points']))
            mirrored=motion.gait(action,8,'left')
            for a,b in zip(poses,mirrored):
                for (x,y),(mx,my) in zip(a['points'],b['points']):self.assertAlmostEqual(x+mx,1);self.assertEqual(y,my)
        self.assertTrue(all(max(p['points'][10][1],p['points'][13][1])==.92 for p in walk))
        self.assertTrue(any(max(p['points'][10][1],p['points'][13][1])<.9 for p in run))
        self.assertGreater(run[0]['points'][1][0]-(run[0]['points'][8][0]+run[0]['points'][11][0])/2,.08)
        # A hand swings opposite its same-side ankle, relative to the body's center.
        self.assertLess((walk[0]['points'][4][0]-walk[0]['points'][2][0])*(walk[0]['points'][10][0]-.48),0)
        for stride in (.04,.22):
            motion.validate(self.payload()|dict(action='run',poses=motion.gait('run',8,stride=stride)))

    def test_canvas_alignment_preserves_bob_flight_and_size(self):
        from PIL import ImageDraw
        boxes=[]
        for dy in (0,-30):
            image=Image.new('RGBA',(512,768));ImageDraw.Draw(image).rectangle((180,180+dy,300,700+dy),fill='red')
            out,info=motion.preserve_canvas(image,(512,768))
            self.assertEqual(out.tobytes(),image.tobytes());self.assertEqual(info['mode'],'fixed-canvas')
            boxes.append(out.getchannel('A').getbbox())
        self.assertEqual(boxes[0][3]-boxes[1][3],30)
        with self.assertRaises(RuntimeError):motion.preserve_canvas(Image.new('RGBA',(512,768)),(512,768))

    def test_run_prompt_requires_upper_body_action_without_freezing_silhouette(self):
        p=self.payload()|dict(action='run');text=motion.identity_prompt(p,motion.gait('run')[1],1)
        for term in ('running','flight','elbows bent','shoulders','pelvis','NOT remain frozen','Preserve design'):
            self.assertIn(term,text)

    def test_fixed_identity_anchor_is_reused_without_recursive_drift(self):
        folder=self.root/'motions'/'task';folder.mkdir(parents=True)
        Image.new('RGBA',(100,150),'blue').save(folder/'reference.png')
        p=dict(self.payload(),action='run',consistency='reference-edit',_motionRoot=str(folder.parent),_frameRoot=str(self.root/'frames'),workspaceId='set',fps=8,denoise=.8,seed=123)
        references=[];prompts=[]
        def fake(reference,pose,size,seed,prompt,root,i):
            references.append(reference.copy());prompts.append(prompt)
            return Image.new('RGBA',size,[(180,0,0,255),(0,180,0,255),(0,0,180,255),(180,180,0,255)][i])
        with patch.object(motion.motion_identity,'edit_frame',side_effect=fake),patch.object(motion,'update_job'),patch.object(motion.image_engine.requests,'post'):
            doc=motion.run_job('task',p)
        self.assertEqual(len(doc['frames']),4)
        self.assertEqual(references[1].tobytes(),references[2].tobytes());self.assertEqual(references[1].tobytes(),references[3].tobytes())
        self.assertNotEqual(references[0].tobytes(),references[1].tobytes())
        self.assertTrue((folder/'identity-anchor.png').is_file());self.assertEqual(doc['motion']['appearanceAnchorFrame'],0)
        self.assertIn('same side view',prompts[1]);self.assertIn('contact step',prompts[0]);self.assertIn('running',prompts[1])
        self.assertEqual(doc['clips'][0]['name'],'run');self.assertEqual(doc['motion']['action'],'run')
        self.assertEqual(doc['motion']['alignment'],'fixed-canvas')

    def test_identity_failure_removes_partial_frames(self):
        folder=self.root/'motions'/'task';folder.mkdir(parents=True);Image.new('RGBA',(100,150),'blue').save(folder/'reference.png')
        p=dict(self.payload(),consistency='reference-edit',_motionRoot=str(folder.parent),_frameRoot=str(self.root/'frames'),workspaceId='set',fps=8,denoise=.8,seed=123)
        with patch.object(motion.motion_identity,'edit_frame',side_effect=[Image.new('RGBA',(512,768),'red'),RuntimeError('edit failed')]),patch.object(motion,'update_job'),patch.object(motion.image_engine.requests,'post'),self.assertRaises(RuntimeError):motion.run_job('task',p)
        self.assertFalse((self.root/'frames/set').exists())

    def test_identity_graph_separates_appearance_and_pose(self):
        graph=motion_identity.workflow('appearance.png','pose.png','output',123)
        self.assertEqual(graph['1']['inputs']['image'],'appearance.png')
        self.assertEqual(graph['10']['inputs']['image'],'pose.png')
        self.assertEqual(graph['5']['inputs']['images.image_2'],['10',0])
        self.assertEqual(graph['6']['inputs']['device'],'cpu')
        self.assertFalse(any(n['class_type']=='LoraLoader' for n in graph.values()))

    def test_identity_edit_cleans_up_inputs_and_keeps_raw_comparison(self):
        generated=self.root/'generated.png';Image.new('RGB',(64,96),'blue').save(generated)
        folder=self.root/'result';folder.mkdir()
        with patch.object(motion_identity.rig,'INPUT_ROOT',self.root),patch.object(motion_identity.requests,'post') as post,\
             patch.object(motion_identity,'wait_for_prompt',return_value={}),\
             patch.object(motion_identity.rig,'_saved_image',return_value=generated),\
             patch.object(motion_identity.image_background,'remove',side_effect=lambda im:im):
            post.return_value.json.return_value={'prompt_id':'test'}
            result=motion_identity.edit_frame(Image.new('RGBA',(64,96),'red'),motion.walking()[0],(64,96),123,'keep appearance',folder,0)
            self.assertEqual(result.size,(64,96));self.assertTrue((folder/'edit-raw-000.png').is_file())
            self.assertEqual(list(self.root.glob('motion_identity_*.png')),[]);self.assertEqual(list(self.root.glob('motion_pose_*.png')),[])
        with patch.object(motion_identity.rig,'INPUT_ROOT',self.root),patch.object(motion_identity.requests,'post',side_effect=RuntimeError('failed')),self.assertRaises(RuntimeError):
            motion_identity.edit_frame(Image.new('RGBA',(64,96),'red'),motion.walking()[0],(64,96),123,'keep appearance',folder,1)
        self.assertEqual(list(self.root.glob('motion_identity_*.png')),[]);self.assertEqual(list(self.root.glob('motion_pose_*.png')),[])

    def test_identity_poll_retries_transient_timeout_without_resubmission(self):
        response=unittest.mock.Mock();response.json.return_value={'task':dict(status=dict(status_str='success'),outputs={})}
        with patch.object(motion_identity.requests,'get',side_effect=[motion_identity.requests.Timeout('busy'),response]) as get,patch.object(motion_identity.requests,'post') as post,patch.object(motion_identity.time,'sleep'):
            result=motion_identity.wait_for_prompt('task',timeout=10)
        self.assertEqual(result['status']['status_str'],'success');self.assertEqual(get.call_count,2);post.assert_not_called()


class MotionAPITests(unittest.TestCase):
    def setUp(self):
        fixtures.TeamTests.setUp(self)
        flag=patch.object(motion,'GENERATE_ENABLED',True);flag.start();self.addCleanup(flag.stop)
    tearDown=fixtures.TeamTests.tearDown
    post=fixtures.TeamTests.post
    approve=fixtures.TeamTests.approve

    def test_retired_generator_redirects_and_cannot_enqueue(self):
        with patch.object(motion,'GENERATE_ENABLED',False):
            response=self.admin.get('/motion-studio');self.assertEqual(response.status_code,302);self.assertEqual(response.location,'/#/create/sprite')
            self.assertEqual(self.guest.get('/api/motions/poses').status_code,401)
            for url in ('/api/motions/poses','/api/motions/templates'):
                response=self.admin.get(url);self.assertEqual(response.status_code,410);self.assertTrue(response.json['retired'])
            response=self.post(self.admin,'motions');self.assertEqual(response.status_code,410)
            with self.connect_db() as con:self.assertEqual(con.execute("SELECT count(*) FROM jobs WHERE json_extract(payload,'$.jobType')='pose-motion'").fetchone()[0],0)

    def connect_db(self):return closing(sqlite3.connect(self.data/'team.sqlite3'))

    def test_template_api_uses_the_same_gaits_and_rejects_bad_controls(self):
        self.assertEqual(self.guest.get('/api/motions/poses').status_code,401)
        self.assertEqual(self.admin.get('/api/motions/poses?action=run&count=8&facing=left&stride=.2').json['poses'],motion.gait('run',8,'left',.2))
        for query in ('action=jump','count=5','count=x','stride=NaN','stride=.5','facing=up'):
            self.assertEqual(self.admin.get('/api/motions/poses?'+query).status_code,400,query)

    def test_creation_permissions_and_fifo_workspace_publication(self):
        self.approve();cid=self.post(self.admin,'characters',name='walker').json['id']
        self.post(self.admin,'characters/'+cid+'/reference',imageData=character_studio.image_data(Image.new('RGBA',(64,96),'blue')))
        p=dict(action='run',characterId=cid,poses=motion.gait('run'),prompt='blue coat',fps=12)
        self.assertEqual(self.post(self.guest,'motions',**p).status_code,401)
        with patch.object(motion.image_pose,'status',return_value=dict(ready=True)),patch.object(motion.image_background,'status',return_value=dict(ready=True)),patch.object(motion.image_engine.engine,'COMFY_ROOT',self.data):
            for model in motion.image_pose.SUPPORTED:
                for filename in motion.image_engine.MODELS[model]['files']:
                    target=self.data/'models'/filename;target.parent.mkdir(parents=True,exist_ok=True);target.touch()
            self.assertEqual(self.post(self.member,'motions',**p).status_code,403)
            result=self.post(self.admin,'motions',**p);self.assertEqual(result.status_code,202,result.json);task=result.json['taskId']
            self.assertEqual(self.admin.get('/api/motions/'+task).json['state'],'queued')
            self.assertEqual(self.member.get('/api/motions/'+task).status_code,403)
            self.assertEqual(self.admin.get('/api/motions/missing').status_code,404)
            called=[]
            def fake(jid,p):
                called.append(p);folder=Path(p['_frameRoot'])/p['workspaceId'];folder.mkdir()
                for i in range(4):Image.new('RGBA',(32,48),'blue').save(folder/f'original-{i:03d}.png')
                return dict(revision=0,width=32,height=48,columns=4,rows=1,fps=p['fps'],motion=dict(action=p['action']),clips=[dict(name=p['action'],start=0,end=3)],frames=[dict(file=f'original-{i:03d}.png',locked=False) for i in range(4)])
            import time
            with patch.object(motion,'run_job',side_effect=fake),patch.object(motion,'update_job'),patch.object(server.rigging,'comfy_ready',return_value=True),patch.object(server.engine.requests,'get') as get:
                get.return_value.json.return_value={'queue_running':[],'queue_pending':[]}
                self.app.start_worker()
                for _ in range(80):
                    r=self.admin.get('/api/motions/'+task).json
                    if r['state']=='complete':break
                    time.sleep(.05)
                self.app.stop_worker();time.sleep(.6)
                self.assertEqual(r['state'],'complete',r)
            wid=r['workspaceId'];info=self.admin.get('/api/frames/'+wid).json;self.assertEqual(info['characterId'],cid)
            self.assertEqual(len(info['frames']),4);self.assertEqual([x['points'] for x in called[0]['poses']],[x['points'] for x in p['poses']])
            self.assertEqual(called[0]['action'],'run');self.assertEqual(called[0]['fps'],12)
            export=self.admin.get('/api/frames/'+wid+'/export.zip')
            self.assertIn('sprite-run-v1.zip',export.headers['Content-Disposition'])
            with zipfile.ZipFile(io.BytesIO(export.data)) as archive:
                exported=json.loads(archive.read('animation.json'));self.assertEqual(exported['motion']['action'],'run');self.assertEqual(exported['clips'][0]['name'],'run');self.assertEqual(exported['fps'],12)
            self.assertEqual(self.admin.get('/api/characters/'+cid).json['frames'][0]['id'],wid)
            self.assertNotIn(task,[x['id'] for x in self.admin.get('/api/jobs').json['jobs']])
