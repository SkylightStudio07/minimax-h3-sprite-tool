"""Artifact acceptance for the private triple-slash sprite generation."""
from pathlib import Path
import hashlib,json,re
import av,numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/pixel-sword-combo-20261019'
def main():
 source=json.loads((OUT/'source-settings.json').read_text(encoding='utf-8'));palette={tuple(c) for c in source['palette']};w,h=source['spriteSize']
 p=Path(source['source']);assert hashlib.sha256(p.read_bytes()).hexdigest()==source['sha256']
 original=np.array(Image.open(p).convert('RGBA'));padded=np.array(Image.open(OUT/'reference.png').convert('RGBA'));assert np.array_equal(padded[:128,8:136],original)
 assert not padded[:,:8,3].any() and not padded[:,136:,3].any()
 expected=json.loads((OUT/'video-settings.json').read_text(encoding='utf-8'))['frames']
 with av.open(str(OUT/'combo-raw.mp4')) as video:
  stream=video.streams.video[0];assert (stream.width,stream.height)==tuple(source['videoSize']) and float(stream.average_rate)==24
  count=sum(1 for _ in video.decode(video=0));assert count==expected
 allframes=list((OUT/'all-frames').glob('frame-*.png'));assert len(allframes)==count
 for path in allframes:
  a=np.array(Image.open(path).convert('RGBA'));assert a.shape==(h,w,4) and set(np.unique(a[:,:,3]))<={0,255};assert a[:,:,3].any()
  assert {tuple(c) for c in np.unique(a[:,:,:3][a[:,:,3]>0],axis=0)}<=palette
 meta=json.loads((OUT/'frames.json').read_text(encoding='utf-8'));indices=meta['sourceIndices'];n=len(indices);assert indices==sorted(set(indices))
 assert len(meta['durationMs'])==n and all(20<=t<=2000 for t in meta['durationMs'])
 grid=Image.open(OUT/'sheet-grid.png').convert('RGBA');strip=Image.open(OUT/'sheet.png').convert('RGBA')
 assert grid.size==(w*meta['columns'],h*meta['rows']) and strip.size==(w*n,h)
 for j,i in enumerate(indices):
  a=np.array(Image.open(OUT/f'frame-{j:02d}.png'));assert np.array_equal(a,np.array(Image.open(OUT/'all-frames'/f'frame-{i:03d}.png')))
  assert np.array_equal(a,np.array(strip.crop((j*w,0,(j+1)*w,h))))
  col,row=j%meta['columns'],j//meta['columns'];assert np.array_equal(a,np.array(grid.crop((col*w,row*h,(col+1)*w,(row+1)*h))))
 for filename in ['animation.png','animation.webp']:assert Image.open(OUT/filename).n_frames==n
 assert Image.open(OUT/'full-animation.webp').n_frames==count
 page=(OUT/'preview.html').read_text(encoding='utf-8')
 for url in re.findall(r'(?:src|href)=["\']([^"\']+)',page):
  if not url.startswith(('http','data:','#')):assert (OUT/url).exists(),url
 cfg=json.loads(re.search(r'<script id="cfg" type="application/json">(.*?)</script>',page,re.S).group(1))
 assert cfg['indices']==indices and cfg['durations']==meta['durationMs'] and len(cfg['labels'])==n
 uploaded=json.loads((OUT/'upload.json').read_text(encoding='utf-8'));assert hashlib.sha256((OUT/'video-input.png').read_bytes()).hexdigest()==uploaded['sha256']
 report=dict(nativeVideoSize=source['videoSize'],sourceFrames=count,sourceFPS=24,pixelFrameSize=[w,h],selectedFrames=n,gamePlaybackDurationMs=sum(meta['durationMs']),gridSize=list(grid.size),paletteLimit=len(palette),binaryAlpha=True,sourceStaticRGBAUnchanged=True,checks='All RGBA frames, exact selection/sheets, palette, animation counts, source/input hashes and static/dynamic links passed',actualBrowserVerified=False)
 (OUT/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
