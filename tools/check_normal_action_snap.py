"""Verify native frames, explicit retiming and delivered media; no artistic score."""
import hashlib,json,sys
from pathlib import Path
import av,numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.verify_normal_action_snap import OUT,CASES
def main():
 global OUT,CASES
 if len(sys.argv)>1:
  from tools.verify_normal_run_sheathed import snap
  OUT,CASES=snap.OUT,snap.CASES
 records=[]
 for action,item in CASES.items():
  folder=OUT/action
  if not (folder/'frames.json').exists():continue
  meta=json.loads((folder/'frames.json').read_text(encoding='utf-8'));settings=json.loads((folder/'settings.json').read_text(encoding='utf-8'))
  report=meta['timing'];graph=json.loads((folder/(item['revision']+'-workflow.json')).read_text(encoding='utf-8'))
  assert ('last_frame' in graph['6']['inputs'])==item['loop']
  assert graph['10']['inputs']['steps']==(8 if settings['workflowId']=='fasth3-sprite' else 20)
  assert settings['motionSpeed']==report['motionSpeed'] and settings['trimAction']==report['trimAction']
  assert settings['animationType']==action and settings['backgroundRemoval']=='ai' and not settings['pixelOutput']
  assert sum(meta['durationMs'])==sum(meta['previewTimingMs'])==report['totalMs']
  with av.open(str(folder/'raw.mp4')) as clip:native=[f.to_image().convert('RGB') for f in clip.decode(video=0)]
  assert len(native)==73
  for i,path in enumerate(sorted((folder/'all-frames').glob('frame-*.png'))):
   a=np.array(Image.open(path).convert('RGBA'));alpha=a[:,:,3]
   assert a.shape==(settings['height'],settings['width'],4) and (alpha>128).sum()>5000,(action,i,'missing body')
   assert not (alpha[0].any() or alpha[-1].any() or alpha[:,0].any() or alpha[:,-1].any()),(action,i,'edge contact')
   assert np.array_equal(a[:,:,:3],np.array(native[i])),(action,i,'RGB changed')
  with av.open(str(folder/'motion.mp4')) as clip:
   assert abs(float(clip.streams.video[0].average_rate)-report['outputFps'])<.01
   assert len(list(clip.decode(video=0)))==report['outputFrames']
  for name in ('animation.webp','animation.gif'):
   with Image.open(folder/name) as im:
    total=0
    for i in range(im.n_frames):im.seek(i);im.convert('RGBA');total+=im.info.get('duration',0)
    assert abs(total-report['totalMs'])<=10,(action,name,total,report['totalMs'])
  review=json.loads((folder/'review.json').read_text(encoding='utf-8')) if (folder/'review.json').exists() else None
  records.append(dict(action=action,nativeFrames=73,shownFrames=report['outputFrames'],sourceRange=[report['sourceStart'],report['sourceEnd']],totalMs=report['totalMs'],motionSpeed=report['motionSpeed'],rawSha256=hashlib.sha256((folder/'raw.mp4').read_bytes()).hexdigest(),review=review))
 baseline=json.loads((ROOT/'outputs/normal-sprite-examples-20261020/previous-pixel-hashes.json').read_text(encoding='utf-8'))
 for path,digest in baseline.items():assert hashlib.sha256((ROOT/'web'/path).read_bytes()).hexdigest()==digest,path
 (OUT/'validation.json').write_text(json.dumps(dict(technicalChecksPassed=True,records=records,pixelHashesUnchanged=16,actualBrowserVerified=False),ensure_ascii=False,indent=2),encoding='utf-8')
 print('PASS',len(records),'actions: native RGB/canvas, retimed video/sheet/GIF, timing total, original frames + accepted pixel assets preserved')
if __name__=='__main__':main()
