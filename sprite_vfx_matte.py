"""Preserve jointly generated blade trails while protecting the character on a flat matte."""
import numpy as np
from PIL import Image
from scipy import ndimage

REVISION="subtle-vfx-matte-v1"

def clean_flat_matte(image,tolerance=24,radius=3,chroma_key=False):
 a=np.array(image.convert('RGBA'));rgb=a[:,:,:3].astype(np.float32)
 border=np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1]));bg=np.median(border,axis=0)
 near=np.max(np.abs(rgb-bg),axis=2)<=tolerance
 seed=np.zeros(near.shape,bool);seed[0]=near[0];seed[-1]=near[-1];seed[:,0]=near[:,0];seed[:,-1]=near[:,-1]
 # Explicit chroma-key inputs contain no foreground in the key colour. Remove
 # matching enclosed holes as well; border connectivity alone misses arm gaps.
 exterior=near if chroma_key else ndimage.binary_propagation(seed,mask=near)
 mask=~exterior & (a[:,:,3]>0);a[exterior,3]=0
 depth=ndimage.distance_transform_edt(mask);core=mask&(depth>radius)
 if not core.any():return Image.fromarray(a),dict(background=bg.tolist(),unmattedPixels=0)
 distance,indices=ndimage.distance_transform_edt(~core,return_indices=True)
 prior=rgb[indices[0],indices[1]];axis=prior-bg
 norm=np.sum(axis*axis,axis=2)
 alpha=np.clip(np.sum((rgb-bg)*axis,axis=2)/np.maximum(norm,1),0,1)
 residual=np.linalg.norm(rgb-(bg+alpha[:,:,None]*axis),axis=2)
 band=mask&(depth<=radius)&(distance<=radius*2+1)&(norm>40**2)&(residual<(40 if chroma_key else 22))&(alpha<.97)
 unmix=np.clip((rgb-bg*(1-alpha[:,:,None]))/np.maximum(alpha[:,:,None],.06),0,255)
 a[band,:3]=np.rint(unmix[band]).astype(np.uint8)
 adjusted=np.where(alpha>.10,np.rint(alpha*255),0).astype(np.uint8)
 a[band,3]=np.minimum(a[:,:,3][band],adjusted[band])
 spill_count=0
 if chroma_key and bg[1]>bg[0]+100 and bg[1]>bg[2]+100:
  # This explicit green-key recipe contains no green costume parts. Colour-line
  # fitting can fail near two different contour colours; despill that final rim.
  current=a[:,:,:3].astype(np.float32);spill=current[:,:,1]-np.maximum(current[:,:,0],current[:,:,2])
  rim=(a[:,:,3]>0)&(depth<=radius+2)&(spill>8)
  opacity=np.clip(1-spill/max(bg[1],1),0,1)
  foreground=np.clip((current-bg*(1-opacity[:,:,None]))/np.maximum(opacity[:,:,None],.06),0,255)
  foreground[:,:,1]=np.minimum(foreground[:,:,1],np.maximum(foreground[:,:,0],foreground[:,:,2]))
  a[rim,:3]=np.rint(foreground[rim]).astype(np.uint8)
  a[rim,3]=np.rint(a[:,:,3][rim]*opacity[rim]).astype(np.uint8)
  a[rim&(a[:,:,3]<20),3]=0;spill_count=int(rim.sum())
 a[a[:,:,3]==0,:3]=0
 return Image.fromarray(a),dict(background=bg.tolist(),radius=radius,chromaKey=chroma_key,unmattedPixels=int(band.sum()),despilledPixels=spill_count,removedEdgePixels=int((band&(a[:,:,3]==0)).sum()),method='known chroma key including enclosed holes + local unmatting' if chroma_key else 'border-connected flat matte + local colour-line unmatting, narrow band only')

def remove(raw,neutral_glow=True):
 cut,meta=clean_flat_matte(raw,tolerance=38,radius=3,chroma_key=True)
 rgb=np.array(raw.convert('RGB'),dtype=float);a=np.array(cut,dtype=np.uint8)
 bg=np.array(meta['background'])
 if min(bg[0],bg[2])>bg[1]+100:
  # Magenta mixtures extend far beyond a narrow colour-key threshold. Solve
  # their minimum physical opacity; actual cyan/white/gold cores stay opaque.
  mixed=(np.minimum(rgb[:,:,0],rgb[:,:,2])-rgb[:,:,1]>8)&(a[:,:,3]>0)
  opacity=np.maximum(1-np.minimum(rgb[:,:,0],rgb[:,:,2])/255,rgb[:,:,1]/255)
  opacity=np.clip(opacity,0,1)
  foreground=np.clip((rgb-bg*(1-opacity[:,:,None]))/np.maximum(opacity[:,:,None],.01),0,255)
  a[mixed,:3]=np.rint(foreground[mixed]).astype('uint8')
  a[mixed,3]=np.minimum(a[:,:,3][mixed],np.rint(opacity[mixed]*255).astype('uint8'))
  a[mixed&(opacity<.05)]=0
  meta['magentaUnmixedPixels']=int(mixed.sum())
 elif np.ptp(bg)<12:
  # Recover blue/cyan energy glow from a neutral matte instead of leaving an
  # opaque grey band. Dark costume colours do not enter this bright VFX mask.
  cool=(rgb[:,:,2]-rgb[:,:,0]>16)&(rgb.max(2)>145)
  distance=np.max(np.abs(rgb-bg),axis=2)
  opacity=np.maximum(((bg-rgb)/np.maximum(bg,1)).max(2),((rgb-bg)/np.maximum(255-bg,1)).max(2))
  opacity=np.clip(opacity,0,1)*np.clip((distance-6)/20,0,1)
  foreground=np.clip((rgb-bg*(1-opacity[:,:,None]))/np.maximum(opacity[:,:,None],.01),0,255)
  a[cool,:3]=np.rint(foreground[cool]).astype('uint8');a[cool,3]=np.rint(opacity[cool]*255).astype('uint8')
  a[cool&(opacity<.04)]=0
  meta['neutralBlueGlowUnmixedPixels']=int(cool.sum())
  if neutral_glow:
   # A pale achromatic trail is white light mixed with the grey backdrop.
   # Leaving its sampled RGB opaque creates a grey paper-like strip.
   white=(np.ptp(rgb,axis=2)<18)&(np.min(rgb-bg,axis=2)>8)
   white_alpha=np.clip(((rgb-bg)/np.maximum(255-bg,1)).max(2),0,1)
   white_rgb=np.clip((rgb-bg*(1-white_alpha[:,:,None]))/np.maximum(white_alpha[:,:,None],.01),0,255)
   a[white,:3]=np.rint(white_rgb[white]).astype('uint8');a[white,3]=np.rint(white_alpha[white]*255).astype('uint8')
   meta['neutralWhiteGlowUnmixedPixels']=int(white.sum())
  # A neutral key can coincide with grey/brown costume shadows. Restore only
  # confident anime-character pixels, without using this model to cut VFX.
  import image_background
  semantic=np.array(image_background.remove(raw).getchannel('A'))
  border=np.concatenate((semantic[0],semantic[-1],semantic[:,0],semantic[:,-1]))
  if np.mean(border>224)<.01:
   restore=(semantic>224)&(semantic>a[:,:,3])
   a[restore,:3]=rgb[restore].astype('uint8');a[restore,3]=semantic[restore]
   meta['protectedCharacterPixels']=int(restore.sum())
  else:meta['characterProtectionSkipped']='segmentation leaked onto border'
 return Image.fromarray(a),meta
