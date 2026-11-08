"""CPU comparison: same two accepted pixel clips, four cleanup methods.

No new models, inference, service mutations or accepted output replacement.
"""
import json,sys,zipfile,shutil,hashlib
from pathlib import Path
import av,cv2
import numpy as np
from scipy import ndimage
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.postprocess_pixel_video import robust_grid,temporal_cleanup
from tools.sprite_matte import clean_flat_matte
SOURCE=ROOT/'outputs/pixel-female-combat-20261019'
OUT=ROOT/'outputs/pixel-combat-cleanup-20261019'
NAMES={'original':'기존 · 대표색＋시간축','edge':'경계색 먼저 제거','vote':'경계색＋16픽셀 색 투표','thin':'색 투표＋가는 밝은 부품 보존'}

def save(p,value):p.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def grid_vote(rgb,alpha,palette):
 lab=cv2.cvtColor(rgb.astype(np.float32)/255,cv2.COLOR_RGB2LAB)
 plab=cv2.cvtColor(palette.astype(np.float32)[None]/255,cv2.COLOR_RGB2LAB)[0]
 # All sixteen observed samples vote. Never synthesize an averaged RGB colour.
 labels=((lab[:,:,None,:]-plab[None,None,:,:])**2).sum(axis=3).argmin(axis=2)
 labels=labels.reshape(128,4,128,4).transpose(0,2,1,3).reshape(128,128,16)
 weights=alpha.reshape(128,4,128,4).transpose(0,2,1,3).reshape(128,128,16)
 scores=np.stack([np.sum(weights*(labels==i),axis=2) for i in range(len(palette))],axis=2)
 winner=scores.argmax(axis=2);coverage=weights.mean(axis=2)
 return palette[winner].astype(np.uint8),coverage

def thin_evidence(rgb,alpha,coverage):
 # Only current-frame neutral bright foreground counts; no global alpha dilation.
 neutral=(rgb.min(axis=2)>145)&(np.ptp(rgb.astype(float),axis=2)<55)&(alpha>.35)
 density=neutral.reshape(128,4,128,4).mean(axis=(1,3))
 support=cv2.filter2D((density>.12).astype(np.float32),-1,np.ones((3,3),np.float32))
 add=(coverage>=.20)&(coverage<.50)&(density>=.125)&(support>=3)
 cov=coverage.copy();cov[add]=.8 # Current observed evidence overrides stale alpha.
 return cov,add

def diagnostic(frames,baseline):
 records=[]
 for i,a in enumerate(frames):
  visible=a[:,:,3]>0;old=baseline[i][:,:,3]>0
  # Isolated alpha pixels, regardless of colour. Weapon tips may legitimately be isolated.
  neighbours=cv2.filter2D(visible.astype(np.uint8),-1,np.ones((3,3),np.uint8))
  edge=visible&~ndimage.binary_erosion(visible)
  neutral=(a[:,:,:3].min(axis=2)>205)&(np.ptp(a[:,:,:3].astype(int),axis=2)<35)
  records.append(dict(frame=i,visiblePixels=int(visible.sum()),addedAlphaPixels=int((visible&~old).sum()),removedAlphaPixels=int((old&~visible).sum()),changedVisiblePixels=int((np.any(a!=baseline[i],axis=2)&(visible|old)).sum()),isolatedAlphaPixels=int((visible&(neighbours==1)).sum()),brightNeutralEdgePixels=int((edge&neutral).sum())))
 return dict(meanAddedAlpha=float(np.mean([r['addedAlphaPixels'] for r in records])),meanRemovedAlpha=float(np.mean([r['removedAlphaPixels'] for r in records])),meanIsolatedAlpha=float(np.mean([r['isolatedAlphaPixels'] for r in records])),frames=records,note='Diagnostics include real hair, metal and VFX. They are not quality or identity scores.')

def write_variant(folder,frames,selection):
 folder.mkdir(parents=True,exist_ok=True);allfolder=folder/'all-frames';allfolder.mkdir(exist_ok=True)
 for i,a in enumerate(frames):Image.fromarray(a).save(allfolder/f'frame-{i:03d}.png')
 selected=[Image.fromarray(frames[i]) for i in selection['indices']];grid=Image.new('RGBA',(512,128*((len(selected)+3)//4)));strip=Image.new('RGBA',(128*len(selected),128))
 for i,im in enumerate(selected):
  im.save(folder/f'frame-{i:02d}.png');grid.paste(im,((i%4)*128,(i//4)*128));strip.paste(im,(i*128,0))
 grid.save(folder/'sheet-grid.png');strip.save(folder/'sheet.png')
 selected[0].save(folder/'animation.png',save_all=True,append_images=selected[1:],duration=selection['durationMs'],loop=0,disposal=0,blend=0)
 large=[im.resize((512,512),Image.Resampling.NEAREST) for im in selected]
 large[0].save(folder/'animation.webp',save_all=True,append_images=large[1:],duration=selection['durationMs'],loop=0,lossless=True)
 save(folder/'frames.json',dict(frameWidth=128,frameHeight=128,columns=4,rows=(len(selected)+3)//4,sourceIndices=selection['indices'],durationMs=selection['durationMs'],sourceFPS=24,review=selection.get('notes'),oneShot=selection.get('oneShot',True)))

def main():
 OUT.mkdir(exist_ok=True);summary={};hashes={}
 for character in ['swordswoman','musketeer']:
  source=SOURCE/character;target=OUT/character;target.mkdir(exist_ok=True)
  hashes[character]=hashlib.sha256((source/'action-raw.mp4').read_bytes()).hexdigest()
  selection=json.loads((source/'selection.json').read_text(encoding='utf-8'));palette=np.array(json.loads((source/'reference-settings.json').read_text(encoding='utf-8'))['palette'],np.float32)
  baseline=[np.array(Image.open(source/'all-frames'/f'frame-{i:03d}.png').convert('RGBA')) for i in range(73)]
  batches={name:dict(rgbs=[],coverages=[]) for name in ['edge','vote','thin']};grays=[];matte_stats=[];thin_stats=[]
  with av.open(str(source/'action-raw.mp4')) as video:
   for i,f in enumerate(video.decode(video=0)):
    raw=np.array(f.to_image().convert('RGB'));cut,stat=clean_flat_matte(Image.fromarray(raw),tolerance=26,radius=3)
    a=np.array(cut);rgb=a[:,:,:3];alpha=a[:,:,3].astype(np.float32)/255
    spatial,cov=robust_grid(rgb,alpha>=.5);vote,softcov=grid_vote(rgb,alpha,palette);thincov,added=thin_evidence(rgb,alpha,softcov)
    batches['edge']['rgbs'].append(spatial);batches['edge']['coverages'].append(cov)
    batches['vote']['rgbs'].append(vote);batches['vote']['coverages'].append(softcov)
    batches['thin']['rgbs'].append(vote);batches['thin']['coverages'].append(thincov)
    grays.append(cv2.cvtColor(cv2.resize(raw,(128,128),interpolation=cv2.INTER_AREA),cv2.COLOR_RGB2GRAY));matte_stats.append(stat);thin_stats.append(int(added.sum()))
  variants={'original':baseline}
  for name,data in batches.items():
   variants[name],stats=temporal_cleanup(data['rgbs'],data['coverages'],grays,palette)
   save(target/f'{name}-temporal.json',stats)
  summary[character]={}
  allowed={tuple(c) for c in palette.astype(np.uint8)}
  comparison=Image.new('RGB',(12*192,4*212),'#202632');draw=ImageDraw.Draw(comparison)
  for row,(name,frames) in enumerate(variants.items()):
   for a in frames:
    assert a.shape==(128,128,4) and set(np.unique(a[:,:,3]))<={0,255}
    assert {tuple(c) for c in np.unique(a[:,:,:3][a[:,:,3]>0],axis=0)}<=allowed
   write_variant(target/name,frames,selection);summary[character][name]=diagnostic(frames,baseline)
   for j,index in enumerate(selection['indices']):
    im=Image.fromarray(frames[index]).resize((192,192),Image.Resampling.NEAREST);comparison.paste(im,(j*192,row*212+20),im);draw.text((j*192+4,row*212+3),f'{name} / {index}',fill='white')
  comparison.save(target/'comparison.png');save(target/'matte.json',matte_stats);save(target/'thin-observed-pixels.json',thin_stats)
  print('COMPARED',character,flush=True)
 save(OUT/'results.json',dict(sourceVideoHashes=hashes,metrics=summary,palettePolicy='Same 36-colour source palette in all variants',version='same-video-cleanup-4way-v1'))
 package()

def package():
 from tools.build_pixel_cleanup_review import build
 build(OUT,NAMES)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');main()
