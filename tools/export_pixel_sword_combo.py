"""Rectangular pixel-grid postprocess for the triple-slash experiment."""
import json,sys,zipfile
from pathlib import Path
import av,cv2,numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.verify_pixel_sword_combo import OUT,WIDTH,HEIGHT,SCALE
from tools.sprite_matte import clean_flat_matte
from tools.postprocess_pixel_video import quantize
import sprite_gif
RAW_VIDEO='combo-raw.mp4'
ENCLOSED_MATTE_MIN_AREA=0

def save(name,value):
 (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def remove_large_enclosed_matte(raw,cut,min_area):
 # Opt-in for this known grey-field experiment only. Large grey islands inside
 # a closed sword crescent are background; small neutral costume/blade details
 # remain protected by the connected-component size threshold.
 a=np.array(cut)
 if not min_area:return cut,0
 border=np.concatenate((raw[0],raw[-1],raw[:,0],raw[:,-1]))
 bg=np.median(border,axis=0)
 near=(np.max(np.abs(raw.astype(float)-bg),axis=2)<=26)&(np.ptp(raw.astype(float),axis=2)<=15)
 n,labels,stats,_=cv2.connectedComponentsWithStats(near.astype(np.uint8),8)
 allowed=np.zeros(n,bool);allowed[1:]=stats[1:,cv2.CC_STAT_AREA]>=min_area
 remove=allowed[labels]&(a[:,:,3]>0);a[remove]=0
 return Image.fromarray(a),int(remove.sum())

def vote_grid(rgb,alpha,palette):
 h,w=rgb.shape[0]//SCALE,rgb.shape[1]//SCALE
 lab=cv2.cvtColor(rgb.astype(np.float32)/255,cv2.COLOR_RGB2LAB)
 plab=cv2.cvtColor(palette.astype(np.float32)[None]/255,cv2.COLOR_RGB2LAB)[0]
 labels=((lab[:,:,None,:]-plab[None,None,:,:])**2).sum(axis=3).argmin(axis=2)
 labels=labels.reshape(h,SCALE,w,SCALE).transpose(0,2,1,3).reshape(h,w,SCALE*SCALE)
 weights=alpha.reshape(h,SCALE,w,SCALE).transpose(0,2,1,3).reshape(h,w,SCALE*SCALE)
 scores=np.stack([(weights*(labels==i)).sum(axis=2) for i in range(len(palette))],axis=2)
 rgb=palette[scores.argmax(axis=2)].astype(np.uint8);coverage=weights.mean(axis=2)
 return rgb,coverage

def thin_coverage(raw,alpha,coverage):
 h,w=coverage.shape
 neutral=(raw.min(axis=2)>145)&(np.ptp(raw.astype(float),axis=2)<55)&(alpha>.35)
 density=neutral.reshape(h,SCALE,w,SCALE).mean(axis=(1,3))
 support=cv2.filter2D((density>.12).astype(np.float32),-1,np.ones((3,3),np.float32))
 keep=(coverage>=.2)&(coverage<.5)&(density>=.125)&(support>=3)
 result=coverage.copy();result[keep]=.8
 return result,int(keep.sum())

def flow_pair(previous,current):
 h,w=previous.shape;dis=cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
 f=dis.calc(previous,current,None);b=dis.calc(current,previous,None)
 yy,xx=np.indices((h,w),dtype=np.float32);mx=xx+b[:,:,0];my=yy+b[:,:,1]
 opposite=cv2.remap(f,mx,my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
 error=np.linalg.norm(b+opposite,axis=2)
 return mx,my,(mx>=1)&(my>=1)&(mx<w-2)&(my<h-2)&(error<.65)

def temporal_cleanup(rgbs,coverages,grays,palette):
 frames=[];records=[];previous_labels=None;previous_alpha=None
 for i,(rgb,coverage) in enumerate(zip(rgbs,coverages)):
  labels,distance=quantize(rgb,palette);alpha=coverage>=.5;cc=ca=0
  if i:
   mx,my,valid=flow_pair(grays[i-1],grays[i])
   warped=cv2.remap(previous_labels,mx,my,cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT)
   oldalpha=cv2.remap(previous_alpha.astype(np.uint8),mx,my,cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT)>0
   oldgray=cv2.remap(grays[i-1],mx,my,cv2.INTER_LINEAR)
   valid&=np.abs(grays[i].astype(np.float32)-oldgray.astype(np.float32))<18
   previous_cost=np.take_along_axis(distance,warped[:,:,None],axis=2)[:,:,0];best_cost=distance.min(axis=2)
   keep=valid&oldalpha&alpha&(labels!=warped)&(previous_cost-best_cost<260)&(previous_cost<1500)
   cc=int(keep.sum());labels[keep]=warped[keep]
   keep_alpha=valid&(coverage>.30)&(coverage<.70)&(alpha!=oldalpha);ca=int(keep_alpha.sum());alpha[keep_alpha]=oldalpha[keep_alpha]
  a=np.dstack((palette[labels].astype(np.uint8),alpha.astype(np.uint8)*255));a[~alpha,:3]=0;frames.append(a)
  previous_labels=quantize(rgb,palette)[0];previous_alpha=coverage>=.5
  records.append(dict(frame=i,changedColors=cc,changedAlpha=ca))
 return frames,records

def process():
 cv2.setNumThreads(4)
 palette=np.array(json.loads((OUT/'source-settings.json').read_text(encoding='utf-8'))['palette'],np.float32)
 colors=[];coverages=[];grays=[];matte_records=[];thin_records=[]
 with av.open(str(OUT/RAW_VIDEO)) as video:
  stream=video.streams.video[0];assert (stream.width,stream.height)==(WIDTH*SCALE,HEIGHT*SCALE)
  for i,f in enumerate(video.decode(video=0)):
   raw=np.array(f.to_image().convert('RGB'));cut,meta=clean_flat_matte(Image.fromarray(raw),tolerance=26,radius=3)
   cut,removed=remove_large_enclosed_matte(raw,cut,ENCLOSED_MATTE_MIN_AREA);meta['largeEnclosedGreyPixelsRemoved']=removed
   a=np.array(cut);alpha=a[:,:,3].astype(np.float32)/255;rgb,cov=vote_grid(a[:,:,:3],alpha,palette);cov,count=thin_coverage(a[:,:,:3],alpha,cov)
   colors.append(rgb);coverages.append(cov);grays.append(cv2.cvtColor(cv2.resize(raw,(WIDTH,HEIGHT),interpolation=cv2.INTER_AREA),cv2.COLOR_RGB2GRAY));matte_records.append(meta);thin_records.append(count)
 frames,changes=temporal_cleanup(colors,coverages,grays,palette)
 folder=OUT/'all-frames';folder.mkdir(exist_ok=True);allowed={tuple(c) for c in palette.astype(np.uint8)}
 diagnostic=[]
 for i,a in enumerate(frames):
  assert a.shape==(HEIGHT,WIDTH,4) and set(np.unique(a[:,:,3]))<={0,255}
  assert {tuple(c) for c in np.unique(a[:,:,:3][a[:,:,3]>0],axis=0)}<=allowed
  Image.fromarray(a).save(folder/f'frame-{i:03d}.png')
  edge=np.any(a[0,:,3]) or np.any(a[-1,:,3]) or np.any(a[:,0,3]) or np.any(a[:,-1,3])
  diagnostic.append(dict(frame=i,edgeContact=bool(edge),visiblePixels=int((a[:,:,3]>0).sum()),brightnessPixels=int(((a[:,:,:3].min(axis=2)>145)&(a[:,:,3]>0)).sum()),difference=int(np.any(a!=frames[i-1],axis=2).sum()) if i else 0))
 # Contacts split into short segments, with exact integer enlargements.
 thumb_w,thumb_h=WIDTH*2,HEIGHT*2
 for start in range(0,len(frames),40):
  indices=list(range(start,min(len(frames),start+40)));contact=Image.new('RGB',(8*thumb_w,5*(thumb_h+24)),'#202632');draw=ImageDraw.Draw(contact)
  for j,index in enumerate(indices):
   im=Image.fromarray(frames[index]).resize((thumb_w,thumb_h),Image.Resampling.NEAREST);x=(j%8)*thumb_w;y=(j//8)*(thumb_h+24);contact.paste(im,(x,y+24),im);draw.text((x+6,y+4),str(index),fill='white')
  contact.save(OUT/f'contact-{start:03d}.png')
 large=[Image.fromarray(a).resize((WIDTH*3,HEIGHT*3),Image.Resampling.NEAREST) for a in frames]
 large[0].save(OUT/'full-animation.webp',save_all=True,append_images=large[1:],duration=42,loop=0,lossless=True)
 save('postprocess.json',dict(width=WIDTH,height=HEIGHT,palette=palette.astype(np.uint8).tolist(),frames=len(frames),temporal=changes,thinPixels=thin_records,matte=matte_records,diagnostic=diagnostic,enclosedMatteMinRawArea=ENCLOSED_MATTE_MIN_AREA,method=f'Cleaned still -> native video -> local matte -> {SCALE*SCALE}-pixel palette vote -> thin evidence -> motion-gated temporal cleanup; actual canvas dimensions'))
 print('PROCESSED',len(frames),'frames',flush=True)

def selected():
 meta=json.loads((OUT/'postprocess.json').read_text(encoding='utf-8'));selpath=OUT/'selection.json'
 selection=json.loads(selpath.read_text(encoding='utf-8')) if selpath.exists() else dict(indices=np.linspace(0,meta['frames']-1,24).round().astype(int).tolist(),durationMs=[150]*24,notes='Uniform initial draft; manual review pending')
 indices=selection['indices'];durations=selection['durationMs'];assert indices==sorted(set(indices)) and len(indices)==len(durations)
 frames=[Image.open(OUT/'all-frames'/f'frame-{i:03d}.png').convert('RGBA') for i in indices]
 cols=6;rows=(len(frames)+cols-1)//cols;grid=Image.new('RGBA',(WIDTH*cols,HEIGHT*rows));strip=Image.new('RGBA',(WIDTH*len(frames),HEIGHT))
 for j,im in enumerate(frames):im.save(OUT/f'frame-{j:02d}.png');grid.paste(im,((j%cols)*WIDTH,(j//cols)*HEIGHT));strip.paste(im,(j*WIDTH,0))
 grid.save(OUT/'sheet-grid.png');strip.save(OUT/'sheet.png')
 frames[0].save(OUT/'animation.png',save_all=True,append_images=frames[1:],duration=durations,loop=0,disposal=0,blend=0)
 large=[im.resize((WIDTH*3,HEIGHT*3),Image.Resampling.NEAREST) for im in frames];large[0].save(OUT/'animation.webp',save_all=True,append_images=large[1:],duration=durations,loop=0,lossless=True)
 gif,gif_info=sprite_gif.encode(frames,durations);(OUT/'animation.gif').write_bytes(gif);save('gif.json',gif_info)
 save('frames.json',dict(frameWidth=WIDTH,frameHeight=HEIGHT,columns=cols,rows=rows,sourceIndices=indices,sourceTimeMs=[round(i/24*1000) for i in indices],durationMs=durations,review=selection,sourceFPS=24,oneShot=True))
 print('EXPORTED',len(frames),'selected frames',flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');import argparse;p=argparse.ArgumentParser();p.add_argument('stage',choices=['process','selected']);a=p.parse_args();globals()[a.stage]()
