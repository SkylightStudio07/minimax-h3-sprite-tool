"""Explicit sprite playback speed and optional one-shot idle trimming."""
from fractions import Fraction
import math
import av
import numpy as np
from PIL import Image
import sprite_loop

SPEEDS=(1.,1.25,1.5,2.,3.)
def options(payload):
 speed=payload.get('motionSpeed',1.)
 if isinstance(speed,bool) or not isinstance(speed,(int,float)) or speed not in SPEEDS:raise ValueError('동작 속도는 1, 1.25, 1.5, 2, 3배 중 선택하세요.')
 trim=payload.get('trimAction',False)
 if not isinstance(trim,bool):raise ValueError('공격 앞뒤 멈춤 정리는 체크박스로 선택하세요.')
 if trim and (payload.get('animationType','idle')!='attack' or payload.get('loop',False)):raise ValueError('멈춤 정리는 반복하지 않는 공격에서 사용하세요.')
 return dict(motionSpeed=float(speed),trimAction=trim)

def plan(frames,fps,speed=1.,trim=False):
 if not frames or fps<=0 or fps*speed>100:raise ValueError('재생할 프레임과 속도를 확인하세요.')
 start,end=0,len(frames)-1;scores=[]
 if trim and len(frames)>8:
  small=[np.asarray(im.convert('RGB').resize((192,192),Image.Resampling.BILINEAR),dtype=float) for im in frames]
  for before,after in zip(small,small[1:]):
   delta=np.abs(after-before).mean(axis=2).ravel();top=max(1,len(delta)//50)
   scores.append(float(np.partition(delta,-top)[-top:].mean()))
  threshold=max(2.,max(scores)*.18)
  active=[i+1 for i,v in enumerate(scores) if v>=threshold]
  if active:
   start=max(0,active[0]-3);end=min(len(frames)-1,active[-1]+5)
   if end-start<7:start=max(0,end-7)
 indices=list(range(start,end+1));rate=fps*speed
 ticks=[round(i*1000/rate) for i in range(len(indices)+1)]
 durations=[b-a for a,b in zip(ticks,ticks[1:])]
 return dict(sourceIndices=indices,durationMs=durations,motionSpeed=speed,trimAction=trim,
  sourceFrames=len(frames),sourceFps=fps,sourceStart=start,sourceEnd=end,outputFrames=len(indices),outputFps=rate,totalMs=sum(durations),
  motionScores=scores,method='fixed playback speed + conservative frame-change trim' if trim else 'fixed playback speed')

def retime_video(source,target,settings):
 with av.open(str(source)) as clip:
  fps=float(clip.streams.video[0].average_rate or 24);frames=[f.to_image().convert('RGB') for f in clip.decode(video=0)]
 report=plan(frames,fps,settings['motionSpeed'],settings['trimAction'])
 with av.open(str(target),'w') as out:
  stream=out.add_stream('libx264',rate=Fraction(str(report['outputFps'])).limit_denominator(1000))
  stream.width,stream.height=frames[0].size;stream.pix_fmt='yuv420p';stream.options={'crf':'16'}
  for i in report['sourceIndices']:
   for packet in stream.encode(av.VideoFrame.from_image(frames[i])):out.mux(packet)
  for packet in stream.encode():out.mux(packet)
 return report

def sheet_durations(video,count,loop):
 with av.open(str(video)) as clip:
  fps=float(clip.streams.video[0].average_rate or 24);n=sum(1 for _ in clip.decode(video=0))
 indices=sprite_loop.sample_indices(n,min(count,n),loop)
 bounds=[round(int(i)*1000/fps) for i in indices]+[round(n*1000/fps)]
 return [b-a for a,b in zip(bounds,bounds[1:])]
