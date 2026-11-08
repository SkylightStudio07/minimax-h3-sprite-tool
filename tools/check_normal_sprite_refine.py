"""Media/provenance checks; artistic approval remains a separate review.json."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.verify_normal_sprite_refine import OUT,ACTIONS
def main():
 global OUT,ACTIONS
 if len(sys.argv)>1:
  from tools.verify_normal_sprite_attack_v3 import run
  OUT,ACTIONS=run.OUT,run.ACTIONS
 records=[]
 for action,item in ACTIONS.items():
  folder=OUT/action
  if not (folder/'frames.json').exists():continue
  settings=json.loads((folder/'settings.json').read_text(encoding='utf-8'))
  graph=json.loads((folder/(settings.get('generationRevision','motion-v2')+'-workflow.json')).read_text(encoding='utf-8'))
  meta=json.loads((folder/'frames.json').read_text(encoding='utf-8'))
  review=json.loads((folder/'review.json').read_text(encoding='utf-8')) if (folder/'review.json').exists() else None
  if review and review.get('publish') is False:
   records.append(dict(action=action,rejected=True,review=review));continue
  assert ('last_frame' in graph['6']['inputs'])==item['loop']
  assert graph['10']['inputs']['steps']==20
  assert settings['backgroundRemoval']=='ai' and settings['pixelOutput'] is False
  assert 'Do not freeze the torso or hips' in graph['6']['inputs']['prompt']
  assert meta['previewFrames']==73 and sum(meta['previewTimingMs'])==3042
  coverage=[]
  for path in sorted((folder/'all-frames').glob('*.png')):
   im=Image.open(path).convert('RGBA');a=np.array(im)
   assert im.size==(768,768)
   assert not a[0,:,3].any() and not a[-1,:,3].any() and not a[:,0,3].any() and not a[:,-1,3].any(),(action,path.name,'cropped')
   coverage.append(int((a[:,:,3]>128).sum()))
   assert coverage[-1]>7000,(action,path.name,'lost foreground')
  assert len(coverage)==73
  with Image.open(folder/'animation.webp') as preview:assert preview.n_frames==73 and preview.size==(512,512)
  records.append(dict(action=action,frames=73,foregroundRange=[min(coverage),max(coverage)],
   removedEnclosedMattePixels=sum(d['clearedEnclosedMattePixels'] for d in meta['diagnostic']),
   rawSha256=hashlib.sha256((folder/'raw.mp4').read_bytes()).hexdigest(),review=review))
 baseline=json.loads((ROOT/'outputs/normal-sprite-examples-20261020/previous-pixel-hashes.json').read_text(encoding='utf-8'))
 for path,digest in baseline.items():assert hashlib.sha256((ROOT/'web'/path).read_bytes()).hexdigest()==digest,path
 (OUT/'validation.json').write_text(json.dumps(dict(technicalChecksPassed=True,records=records,pixelHashesUnchanged=len(baseline),actualBrowserVerified=False),ensure_ascii=False,indent=2),encoding='utf-8')
 print('PASS',sum(not r.get('rejected') for r in records),'candidate motions checked;',sum(bool(r.get('rejected')) for r in records),'archived rejects; one-shot/loop anchors, AI matte, full-frame alpha/canvas, 73-frame timing, accepted pixel hashes')
if __name__=='__main__':main()
