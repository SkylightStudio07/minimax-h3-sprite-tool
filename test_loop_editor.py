"""Real decoded video frames, isolated API/SQLite; no GPU/model requests."""
from contextlib import closing
import io
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch
import zipfile

import av
from PIL import Image,ImageDraw
import loop_editor
import character_studio
import test_team_server as fixture
import team_server as server


def video_fixture(path,count=24):
    with av.open(str(path),'w') as container:
        stream=container.add_stream('libx264',rate=12);stream.width=64;stream.height=96;stream.pix_fmt='yuv420p'
        for i in range(count):
            image=Image.new('RGB',(64,96),(40,40,40));d=ImageDraw.Draw(image);d.rectangle((10+i,20,30+i,80),fill=(80+i*5,140,190))
            for packet in stream.encode(av.VideoFrame.from_image(image)):container.mux(packet)
        for packet in stream.encode():container.mux(packet)


class LoopTests(unittest.TestCase):
    post=fixture.TeamTests.post

    def setUp(self):
        fixture.TeamTests.setUp(self);self.addCleanup(lambda:fixture.TeamTests.tearDown(self));fixture.TeamTests.approve(self)
        self.folder=self.data/'results'/'clip';self.folder.mkdir(parents=True);video_fixture(self.folder/'video.mp4')
        self.root_patch=patch.object(server.engine,'RESULT_ROOT',self.folder.parent);self.root_patch.start();self.addCleanup(self.root_patch.stop)
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            uid=self.admin.get('/api/me').json['user']['id']
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',('clip',uid,'complete',1,1,json.dumps(dict(animationType='walk')),json.dumps(dict(video='/outputs/results/clip/video.mp4'))));con.commit()

    def test_metadata_frames_and_access(self):
        self.assertEqual(self.guest.get('/api/jobs/clip/loop-editor').status_code,401)
        self.assertEqual(self.member.get('/api/jobs/clip/loop-editor').status_code,403)
        meta=self.admin.get('/api/jobs/clip/loop-editor').json;self.assertEqual(meta['frameCount'],24);self.assertAlmostEqual(meta['duration'],2)
        self.assertEqual(meta['fps'],12);self.assertEqual(meta['times'][0],0)
        for query in ('source=../../else','source=rawVideo'):
            self.assertEqual(self.admin.get('/api/jobs/clip/loop-editor?'+query).status_code,400)
        response=self.admin.get('/api/jobs/clip/loop-frame?frame=6');self.assertEqual(response.status_code,200);self.assertIn('no-store',response.headers['Cache-Control'])
        with av.open(str(self.folder/'video.mp4')) as container:expected=list(container.decode(video=0))[6].to_image()
        with Image.open(io.BytesIO(response.data)) as image:self.assertEqual(image.tobytes(),expected.tobytes())
        for value in ('-1','24','no'):
            self.assertEqual(self.admin.get('/api/jobs/clip/loop-frame?frame='+value).status_code,400)

    def test_small_trail_export_uses_character_and_effect_matte(self):
        import sprite_vfx_matte
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            con.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(dict(combatEffect='subtle',pixelOutput=False)),'clip'));con.commit()
        def matte(image):
            result=image.copy();result.putalpha(180);return result,{}
        with patch.object(server.engine.image_background,'status',return_value=dict(ready=True)),patch.object(sprite_vfx_matte,'remove',side_effect=matte) as cut:
            response=self.post(self.admin,'jobs/clip/loop-editor',source='video',start=2,end=10,count=4,fps=6,background='flat')
            self.assertEqual(response.status_code,201,response.json)
            self.assertEqual(cut.call_count,4)

    def test_export_exact_pixels_timing_and_existing_result_preserved(self):
        params=dict(source='video',start=4,end=19,count=8,fps=6,background='keep')
        self.assertEqual(self.post(self.member,'jobs/clip/loop-editor',**params).status_code,403)
        response=self.post(self.admin,'jobs/clip/loop-editor',**params);self.assertEqual(response.status_code,201,response.json)
        wid=response.json['id'];doc=self.admin.get('/api/frames/'+wid).json
        self.assertEqual(len(doc['frames']),8);self.assertEqual(doc['fps'],6)
        self.assertEqual([f['sourceFrame'] for f in doc['frames']],loop_editor.indices(4,19,8))
        self.assertAlmostEqual(doc['videoRange']['duration'],16/12)
        with av.open(str(self.folder/'video.mp4')) as container:decoded=[f.to_image().convert('RGBA') for f in container.decode(video=0)]
        with zipfile.ZipFile(io.BytesIO(self.admin.get(response.json['download']).data)) as archive:
            for i,n in enumerate(loop_editor.indices(4,19,8)):
                with Image.open(io.BytesIO(archive.read(f'frames/{i:03d}.png'))) as image:self.assertEqual(image.tobytes(),decoded[n].tobytes())
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:result=json.loads(con.execute("SELECT result FROM jobs WHERE id='clip'").fetchone()[0])
        self.assertEqual(result['video'],'/outputs/results/clip/video.mp4');self.assertEqual(result['frameWorkspace']['id'],wid)
        second=self.post(self.admin,'jobs/clip/loop-editor',**params);self.assertNotEqual(second.json['id'],wid)
        self.assertEqual(self.admin.get('/api/frames/'+wid).status_code,200)

    def test_validation_and_failure_cleanup(self):
        params=dict(start=4,end=12,count=6,fps=8)
        for change in (dict(start=True),dict(end=24),dict(end=4),dict(end=3),dict(count=12),dict(count=1),dict(fps=1.5),dict(background='bad')):
            self.assertEqual(self.post(self.admin,'jobs/clip/loop-editor',**(params|change)).status_code,400,change)
        with patch.object(character_studio,'make_sheet',side_effect=ValueError('failed')):
            self.assertEqual(self.post(self.admin,'jobs/clip/loop-editor',**params).status_code,400)
        self.assertEqual(list((self.data/'frame-workspaces').iterdir()),[])
        # Failure releases the shared extraction lock.
        self.assertEqual(self.post(self.admin,'jobs/clip/loop-editor',**params).status_code,201)

    def test_sampler_has_no_duplicate_frames(self):
        for available in (2,3,8,31,70):
            for count in range(2,min(64,available)+1):
                values=loop_editor.indices(7,7+available-1,count)
                self.assertEqual(len(set(values)),count);self.assertEqual(values[0],7);self.assertEqual(values[-1],7+available-1)
