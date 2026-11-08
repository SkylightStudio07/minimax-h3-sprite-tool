import base64,hashlib,io,json,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
import av
from PIL import Image,ImageDraw
import motion_timing as timing

class TimingTests(unittest.TestCase):
 def frames(self):
  out=[]
  for x in [8]*8+list(range(10,35,3))+[34]*18:
   im=Image.new('RGB',(64,64),'#808080');ImageDraw.Draw(im).rectangle((x,12,x+14,52),fill='red');out.append(im)
  return out
 def test_trim_keeps_motion_and_speed_changes_duration(self):
  frames=self.frames();plan=timing.plan(frames,24,2,True)
  self.assertGreater(plan['sourceStart'],0);self.assertLess(plan['sourceEnd'],len(frames)-1)
  self.assertLessEqual(plan['sourceStart'],8);self.assertGreaterEqual(plan['sourceEnd'],16)
  self.assertEqual(plan['totalMs'],round(plan['outputFrames']*1000/48))
  self.assertEqual(timing.plan(frames,24)['sourceIndices'],list(range(len(frames))))
 def test_validation(self):
  self.assertEqual(timing.options({}),dict(motionSpeed=1.,trimAction=False))
  for p in ({'motionSpeed':True},{'motionSpeed':0},{'motionSpeed':float('nan')},{'trimAction':1},{'trimAction':True,'animationType':'run'},{'trimAction':True,'animationType':'attack','loop':True}):
   with self.assertRaises(ValueError):timing.options(p)
 def test_real_video_speed_frames_and_original_preserved(self):
  with tempfile.TemporaryDirectory() as temp:
   source=Path(temp)/'source.mp4';target=Path(temp)/'fast.mp4'
   with av.open(str(source),'w') as clip:
    stream=clip.add_stream('libx264',rate=24);stream.width=64;stream.height=64;stream.pix_fmt='yuv420p'
    for im in self.frames():
     for packet in stream.encode(av.VideoFrame.from_image(im)):clip.mux(packet)
    for packet in stream.encode():clip.mux(packet)
   before=hashlib.sha256(source.read_bytes()).hexdigest()
   report=timing.retime_video(source,target,dict(motionSpeed=2.,trimAction=True))
   with av.open(str(target)) as clip:
    self.assertEqual(float(clip.streams.video[0].average_rate),48)
    self.assertEqual(len(list(clip.decode(video=0))),report['outputFrames'])
   times=timing.sheet_durations(target,8,False);self.assertEqual(len(times),8);self.assertEqual(sum(times),report['totalMs'])
   self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),before)

 def test_actual_job_pipeline_keeps_raw_and_exports_fast_sheet_timing(self):
  import idle_tool as engine
  from types import SimpleNamespace
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);source=root/'native.mp4'
   with av.open(str(source),'w') as out:
    stream=out.add_stream('libx264',rate=24);stream.width=64;stream.height=64;stream.pix_fmt='yuv420p'
    for im in self.frames():
     for packet in stream.encode(av.VideoFrame.from_image(im)):out.mux(packet)
    for packet in stream.encode():out.mux(packet)
   raw_hash=hashlib.sha256(source.read_bytes()).hexdigest();updates=[]
   buf=io.BytesIO();Image.new('RGBA',(256,256),(70,80,120,255)).save(buf,format='PNG')
   p=dict(imageData=base64.b64encode(buf.getvalue()).decode(),width=256,height=256,duration=3,seed=1,animationType='attack',loop=False,
    motionSpeed=2,trimAction=True,stabilize=False,optimizeLoop=False,frameCount=16,removeBackground=False)
   post=SimpleNamespace(ok=True,json=lambda:{'prompt_id':'fake'})
   get=SimpleNamespace(json=lambda:{'fake':{'status':{'status_str':'success','completed':True}}})
   with patch.object(engine,'RESULT_ROOT',root/'results'),patch.object(engine,'upload_image',return_value='fake.png'),patch.object(engine,'find_saved_video',return_value=source),patch.object(engine.requests,'post',return_value=post),patch.object(engine.requests,'get',return_value=get),patch.object(engine,'update_job',side_effect=lambda jid,**kw:updates.append(kw)):
    engine.run_job('job',p)
   result=updates[-1];self.assertEqual(result['state'],'complete',result)
   self.assertEqual(result['motionTiming']['motionSpeed'],2)
   self.assertLess(result['motionTiming']['outputFrames'],len(self.frames()))
   self.assertEqual(sum(result['sheetTimingMs']),result['motionTiming']['totalMs'])
   folder=root/'results/job';self.assertEqual(hashlib.sha256((folder/'attack_raw.mp4').read_bytes()).hexdigest(),raw_hash)
   with av.open(str(folder/'attack.mp4')) as clip:self.assertEqual(float(clip.streams.video[0].average_rate),48)
   self.assertTrue((folder/'attack_sprite_sheet.png').exists())
