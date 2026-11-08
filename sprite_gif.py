"""Deterministic handoff GIFs: one shared palette, hard alpha, cumulative 10ms timing."""
import io,math
import numpy as np
from PIL import Image

MAX_PIXELS=64_000_000

def durations_ms(values):
 if not values or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<10 or v>655350 for v in values):
  raise ValueError('GIF 프레임 시간은 10ms 이상이어야 합니다.')
 total=0.;last=0;out=[]
 for value in values:
  total+=value;tick=max(last+1,int(math.floor(total/10+.5)));out.append((tick-last)*10);last=tick
 return out

def encode(frames,durations,repeat=True,scale=1):
 if type(scale) is not int or not 1<=scale<=4:raise ValueError('GIF 배율은 1~4 정수여야 합니다.')
 if not frames or len(frames)!=len(durations) or len(frames)>1024:raise ValueError('GIF 프레임과 재생 시간을 확인하세요.')
 size=frames[0].size
 if any(f.size!=size for f in frames) or size[0]*size[1]*len(frames)*scale*scale>MAX_PIXELS:raise ValueError('GIF 프레임 크기를 맞추고 총 64MP 이하로 줄이세요.')
 timing=durations_ms(durations);images=[f.convert('RGBA') for f in frames];colors=set();exact=True
 for im in images:
  a=np.asarray(im);visible=a[:,:,:3][a[:,:,3]>=128]
  colors.update(map(tuple,np.unique(visible,axis=0).tolist()))
  if len(colors)>255:exact=False;break
 if exact:
  entries=sorted(colors) or [(0,0,0)]
 else:
  samples=[]
  for im in images:
   a=np.asarray(im);v=a[:,:,:3][a[:,:,3]>=128];samples.append(v[::max(1,math.ceil(len(v)/max(1,1_000_000//len(images))))])
  sample=np.concatenate(samples)
  if not len(sample):sample=np.zeros((1,3),np.uint8)
  strip=Image.fromarray(sample.reshape(1,-1,3));quant=strip.quantize(colors=255,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
  entries=[tuple(quant.getpalette()[i*3:i*3+3]) for i,_ in sorted((index,count) for count,index in quant.getcolors())]
 table=[0,0,0]+[v for c in entries for v in c];table+=[0]*(768-len(table));p=Image.new('P',(1,1));p.putpalette(table)
 packed=np.array([int(c[0])*65536+int(c[1])*256+int(c[2]) for c in entries],np.uint32)
 encoded=[]
 for im in images:
  a=np.asarray(im);opaque=a[:,:,3]>=128
  if exact:
   keys=a[:,:,0].astype(np.uint32)*65536+a[:,:,1].astype(np.uint32)*256+a[:,:,2]
   labels=np.zeros(opaque.shape,np.uint8);labels[opaque]=np.searchsorted(packed,keys[opaque])+1
  else:
   # Reserve zero for transparency. Duplicate first opaque colour at zero during
   # lookup, then move any opaque zero labels to its equivalent opaque index.
   quant_palette=Image.new('P',(1,1));quant_palette.putpalette(list(entries[0])+table[3:])
   labels=np.array(im.convert('RGB').quantize(palette=quant_palette,dither=Image.Dither.NONE));labels[opaque&(labels==0)]=1;labels[~opaque]=0
  frame=Image.fromarray(labels,'P');frame.putpalette(table)
  if scale!=1:frame=frame.resize((size[0]*scale,size[1]*scale),Image.Resampling.NEAREST)
  frame.info['transparency']=0;encoded.append(frame)
 out=io.BytesIO();options=dict(save_all=True,append_images=encoded[1:],duration=timing,transparency=0,background=0,disposal=2,optimize=False)
 if repeat:options['loop']=0
 encoded[0].save(out,format='GIF',**options)
 return out.getvalue(),dict(sourceFrames=len(frames),durationMs=timing,totalMs=sum(timing),size=[size[0]*scale,size[1]*scale],sharedPalette=True,exactOpaqueColors=exact,binaryAlpha=True,repeat=repeat)

def split_sheet(image,columns,rows,count):
 if any(type(v) is not int or v<1 for v in (columns,rows,count)) or count>columns*rows or image.width<columns or image.height<rows or image.width*image.height>MAX_PIXELS:
  raise ValueError('시트 열·행·프레임 수를 확인하세요.')
 w,h=math.ceil(image.width/columns),math.ceil(image.height/rows);out=[]
 for i in range(count):
  box=(round(i%columns*image.width/columns),round(i//columns*image.height/rows),round((i%columns+1)*image.width/columns),round((i//columns+1)*image.height/rows))
  frame=Image.new('RGBA',(w,h));frame.paste(image.crop(box),(0,0));out.append(frame)
 return out
