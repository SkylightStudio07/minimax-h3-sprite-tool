"""Private idle/club-attack test using the user's supplied enemy illustration."""
import argparse
import hashlib
import html
import json
import math
import shutil
import sys
import zipfile
from fractions import Fraction
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import av
import numpy as np
from PIL import Image,ImageDraw
from scipy import ndimage
import idle_tool as engine
import image_background
import sprite_gif
import sprite_loop
from tools import verify_pixel_minimax as executor
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release

SOURCE=Path('Z:/Vertex/적/c1d542a5-9813-471e-a250-67fdac388b80.png')
OUT=ROOT/'outputs/masked-raider-motion-20261023'
IDENTITY=(
 'The EXACT SAME single fully masked tactical raider in the supplied illustration, same adult proportions and '
 'anime linework and cel shading. Keep the tan ballistic helmet and mounts, dark purple reflective gas-mask '
 'lenses, olive respirator and round filter, black high collar, long ragged charcoal coat with burgundy lining, '
 'tan plate carrier with rifle magazines and red-and-brass shotgun shells, grey cargo trousers, tan knee pads, '
 'tactical gloves and lace-up combat boots. The black pistol remains HOLSTERED at the belt throughout. '
 'Keep ONE rigid wooden club with the same wrapped wire/spikes in the original club hand, fixed grip and length. '
 'No new weapon or gear, no gun drawn, no shooting. Face is completely concealed behind the original mask, '
 'no human mouth or eyes, no speaking or changing the mask. Same costume colors and body scale. ')
ACTIONS={
 'attack':dict(title='방망이 공격 · 왼쪽',seed=2026102311,padding=40,referenceOffsetX=96,loop=False,strength='high',frames=24,
  prompt=(
   'Perform exactly ONE fast powerful CLUB STRIKE toward SCREEN LEFT. Preserve the original LEFT-facing '
   'three-quarter orientation; the gas-mask nose points left throughout. From the supplied low club position, '
   'during the first 0.4 seconds brace both boots, bend the knees and draw the club hand back and UP beside '
   'the rear shoulder. Keep the empty hand clenched near the chest as a counterbalance. Then push off the '
   'rear boot, take ONE short grounded step toward LEFT and rotate the hips and shoulders together. '
   'Drive the same rigid wooden club in ONE swift diagonal DOWNWARD arc toward the empty space at SCREEN LEFT, '
   'reaching impact before 1.2 seconds. The club is a heavy short bat, never a sword or flexible whip. '
   'Stop the club low and forward-left with the leading knee bent, chest lifted and firm spine. '
   'Let the long coat tails whip once then settle. Recover to the low opening ready stance during the '
   'remaining time. One attack only; no second swing, full spin, dance, jumping, waist bow, gunfire, '
   'victim, blood, gore, projectile, explosions, magic trails or big effects. Show the full club arc and both boots.'
  )),
 'idle':dict(title='대기 · 원본 자세',seed=2026102310,padding=10,loop=True,strength='low',frames=16,
  prompt=(
   'A restrained combat-ready IDLE loop in the exact supplied LEFT-facing three-quarter pose. Both boots '
   'remain firmly planted at the original positions; keep the same bent knees and slightly forward posture. '
   'Very small natural breathing raises and lowers the shoulders and upper chest together, with almost '
   'imperceptible weight sway. Preserve the rigid plate carrier and magazine/shell shapes: no local ballooning '
   'or rubber chest deformation. The ragged coat hem and loose straps follow with a subtle delayed sway. '
   'The helmet and respirator stay steady, purple lens reflections move minimally, mask shape never changes. '
   'Keep the wooden club in the SAME lowered diagonal-left pose with almost no hand movement; the empty '
   'gloved hand stays beside the thigh. No stepping, walking, attack, arm raising, head turn, looking at the '
   'viewer, mouth movement or blinking. The motion and pose flow into the matching ending reference.'
  )),
}


def save(path,value):
 path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
 OUT.mkdir(parents=True,exist_ok=True)
 original=OUT/'source-original.png'
 if not original.exists():shutil.copyfile(SOURCE,original)
 assert digest(SOURCE)==digest(original)
 cleaned=OUT/'reference.png'
 if not cleaned.exists():
  image=Image.open(original).convert('RGBA');rgba=np.array(image)
  rgb=rgba[:,:,:3].astype(float);alpha=rgba[:,:,3]
  # Strip only the exterior-connected neutral white sticker stroke. Highlights
  # inside the character are not selected by brightness alone.
  white=(rgb.min(2)>205)&(np.ptp(rgb,axis=2)<30)
  transparent=alpha<16
  allowed=white|transparent
  seeds=transparent.copy();seeds[0]|=allowed[0];seeds[-1]|=allowed[-1]
  seeds[:,0]|=allowed[:,0];seeds[:,-1]|=allowed[:,-1]
  exterior=ndimage.binary_propagation(seeds,mask=allowed)
  removed=exterior&white&(alpha>0)
  alpha[removed]=0;alpha[alpha<16]=0
  # The original sticker also has a detached, antialiased outer hairline.
  labels,count=ndimage.label(alpha>=32,structure=np.ones((3,3)))
  sizes=np.bincount(labels.ravel());sizes[0]=0
  core=labels==int(sizes.argmax())
  support=ndimage.binary_dilation(core,iterations=1)
  detached=(alpha>0)&~support
  alpha[detached]=0
  rgba[:,:,3]=alpha
  rgba[alpha==0,:3]=0
  cut=Image.fromarray(rgba)
  box=cut.getchannel('A').getbbox()
  assert box
  # Pad the cleaned source: its original helmet/boots touch the image borders.
  cut=cut.crop(box)
  canvas=Image.new('RGBA',(cut.width+48,cut.height+48))
  canvas.paste(cut,(24,24));canvas.save(cleaned)
  save(OUT/'source.json',dict(sourcePath=str(SOURCE),sourceSha256=digest(SOURCE),
   sourceSize=list(image.size),referenceSize=list(canvas.size),cropBounds=box,
   removedWhiteOutlinePixels=int(removed.sum()),detachedRimPixels=int(detached.sum()),preparation='exterior-connected white stroke and detached sticker rim removal; original RGB retained elsewhere; 24px transparent border',
   pixelOutput=False,sourceUnchanged=True,published=False))
 for name in ACTIONS:(OUT/name).mkdir(exist_ok=True)
 build()


def generate():
 prepare()
 for name,item in ACTIONS.items():
  folder=OUT/name
  if (folder/'raw.mp4').exists():continue
  pending=folder/'native-v1-pending.json'
  if pending.exists():
   graph=json.loads((folder/'native-v1-workflow.json').read_text(encoding='utf-8'))
  else:
   ensure_idle();engine.start_comfy();release((8190,8191))
   prepared=engine.prepare_reference_image((OUT/'reference.png').read_bytes(),768,768,item['padding'])
   if item.get('referenceOffsetX'):
    import io
    frame=Image.open(io.BytesIO(prepared)).convert('RGB')
    shifted=Image.new('RGB',frame.size,(128,128,128))
    shifted.paste(frame,(item['referenceOffsetX'],0))
    buf=io.BytesIO();shifted.save(buf,format='PNG');prepared=buf.getvalue()
   (folder/'reference-prepared.png').write_bytes(prepared)
   uploaded=engine.upload_image(prepared,'masked-raider-'+name+'.png')
   prompt=(IDENTITY+item['prompt']+' Fixed camera and lighting, no zoom, pan, shake or cut. '
    'Keep the entire helmet, coat, boots and weapon inside the canvas with empty margins. '
    'Uniform flat medium GREY background including all gaps between arms, legs and coat. '
    'No white sticker outline, floor, cast shadow, scenery, text or extra characters.')
   graph=engine.build_workflow(uploaded,prompt,3,768,768,item['seed'],animation_type=name,
    loop=item['loop'],facing='left',flat_background=True,blink_mode='none',motion_strength=item['strength'],
    sampling_mode='quality',workflow_id='standard')
   graph['15']['inputs'].pop('audio',None);graph.pop('14',None);graph.pop('5',None)
   graph['16']['inputs']['filename_prefix']='masked_raider_20261023/'+name
   save(folder/'settings.json',dict(animationType=name,seed=item['seed'],width=768,height=768,duration=3,
    frameCount=item['frames'],loop=item['loop'],facing='left',motionPadding=item['padding'],
    motionStrength=item['strength'],samplingMode='quality',workflowId='standard',prompt=prompt,
    actualPrompt=graph['6']['inputs']['prompt'],pixelOutput=False,removeBackground=True,backgroundRemoval='ai',
    referenceSha256=digest(OUT/'reference.png'),sourceSha256=digest(SOURCE)))
   settings=json.loads((folder/'settings.json').read_text(encoding='utf-8'))
   settings['referenceOffsetX']=item.get('referenceOffsetX',0)
   save(folder/'settings.json',settings)
  executor.OUT=folder
  history=executor.execute(graph,engine.COMFY_URL,'native-v1')
  shutil.copyfile(engine.find_saved_video(history),folder/'raw.mp4')
  print('VIDEO_READY',name,flush=True)
  export(name)
 ensure_idle();release((8189,))


def export(only=None):
 for name,item in ACTIONS.items():
  if only and only!=name:continue
  folder=OUT/name
  if not (folder/'raw.mp4').exists():continue
  if (folder/'frames.json').exists():continue
  with av.open(str(folder/'raw.mp4')) as video:
   frames=[f.to_image().convert('RGBA') for f in video.decode(video=0)]
  all_folder=folder/'all-frames';all_folder.mkdir(exist_ok=True)
  cuts=[];diagnostics=[]
  for i,frame in enumerate(frames):
   path=all_folder/f'frame-{i:03d}.png'
   if path.exists():cut=Image.open(path).convert('RGBA')
   else:cut=image_background.remove_sprite(frame);cut.save(path)
   a=np.asarray(cut.getchannel('A'))
   diagnostics.append(dict(frame=i,edgeContact=bool(a[0].any() or a[-1].any() or a[:,0].any() or a[:,-1].any())))
   cuts.append(cut)
  selection_path=folder/'selection.json'
  selection=json.loads(selection_path.read_text(encoding='utf-8')) if selection_path.exists() else dict(start=0,end=len(cuts)-1)
  start,end=selection['start'],selection['end']
  indices=list(range(start,end+1));shown=[cuts[i] for i in indices]
  boxes=[im.getchannel('A').getbbox() for im in shown]
  assert all(boxes)
  l,t,r,b=min(x[0] for x in boxes),min(x[1] for x in boxes),max(x[2] for x in boxes),max(x[3] for x in boxes)
  side=math.ceil(max(r-l,b-t)*1.10)
  x,y=math.floor((l+r-side)/2),math.floor((t+b-side)/2)
  crop=(x,y,x+side,y+side)
  preview=[im.crop(crop).resize((512,512),Image.Resampling.LANCZOS) for im in shown]
  speed=selection.get('playbackSpeed',1.)
  ticks=[round(i*1000/(24*speed)) for i in range(len(preview)+1)];times=[b-a for a,b in zip(ticks,ticks[1:])]
  preview[0].save(folder/'animation.webp',save_all=True,append_images=preview[1:],duration=times,loop=0,lossless=True)
  gif,gifmeta=sprite_gif.encode(preview,times);(folder/'animation.gif').write_bytes(gif)
  selected=list(map(int,sprite_loop.sample_indices(len(shown),min(item['frames'],len(shown)),item['loop'])))
  cols=4;rows=math.ceil(len(selected)/cols);sheet=Image.new('RGBA',(768*cols,768*rows))
  contact=Image.new('RGB',(320*cols,344*rows),'#263247');draw=ImageDraw.Draw(contact)
  selected_folder=folder/'selected';selected_folder.mkdir(exist_ok=True)
  for n,j in enumerate(selected):
   shown[j].save(selected_folder/f'frame-{n:02d}.png')
   sheet.paste(shown[j],(n%cols*768,n//cols*768))
   small=preview[j].resize((320,320),Image.Resampling.LANCZOS)
   contact.paste(small,(n%cols*320,n//cols*344+24),small)
   draw.text((n%cols*320+8,n//cols*344+5),f'raw {indices[j]}',fill='white')
  sheet.save(folder/'sheet.png');contact.save(folder/'contact.webp',quality=94)
  preview[0].save(folder/'poster.png')
  bounds=[ticks[j] for j in selected]+[ticks[-1]]
  save(folder/'frames.json',dict(frameWidth=768,frameHeight=768,columns=cols,rows=rows,
   sourceFrames=len(frames),sourceIndices=[indices[j] for j in selected],
   durationMs=[b-a for a,b in zip(bounds,bounds[1:])],previewSourceIndices=indices,previewDurationMs=times,
   previewCropBounds=crop,diagnostics=diagnostics,gif=gifmeta,sourceFPS=24,loop=item['loop'],
   selection=selection,playbackSpeed=speed,rawSha256=digest(folder/'raw.mp4')))
  strip_indices=np.linspace(0,len(preview)-1,8).round().astype(int).tolist()
  strip=Image.new('RGB',(1280,640),'#263247');d=ImageDraw.Draw(strip)
  for n,j in enumerate(strip_indices):
   im=preview[j].resize((320,320),Image.Resampling.LANCZOS);strip.paste(im,(n%4*320,n//4*320),im)
   d.text((n%4*320+8,n//4*320+8),str(indices[j]),fill='white')
  strip.save(folder/'review-strip.webp',quality=94)
  print('EXPORTED',name,len(preview),'animation frames',len(selected),'sheet cells',flush=True)
  build()


def game():
 """Register both motions at the same input-derived scale and canvas center."""
 metas={};images={};scales={};translations={}
 target_padding=max(x['padding'] for x in ACTIONS.values())
 settings={name:json.loads((OUT/name/'settings.json').read_text(encoding='utf-8')) for name in ACTIONS}
 target_offset=max(x.get('referenceOffsetX',0) for x in settings.values())
 for name,item in ACTIONS.items():
  folder=OUT/name
  meta=json.loads((folder/'frames.json').read_text(encoding='utf-8'))
  scale=(1-target_padding/100)/(1-item['padding']/100)
  size=round(768*scale)
  dx=target_offset-round(settings[name].get('referenceOffsetX',0)*scale)
  aligned=[]
  for index in meta['previewSourceIndices']:
   source=Image.open(folder/'all-frames'/f'frame-{index:03d}.png').convert('RGBA')
   frame=Image.new('RGBA',(768,768))
   resized=source.resize((size,size),Image.Resampling.LANCZOS)
   frame.paste(resized,((768-size)//2+dx,(768-size)//2))
   assert int(np.asarray(frame.getchannel('A')).sum())==int(np.asarray(resized.getchannel('A')).sum()),'Registration clipped visible pixels'
   aligned.append(frame)
  metas[name]=meta;images[name]=aligned;scales[name]=size/768;translations[name]=dx
 boxes=[im.getchannel('A').getbbox() for frames in images.values() for im in frames]
 l,t,r,b=min(x[0] for x in boxes),min(x[1] for x in boxes),max(x[2] for x in boxes),max(x[3] for x in boxes)
 side=math.ceil(max(r-l,b-t)*1.10)
 x,y=math.floor((l+r-side)/2),math.floor((t+b-side)/2)
 crop=(x,y,x+side,y+side)
 for name,frames in images.items():
  folder=OUT/name;meta=metas[name]
  previews=[im.crop(crop).resize((512,512),Image.Resampling.LANCZOS) for im in frames]
  previews[0].save(folder/'game-animation.webp',save_all=True,append_images=previews[1:],duration=meta['previewDurationMs'],loop=0,lossless=True)
  data,gifinfo=sprite_gif.encode(previews,meta['previewDurationMs'])
  (folder/'game-animation.gif').write_bytes(data)
  sheet=Image.new('RGBA',(768*meta['columns'],768*meta['rows']))
  selected_folder=folder/'game-selected';selected_folder.mkdir(exist_ok=True)
  for n,index in enumerate(meta['sourceIndices']):
   j=meta['previewSourceIndices'].index(index)
   frame=frames[j]
   frame.save(selected_folder/f'frame-{n:02d}.png')
   sheet.paste(frame,(n%4*768,n//4*768))
  sheet.save(folder/'game-sheet.png')
  save(folder/'game-frames.json',dict(frameWidth=768,frameHeight=768,columns=meta['columns'],rows=meta['rows'],
   sourceIndices=meta['sourceIndices'],durationMs=meta['durationMs'],loop=meta['loop'],
   scaleAboutCanvasCenter=scales[name],translationAfterScale=[translations[name],0],registrationAnchor=[384+target_offset,384],
   commonPresentationCrop=crop,gif=gifinfo,previewDurationMs=meta['previewDurationMs'],
   note='Static scale registration from known input padding. No per-frame resizing or root-motion removal.'))
 save(OUT/'game-registration.json',dict(frameWidth=768,frameHeight=768,anchor=[384+target_offset,384],
  scales=scales,presentationCrop=crop,sourceUnchanged=True))
 build()
 print('GAME_CANVASES_ALIGNED',scales,flush=True)


def build():
 cards=[]
 for name in ('idle','attack'):
  item=ACTIONS[name]
  folder=OUT/name
  if not (folder/'animation.webp').exists():continue
  review=json.loads((folder/'review.json').read_text(encoding='utf-8')) if (folder/'review.json').exists() else {}
  prefix='game-' if (folder/'game-animation.webp').exists() else ''
  cards.append(f'<article><h2>{item["title"]}</h2><p>{html.escape(review.get("note","생성 후 프레임 검토 전입니다."))}</p>'
   f'<img class="motion" src="{name}/{prefix}animation.webp" alt="{item["title"]}"><p><a href="{name}/{prefix}animation.gif" download>GIF</a> · '
   f'<a href="{name}/{prefix}sheet.png" download>투명 PNG 시트</a> · <a href="{name}/{prefix}frames.json">프레임 시간</a> · '
   f'<a href="{name}/contact.webp">프레임 비교</a> · <a href="{name}/raw.mp4">생성 원본 영상</a> · '
   f'<a href="{name}/settings.json">프롬프트·설정</a></p></article>')
 page=('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
  '<title>방독면 적 캐릭터 · 대기 / 방망이 공격</title><style>body{margin:24px;background:#171e2b;color:#eef0f6;font:15px/1.6 system-ui}'
  'main{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px}article{background:#263247;border-radius:16px;padding:20px}'
  'img{max-width:100%;background:repeating-conic-gradient(#263247 0 25%,#43516a 0 50%) 0/24px 24px}.motion{width:512px}'
  '.source{height:380px;width:auto}a{color:#c9c0ff}button{padding:8px 16px}body.light img{background:#eee}</style>'
  '<h1>방독면 적 캐릭터 · 대기와 방망이 공격</h1><p>첨부한 원화를 실제 이미지 입력으로 사용했습니다. 원본의 왼쪽 방향과 '
  '방독면·헬멧·복장·장비를 유지하도록 요청했으며 권총은 홀스터에 둡니다. 입력용 사본의 바깥쪽 흰 테두리만 정리했습니다.</p>'
  '<p>MiniMax 768×768·24FPS·20단계 영상 생성 → AI 배경 제거 → PNG 시트·GIF. 원본 픽셀을 그대로 움직인 리깅 애니메이션은 아니며 '
  '손·무기·탄창 같은 세부 형태는 프레임마다 달라질 수 있습니다. 게임용 시트는 대기·공격의 캐릭터 크기를 맞춘 768px 고정 캔버스이며, 미리보기는 두 동작에 같은 확대 영역을 씁니다. 생성 원본도 별도로 보관합니다.</p>'
  '<button onclick="document.body.classList.toggle(\'light\')">밝은 / 어두운 배경</button> '
  '<a href="source-original.png">입력 원본</a> · <a href="reference.png">테두리 정리 사본</a> '
  +('<a href="masked-raider-handoff.zip" download>전체 ZIP</a>' if (OUT/'masked-raider-handoff.zip').exists() else '')+
  '<br><img class="source" src="reference.png" alt="입력 원화 사본"><main>'+''.join(cards)+'</main></html>')
 (OUT/'preview.html').write_text(page,encoding='utf-8')


def check():
 assert digest(SOURCE)==digest(OUT/'source-original.png')
 result={}
 for name,item in ACTIONS.items():
  folder=OUT/name;meta=json.loads((folder/'frames.json').read_text(encoding='utf-8'))
  active=set(meta['previewSourceIndices'])
  assert not any(x['edgeContact'] for x in meta['diagnostics'] if x['frame'] in active),'An exported motion touches the frame edge'
  history=json.loads((folder/'native-v1-history.json').read_text(encoding='utf-8'))
  assert history['status']['status_str']=='success'
  with av.open(str(folder/'raw.mp4')) as clip:
   stream=clip.streams.video[0]
   assert (stream.width,stream.height)==(768,768) and float(stream.average_rate)==24
   assert sum(1 for _ in clip.decode(video=0))==73
  sheet=Image.open(folder/'sheet.png').convert('RGBA')
  for n,index in enumerate(meta['sourceIndices']):
   original=Image.open(folder/'all-frames'/f'frame-{index:03d}.png').convert('RGBA')
   cell=sheet.crop((n%4*768,n//4*768,(n%4+1)*768,(n//4+1)*768))
   assert np.array_equal(np.asarray(original),np.asarray(cell))
   assert original.getchannel('A').getextrema()==(0,255)
  with Image.open(folder/'animation.gif') as gif:
   assert gif.n_frames==len(meta['previewSourceIndices']) and gif.size==(512,512)
   duration=0
   for i in range(gif.n_frames):gif.seek(i);duration+=gif.info['duration']
   assert abs(duration-sum(meta['previewDurationMs']))<=10
  result[name]=dict(sourceFrames=73,sheetFrames=len(meta['sourceIndices']),previewFrames=len(meta['previewSourceIndices']),
   durationMs=sum(meta['previewDurationMs']),edgeContactFrames=sum(x['edgeContact'] for x in meta['diagnostics']),
   rawSha256=digest(folder/'raw.mp4'))
  registered=json.loads((folder/'game-frames.json').read_text(encoding='utf-8'))
  game_sheet=Image.open(folder/'game-sheet.png').convert('RGBA')
  size=round(768*registered['scaleAboutCanvasCenter'])
  for n,index in enumerate(meta['sourceIndices']):
   source=Image.open(folder/'all-frames'/f'frame-{index:03d}.png').convert('RGBA')
   expected=Image.new('RGBA',(768,768))
   dx=registered.get('translationAfterScale',[0,0])[0]
   expected.paste(source.resize((size,size),Image.Resampling.LANCZOS),((768-size)//2+dx,(768-size)//2))
   cell=game_sheet.crop((n%4*768,n//4*768,(n%4+1)*768,(n//4+1)*768))
   assert np.array_equal(np.asarray(expected),np.asarray(cell))
  with Image.open(folder/'game-animation.gif') as gif:
   assert gif.n_frames==len(meta['previewSourceIndices']) and gif.size==(512,512)
 save(OUT/'validation.json',dict(passed=True,sourceUnchanged=True,websiteUnchanged=True,cases=result))
 text=['방독면 적 캐릭터 · 대기 / 방망이 공격','',
  '게임용 파일: 각 동작 폴더의 game-sheet.png, game-frames.json, game-selected/*.png',
  '두 동작 모두 시트 한 칸은 768×768px이며 캐릭터 비율과 등록 기준을 맞췄습니다.',
  '미리보기: game-animation.gif / game-animation.webp (512px, 두 동작 공통 확대 영역)',
  'frames.json / game-frames.json의 durationMs를 각 시트 칸의 재생 시간으로 사용하세요.',
  'raw.mp4는 생성 원본 73프레임을 보존합니다. 원본 입력 이미지도 수정하지 않았습니다.','']
 for name in ('idle','attack'):
  info=result[name]
  text.append(f'{name}: 시트 {info["sheetFrames"]}장, 미리보기 {info["previewFrames"]}프레임, {info["durationMs"]}ms')
 text+=['','세부 장비·손·방망이 철조망에는 AI 생성에 따른 변화가 남습니다.',
  '공격이 전진 자세에서 끝나는 경우 원래 위치로 돌아오는 회복 동작은 포함되지 않습니다.',
  '입력 원화의 바깥 흰 스티커 테두리는 생성용 사본에서만 정리했습니다.']
 (OUT/'README.txt').write_text('\n'.join(text)+'\n',encoding='utf-8')
 with zipfile.ZipFile(OUT/'masked-raider-handoff.zip','w',zipfile.ZIP_DEFLATED) as z:
  for name in ACTIONS:
   for file in ('animation.gif','animation.webp','sheet.png','frames.json','raw.mp4','reference-prepared.png','settings.json','native-v1-workflow.json'):
    z.write(OUT/name/file,name+'/'+file)
   for file in ('game-animation.gif','game-animation.webp','game-sheet.png','game-frames.json'):
    z.write(OUT/name/file,name+'/'+file)
   for file in (OUT/name/'game-selected').glob('*.png'):
    z.write(file,name+'/game-selected/'+file.name)
  for file in ('source-original.png','reference.png','source.json','validation.json','game-registration.json','README.txt'):z.write(OUT/file,file)
 with zipfile.ZipFile(OUT/'masked-raider-handoff.zip') as z:assert z.testzip() is None
 build()
 print('VALIDATED',result,flush=True)


if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8')
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','generate','export','game','build','check','all'])
 a=p.parse_args()
 if a.stage=='all':generate();export();game();check()
 else:globals()[a.stage]()
