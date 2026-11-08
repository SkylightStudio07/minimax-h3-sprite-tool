"""Measure visible cyan coverage on identical native canvases; no rescaling of effects."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from PIL import Image,ImageDraw,ImageFont
OLD=ROOT/'outputs/normal-sword-vfx-contained-20261020'

def scan(folder):
 rows=[]
 for file in sorted((folder/'all-frames').glob('frame-*.png')):
  rgba=np.asarray(Image.open(file).convert('RGBA')).astype(int);r,g,b,a=rgba.transpose(2,0,1)
  mask=(b-r>40)&(g>130)&(b>180)&(a>96)
  y,x=np.where(mask)
  if len(x):rows.append(dict(frame=int(file.stem.split('-')[-1]),pixels=len(x),width=int(x.max()-x.min()+1),height=int(y.max()-y.min()+1)))
 assert rows
 peak=max(rows,key=lambda r:r['pixels'])
 return dict(peak=peak,maxWidth=max(r['width'] for r in rows),maxHeight=max(r['height'] for r in rows),framesWithCyan=len(rows))

def measure(out):
 report={};canvas=Image.new('RGB',(1536,832),'#17202e');draw=ImageDraw.Draw(canvas);font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',24)
 for row,name in enumerate(('slash','spin')):
  before,after=scan(OLD/name),scan(out/name)
  assert hashlib.sha256((OLD/name/'reference-prepared.png').read_bytes()).digest()==hashlib.sha256((out/name/'reference-prepared.png').read_bytes()).digest()
  old_settings=json.loads((OLD/name/'settings.json').read_text());new_settings=json.loads((out/name/'settings.json').read_text())
  assert old_settings['seed']==new_settings['seed']
  report[name]=dict(before=before,after=after,peakCyanAreaRatio=round(after['peak']['pixels']/before['peak']['pixels'],4),
   peakWidthRatio=round(after['peak']['width']/before['peak']['width'],4),peakHeightRatio=round(after['peak']['height']/before['peak']['height'],4),
   samePreparedReference=True,sameSeed=True,method='thresholded visible cyan coverage; excludes white core and gold sparks; approximate comparison, not a semantic effect mask')
  for col,(folder,result,label) in enumerate(((OLD/name,before,'이전'),(out/name,after,'축소 요청'))):
   im=Image.open(folder/'all-frames'/f'frame-{result["peak"]["frame"]:03d}.png').convert('RGBA').resize((384,384),Image.Resampling.LANCZOS)
   x=col*768;y=row*416;canvas.paste(im,(x+192,y+32),im);draw.text((x+24,y+4),('검 휘두르기' if name=='slash' else '회전베기')+' · '+label,font=font,fill='white')
 canvas.save(out/'size-comparison.webp');(out/'size-comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=='__main__':measure(ROOT/'outputs/normal-sword-vfx-small-20261020')
