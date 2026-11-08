"""Transfer the four CPU cleanup variants to the accepted layered walk clip."""
import sys,json,hashlib
from pathlib import Path
import av,cv2,numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.compare_pixel_combat_cleanup import OUT,NAMES,grid_vote,thin_evidence,diagnostic,write_variant,save,package
from tools.sprite_matte import clean_flat_matte
from tools import postprocess_pixel_video as pp
from tools.verify_pixel_weapon_layers import weapon_transform,over
SOURCE=ROOT/'outputs/pixel-weapon-layers-20261019'

def main():
 target=OUT/'walking';target.mkdir(exist_ok=True)
 palette=np.array(json.loads((SOURCE/'prepare.json').read_text(encoding='utf-8'))['palette'],np.float32)
 tracks=json.loads((SOURCE/'tracks.json').read_text(encoding='utf-8'));settings=json.loads((SOURCE/'editor-settings.json').read_text(encoding='utf-8'))
 selection=dict(indices=[f['sourceFrame'] for f in settings['frames']],durationMs=[125]*8,oneShot=False,notes='Identical cached original head tracks, foreground hands, restored original sword and sword transforms across all variants. This tests body cleanup, not a new weapon tracker.')
 reference=Image.open(SOURCE/'body-reference.png').convert('RGBA')
 weapon=np.array(Image.open(ROOT/'outputs/pixel-weapon-edge-20261019/restored/weapon.png').convert('RGBA'))
 batches={name:dict(rgb=[],cov=[]) for name in ['edge','vote','thin']};grays=[]
 with av.open(str(SOURCE/'body-walk.mp4')) as video:
  for f in video.decode(video=0):
   raw=np.array(f.to_image().convert('RGB'));im,_=clean_flat_matte(Image.fromarray(raw),tolerance=26,radius=3);a=np.array(im);rgb=a[:,:,:3];alpha=a[:,:,3].astype(np.float32)/255
   color,cov=pp.robust_grid(rgb,alpha>=.5);vote,coverage=grid_vote(rgb,alpha,palette);thincov,_=thin_evidence(rgb,alpha,coverage)
   for name,c,covariance in [('edge',color,cov),('vote',vote,coverage),('thin',vote,thincov)]:batches[name]['rgb'].append(c);batches[name]['cov'].append(covariance)
   grays.append(cv2.cvtColor(cv2.resize(raw,(128,128),interpolation=cv2.INTER_AREA),cv2.COLOR_RGB2GRAY))
 variants={'original':[]};hands=[];weapons=[]
 for i,w in enumerate(tracks['weapon']):
  layer,_=weapon_transform(weapon,w['grip'],w['angle']);weapons.append(layer)
  body=np.array(Image.open(SOURCE/'body'/f'all-{i:03d}.png').convert('RGBA'));hand=np.array(Image.open(SOURCE/'hand'/f'all-{i:03d}.png').convert('RGBA'));hands.append(hand)
  variants['original'].append(over(over(body,layer),hand))
 for name,data in batches.items():
  temporal,_=pp.temporal_cleanup(data['rgb'],data['cov'],grays,palette)
  stable,_=pp.apply_parts(temporal,reference,tracks['head'],[dict(accepted=False) for _ in temporal],np.zeros((128,128),bool))
  variants[name]=[]
  for i,body in enumerate(stable):
   body=body.copy();body[hands[i][:,:,3]>0]=0
   result=over(over(body,weapons[i]),hands[i]);variants[name].append(result)
   assert np.array_equal(result[hands[i][:,:,3]>0],hands[i][hands[i][:,:,3]>0])
 comparison=Image.new('RGB',(8*240,4*264),'#202632');draw=ImageDraw.Draw(comparison);report={}
 allowed={tuple(c) for c in palette.astype(np.uint8)}
 for row,(name,frames) in enumerate(variants.items()):
  for a in frames:
   assert set(np.unique(a[:,:,3]))<={0,255} and {tuple(c) for c in np.unique(a[:,:,:3][a[:,:,3]>0],axis=0)}<=allowed
  write_variant(target/name,frames,selection);report[name]=diagnostic(frames,variants['original'])
  for col,index in enumerate(selection['indices']):
   im=Image.fromarray(frames[index]).resize((240,240),Image.Resampling.NEAREST);comparison.paste(im,(col*240,row*264+24),im);draw.text((col*240+5,row*264+5),f'{name} / {index}',fill='white')
 comparison.save(target/'comparison.png')
 save(target/'results.json',dict(metrics=report,sourceVideoSHA256=hashlib.sha256((SOURCE/'body-walk.mp4').read_bytes()).hexdigest(),referenceHeadAndWeaponIdenticalAcrossVariants=True,scope='The source is the same accepted weapon-free walk video. Cached manual masks/tracks/foreground hand remain character-specific.'))
 package();print('TRANSFER CHECK COMPLETE',flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');main()
