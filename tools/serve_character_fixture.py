"""Disposable local integration fixture, never connected to production accounts or the GPU queue."""
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
from contextlib import closing
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image,ImageDraw
from flask import jsonify
import team_server as server
import character_studio
os.environ['SPRITE_HTTPS']='0'
temporary=tempfile.TemporaryDirectory();data=Path(temporary.name)
def fake_face_runner(jid,p):
 import image_face_refine
 folder=server.image_engine.RESULT_ROOT/jid
 with Image.open(folder/'image-1-before-face.png') as im:original=im.convert('RGBA')
 mask=Image.new('L',original.size);ImageDraw.Draw(mask).ellipse((int(original.width*.4),int(original.height*.05),int(original.width*.6),int(original.height*.2)),fill=255)
 edited,box=image_face_refine.composite(original,Image.new('RGB',original.size,(120,160,210)),mask);edited.save(folder/'image-1.png')
 image=dict(url=f'/api/images/{jid}/image-1.png',beforeFaceUrl=f'/api/images/{jid}/image-1-before-face.png',seed=42,faceBox=box,faceDetailApplied=True)
 server.image_engine.update_job(jid,state='complete',message='fixture face refinement',image=image['url'],images=[image])
app=server.create_app(data,runner=lambda *_:None,image_runner=fake_face_runner if '--fake-face' in sys.argv else None)
from werkzeug.security import generate_password_hash
with closing(sqlite3.connect(data/'team.sqlite3')) as con:
 con.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)',(1,'fixture','테스트',generate_password_hash('fixture-password'),'approved','admin',time.time()))
 con.commit()
server.engine.RESULT_ROOT=data/'results';folder=server.engine.RESULT_ROOT/'sprite';folder.mkdir(parents=True)
sheet=Image.new('RGBA',(128,64));draw=ImageDraw.Draw(sheet)
for i in range(4):draw.rounded_rectangle((i*32+7,8,i*32+24,58),radius=6,fill=(70+30*i,100,160,255));draw.ellipse((i*32+10,8,i*32+21,23),fill=(250,210,190,255))
sheet.save(folder/'sheet.png')
from test_loop_editor import video_fixture
video_fixture(folder/'video.mp4')
if '--gait-preview' in sys.argv:
 import shutil
 shutil.copyfile(Path(__file__).resolve().parents[1]/'outputs/gait-video-20261018/run/run_raw.mp4',folder/'video.mp4')
server.image_engine.RESULT_ROOT=(Path(tempfile.mkdtemp(prefix='image-journey-',dir=server.ROOT/'outputs')) if '--real-image' in sys.argv else data/'images');art=server.image_engine.RESULT_ROOT/'art';art.mkdir(parents=True)
sheet.crop((0,0,32,64)).save(art/'image-1.png')
with closing(sqlite3.connect(data/'team.sqlite3')) as con:
 uid=con.execute("SELECT id FROM users WHERE username='fixture'").fetchone()[0]
 con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',('sprite',uid,'complete',1,1,json.dumps(dict(frameCount=4,animationType='walk')),json.dumps(dict(spriteSheet='/outputs/results/sprite/sheet.png',video='/outputs/results/sprite/video.mp4'))))
 con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',('art',uid,'complete',1,1,json.dumps(dict(jobType='image',model='wai-cutscene-counter',prompt='hood, navy coat',animationType='캐릭터 원화',title='캐릭터 원화')),json.dumps(dict(image='/api/images/art/image-1.png',images=[dict(url='/api/images/art/image-1.png',seed=1)]))))
 con.commit()

if '--face-refine' in sys.argv:
 import shutil
 jid='c'*32;folder=server.image_engine.RESULT_ROOT/jid;folder.mkdir()
 source=server.ROOT/'outputs/cutscene-cleanup-20261018/no-series-negative-halo.png'
 shutil.copyfile(source,folder/'image-1.png')
 settings=dict(jobType='image',model='wai-cutscene-counter',title='얼굴 보정 검증',prompt='short dark hair, same character, same facial expression',preset='illustration',mode='reference',assetSpec=dict(type='side',facing='right',directionCount=1))
 result=dict(image=f'/api/images/{jid}/image-1.png',images=[dict(url=f'/api/images/{jid}/image-1.png',seed=20261018)])
 with closing(sqlite3.connect(data/'team.sqlite3')) as con:
  con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(jid,uid,'complete',2,2,json.dumps(settings),json.dumps(result)));con.commit()

@app.post('/__fixture/finish/<task>')
def finish(task):
 with closing(sqlite3.connect(data/'team.sqlite3')) as con:
  p=json.loads(con.execute('SELECT payload FROM jobs WHERE id=?',(task,)).fetchone()[0]);folder=data/'frame-workspaces'/p['workspaceId'];target=folder/'candidates'/task;target.mkdir(parents=True,exist_ok=True)
  with Image.open(folder/p['sourceFile']) as im:source=im.convert('RGBA')
  with Image.open(folder/p['maskFile']) as im:mask=im.convert('L')
  edited=Image.composite(Image.new('RGBA',source.size,(80,200,70,255)),source,mask);edited.putalpha(source.getchannel('A'));edited.save(target/'candidate.png')
  (target/'candidate.json').write_text(json.dumps(dict(workspaceId=p['workspaceId'],revision=p['revision'],frame=p['frame'],seed=123)))
  con.execute("UPDATE jobs SET state='complete',result=? WHERE id=?",(json.dumps(dict(message='fixture candidate complete')),task))
  con.commit()
 return jsonify(ok=True)

@app.post('/__fixture/finish-motion/<task>')
def finish_motion(task):
 with closing(sqlite3.connect(data/'team.sqlite3')) as con:
  row=con.execute('SELECT user_id,payload FROM jobs WHERE id=?',(task,)).fetchone();p=json.loads(row[1]);folder=data/'frame-workspaces'/p['workspaceId'];folder.mkdir(exist_ok=True)
  for i in range(len(p['poses'])):sheet.crop((i%4*32,0,(i%4+1)*32,64)).save(folder/f'original-{i:03d}.png')
  doc=dict(revision=0,width=32,height=64,columns=len(p['poses']),rows=1,fps=p['fps'],clips=[dict(name=p.get('action','walk'),start=0,end=len(p['poses'])-1)],motion=dict(action=p.get('action','walk'),appearanceAnchorFrame=0,consistency=p.get('consistency','independent')),frames=[dict(file=f'original-{i:03d}.png',locked=False) for i in range(len(p['poses']))])
  con.execute('INSERT OR IGNORE INTO frame_workspaces VALUES(?,?,?,?,?,?,?)',(p['workspaceId'],None,p.get('characterId'),row[0],json.dumps(doc),time.time(),time.time()))
  con.execute('INSERT OR IGNORE INTO frame_versions VALUES(?,?,?,?)',(p['workspaceId'],0,json.dumps(doc),time.time()))
  con.execute("UPDATE jobs SET state='complete',result=? WHERE id=?",(json.dumps(dict(message='fixture walk complete',workspaceId=p['workspaceId'],editor='/frame-editor?set='+p['workspaceId'])),task));con.commit()
 return jsonify(ok=True)

if __name__=='__main__':
 from werkzeug.serving import make_server
 http=make_server('127.0.0.1',0,app,threaded=True)
 if '--fake-face' in sys.argv:app.start_worker()
 if '--real-image' in sys.argv:
  from tools.verify_rpg_sprite_styles import ensure_idle
  ensure_idle();app.start_worker()
 print(json.dumps(dict(port=http.server_port,imageRoot=str(server.image_engine.RESULT_ROOT))),flush=True)
 try:http.serve_forever()
 finally:temporary.cleanup()
