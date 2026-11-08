"""Character collections and sprite frame editing use only disposable jobs/files."""
import base64
from contextlib import closing
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch
import zipfile
from PIL import Image,ImageDraw
import numpy as np
import character_studio as studio
import frame_edit
import test_team_server as fixtures
import team_server as server


class CharacterTests(unittest.TestCase):
    setUp=fixtures.TeamTests.setUp
    tearDown=fixtures.TeamTests.tearDown
    post=fixtures.TeamTests.post
    approve=fixtures.TeamTests.approve

    def connect(self):return closing(sqlite3.connect(self.data/'team.sqlite3'))

    def test_trim_versions_preserve_pixels_locks_and_rebase_clips(self):
        self.approve();folder=self.fixture()
        with patch.object(server.engine,'RESULT_ROOT',folder.parent):
            wid=self.post(self.admin,'jobs/sprite/frames',source='spriteSheet').json['id']
        with self.connect() as con:
            doc=json.loads(con.execute('SELECT document FROM frame_workspaces WHERE id=?',(wid,)).fetchone()[0])
            doc['frames'][1]['locked']=True;doc['clips']=[dict(name='left',start=0,end=0),dict(name='right',start=1,end=1)]
            doc['motion']=dict(action='walk',poses=[{'x':0},{'x':1}],appearanceAnchorFrame=0)
            for table in ('frame_workspaces','frame_versions'):
                con.execute('UPDATE '+table+' SET document=? WHERE '+('id' if table=='frame_workspaces' else 'workspace_id')+'=?',(json.dumps(doc),wid))
            con.commit()
        source=self.data/'frame-workspaces'/wid
        before={f['file']:(source/f['file']).read_bytes() for f in doc['frames']}
        endpoint='frames/'+wid+'/trim'
        self.assertEqual(self.post(self.guest,endpoint,revision=0,start=1,end=1).status_code,401)
        self.assertEqual(self.post(self.member,endpoint,revision=0,start=1,end=1).status_code,403)
        for start,end in ((-1,1),(0,2),(1,0),(True,1),(0,1.5)):
            self.assertEqual(self.post(self.admin,endpoint,revision=0,start=start,end=end).status_code,400)
        self.assertEqual(self.post(self.admin,endpoint,revision=99,start=1,end=1).status_code,400)
        self.assertEqual(self.post(self.admin,endpoint,revision=0,start=0,end=1).json['revision'],0)
        self.assertEqual(self.post(self.admin,endpoint,revision=0,start=1,end=1).json['revision'],1)
        trimmed=self.admin.get('/api/frames/'+wid).json
        self.assertEqual(len(trimmed['frames']),1);self.assertTrue(trimmed['frames'][0]['locked'])
        self.assertEqual((trimmed['columns'],trimmed['rows']),(1,1));self.assertEqual(trimmed['clips'],[dict(name='right',start=0,end=0)])
        self.assertEqual(trimmed['motion']['poses'],[{'x':1}]);self.assertNotIn('appearanceAnchorFrame',trimmed['motion'])
        with zipfile.ZipFile(io.BytesIO(self.admin.get('/api/frames/'+wid+'/export.zip').data)) as archive:
            self.assertEqual(archive.read('frames/000.png'),before[doc['frames'][1]['file']])
            self.assertEqual(len(json.loads(archive.read('animation.json'))['frames']),1)
        self.assertEqual(self.post(self.admin,'frames/'+wid+'/restore',revision=1,target=0).status_code,200)
        restored=self.admin.get('/api/frames/'+wid).json;self.assertEqual(len(restored['frames']),2)
        for name,pixels in before.items():self.assertEqual((source/name).read_bytes(),pixels)
        with self.connect() as con:
            result=json.loads(con.execute("SELECT result FROM jobs WHERE id='sprite'").fetchone()[0])
            self.assertEqual(result['frameWorkspace']['revision'],2)

    def fixture(self):
        uid=self.admin.get('/api/me').json['user']['id'];folder=self.data/'results'/'sprite';folder.mkdir(parents=True)
        sheet=Image.new('RGBA',(64,32));ImageDraw.Draw(sheet).rectangle((4,4,24,26),fill=(100,40,80,255));ImageDraw.Draw(sheet).rectangle((35,7,58,29),fill=(40,100,80,255));sheet.save(folder/'sheet.png')
        with self.connect() as con:
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',('sprite',uid,'complete',1,1,json.dumps(dict(frameCount=2,animationType='idle')),json.dumps(dict(spriteSheet='/outputs/results/sprite/sheet.png'))))
            con.commit()
        return folder

    def test_collection_permissions_recipe_reference_and_atomic_generation_link(self):
        self.approve();cid=self.post(self.admin,'characters',name='정찰병').json['id']
        self.assertEqual(self.post(self.guest,'characters',name='x').status_code,401)
        self.assertEqual(self.post(self.member,'characters/'+cid,revision=0,name='x').status_code,403)
        self.assertEqual(self.post(self.admin,'characters/'+cid,revision=9,name='x').status_code,409)
        image=studio.image_data(Image.new('RGBA',(32,32),'red'))
        self.assertEqual(self.post(self.admin,'characters/'+cid+'/reference',imageData=image).status_code,200)
        media=self.member.get('/api/characters/'+cid+'/reference');self.assertEqual(media.status_code,200);media.close()
        p=self.payload|dict(characterId=cid)
        response=self.post(self.admin,'generate',**p);self.assertEqual(response.status_code,202,response.json)
        jid=response.json['jobId']
        entries=self.admin.get('/api/characters/'+cid).json['jobs'];self.assertEqual(entries[0]['jobId'],jid)
        with self.connect() as con:
            con.execute("UPDATE jobs SET state='error' WHERE id=?",(jid,));con.commit()
            before=con.execute('SELECT count(*) FROM jobs').fetchone()[0]
        self.assertEqual(self.post(self.admin,'generate',**(self.payload|dict(characterId='missing'))).status_code,400)
        with self.connect() as con:self.assertEqual(con.execute('SELECT count(*) FROM jobs').fetchone()[0],before,'generation must roll back if character linking fails')
        uid=self.admin.get('/api/me').json['user']['id']
        with self.connect() as con:
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',('art',uid,'complete',1,1,json.dumps(dict(jobType='image',model='wai-cutscene-counter',prompt='hood',lookId='example',imageData='secret')),'{}'));con.commit()
        current=self.admin.get('/api/characters/'+cid).json['character']
        self.assertEqual(self.post(self.admin,'characters/'+cid,revision=current['revision'],recipeFrom='art').status_code,200)
        recipe=self.admin.get('/api/characters/'+cid).json['character']['recipe'];self.assertEqual(recipe['prompt'],'hood');self.assertNotIn('imageData',recipe)
        self.assertEqual(self.post(self.admin,'characters/'+cid+'/jobs',jobId='art',role='style',direction='right',action='idle').status_code,200)
        self.assertEqual(self.post(self.admin,'characters/'+cid+'/jobs',jobId='art',detach=True).status_code,200)

    def test_frames_locks_candidates_apply_versions_and_export(self):
        self.approve();folder=self.fixture();cid=self.post(self.admin,'characters',name='정찰병').json['id']
        self.post(self.admin,'characters/'+cid+'/jobs',jobId='sprite',role='motion')
        original=hashlib.sha256((folder/'sheet.png').read_bytes()).hexdigest()
        with patch.object(server.engine,'RESULT_ROOT',folder.parent),patch.object(server.rigging,'QWEN_MODEL_PATHS',[]):
            self.assertEqual(self.member.get('/api/jobs/sprite/frames').status_code,403)
            self.assertEqual(self.post(self.admin,'jobs/sprite/frames',source='spriteSheet',columns=3,rows=1,count=4).status_code,400)
            created=self.post(self.admin,'jobs/sprite/frames',source='spriteSheet');self.assertEqual(created.status_code,201,created.json);wid=created.json['id']
            self.assertEqual(self.guest.get('/api/frames/'+wid).status_code,401)
            info=self.admin.get('/api/frames/'+wid).json;self.assertEqual((info['width'],info['height'],len(info['frames'])),(32,32,2));self.assertEqual(info['characterId'],cid)
            self.assertEqual(self.post(self.member,'frames/'+wid+'/settings',revision=0,fps=12).status_code,403)
            locked=self.post(self.admin,'frames/'+wid+'/settings',revision=0,locks=[False,True]);self.assertEqual(locked.status_code,200)
            mask=studio.image_data(Image.new('RGB',(32,32),'white'))
            self.assertEqual(self.post(self.admin,'frames/'+wid+'/regenerate',revision=1,frame=1,prompt='fix face',maskData=mask).status_code,400)
            task=self.post(self.admin,'frames/'+wid+'/regenerate',revision=1,frame=0,prompt='fix face',maskData=mask);self.assertEqual(task.status_code,202,task.json);task=task.json['taskId']
            self.assertEqual(self.admin.get('/api/frames/'+wid+'/candidates/'+task).json['state'],'queued')
            target=self.data/'frame-workspaces'/wid/'candidates'/task;target.mkdir(parents=True);Image.new('RGBA',(32,32),'green').save(target/'candidate.png');(target/'candidate.json').write_text(json.dumps(dict(workspaceId=wid,frame=0,revision=1)))
            with self.connect() as con:con.execute("UPDATE jobs SET state='complete' WHERE id=?",(task,));con.commit()
            before=(self.data/'frame-workspaces'/wid/'original-001.png').read_bytes()
            self.assertEqual(self.post(self.admin,'frames/'+wid+'/apply',revision=0,taskId=task).status_code,400)
            self.assertEqual(self.post(self.admin,'frames/'+wid+'/apply',revision=1,taskId=task).status_code,200)
            info=self.admin.get('/api/frames/'+wid).json;self.assertEqual(info['revision'],2);self.assertNotEqual(info['frames'][0]['file'],'original-000.png');self.assertEqual(info['frames'][1]['file'],'original-001.png');self.assertEqual(before,(self.data/'frame-workspaces'/wid/'original-001.png').read_bytes())
            self.assertEqual(self.post(self.admin,'frames/'+wid+'/apply',revision=2,taskId=task).status_code,400,'stale candidate cannot overwrite new revision')
            with self.connect() as con:result=json.loads(con.execute("SELECT result FROM jobs WHERE id='sprite'").fetchone()[0])
            self.assertEqual(result['frameWorkspace']['revision'],2)
            response=self.admin.get('/api/frames/'+wid+'/export.zip');self.assertEqual(response.status_code,200)
            with zipfile.ZipFile(io.BytesIO(response.data)) as z:self.assertEqual(len([n for n in z.namelist() if n.startswith('frames/')]),2);self.assertEqual(json.loads(z.read('animation.json'))['fps'],8)
            response.close()
            self.assertEqual(self.post(self.admin,'frames/'+wid+'/restore',revision=2,target=0).status_code,200)
            info=self.admin.get('/api/frames/'+wid).json;self.assertEqual(info['revision'],3);self.assertFalse(info['frames'][1]['locked']);self.assertEqual(info['frames'][0]['file'],'original-000.png')
            self.assertEqual(hashlib.sha256((folder/'sheet.png').read_bytes()).hexdigest(),original)

    def test_rpg_sheet_with_fractional_cells_normalizes_without_resampling(self):
        uid=self.admin.get('/api/me').json['user']['id'];folder=self.data/'images'/'rpg';folder.mkdir(parents=True)
        Image.new('RGBA',(14,20),(70,80,90,255)).save(folder/'image-1.png')
        with self.connect() as con:
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',('rpg',uid,'complete',1,1,json.dumps(dict(jobType='image',sheetLayout=dict(columns=3,rows=4,directions=['front','left','right','back']))),json.dumps(dict(images=[dict(url='/api/images/rpg/image-1.png')]))));con.commit()
        with patch.object(server.image_engine,'RESULT_ROOT',folder.parent):
            created=self.post(self.admin,'jobs/rpg/frames',source='image:0');self.assertEqual(created.status_code,201,created.json)
            info=self.admin.get('/api/frames/'+created.json['id']).json
        self.assertEqual((info['width'],info['height'],len(info['frames'])),(5,5,12));self.assertTrue(info['gridNormalized']);self.assertEqual(info['clips'][1],dict(name='left',start=3,end=5))

    def test_worker_mask_composition_keeps_original_alpha_and_other_pixels(self):
        folder=self.data/'workspaces'/'test';folder.mkdir(parents=True)
        original=Image.new('RGBA',(64,64),(90,50,100,0));ImageDraw.Draw(original).rectangle((5,5,58,58),fill=(90,50,100,255));original.save(folder/'source.png')
        mask=Image.new('L',(64,64));ImageDraw.Draw(mask).rectangle((20,20,35,35),fill=255);mask.save(folder/'mask.png')
        generated=folder/'generated.png';Image.new('RGB',(64,64),(15,200,30)).save(generated)
        changes=[]
        with patch.object(frame_edit.rigging,'INPUT_ROOT',folder),patch.object(frame_edit.requests,'post') as post,patch.object(frame_edit.rigging,'_wait_for_prompt',return_value={}),patch.object(frame_edit.rigging,'_saved_image',return_value=generated),patch.object(frame_edit,'update_job',side_effect=lambda jid,**kw:changes.append(kw)):
            post.return_value.json.return_value={'prompt_id':'test'}
            frame_edit.run_job('candidate',dict(_workspaceRoot=str(folder.parent),workspaceId='test',sourceFile='source.png',maskFile='mask.png',prompt='fix face',frame=0,revision=0))
        with Image.open(folder/'candidates/candidate/candidate.png') as im:output=np.array(im)
        initial=np.array(original);outside=np.array(mask)==0
        np.testing.assert_array_equal(output[outside],initial[outside]);np.testing.assert_array_equal(output[:,:,3],initial[:,:,3]);self.assertNotEqual(tuple(output[25,25,:3]),tuple(initial[25,25,:3]));self.assertEqual(changes[-1]['state'],'complete')
