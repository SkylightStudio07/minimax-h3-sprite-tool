"""Verify selected-frame outline repair artifacts and protected materials."""
import json,hashlib,re,zipfile
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/pixel-outline-repair-20261019';SOURCE=ROOT/'outputs/pixel-combat-cleanup-20261019'
report={};count=0
for char,n in [('swordswoman',12),('musketeer',12),('walking',8)]:
 methods=['before','contour']+(['blade'] if char!='musketeer' else [])
 palpath=ROOT/('outputs/pixel-weapon-layers-20261019/prepare.json' if char=='walking' else f'outputs/pixel-female-combat-20261019/{char}/reference-settings.json')
 allowed={tuple(c) for c in json.loads(palpath.read_text(encoding='utf-8'))['palette']}
 details=json.loads((OUT/char/'review.json').read_text(encoding='utf-8'))
 for method in methods:
  folder=OUT/char/method;meta=json.loads((folder/'frames.json').read_text(encoding='utf-8'));assert len(meta['sourceIndices'])==n
  grid=Image.open(folder/'sheet-grid.png').convert('RGBA');strip=Image.open(folder/'sheet.png').convert('RGBA');assert grid.size==(512,((n+3)//4)*128) and strip.size==(n*128,128)
  for i in range(n):
   a=np.array(Image.open(folder/f'frame-{i:02d}.png').convert('RGBA'));assert a.shape==(128,128,4) and set(np.unique(a[:,:,3]))<={0,255}
   assert {tuple(c) for c in np.unique(a[:,:,:3][a[:,:,3]>0],axis=0)}<=allowed
   assert np.array_equal(a,np.array(grid.crop(((i%4)*128,(i//4)*128,(i%4+1)*128,(i//4+1)*128))))
   assert np.array_equal(a,np.array(strip.crop((i*128,0,(i+1)*128,128))))
   before=np.array(Image.open(SOURCE/char/'thin'/f'frame-{i:02d}.png').convert('RGBA'))
   if method=='before':assert np.array_equal(a,before)
   if method=='contour':
    protected=np.array(Image.open(OUT/char/'protected-materials'/f'frame-{i:02d}.png'))>0;assert np.array_equal(a[protected],before[protected])
   if method=='blade' and not details[i]['sword']['applied']:assert np.array_equal(a,np.array(Image.open(OUT/char/'contour'/f'frame-{i:02d}.png')))
   count+=1
  for filename in ['animation.png','animation.webp']:assert Image.open(folder/filename).n_frames==n
 report[char]=dict(selectedFrames=n,variants=len(methods),protectedMaterialsRGBAIdentical=True,recoloredPixels=sum(r['dehalo']['recoloredPixels'] for r in details),removedPixels=sum(r['dehalo']['removedPixels'] for r in details),redrawnBlades=sum(r['sword'].get('applied',False) for r in details))
page=(OUT/'preview.html').read_text(encoding='utf-8')
for url in re.findall(r'(?:src|href)=[\"\']([^\"\']+)',page):
 if not url.startswith(('http','data:','#')):assert (OUT/url).exists(),url
configs=json.loads(re.search(r'<script id="configs" type="application/json">(.*?)</script>',page,re.S).group(1))
for c in configs:
 for method in c['methods']:
  for i in range(len(c['indices'])):assert (OUT/c['id']/method/f'frame-{i:02d}.png').exists()
report.update(selectedPNGsChecked=count,binaryAlpha=True,sourcePalettesPreserved=True,automatic=False,fullVideoCorrected=False,actualBrowserVerified=False,limitations='Only selected frames and reviewed material masks/anchors; visual review of all static comparisons and blade sheet; broad slash smear remains generated.')
(OUT/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
