"""Compact playback comparison of the actual reviewed output animations."""
import bisect,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import sprite_gif
OUT=ROOT/'outputs/normal-action-snap-20261020'
def read(path,size=384):
 frames=[];bounds=[0]
 with Image.open(path) as im:
  for i in range(im.n_frames):
   im.seek(i);frame=im.convert('RGBA');frames.append(frame.resize((size,size),Image.Resampling.LANCZOS));bounds.append(bounds[-1]+im.info['duration'])
 return frames,bounds
def main():
 sources=[read(ROOT/'outputs/normal-run-sheathed-20261020/run/animation.webp',300),read(OUT/'attack/animation.webp')]
 font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',17)
 total=sources[0][1][-1];ticks=list(range(0,total,40))+[total];durations=[b-a for a,b in zip(ticks,ticks[1:])];frames=[]
 for t in ticks[:-1]:
  canvas=Image.new('RGB',(768,420),'#252936');draw=ImageDraw.Draw(canvas)
  draw.text((16,8),'뛰기 · 무기 수납',fill='white',font=font);draw.text((400,8),'빠른 내려찍기 · 단발 동작 반복',fill='white',font=font)
  for col,(images,bounds) in enumerate(sources):
   index=bisect.bisect_right(bounds,t%bounds[-1])-1;im=images[index];canvas.paste(im,(42,126) if col==0 else (384,36),im)
  frames.append(canvas.convert('RGBA'))
 frames[0].save(OUT/'comparison-poster.png')
 data,info=sprite_gif.encode(frames,durations);(OUT/'comparison.gif').write_bytes(data)
 print('Comparison',info['totalMs'],'ms',len(frames),'display frames; source timing preserved')
if __name__=='__main__':main()
