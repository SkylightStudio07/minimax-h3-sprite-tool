"""Decode exported GIFs and compare their timing, hard alpha and visible pixels."""
import hashlib,json,sys,zipfile
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.export_pixel_handoff_gifs import OUT

def main():
 items=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'));count=0
 for item in items:
  source=Path(item['source']);assert hashlib.sha256(source.read_bytes()).hexdigest()==item['sourceSha256']
  refs=[]
  with Image.open(source) as im:
   for i in range(im.n_frames):im.seek(i);refs.append(np.array(im.convert('RGBA').resize(tuple(item['size']),Image.Resampling.NEAREST)))
  for key,scale in [('gif',1),('preview',3)]:
   decoded=[];durations=[]
   with Image.open(OUT/item[key]) as gif:
    assert gif.info.get('loop')==0
    for i in range(gif.n_frames):gif.seek(i);decoded.append(np.array(gif.convert('RGBA')));durations.append(gif.info['duration'])
   assert sum(durations)==item['totalMs'];time=0
   for expected,span in zip(refs,item['durationMs']):
    k=int(np.searchsorted(np.cumsum(durations),time,side='right'));got=decoded[k]
    if scale!=1:expected=np.repeat(np.repeat(expected,scale,axis=0),scale,axis=1)
    alpha=(expected[:,:,3]>=128)*255;assert np.array_equal(got[:,:,3],alpha),(item[key],time,'alpha')
    if item['exactOpaqueColors']:assert np.array_equal(got[:,:,:3][alpha>0],expected[:,:,:3][alpha>0]),(item[key],time,'colours')
    time+=span;count+=1
 for name in ['pixel-gifs-all.zip','pixel-gifs-latest.zip']:
  with zipfile.ZipFile(OUT/name) as z:assert z.testzip() is None
 report=dict(passed=True,animations=len(items),gifFiles=len(items)*2,decodedSourceFrameChecks=count,sharedPalette=True,alphaAndVisiblePixelsChecked=True,centisecondTimingChecked=True,zipIntegrity=True,sourceHashesPreserved=True)
 (OUT/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)

if __name__=='__main__':main()
