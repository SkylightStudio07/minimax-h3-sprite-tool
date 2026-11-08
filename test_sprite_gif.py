import io,json,unittest
from PIL import Image,ImageDraw
import numpy as np
import sprite_gif
from unittest.mock import patch
import character_studio
import tempfile,threading
from pathlib import Path
from urllib.request import urlopen
from http.server import ThreadingHTTPServer
from test_character_studio import CharacterTests

class GifEncodingTests(unittest.TestCase):
 def test_standalone_http_gif_download(self):
  import idle_tool
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);folder=root/'outputs/results/demo';folder.mkdir(parents=True)
   sheet=Image.new('RGBA',(32,16));ImageDraw.Draw(sheet).rectangle((1,2,5,8),fill='red');ImageDraw.Draw(sheet).rectangle((23,2,27,8),fill='red');sheet.save(folder/'sheet.png')
   with patch.object(idle_tool,'ROOT',root),patch.object(idle_tool,'RESULT_ROOT',folder.parent),patch.object(idle_tool,'JOBS',{'demo':dict(state='complete',spriteSheet='/outputs/results/demo/sheet.png',frameCount=2)}):
    server=ThreadingHTTPServer(('127.0.0.1',0),idle_tool.Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
     with urlopen(f'http://127.0.0.1:{server.server_port}/api/jobs/demo/sheet.gif?source=spriteSheet') as r:
      self.assertEqual(r.headers['Content-Type'],'image/gif');data=r.read()
     with Image.open(io.BytesIO(data)) as gif:self.assertEqual(gif.n_frames,2);self.assertEqual(gif.size,(16,16))
    finally:server.shutdown();server.server_close();thread.join()

 def test_shared_exact_palette_transparency_no_trail_and_timing(self):
  frames=[]
  for x in [1,9,17]:
   a=Image.new('RGBA',(32,24));ImageDraw.Draw(a).rectangle((x,5,x+4,10),fill=(150,70,25,255));frames.append(a)
  data,meta=sprite_gif.encode(frames,[42,42,42])
  self.assertEqual(meta['durationMs'],[40,40,50]);self.assertTrue(meta['exactOpaqueColors'])
  with Image.open(io.BytesIO(data)) as gif:
   self.assertEqual(gif.n_frames,3)
   for i,want in enumerate(frames):
    gif.seek(i);got=np.array(gif.convert('RGBA'));ref=np.array(want);self.assertTrue(np.array_equal(got[:,:,3],ref[:,:,3]));self.assertTrue(np.array_equal(got[ref[:,:,3]>0],ref[ref[:,:,3]>0]));self.assertEqual(gif.info['duration'],meta['durationMs'][i])
 def test_quantized_many_colors_opaque_and_invalid_limits(self):
  a=np.zeros((32,32,4),np.uint8);a[:,:,0]=np.arange(32)[None]*8;a[:,:,1]=np.arange(32)[:,None]*8;a[:,:,3]=255
  data,meta=sprite_gif.encode([Image.fromarray(a)],[125]);self.assertFalse(meta['exactOpaqueColors'])
  self.assertTrue(np.all(np.array(Image.open(io.BytesIO(data)).convert('RGBA'))[:,:,3]==255))
  for times in [[],[0],[float('nan')],[True]]:
   with self.assertRaises(ValueError):sprite_gif.encode([Image.fromarray(a)],times)
 def test_sheet_count_excludes_empty_cells(self):
  frames=sprite_gif.split_sheet(Image.new('RGBA',(96,64),'red'),3,2,5);self.assertEqual(len(frames),5);self.assertEqual(frames[0].size,(32,32))

class GifRouteTests(CharacterTests):
 def test_normal_sheet_preserves_processed_action_timing(self):
  self.approve();self.fixture()
  root_patch=patch.object(character_studio.engine,'RESULT_ROOT',self.data/'results');root_patch.start();self.addCleanup(root_patch.stop)
  with self.connect() as con:
   result=json.loads(con.execute("SELECT result FROM jobs WHERE id='sprite'").fetchone()[0]);result.update(sheetTimingMs=[40,110])
   con.execute("UPDATE jobs SET result=? WHERE id='sprite'",(json.dumps(result),));con.commit()
  response=self.admin.get('/api/jobs/sprite/sheet.gif?source=spriteSheet')
  self.assertEqual(response.status_code,200,response.json)
  with Image.open(io.BytesIO(response.data)) as gif:
   self.assertEqual(gif.info['duration'],40);gif.seek(1);self.assertEqual(gif.info['duration'],110)
  response=self.admin.get('/api/jobs/sprite/sheet.gif?source=spriteSheet&fps=10')
  with Image.open(io.BytesIO(response.data)) as gif:self.assertEqual(gif.info['duration'],100)
  wid=self.post(self.admin,'jobs/sprite/frames',source='spriteSheet',columns=2,rows=1,count=2).json['id']
  doc=self.admin.get('/api/frames/'+wid).json
  self.assertEqual([f['durationMs'] for f in doc['frames']],[40,110])
  response=self.admin.get('/api/frames/'+wid+'/animation.gif')
  with Image.open(io.BytesIO(response.data)) as gif:self.assertEqual(gif.info['duration'],40);gif.seek(1);self.assertEqual(gif.info['duration'],110)
  self.assertEqual(self.post(self.admin,'frames/'+wid+'/settings',revision=0,fps=20).status_code,200)
  response=self.admin.get('/api/frames/'+wid+'/animation.gif')
  with Image.open(io.BytesIO(response.data)) as gif:self.assertEqual(gif.info['duration'],50);gif.seek(1);self.assertEqual(gif.info['duration'],50)

 def test_pixel_sheet_uses_actual_frame_count_and_recorded_timing(self):
  self.approve();self.fixture()
  root_patch=patch.object(character_studio.engine,'RESULT_ROOT',self.data/'results');root_patch.start();self.addCleanup(root_patch.stop)
  with self.connect() as con:
   result=json.loads(con.execute("SELECT result FROM jobs WHERE id='sprite'").fetchone()[0])
   result.update(frameCount=2,pixelExport=dict(durationMs=[120,380]))
   con.execute("UPDATE jobs SET payload=?,result=? WHERE id='sprite'",(json.dumps(dict(jobType='video',frameCount=30)),json.dumps(result)));con.commit()
  response=self.admin.get('/api/jobs/sprite/sheet.gif?source=spriteSheet')
  self.assertEqual(response.status_code,200,response.json)
  with Image.open(io.BytesIO(response.data)) as gif:
   self.assertEqual(gif.n_frames,2);self.assertEqual(gif.info['duration'],120);gif.seek(1);self.assertEqual(gif.info['duration'],380)
  response=self.admin.get('/api/jobs/sprite/sheet.gif?source=spriteSheet&fps=10')
  with Image.open(io.BytesIO(response.data)) as gif:self.assertEqual(gif.info['duration'],100)

 def test_reextracted_count_and_image_sheet_sources(self):
  self.approve();folder=self.fixture()
  root_patch=patch.object(character_studio.engine,'RESULT_ROOT',self.data/'results');root_patch.start();self.addCleanup(root_patch.stop)
  image_patch=patch.object(character_studio.image_engine,'RESULT_ROOT',self.data/'images');image_patch.start();self.addCleanup(image_patch.stop)
  grid=Image.new('RGBA',(128,32))
  for i in range(10):ImageDraw.Draw(grid).rectangle((i%8*16+2,i//8*16+2,i%8*16+10,i//8*16+10),fill=(20+i*10,70,110,255))
  grid.save(folder/'extra.png')
  with self.connect() as con:
   result=json.loads(con.execute("SELECT result FROM jobs WHERE id='sprite'").fetchone()[0]);result['exportSheets']={'sheet_10_0123456789abcdef_transparent':'/outputs/results/sprite/extra.png'}
   con.execute("UPDATE jobs SET result=? WHERE id='sprite'",(json.dumps(result),));con.commit()
  response=self.admin.get('/api/jobs/sprite/sheet.gif?source=export:sheet_10_0123456789abcdef_transparent')
  with Image.open(io.BytesIO(response.data)) as gif:self.assertEqual(gif.n_frames,10);self.assertEqual(gif.size,(16,16))
  art=self.data/'images'/'art';art.mkdir(parents=True);grid.crop((0,0,48,32)).save(art/'sheet.png')
  with self.connect() as con:
   uid=self.admin.get('/api/me').json['user']['id'];con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',('art',uid,'complete',1,1,json.dumps(dict(jobType='image',sheetLayout=dict(columns=3,rows=2))),json.dumps(dict(images=[dict(url='/api/images/art/sheet.png')]))));con.commit()
  response=self.admin.get('/api/jobs/art/sheet.gif?source=image:0');self.assertEqual(response.status_code,200)
  with Image.open(io.BytesIO(response.data)) as gif:self.assertEqual(gif.size,(16,16))

 def test_job_sheet_gif_and_workspace_clip_auth(self):
  self.approve();self.fixture()
  root_patch=patch.object(character_studio.engine,'RESULT_ROOT',self.data/'results');root_patch.start();self.addCleanup(root_patch.stop)
  self.assertEqual(self.guest.get('/api/jobs/sprite/sheet.gif').status_code,401)
  response=self.admin.get('/api/jobs/sprite/sheet.gif?source=spriteSheet&fps=6');self.assertEqual(response.status_code,200,response.json)
  with Image.open(io.BytesIO(response.data)) as gif:self.assertEqual(gif.n_frames,2);self.assertEqual(gif.size,(32,32));self.assertEqual(gif.info['duration'],170)
  for query in ['source=../../else','fps=0','fps=NaN','fps=61']:
   self.assertEqual(self.admin.get('/api/jobs/sprite/sheet.gif?'+query).status_code,400)
  wid=self.post(self.admin,'jobs/sprite/frames',source='spriteSheet',columns=2,rows=1,count=2).json['id']
  result=self.admin.get('/api/frames/'+wid+'/animation.gif');self.assertEqual(result.status_code,200)
  self.assertEqual(self.guest.get('/api/frames/'+wid+'/animation.gif').status_code,401)
  self.assertEqual(self.admin.get('/api/frames/'+wid+'/animation.gif?clip=99').status_code,400)
  with self.connect() as con:
   doc=json.loads(con.execute('SELECT document FROM frame_workspaces WHERE id=?',(wid,)).fetchone()[0]);doc['clips']=[dict(name='right',start=1,end=1)];doc['fps']=5
   con.execute('UPDATE frame_workspaces SET document=? WHERE id=?',(json.dumps(doc),wid));con.commit()
  result=self.admin.get('/api/frames/'+wid+'/animation.gif?clip=0')
  with Image.open(io.BytesIO(result.data)) as gif:self.assertEqual(gif.n_frames,1);self.assertEqual(gif.info['duration'],200)
  with self.connect() as con:
   result=json.loads(con.execute("SELECT result FROM jobs WHERE id='sprite'").fetchone()[0]);result['spriteSheet']='/outputs/results/sprite/../../private.png';con.execute("UPDATE jobs SET result=? WHERE id='sprite'",(json.dumps(result),));con.commit()
  self.assertEqual(self.admin.get('/api/jobs/sprite/sheet.gif').status_code,400)

if __name__=='__main__':unittest.main()
