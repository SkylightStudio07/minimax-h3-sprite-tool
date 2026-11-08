"""Artifact checks for the four-way pixel cleanup experiment."""
from pathlib import Path
import json,re,zipfile,hashlib
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/pixel-combat-cleanup-20261019';SOURCE=ROOT/'outputs/pixel-female-combat-20261019';WALK=ROOT/'outputs/pixel-weapon-layers-20261019'
report={};total=0
for character in ['swordswoman','musketeer','walking']:
 if character=='walking':palette=json.loads((WALK/'prepare.json').read_text(encoding='utf-8'))['palette'];n=8
 else:palette=json.loads((SOURCE/character/'reference-settings.json').read_text(encoding='utf-8'))['palette'];n=12
 allowed={tuple(col) for col in palette};base=[np.array(Image.open(OUT/character/'original/all-frames'/f'frame-{i:03d}.png').convert('RGBA')) for i in range(73)]
 if character!='walking':
  for i,a in enumerate(base):assert np.array_equal(a,np.array(Image.open(SOURCE/character/'all-frames'/f'frame-{i:03d}.png').convert('RGBA')))
 for name in ['original','edge','vote','thin']:
  p=OUT/character/name;meta=json.loads((p/'frames.json').read_text(encoding='utf-8'));assert len(meta['sourceIndices'])==n
  strip=Image.open(p/'sheet.png').convert('RGBA');grid=Image.open(p/'sheet-grid.png').convert('RGBA');assert strip.size==(n*128,128) and grid.size==(512,128*((n+3)//4))
  assert len(list((p/'all-frames').glob('frame-*.png')))==73
  for i in range(73):
   a=np.array(Image.open(p/'all-frames'/f'frame-{i:03d}.png').convert('RGBA'));assert a.shape==(128,128,4) and set(np.unique(a[:,:,3]))<={0,255}
   assert {tuple(c) for c in np.unique(a[:,:,:3][a[:,:,3]>0],axis=0)}<=allowed;total+=1
  for i,source in enumerate(meta['sourceIndices']):
   a=np.array(Image.open(p/f'frame-{i:02d}.png').convert('RGBA'));assert np.array_equal(a,np.array(Image.open(p/'all-frames'/f'frame-{source:03d}.png')))
   assert np.array_equal(a,np.array(strip.crop((i*128,0,(i+1)*128,128))))
   assert np.array_equal(a,np.array(grid.crop(((i%4)*128,(i//4)*128,(i%4+1)*128,(i//4+1)*128))))
  for filename in ['animation.png','animation.webp']:assert Image.open(p/filename).n_frames==n
 report[character]=dict(fullFramesPerVariant=73,selectedFrames=n,variantCount=4,paletteLimit=len(palette))
# Walk is a controlled body-only comparison: the visible original head, weapon
# and foreground hand must remain exactly identical in every variant.
tracks=json.loads((WALK/'tracks.json').read_text(encoding='utf-8'));ref=np.array(Image.open(WALK/'body-reference.png').convert('RGBA'))
for name in ['edge','vote','thin']:
 for i,head in enumerate(tracks['head']):
  a=np.array(Image.open(OUT/'walking'/name/'all-frames'/f'frame-{i:03d}.png').convert('RGBA'));b=np.array(Image.open(OUT/'walking/original/all-frames'/f'frame-{i:03d}.png').convert('RGBA'))
  dx,dy=round(head['dx']),round(head['dy']);mask=np.zeros((128,128),bool);mask[18:39,54:73]=ref[18:39,54:73,3]>0
  yy,xx=np.where(mask);assert np.array_equal(a[yy+dy,xx+dx],b[yy+dy,xx+dx])
  hand=np.array(Image.open(WALK/'hand'/f'all-{i:03d}.png').convert('RGBA'));assert np.array_equal(a[hand[:,:,3]>0],hand[hand[:,:,3]>0])
# All links and dynamically chosen frame URLs exist.
page=(OUT/'preview.html').read_text(encoding='utf-8')
for url in re.findall(r'(?:src|href)=[\"\']([^\"\']+)',page):
 if not url.startswith(('http','data:','#')):assert (OUT/url).exists(),url
configs=json.loads(re.search(r'<script id="configs" type="application/json">(.*?)</script>',page,re.S).group(1))
for cfg in configs:
 for method in ['original','edge','vote','thin']:
  for i in range(len(cfg['indices'])):assert (OUT/cfg['id']/method/f'frame-{i:02d}.png').exists()
source=json.loads((OUT/'results.json').read_text(encoding='utf-8'))['sourceVideoHashes']
for key,signature in source.items():assert hashlib.sha256((SOURCE/key/'action-raw.mp4').read_bytes()).hexdigest()==signature
report.update(fullFrameFilesChecked=total,sourceClipsUnchanged=True,walkHeadAndForegroundHandIdentical=True,actualBrowserTested=False,notes='Native local file browser automation is unavailable; static images and file/JS logic checks only.')
(OUT/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
