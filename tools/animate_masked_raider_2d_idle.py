"""A source-pixel 2D idle control: mesh displacement, no generative repainting."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import cv2
import numpy as np
from PIL import Image
import sprite_gif

OUT=ROOT/'outputs/masked-raider-flat2d-20261023/source-pixel-idle'
SOURCE=ROOT/'outputs/masked-raider-motion-20261023/source-original.png'


def smoothstep(a,b,x):
 t=np.clip((x-a)/(b-a),0,1)
 return t*t*(3-2*t)


def main():
 OUT.mkdir(parents=True,exist_ok=True)
 source=Image.open(SOURCE).convert('RGBA')
 scale=min(768/source.width,768/source.height)*.9
 resized=source.resize((round(source.width*scale),round(source.height*scale)),Image.Resampling.LANCZOS)
 canvas=Image.new('RGBA',(768,768))
 canvas.paste(resized,((768-resized.width)//2,(768-resized.height)//2))
 canvas.save(OUT/'reference.png')
 rgba=np.asarray(canvas).astype(np.float32)/255
 alpha=rgba[:,:,3:]
 # Premultiplied resampling avoids fringes around a moving transparent outline.
 premult=np.concatenate((rgba[:,:,:3]*alpha,alpha),axis=2)
 yy,xx=np.mgrid[:768,:768].astype(np.float32)
 upper=1-smoothstep(420,690,yy)
 club=(1-smoothstep(330,370,xx))*(1-smoothstep(620,650,yy))
 upper=np.maximum(upper,club)
 tail=smoothstep(400,490,xx)*smoothstep(380,500,yy)*(1-smoothstep(650,700,yy))
 frames=[]
 for i in range(72):
  phase=i*2*np.pi/72
  dx=upper*(1.2*np.sin(phase))+tail*(1.5*(np.sin(phase-np.pi/3)+np.sin(np.pi/3)))
  dy=upper*(-2.0*np.sin(phase))
  warped=cv2.remap(premult,xx-dx.astype(np.float32),yy-dy.astype(np.float32),
   interpolation=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=0)
  a=warped[:,:,3:]
  rgb=np.where(a>1e-6,warped[:,:,:3]/np.maximum(a,1e-6),0)
  output=np.concatenate((rgb,a),axis=2)
  encoded=np.clip(np.rint(output*255),0,255).astype('uint8')
  # Pin the foot strip, including otherwise irrelevant RGB in transparent pixels.
  encoded[700:]=np.asarray(canvas)[700:]
  if i==0:encoded=np.array(canvas)
  frames.append(Image.fromarray(encoded))
 assert np.array_equal(np.asarray(frames[0]),np.asarray(canvas))
 # The feet remain exactly the original pixels, not regenerated approximations.
 for im in frames:assert np.array_equal(np.asarray(im)[700:],np.asarray(canvas)[700:])
 common=OUT.parent/'comparison-crop.json'
 crop=json.loads(common.read_text(encoding='utf-8'))['bounds'] if common.exists() else json.loads((ROOT/'outputs/masked-raider-motion-20261023/idle/frames.json').read_text(encoding='utf-8'))['previewCropBounds']
 previews=[im.crop(crop).resize((512,512),Image.Resampling.LANCZOS) for im in frames]
 ticks=[round(i*1000/24) for i in range(73)]
 times=[b-a for a,b in zip(ticks,ticks[1:])]
 previews[0].save(OUT/'animation.webp',save_all=True,append_images=previews[1:],duration=times,loop=0,lossless=True)
 data,gif=sprite_gif.encode(previews,times)
 (OUT/'animation.gif').write_bytes(data)
 selected=[round(i*72/16) for i in range(16)]
 sheet=Image.new('RGBA',(768*4,768*4))
 for n,i in enumerate(selected):sheet.paste(frames[i],(n%4*768,n//4*768))
 sheet.save(OUT/'sheet.png')
 bounds=[ticks[i] for i in selected]+[ticks[-1]]
 (OUT/'frames.json').write_text(json.dumps(dict(frameWidth=768,frameHeight=768,columns=4,rows=4,
  sourceIndices=selected,durationMs=[b-a for a,b in zip(bounds,bounds[1:])],
  method='original supplied artwork, including its outline, with 2D mesh displacement; no AI generation',
  sourcePath=str(SOURCE),newDrawnParts=False,newLighting=False,
  firstFramePixelExact=True,footPixelsExact=True,maxUpperBodyDisplacementPx=[1.2,2.0],gif=gif),indent=2),encoding='utf-8')
 print('SOURCE_PIXEL_2D_IDLE_READY',OUT,flush=True)


if __name__=='__main__':main()
