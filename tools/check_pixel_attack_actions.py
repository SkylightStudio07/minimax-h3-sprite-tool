"""Reusable file-level checks for separately reviewed pixel action experiments."""
import json,hashlib,re,sys
from pathlib import Path
import av,numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.verify_pixel_attack_actions import OUT,OFFSET,WIDTH,HEIGHT,SCALE
from pixel_attack_prompts import TEMPLATES

def main():
 report={}
 for key in TEMPLATES:
  folder=OUT/key
  if not (folder/'frames.json').exists():continue
  source=json.loads((folder/'source-settings.json').read_text(encoding='utf-8'));palette={tuple(c) for c in source['palette']}
  rawpath=Path(source['source']);assert hashlib.sha256(rawpath.read_bytes()).hexdigest()==source['sha256']
  original=np.array(Image.open(rawpath).convert('RGBA'));padded=np.array(Image.open(folder/'reference.png').convert('RGBA'));x,y=OFFSET
  assert np.array_equal(padded[y:y+128,x:x+128],original)
  outside=padded.copy();outside[y:y+128,x:x+128]=0;assert not outside.any()
  enlarged=Image.fromarray(padded).resize((WIDTH*SCALE,HEIGHT*SCALE),Image.Resampling.NEAREST)
  expected=Image.new('RGB',enlarged.size,(128,128,128));expected.paste(enlarged,mask=enlarged.getchannel('A'))
  assert np.array_equal(np.array(expected),np.array(Image.open(folder/'video-input.png').convert('RGB')))
  settings=json.loads((folder/'video-settings.json').read_text(encoding='utf-8'))
  with av.open(str(folder/'action-raw.mp4')) as v:
   stream=v.streams.video[0];assert (stream.width,stream.height)==tuple(source['videoSize']) and float(stream.average_rate)==24
   count=sum(1 for _ in v.decode(video=0));assert count==settings['frames']
  allframes=list((folder/'all-frames').glob('frame-*.png'));assert len(allframes)==count
  for p in allframes:
   a=np.array(Image.open(p).convert('RGBA'));assert a.shape==(HEIGHT,WIDTH,4) and set(np.unique(a[:,:,3]))<={0,255};assert a[:,:,3].any()
   assert {tuple(c) for c in np.unique(a[:,:,:3][a[:,:,3]>0],axis=0)}<=palette
  meta=json.loads((folder/'frames.json').read_text(encoding='utf-8'));indices=meta['sourceIndices'];n=len(indices)
  assert indices==sorted(set(indices)) and len(meta['durationMs'])==n
  assert all(20<=t<=2000 for t in meta['durationMs'])
  strip=Image.open(folder/'sheet.png').convert('RGBA');grid=Image.open(folder/'sheet-grid.png').convert('RGBA')
  assert strip.size==(WIDTH*n,HEIGHT) and grid.size==(WIDTH*meta['columns'],HEIGHT*meta['rows'])
  for j,i in enumerate(indices):
   a=np.array(Image.open(folder/f'frame-{j:02d}.png'));assert np.array_equal(a,np.array(Image.open(folder/'all-frames'/f'frame-{i:03d}.png')))
   col,row=j%meta['columns'],j//meta['columns']
   assert np.array_equal(a,np.array(grid.crop((col*WIDTH,row*HEIGHT,(col+1)*WIDTH,(row+1)*HEIGHT))))
   assert np.array_equal(a,np.array(strip.crop((j*WIDTH,0,(j+1)*WIDTH,HEIGHT))))
  for name in ['animation.png','animation.webp']:assert Image.open(folder/name).n_frames==n
  assert Image.open(folder/'full-animation.webp').n_frames==count
  assert hashlib.sha256((folder/'video-input.png').read_bytes()).hexdigest()==json.loads((folder/'upload.json').read_text())['sha256']
  report[key]=dict(videoSize=source['videoSize'],frameSize=[WIDTH,HEIGHT],sourceFrames=count,sourceFPS=24,selectedFrames=n,playbackMs=sum(meta['durationMs']),paletteLimit=len(palette),binaryAlpha=True,correctedSourcePixelsUnchanged=True)
 page=(OUT/'preview.html').read_text(encoding='utf-8')
 for url in re.findall(r'(?:src|href)=["\']([^"\']+)',page):
  if not url.startswith(('http','data:','#')):assert (OUT/url).exists(),url
 cfg=json.loads(re.search(r'<script id="configs" type="application/json">(.*?)</script>',page,re.S).group(1))
 for item in cfg:
  assert len(item['labels'])==len(item['indices'])==len(item['durations'])
  for i in range(len(item['indices'])):assert (OUT/item['id']/f'frame-{i:02d}.png').exists()
 templates=json.loads((OUT/'templates.json').read_text(encoding='utf-8'))
 assert set(report)==set(TEMPLATES)
 for key in TEMPLATES:
  assert templates[key]['status']!='experimental; observed motion review pending'
  assert templates[key]['observedPhases'] and templates[key]['limitations']
 report.update(actualBrowserVerified=False,checks='Source/input hashes, exact original RGBA placement and nearest-neighbour grey video input, all frame palettes/alpha/dimensions, exact selections and sheets, animation counts, local links and reviewed template metadata')
 (OUT/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
