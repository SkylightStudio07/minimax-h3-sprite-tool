"""Review-scoped halo removal and manually anchored sword redraw.

Only selected frames are processed. Protection geometry is hand-reviewed for
these three references; this is not a generic semantic dehalo model.
"""
from pathlib import Path
import json,sys,zipfile
import numpy as np
from scipy import ndimage
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
SOURCE=ROOT/'outputs/pixel-combat-cleanup-20261019'
OUT=ROOT/'outputs/pixel-outline-repair-20261019'
SWORD={0:((72,61),(97,46)),1:((78,35),(82,9)),2:((59,22),(32,8)),3:((50,26),(24,40)),7:((80,78),(100,98)),8:((80,78),(102,97)),9:((79,74),(107,85)),10:((72,61),(97,46)),11:((72,61),(97,46))}
FACE=[(56,28,65,38),(62,28,71,39),(59,27,70,39),(62,31,72,45),(68,37,80,52),(69,41,81,55),(69,41,81,55),(67,44,80,58),(67,44,80,58),(66,39,78,53),(56,28,65,38),(56,28,65,38)]

def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def line_mask(base,tip,width,extension=0):
 yy,xx=np.indices((128,128));axis=np.array(tip,dtype=float)-base;length=np.linalg.norm(axis);v=axis/length;along=(xx-base[0])*v[0]+(yy-base[1])*v[1];across=(xx-base[0])*(-v[1])+(yy-base[1])*v[0]
 return (np.abs(across)<=width)&(along>=-extension)&(along<=length+extension),along,across,length

def protect(character,index,a):
 mask=np.zeros((128,128),bool);yy,xx=np.indices(mask.shape)
 if character=='swordswoman':
  x0,y0,x1,y1=FACE[index];mask[y0:y1,x0:x1]=True
  if index in SWORD:mask|=line_mask(*SWORD[index],width=4,extension=3)[0]
  else:
   # Generated broad slash/smear remains an intentional protected VFX region.
   neutral=(a[:,:,:3].min(axis=2)>125)&(np.ptp(a[:,:,:3].astype(float),axis=2)<35)&(a[:,:,3]>0)
   labels,n=ndimage.label(neutral,structure=np.ones((3,3)))
   for label in range(1,n+1):
    region=labels==label
    if region.sum()>100:mask|=ndimage.binary_dilation(region,iterations=1)
 elif character=='musketeer':
  mask|=yy<41 # Actual white hair, face and rigid gun/flash share this upper region.
  mask|=(xx>67)&(yy<64) # Recoil barrel/smoke pass above and in front of torso.
  mask|=(xx>=51)&(xx<=65)&(yy>=38)&(yy<=46) # Cream cuffs / gripping fingers.
 else:
  mask|=yy<43 # Original locked face and scarf must stay identical.
  tracks=json.loads((ROOT/'outputs/pixel-weapon-layers-20261019/editor-settings.json').read_text(encoding='utf-8'))['frames'][index]
  origin=np.array(tracks['grip']);angle=np.radians(35+tracks['angle']);tip=origin+np.array([np.cos(angle),np.sin(angle)])*40
  mask|=line_mask(origin,tip,width=5,extension=4)[0]
  source=tracks['sourceFrame'];hand=np.array(Image.open(ROOT/'outputs/pixel-weapon-layers-20261019/hand'/f'all-{source:03d}.png').convert('RGBA'));mask|=hand[:,:,3]>0
 return mask

def dehalo(a,protected):
 result=a.copy();visible=a[:,:,3]>0;rgb=a[:,:,:3].astype(float)
 # White/grey edge specks baked into the starting sprite are already opaque;
 # alpha unmatting cannot identify them. Use the manually protected material
 # regions, then replace only boundary-neutral contamination with nearby body RGB.
 yy,xx=np.indices(visible.shape)
 neutral=(rgb.min(axis=2)>=95)&(np.ptp(rgb,axis=2)<25)
 # Brown/black boots have no cream trim in these reviewed designs. White matte
 # quantized into a warm cream swatch also needs treatment on their outer edge.
 neutral|=(yy>=72)&(rgb.min(axis=2)>=140)&(np.ptp(rgb,axis=2)<100)
 depth=ndimage.distance_transform_edt(visible)
 candidate=visible&neutral&(depth<=1.5)&~protected
 stable=visible&~neutral&~protected
 distance,ix=ndimage.distance_transform_edt(~stable,return_indices=True)
 neighbor=rgb[ix[0],ix[1]]
 support=ndimage.convolve(stable.astype(np.uint8),np.ones((3,3),np.uint8),mode='constant')
 recolor=candidate&(distance<=2.3)&(support>=1)
 remove=candidate&~recolor
 result[recolor,:3]=neighbor[recolor].astype(np.uint8);result[remove]=0
 assert np.array_equal(result[protected],a[protected])
 assert np.array_equal(result[~candidate],a[~candidate])
 return result,dict(candidatePixels=int(candidate.sum()),recoloredPixels=int(recolor.sum()),removedPixels=int(remove.sum()),protectedRGBAIdentical=True)

def redraw_sword(a,index,character='swordswoman'):
 if character=='swordswoman' and index not in SWORD:return a.copy(),dict(applied=False,reason='Broad generated motion smear has no reliable single straight blade; preserved, not guessed.')
 if character=='swordswoman':
  base,tip=SWORD[index];colors=[[16,30,39,255],[153,150,156,255],[246,247,247,255]]
 else:
  track=json.loads((ROOT/'outputs/pixel-weapon-layers-20261019/editor-settings.json').read_text(encoding='utf-8'))['frames'][index]
  angle=np.radians(track['angle']);rotation=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
  base=np.array(track['grip'])+rotation@np.array([5.,5.]);tip=np.array(track['grip'])+rotation@np.array([28.,22.]);colors=[[26,33,57,255],[181,177,179,255],[252,251,249,255]]
 corridor,along,across,length=line_mask(base,tip,width=3.5,extension=2)
 rgb=a[:,:,:3].astype(float);neutral=(rgb.min(axis=2)>=95)&(np.ptp(rgb,axis=2)<35)&(a[:,:,3]>0)
 old_dark=(rgb.max(axis=2)<120)&(np.ptp(rgb,axis=2)<40)&(along>3)&(a[:,:,3]>0)
 removed=corridor&(neutral|old_dark);result=a.copy();result[removed]=0
 # A crisp tapered two/three-colour native 128px blade: no image rotation,
 # antialiasing, resampling, invented new palette colours or length estimation.
 t=np.clip(along/length,0,1);half=1.55-.65*t
 blade=(along>=0)&(along<=length+.2)&(np.abs(across)<=half)
 result[blade]=colors[0]
 steel=blade&(across<half-.25)&(across>-half+.30);result[steel]=colors[1]
 highlight=steel&(across<-.05);result[highlight]=colors[2]
 assert np.array_equal(result[~(removed|blade)],a[~(removed|blade)])
 labels,count=ndimage.label(blade,structure=np.ones((3,3)));assert count==1
 return result,dict(applied=True,base=list(base),tip=list(tip),manualAnchors=character=='swordswoman',cachedTrackedPlacement=character=='walking',originalBladePixelsRemoved=int(removed.sum()),drawnBladePixels=int(blade.sum()),bladeConnected=True,scope='Native-resolution blade redraw on selected straight-blade poses; generated slash/smear unchanged; original hand/hilt retained.')

def export(folder,frames,meta):
 folder.mkdir(parents=True,exist_ok=True);grid=Image.new('RGBA',(512,128*((len(frames)+3)//4)));strip=Image.new('RGBA',(128*len(frames),128))
 for i,a in enumerate(frames):
  im=Image.fromarray(a);im.save(folder/f'frame-{i:02d}.png');grid.paste(im,((i%4)*128,(i//4)*128));strip.paste(im,(i*128,0))
 grid.save(folder/'sheet-grid.png');strip.save(folder/'sheet.png')
 ims=[Image.fromarray(a) for a in frames];ims[0].save(folder/'animation.png',save_all=True,append_images=ims[1:],duration=meta['durationMs'],loop=0,disposal=0,blend=0)
 large=[im.resize((512,512),Image.Resampling.NEAREST) for im in ims];large[0].save(folder/'animation.webp',save_all=True,append_images=large[1:],duration=meta['durationMs'],loop=0,lossless=True)
 save(folder/'frames.json',meta)

def main():
 OUT.mkdir(exist_ok=True);report={}
 for char in ['swordswoman','musketeer','walking']:
  source=SOURCE/char/'thin';target=OUT/char;target.mkdir(exist_ok=True);meta=json.loads((source/'frames.json').read_text(encoding='utf-8'));before=[];clean=[];rigid=[];records=[]
  protected_folder=target/'protected-materials';protected_folder.mkdir(exist_ok=True)
  for i in range(len(meta['sourceIndices'])):
   a=np.array(Image.open(source/f'frame-{i:02d}.png').convert('RGBA'));mask=protect(char,i,a);b,record=dehalo(a,mask);c,sword=redraw_sword(b,i,char) if char!='musketeer' else (b.copy(),dict(applied=False))
   Image.fromarray(mask.astype(np.uint8)*255).save(protected_folder/f'frame-{i:02d}.png');before.append(a);clean.append(b);rigid.append(c);records.append(dict(frame=i,sourceFrame=meta['sourceIndices'][i],dehalo=record,sword=sword))
  variants={'before':before,'contour':clean,'blade':rigid} if char!='musketeer' else {'before':before,'contour':clean}
  comparison=Image.new('RGB',(len(before)*224,len(variants)*248),'#202632');draw=ImageDraw.Draw(comparison)
  for row,(name,frames) in enumerate(variants.items()):
   export(target/name,frames,dict(meta,correction=dict(variant=name,selectedFramesOnly=True,manualMaterialProtection=True,manualBladeAnchors=char=='swordswoman' and name=='blade',notes='The input is the previous thin candidate. Material masks and this reference-specific geometry are reviewed manually; not a general automatic solution.')))
   for j,a in enumerate(frames):
    im=Image.fromarray(a).resize((224,224),Image.Resampling.NEAREST);comparison.paste(im,(j*224,row*248+24),im);draw.text((j*224+4,row*248+4),f'{name} / {j}',fill='white')
  comparison.save(target/'comparison.png');save(target/'review.json',records);report[char]=records
 save(OUT/'results.json',dict(method='Material-protected neutral edge recolour/removal; manually anchored selected sword redraw',automatic=False,records=report,limitations=['Selected frames only; no full-video correction','Manual material protection and sword anchors specific to these characters','Broad sword smear remains generated','Not a generic AI segmentation model']))
 save(OUT/'manual-protection.json',dict(swordswomanFaceBoxes=FACE,swordswomanBladeAnchors=SWORD,lowerBootRegionY=72,neutralThreshold=dict(minRGB=95,maxSpread=25,maxContourDepth=1.5),warmBootThreshold=dict(minRGB=140,maxSpread=100),scope='Hand-reviewed protective geometry for only these selected frames. Do not apply to new characters unchanged.'))
 from tools.build_pixel_outline_review import build
 build(OUT)
 print('REPAIRED',OUT,flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');main()
