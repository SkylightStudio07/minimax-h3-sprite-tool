"""Timed pixel VFX layers over the accepted chibi attack, without regenerating its body."""
import argparse,hashlib,html,json,math,re,shutil,sys,zipfile
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
SOURCE=ROOT/'outputs/chibi-attack-20261020'
OUT=ROOT/'outputs/chibi-attack-vfx-20261020'
W,H=192,160
MODES={'original':'원본 공격','impact':'타격감 강조','skill':'화려한 스킬'}
C={'deep':(28,52,130,255),'blue':(34,104,218,255),'cyan':(75,199,255,255),'ice':(176,241,255,255),'gold':(255,180,64,255),'orange':(232,90,34,255),'white':(249,240,233,255),'violet':(124,91,220,255)}

def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def blank():return Image.new('RGBA',(W,H))
def xy(x,y):return (round(x),round(y))

def ribbon(image,center,radii,start,end,width,color):
 """Native-grid tapered energy ribbon; no smoothing or fractional-alpha glow."""
 cx,cy=center;rx,ry=radii;outer=[];inner=[]
 for t in np.linspace(0,1,90):
  angle=math.radians(start+(end-start)*t);co,si=math.cos(angle),math.sin(angle)
  normal=np.array([co/rx,si/ry]);normal/=np.linalg.norm(normal)
  thickness=max(.25,width*math.sin(math.pi*t)**.7)/2
  point=np.array([cx+rx*co,cy+ry*si]);outer.append(xy(*(point+normal*thickness)));inner.append(xy(*(point-normal*thickness)))
 ImageDraw.Draw(image).polygon(outer+inner[::-1],fill=color)

def arc(image,center,radii,start,end,width):
 for scale,color in [(1.25,'deep'),(1,'blue'),(.66,'cyan'),(.30,'ice')]:ribbon(image,center,radii,start,end,max(1,width*scale),C[color])

def star(image,x,y,radius,color):
 points=[]
 for i in range(16):
  angle=i*math.pi/8;rad=radius if i%4==0 else radius*.55 if i%2==0 else radius*.18
  points.append(xy(x+math.cos(angle)*rad,y+math.sin(angle)*rad))
 ImageDraw.Draw(image).polygon(points,fill=color)

def effects(index,mode,character):
 back,front=blank(),blank()
 if mode=='original':return back,front
 skill=mode=='skill';bd=ImageDraw.Draw(back);fd=ImageDraw.Draw(front)
 # Small blade-charge glints track the manually reviewed wind-up positions.
 tip={4:(94,31),5:(86,25),6:(59,29),7:(51,35),8:(45,37)}
 if index in tip:
  x,y=tip[index];r=3+(index-4)//2+(2 if skill else 0)
  star(back,x,y,r+2,C['blue']);star(back,x,y,r,C['ice']);bd.rectangle((x,y,x+1,y+1),fill=C['white'])
  if skill:
   for dx,dy in [(-9,4),(5,-7),(10,5)]:bd.rectangle((x+dx,y+dy,x+dx+1,y+dy+1),fill=C['cyan'])
 if index==9:
  arc(back,(74,43),(39,27),-162,-18,8 if skill else 5)
  if skill:
   ribbon(back,(76,48),(46,34),-150,-28,2,C['violet']);star(back,86,24,7,C['ice'])
 if 10<=index<=14:
  age=index-10
  starts=[-65,-18,14,38,59];ends=[66,82,94,103,111]
  widths=[20,15,10,6,3] if skill else [9,7,5,3,1]
  arc(back,(75+age*2,58),(69+age*2,43+age),starts[age],ends[age],widths[age])
  if skill:
   ribbon(back,(75+age*2,58),(80+age,53+age),starts[age]+6,ends[age]-9,max(1,4-age*.7),C['violet'])
   ribbon(back,(75+age*2,58),(84+age,55+age),starts[age]+16,ends[age]-16,max(1,2-age*.3),C['cyan'])
 # Impact is in empty space just ahead of the reviewed sword tip (source 10/11).
 if index in (10,11,12,13):
  radius=([32,25,14,6] if skill else [15,12,7,3])[index-10]
  star(front,147,98,radius+3,C['orange']);star(front,147,98,radius,C['gold']);star(front,147,98,max(2,radius*.48),C['white'])
 if 11<=index<=17:
  age=index-11;rx=12+age*3;ry=4+age
  for lo,hi in [(15,70),(110,160),(200,250),(290,340)]:ribbon(front,(147,98),(rx,ry),lo,hi,2 if skill else 1,C['cyan'] if age<4 else C['blue'])
 if 10<=index<=22:
  age=index-10;t=age/12
  angles=[-65,-38,-12,18,45,70] if not skill else [-75,-60,-43,-25,-8,9,26,42,61,78,117,153]
  for n,degrees in enumerate(angles):
   if age>8+(n%4):continue
   angle=math.radians(degrees);distance=4+t*(17+n%3*3)
   x=147+math.cos(angle)*distance;y=98+math.sin(angle)*distance+t*t*7
   length=max(1,(9 if skill else 6)*(1-t));end=(x+math.cos(angle)*length,y+math.sin(angle)*length)
   color=C['white'] if age<2 else C['gold'] if age<6 else C['orange']
   fd.line([xy(x,y),xy(*end)],fill=color,width=2 if skill and age<5 else 1)
   if skill and n%3==0 and age<6:fd.rectangle((round(x)-1,round(y)-1,round(x),round(y)),fill=C['ice'])
 if skill and 8<=index<=12:
  # A short aura flare sits behind the upper body, rather than recoloring it.
  age=index-8;radius=[27,34,39,44,48][age]
  for n in range(9):
   a=math.radians(-150+n*29);x=82+math.cos(a)*radius;y=72+math.sin(a)*radius*.8
   bd.line([xy(x,y),xy(x+math.cos(a)*5,y+math.sin(a)*4)],fill=C['violet'] if age>2 else C['cyan'],width=1)
 # Preserve every original opaque character/weapon pixel even in the composite.
 a=np.array(front);a[np.array(character.getchannel('A'))>0]=0;front=Image.fromarray(a)
 return back,front

def export_set(folder,frames,durations):
 import sprite_gif
 folder.mkdir(parents=True,exist_ok=True);grid=Image.new('RGBA',(W*6,H*((len(frames)+5)//6)));strip=Image.new('RGBA',(W*len(frames),H))
 for n,im in enumerate(frames):im.save(folder/f'frame-{n:02d}.png');grid.paste(im,((n%6)*W,(n//6)*H));strip.paste(im,(n*W,0))
 grid.save(folder/'sheet-grid.png');strip.save(folder/'sheet.png')
 frames[0].save(folder/'animation.png',save_all=True,append_images=frames[1:],duration=durations,loop=0,disposal=0,blend=0)
 data,meta=sprite_gif.encode(frames,durations);(folder/'animation.gif').write_bytes(data);save(folder/'gif.json',meta)
 data,_=sprite_gif.encode(frames,durations,scale=3);(folder/'animation-3x.gif').write_bytes(data)

def make():
 OUT.mkdir(parents=True,exist_ok=True)
 hashes={str(p.relative_to(ROOT)):sha(p) for p in SOURCE.rglob('*') if p.is_file() and p.suffix in ('.png','.gif','.mp4','.json')}
 old=OUT/'source-hashes.json'
 if old.exists():assert read(old)==hashes
 else:save(old,hashes)
 original=read(SOURCE/'frames.json');indices=sorted(set(original['sourceIndices'])|set(range(4,23)))
 times=[round(i*1000/24) for i in indices];durations=[b-a for a,b in zip(times,times[1:])]+[original['durationMs'][-1]]
 base=[Image.open(SOURCE/'all-frames'/f'frame-{i:03d}.png').convert('RGBA') for i in indices]
 export_set(OUT/'character',base,durations)
 for mode in MODES:
  sets={layer:[] for layer in ['back','front','effects','composite']}
  for index,character in zip(indices,base):
   back,front=effects(index,mode,character);fx=Image.alpha_composite(back,front)
   composite=Image.alpha_composite(Image.alpha_composite(back,character),front)
   for layer,im in [('back',back),('front',front),('effects',fx),('composite',composite)]:sets[layer].append(im)
  for layer,frames in sets.items():export_set(OUT/mode/layer,frames,durations)
  save(OUT/mode/'layer-settings.json',dict(label=MODES[mode],order=['back','character','front'],mergedEffectsOrder=['effects','character'],character='../character',effectPalette={k:list(v) for k,v in C.items()},nativePixelRendering=True,binaryAlpha=True,originalOpaquePixelsPreserved=True))
 save(OUT/'frames.json',dict(frameWidth=W,frameHeight=H,columns=6,rows=(len(indices)+5)//6,sourceIndices=indices,sourceTimeMs=times,durationMs=durations,sourceFPS=24,sourceFrameSize=original['sourceFrameSize'],sourceFrameOffset=original['sourceFrameOffset'],notes='Same original attack video frames; extra samples during VFX decay avoid holding particles. Total source timing and recovered end hold preserved.',vfxMethod='Deterministic native-grid geometry with manually timed charge/slash/impact/sparks; no new image or video generation.'))
 save(OUT/'vfx-settings.json',dict(presets=MODES,renderOrder=['back','character','front'],sourceAttack='one attack and recovery; preview repeats',manualAnchors=dict(impact=[147,98],mainArcCenter=[75,58],mainArcRadii=[69,43]),chargeSourceFrames=[4,9],slashSourceFrames=[9,14],impactSourceFrames=[10,13],particlesSourceFrames=[10,22],palette={k:list(v) for k,v in C.items()},paletteLimit='Original 32-color character plus at most 8 VFX colors; no soft-alpha glow',limitations='The original white sword deformation at source 9/10 is retained. Effects are designed for this attack, not automatic generic motion tracking.'))
 build()

def build():
 meta=read(OUT/'frames.json');cards=[];data={}
 compare=Image.new('RGB',(W*6,(H+24)*3),'#263344');draw=ImageDraw.Draw(compare)
 for row,mode in enumerate(MODES):
  for col,index in enumerate([8,9,10,11,14,20]):
   n=meta['sourceIndices'].index(index);im=Image.open(OUT/mode/'composite'/f'frame-{n:02d}.png').convert('RGBA');x=col*W;y=row*(H+24);compare.paste(im,(x,y+24),im);draw.text((x+5,y+4),f'{mode} / {index}',fill='white')
 compare.save(OUT/'comparison.png')
 peak=Image.new('RGB',(W*6,H*3+24),'#263344');draw=ImageDraw.Draw(peak)
 for col,mode in enumerate(['impact','skill']):
  im=Image.open(OUT/mode/'composite'/f'frame-{meta["sourceIndices"].index(10):02d}.png').convert('RGBA').resize((W*3,H*3),Image.Resampling.NEAREST);peak.paste(im,(col*W*3,24),im);draw.text((col*W*3+6,4),mode+' / source 10 / 3x',fill='white')
 peak.save(OUT/'comparison-peak.png')
 for mode,label in MODES.items():
  data[mode]={layer:[f'{mode}/{layer}/frame-{i:02d}.png' for i in range(len(meta['sourceIndices']))] for layer in ['composite','effects']}
  data[mode]['character']=[f'character/frame-{i:02d}.png' for i in range(len(meta['sourceIndices']))]
  cards.append(f'''<article data-mode="{mode}"><h2>{label}</h2><label>표시 <select class="layer"><option value="composite">합성</option><option value="effects">이펙트만</option><option value="character">캐릭터만</option></select></label><div class="viewport"><img class="sprite" src="{mode}/composite/frame-00.png" width="{W}" height="{H}"></div><p><a href="{mode}/composite/animation-3x.gif" download>합성 GIF 3배</a> · <a href="{mode}/composite/sheet-grid.png" download>합성 시트</a></p><p><a href="{mode}/effects/sheet-grid.png" download>이펙트 시트</a> · <a href="{mode}/layer-settings.json">레이어 순서</a></p></article>''')
 script='''const assets=ASSETS,times=TIMES,indices=INDICES;let i=0,running=true,speed=1,elapsed=0,last;const seek=document.getElementById('seek'),play=document.getElementById('play'),position=document.getElementById('position');const cards=[...document.querySelectorAll('article')];function draw(){for(const c of cards)c.querySelector('.sprite').src=assets[c.dataset.mode][c.querySelector('.layer').value][i];seek.value=i;position.textContent=`${i+1}/${indices.length}장 · 원본 ${indices[i]}번`}function pause(){running=false;play.textContent='재생';elapsed=0}play.onclick=()=>{running=!running;play.textContent=running?'정지':'재생';elapsed=0};document.getElementById('prev').onclick=()=>{pause();i=(i-1+indices.length)%indices.length;draw()};document.getElementById('next').onclick=()=>{pause();i=(i+1)%indices.length;draw()};seek.oninput=e=>{pause();i=Number(e.target.value);draw()};document.getElementById('speed').onchange=e=>speed=Number(e.target.value);document.getElementById('zoom').onchange=e=>document.documentElement.style.setProperty('--zoom',e.target.value);document.getElementById('background').onchange=e=>document.body.dataset.bg=e.target.value;for(const c of cards)c.querySelector('.layer').onchange=draw;document.onkeydown=e=>{if(['INPUT','SELECT'].includes(e.target.tagName))return;if(e.code==='Space'){e.preventDefault();play.onclick()}else if(e.code==='ArrowRight'){e.preventDefault();document.getElementById('next').onclick()}else if(e.code==='ArrowLeft'){e.preventDefault();document.getElementById('prev').onclick()}};function tick(now){if(last!==undefined&&running){elapsed+=Math.min(now-last,200)*speed;while(elapsed>=times[i]){elapsed-=times[i];i=(i+1)%times.length;draw()}}last=now;requestAnimationFrame(tick)}draw();requestAnimationFrame(tick);'''.replace('ASSETS',json.dumps(data)).replace('TIMES',json.dumps(meta['durationMs'])).replace('INDICES',json.dumps(meta['sourceIndices']))
 summary=read(OUT/'review.json')['summary'] if (OUT/'review.json').exists() else '두 단계의 이펙트 비교입니다. 시각 검토 전 초안입니다.'
 page=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>치비 공격 · 이펙트 비교</title><style>:root{{--zoom:2}}body{{background:#151b26;color:#eee;margin:24px;font:15px/1.6 system-ui}}a{{color:#c8c4ff}}h1{{font-size:26px}}main{{display:flex;gap:16px;flex-wrap:wrap}}article{{padding:16px;background:#252d3b;border-radius:12px;max-width:calc(100vw - 80px)}}h2{{font-size:18px}}.viewport{{overflow:auto;margin-top:12px}}.sprite{{display:block;width:calc({W}px * var(--zoom));height:calc({H}px * var(--zoom));image-rendering:pixelated;background:#263344}}body[data-bg=light] .sprite{{background:#eee}}body[data-bg=checker] .sprite{{background:repeating-conic-gradient(#263344 0 25%,#455069 0 50%) 0/24px 24px}}button,select{{padding:7px 10px;border:1px solid #697d9d;background:#35455c;color:#fff;border-radius:6px}}.controls{{position:sticky;top:0;background:#1b2535;padding:12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:18px 0;z-index:2}}.controls input{{flex:1;min-width:130px}}#position{{min-width:170px}}p{{max-width:1100px}}</style><h1>치비 공격 · 이펙트 비교</h1><p>{html.escape(summary)}</p><p>캐릭터를 다시 생성하지 않고 원래 프레임에 맞춰 검기·섬광·불꽃을 도트로 그렸습니다. 세 버전은 같은 프레임·같은 시간으로 재생합니다. 이펙트가 움직이는 구간만 프레임을 더 촘촘히 골랐고 전체 재생 시간은 그대로입니다.</p><p>캐릭터 / 뒤쪽 이펙트 / 앞쪽 이펙트를 따로 저장합니다. 합성해도 기존 캐릭터의 불투명 픽셀은 그대로이며, 원래 칼의 흰 곡선 변형은 남습니다. 이 공격에 맞춰 만든 효과로 범용 자동 추적 도구는 아닙니다.</p><p><a href="chibi-attack-vfx.zip" download>캐릭터·이펙트 레이어·합성 PNG/GIF ZIP</a> · <a href="character/animation.gif" download>캐릭터만 GIF</a></p><div class="controls"><button id="play">정지</button><button id="prev">이전 장</button><button id="next">다음 장</button><input id="seek" type="range" min="0" max="{len(meta['sourceIndices'])-1}" value="0" aria-label="공통 프레임"><span id="position"></span><label>속도 <select id="speed"><option value="0.5">0.5배</option><option value="1" selected>1배</option><option value="2">2배</option></select></label><label>배율 <select id="zoom"><option value="1">1배</option><option value="2" selected>2배</option><option value="3">3배</option></select></label><label>배경 <select id="background"><option value="dark">어두움</option><option value="light">밝음</option><option value="checker">체크</option></select></label></div><p>Space 재생/정지 · ← → 한 장 이동 · 각 카드에서 ‘이펙트만’ 선택 가능</p><main>{''.join(cards)}</main><script>{script}</script></html>'''
 (OUT/'preview.html').write_text(page,encoding='utf-8');(OUT/'preview-script.js').write_text(script,encoding='utf-8')
 with zipfile.ZipFile(OUT/'chibi-attack-vfx.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in OUT.rglob('*'):
   if p.is_file() and p.suffix in ('.png','.gif','.json','.html','.js'):z.write(p,p.relative_to(OUT))
 print('PREVIEW',OUT/'preview.html',flush=True)

def check():
 for p,h in read(OUT/'source-hashes.json').items():assert sha(ROOT/p)==h
 meta=read(OUT/'frames.json');fxcolors={c[:3] for c in C.values()};report={}
 for mode in MODES:
  modified=0
  for n,index in enumerate(meta['sourceIndices']):
   char=np.array(Image.open(OUT/'character'/f'frame-{n:02d}.png').convert('RGBA'));source=np.array(Image.open(SOURCE/'all-frames'/f'frame-{index:03d}.png').convert('RGBA'));assert np.array_equal(char,source)
   back=Image.open(OUT/mode/'back'/f'frame-{n:02d}.png').convert('RGBA');front=Image.open(OUT/mode/'front'/f'frame-{n:02d}.png').convert('RGBA');comp=np.array(Image.open(OUT/mode/'composite'/f'frame-{n:02d}.png').convert('RGBA'))
   assert np.array_equal(np.array(Image.alpha_composite(Image.alpha_composite(back,Image.fromarray(char)),front)),comp)
   merged=Image.open(OUT/mode/'effects'/f'frame-{n:02d}.png').convert('RGBA')
   assert np.array_equal(np.array(Image.alpha_composite(merged,Image.fromarray(char))),comp)
   assert np.array_equal(comp[char[:,:,3]>0],char[char[:,:,3]>0])
   for layer in ['back','front','effects','composite']:
    a=np.array(Image.open(OUT/mode/layer/f'frame-{n:02d}.png').convert('RGBA'));assert a.shape==(H,W,4) and set(np.unique(a[:,:,3]))<={0,255}
    if layer!='composite':assert {tuple(c) for c in np.unique(a[:,:,:3][a[:,:,3]>0],axis=0)}<=fxcolors
    if layer!='composite':assert not (a[0,:,3].any() or a[-1,:,3].any() or a[:,0,3].any() or a[:,-1,3].any())
   modified+=int(np.any(char!=comp,axis=2).sum())
   if mode=='original':assert np.array_equal(char,comp)
  assert mode=='original' or modified>0;report[mode]=dict(addedPixelsAcrossFrames=modified)
 assert sum(meta['durationMs'])==sum(read(SOURCE/'frames.json')['durationMs'])
 for folder in [OUT/'character']+[OUT/mode/layer for mode in MODES for layer in ['back','front','effects','composite']]:
  grid=Image.open(folder/'sheet-grid.png').convert('RGBA');assert grid.size==(W*6,H*meta['rows'])
  for n in range(len(meta['sourceIndices'])):assert np.array_equal(np.array(grid.crop(((n%6)*W,(n//6)*H,(n%6+1)*W,(n//6+1)*H))),np.array(Image.open(folder/f'frame-{n:02d}.png').convert('RGBA')))
  with Image.open(folder/'animation.gif') as gif,Image.open(folder/'animation-3x.gif') as big:
   assert gif.size==(W,H) and big.size==(W*3,H*3) and gif.n_frames==big.n_frames;total=0
   for n in range(gif.n_frames):
    gif.seek(n);big.seek(n);assert np.array_equal(np.array(big.convert('RGBA')),np.repeat(np.repeat(np.array(gif.convert('RGBA')),3,axis=0),3,axis=1));total+=gif.info['duration']
   assert abs(total-sum(meta['durationMs']))<=10
 for link in re.findall(r'(?:href|src)="([^"]+)"',(OUT/'preview.html').read_text(encoding='utf-8')):assert (OUT/link).exists(),link
 save(OUT/'validation.json',dict(passed=True,frames=len(meta['sourceIndices']),modes=report,sourceHashesUnchanged=True,allCharacterPixelsExact=True,compositeCharacterOpaquePixelsExact=True,compositionExact=True,binaryAlpha=True,effectColors=len(fxcolors),timingUnchanged=True,gif3xExact=True,actualBrowserVerified=False));build()
 with zipfile.ZipFile(OUT/'chibi-attack-vfx.zip') as z:assert z.testzip() is None and z.read('validation.json')==(OUT/'validation.json').read_bytes()
 print('PASS source/body pixels, composition, palettes/alpha, sheets, timing, GIFs and ZIP',flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['make','build','check']);a=p.parse_args();globals()[a.stage]()
