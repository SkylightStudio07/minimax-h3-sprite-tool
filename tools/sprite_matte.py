"""Conservative known-flat-background edge unmatting for private sprite tests.

Do not globally erode the silhouette: only line-compatible colours in a narrow
border band are unmatted using a nearby opaque interior colour as a prior.
Thin components with no nearby interior core stay untouched.
"""
import numpy as np
from PIL import Image
from scipy import ndimage

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
