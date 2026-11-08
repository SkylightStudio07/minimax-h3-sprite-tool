"""Two private female pixel combat tests: local Qwen references -> MiniMax -> pixel export."""
import argparse,hashlib,json,shutil,sys,time,zipfile
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
OUT=ROOT/'outputs/pixel-female-combat-20261019'
CASES={
 'swordswoman':dict(label='여검사 · 한 번 베기',seed=2026101911,
  appearance='an adult woman with long auburn hair in a high ponytail, a cream short military jacket with dark teal trim, a dark teal split knee-length battle skirt over fitted dark trousers, brown leather gloves and knee-high brown boots, modest practical clothing',
  pose='a compact RIGHT-FACING side-profile combat ready stance. Both boots planted apart, knees soft. She holds ONE straight silver sword in her near hand in front of her waist, blade pointing diagonally up and right. Her other arm balances behind her. The sword must fit completely in the canvas',
  action='Perform exactly ONE decisive sword slash toward SCREEN RIGHT. At 0.0-0.5 seconds she braces her feet and draws the sword above and behind her right shoulder; at 0.5-1.2 seconds she rotates shoulders and hips and delivers a fast powerful diagonal downward cut from above her head toward screen right, extending the sword arm; at 1.2-1.8 seconds she follows through with a low sword and bent front knee; at 1.8-3.0 seconds she recovers to her opening ready stance. Both arms, torso and ponytail visibly participate. Both feet remain near their original positions, a small forward weight shift only. ONE rigid straight sword of constant length remains connected to her hand. No spinning, no second slash, no jumping, no sword appearing in the empty hand. No magical trails or large effects.'),
 'musketeer':dict(label='여총사 · 머스킷 한 발',seed=2026101912,
  appearance='an adult woman with silver white hair in a short low ponytail, a small dark burgundy tricorne hat, a dark burgundy long military coat with gold buttons and cream cuffs, a brown leather belt, fitted charcoal trousers and black knee-high boots, modest practical clothing',
  pose='a strict RIGHT-FACING side-profile firing stance. Feet planted apart. She shoulders ONE long historical flintlock musket horizontally aimed to screen RIGHT, wooden stock snug to shoulder, near hand at the trigger and far hand supporting the fore-end. A long narrow straight steel barrel, small flintlock hammer, NO scope and NO bayonet. The entire gun muzzle and both feet fit inside the canvas',
  action='Perform exactly ONE flintlock musket shot toward SCREEN RIGHT, NOT automatic fire. At 0.0-0.6 seconds she holds the long musket firmly at her shoulder and aims horizontally right. At 0.6-0.9 seconds she pulls the trigger, a VERY BRIEF small orange white muzzle flash appears at the rightmost barrel tip, a compact pale smoke puff escapes, and the WHOLE rigid musket recoils backward into her shoulder. At 0.9-1.6 seconds her elbows and upper torso absorb the recoil and her coat tails lag slightly; at 1.6-3.0 seconds she settles and re-aims in her opening firing stance, smoke disappears. Both hands stay attached to their original grip points, the wooden stock and straight steel barrel retain their shape and length. Feet planted, modest backward shoulder kick, NO walking. No second shot, no reload, no thrown gun, no gun rotation toward viewer, no extra weapon.')}

def save(folder,name,data):
 (folder/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def release(ports):
 import requests
 for port in ports:
  try:requests.post(f'http://127.0.0.1:{port}/free',json=dict(unload_models=True,free_memory=True),timeout=30).raise_for_status()
  except requests.ConnectionError:pass  # Offline engines hold no GPU models.

def references():
 from tools import verify_pixel_minimax as exp
 from tools.verify_rpg_sprite_styles import ensure_idle
 import rigging_engine as rig
 import idle_tool,image_pixel
 rig.start_comfy()
 OUT.mkdir(parents=True,exist_ok=True)
 source=Image.open(ROOT/'outputs/pixel-minimax-right-20261019/reference-right.png').convert('RGBA').resize((768,768),Image.Resampling.NEAREST)
 matte=Image.new('RGB',source.size,'white');matte.paste(source,mask=source.getchannel('A'))
 path=rig.INPUT_ROOT/'pixel_female_combat_style.png';matte.save(path)
 for name,c in CASES.items():
  folder=OUT/name;folder.mkdir(exist_ok=True);exp.OUT=folder
  if (folder/'reference.png').exists():continue
  ensure_idle();release((8189,8191))
  graph=rig.qwen21_workflow(path.name,'pixel_female_combat/'+name,768,20,c['seed'])
  graph['6']['inputs'].update(device='cpu',dtype='default')
  graph['5']['inputs']['prompt']=(
   'Use image 1 ONLY as a reference for its small square-pixel game-sprite style and proportions. Create a NEW DIFFERENT female character, not the blue-haired character. '
   'ONE full-body sprite of '+c['appearance']+'. '+c['pose']+'. '
   'Head and nose point RIGHT with one visible eye, no eye contact. Clear readable silhouette, adult female build without exaggerated anatomy. '
   'Match the reference chunky square pixel clusters, limited flat colors and compact 4.5-head-high game proportions, not realistic illustration. '
   'Place her boots at about 85 percent of image height, head around 20 percent, body around the center-left. Reserve generous space above and to the right for weapon motion. '
   'No cropping, no other characters, no character sheet, no floor, no cast shadow. Pure uniform WHITE background, no text.')
  graph['5']['inputs']['negative_prompt']='front view, facing left, blue hair, multiple characters, character sheet, extra limbs, giant breasts, bikini, high heels, photorealistic, smooth shading, cropped weapon, text, watermark, shadow'
  start=time.monotonic();hist=exp.execute(graph,rig.COMFY_URL,'reference')
  raw=Image.open(rig._saved_image(hist,'9')).convert('RGBA');raw.save(folder/'reference-raw.png')
  from tools.sprite_matte import clean_flat_matte
  cut,matte_meta=clean_flat_matte(raw,tolerance=24,radius=5)
  ref=image_pixel.finish(cut,128,32);ref.save(folder/'reference.png')
  ref.resize((512,512),Image.Resampling.NEAREST).save(folder/'reference-large.png')
  a=np.array(ref);palette=np.unique(a[:,:,:3][a[:,:,3]>0],axis=0).tolist()
  # Reserve stable effect colours absent from an unlit firearm reference.
  for col in [[255,238,177],[255,173,62],[224,220,211],[174,171,165]]:
   if col not in palette:palette.append(col)
  save(folder,'reference-settings.json',dict(**c,palette=palette,matte=matte_meta,seconds=round(time.monotonic()-start,2),workflow=graph))
  print('REFERENCE READY',name,flush=True)
 release((8190,))

def videos():
 import idle_tool as engine
 from tools import verify_pixel_minimax as exp
 from tools.verify_rpg_sprite_styles import ensure_idle
 engine.start_comfy()
 for name,c in CASES.items():
  folder=OUT/name;exp.OUT=folder
  if (folder/'action-raw.mp4').exists():continue
  ensure_idle();release((8190,8191))
  ref=Image.open(folder/'reference.png').convert('RGBA').resize((512,512),Image.Resampling.NEAREST)
  matte=Image.new('RGB',ref.size,(128,128,128));matte.paste(ref,mask=ref.getchannel('A'));matte.save(folder/'video-input.png')
  digest=hashlib.sha256((folder/'video-input.png').read_bytes()).hexdigest();record=folder/'upload.json'
  if record.exists():
   old=json.loads(record.read_text());assert old['sha256']==digest;uploaded=old['name']
  else:
   uploaded=engine.upload_image((folder/'video-input.png').read_bytes(),f'pixel-female-{name}.png');save(folder,'upload.json',dict(name=uploaded,sha256=digest))
  prompt=(c['action']+' Preserve the exact same woman, face, hairstyle, costume, body proportions, colours and weapon throughout. '
   'Clear side-scrolling game attack animation, full body, facing SCREEN RIGHT throughout. Strong readable preparation, execution, follow-through and recovery. '
   'Fixed orthographic camera, fixed framing and scale; no zoom, pan or cuts. The entire head, boots and weapon remain within the frame. '
   'Keep the flat pixel-art style and clusters; do not add realistic textures. Uniform featureless medium grey background as supplied, also between limbs. No scenery or floor shadow.')
  graph=engine.build_workflow(uploaded,prompt,3,512,512,c['seed']+20,animation_type='custom',loop=True,facing='right',flat_background=True,motion_strength='normal',sampling_mode='quality',workflow_id='standard')
  graph['16']['inputs']['filename_prefix']='pixel_female_combat/'+name
  graph['15']['inputs'].pop('audio',None);graph.pop('14');graph.pop('5')
  save(folder,'video-settings.json',dict(seed=c['seed']+20,steps=20,width=512,height=512,frames=73,fps=24,prompt=graph['6']['inputs']['prompt'],loopReference=True))
  start=time.monotonic();hist=exp.execute(graph,engine.COMFY_URL,'video')
  shutil.copyfile(engine.find_saved_video(hist),folder/'action-raw.mp4')
  save(folder,'video-timing.json',dict(seconds=round(time.monotonic()-start,2)))
  print('VIDEO READY',name,flush=True)
 release((8189,))

def export():
 import av,cv2
 from tools.postprocess_pixel_video import cutout,robust_grid,temporal_cleanup
 for name,c in CASES.items():
  folder=OUT/name
  if not (folder/'action-raw.mp4').exists():continue
  settings=json.loads((folder/'reference-settings.json').read_text(encoding='utf-8'));palette=np.array(settings['palette'],np.float32)
  with av.open(str(folder/'action-raw.mp4')) as video:raw=[np.array(f.to_image().convert('RGB')) for f in video.decode(video=0)]
  rgbs=[];covers=[];grays=[]
  for a in raw:
   rgb,coverage=robust_grid(a,cutout(a));rgbs.append(rgb);covers.append(coverage)
   grays.append(cv2.cvtColor(cv2.resize(a,(128,128),interpolation=cv2.INTER_AREA),cv2.COLOR_RGB2GRAY))
  frames,diagnostics=temporal_cleanup(rgbs,covers,grays,palette)
  allfolder=folder/'all-frames';allfolder.mkdir(exist_ok=True)
  allowed={tuple(map(int,col)) for col in palette}
  for i,a in enumerate(frames):
   assert set(np.unique(a[:,:,3]))<={0,255}
   assert {tuple(col) for col in np.unique(a[:,:,:3][a[:,:,3]>0],axis=0)}<=allowed
   Image.fromarray(a).save(allfolder/f'frame-{i:03d}.png')
  # Keep forward time and export all raw frames as well; adjust selection after visual review.
  review=folder/'selection.json'
  selection=json.loads(review.read_text(encoding='utf-8')) if review.exists() else {}
  selected=selection.get('indices',np.linspace(0,len(frames)-1,12).round().astype(int).tolist())
  assert selected==sorted(set(selected)) and 0<=selected[0]<selected[-1]<len(frames)
  durations=selection.get('durationMs',[round((b-a)/24*1000) for a,b in zip(selected,selected[1:])]+[250])
  assert len(durations)==len(selected) and all(isinstance(t,int) and 20<=t<=2000 for t in durations)
  write_selected(folder,frames,selected,durations,selection)
  contact=Image.new('RGB',(8*192,10*212),'#ddd');draw=ImageDraw.Draw(contact)
  for i,a in enumerate(frames):
   im=Image.fromarray(a).resize((192,192),Image.Resampling.NEAREST);x=(i%8)*192;y=(i//8)*212
   contact.paste(im,(x,y+20),im);draw.text((x+5,y+3),str(i),fill='black')
  contact.save(folder/'all-contact.png')
  large=[Image.fromarray(a).resize((512,512),Image.Resampling.NEAREST) for a in frames]
  large[0].save(folder/'full-animation.webp',save_all=True,append_images=large[1:],duration=42,loop=0,lossless=True)
  save(folder,'postprocess.json',dict(frames=len(frames),method='9-sample spatial medoid + shared character palette + motion-gated temporal cleanup',headLocked=False,diagnostics=diagnostics))
 if all((OUT/name/'postprocess.json').exists() for name in CASES):package()
 else:print('AVAILABLE CLIPS EXPORTED; remaining generation pending',flush=True)

def write_selected(folder,frames,indices,duration,review):
 selected=[Image.fromarray(frames[i]) for i in indices];sheet=Image.new('RGBA',(128*len(indices),128));grid=Image.new('RGBA',(128*4,128*((len(indices)+3)//4)))
 for i,im in enumerate(selected):im.save(folder/f'frame-{i:02d}.png');sheet.paste(im,(128*i,0));grid.paste(im,(128*(i%4),128*(i//4)))
 sheet.save(folder/'sheet.png');grid.save(folder/'sheet-grid.png')
 selected[0].save(folder/'animation.png',save_all=True,append_images=selected[1:],duration=duration,loop=0,disposal=0,blend=0)
 large=[f.resize((512,512),Image.Resampling.NEAREST) for f in selected]
 large[0].save(folder/'animation.webp',save_all=True,append_images=large[1:],duration=duration,loop=0,lossless=True)
 save(folder,'frames.json',dict(frameWidth=128,frameHeight=128,columns=4,rows=(len(indices)+3)//4,sourceFPS=24,sourceIndices=indices,sourceTimeMs=[round(i/24*1000) for i in indices],durationMs=duration,playback='one-shot; preview repeats with no guaranteed seamless boundary',timing='Reviewed sprite playback timing; source video timing remains in sourceTimeMs and full-animation.webp.',review=review,phases='Manual visual phase labels, not automatic hit-event detection'))

def package():
 cards=[]
 for name,c in CASES.items():
  reference=('reference-static-clean-large.png' if (OUT/name/'reference-static-clean-large.png').exists() else 'reference-clean-large.png' if (OUT/name/'reference-clean-large.png').exists() else 'reference-large.png')
  note=('준비 → 머리 위로 올리기 → 내려베기 → 복귀. 칼날의 끊김과 생성된 흰 잔상이 남습니다.' if name=='swordswoman' else '조준 → 한 발 발사 → 반동·연기 → 재조준. 발광 프레임을 직접 골랐고 화면 끝에서 효과가 잘린 프레임은 선택 시트에서 제외했습니다. 전체 영상에는 해당 프레임이 남습니다.')
  cleaned=reference!='reference-large.png'
  cleaned_png='reference-static-clean.png' if reference.startswith('reference-static') else 'reference-clean.png'
  comparison='../pixel-static-source-20261019/preview.html' if reference.startswith('reference-static') else 'source-cleanup-comparison.png'
  cleanup=('<p><a href="'+name+'/'+cleaned_png+'">테두리 보정 정지 PNG</a> · <a href="'+name+'/reference.png">기존 영상 입력 PNG</a> · <a href="'+comparison+'">정지 이미지 전후 비교</a></p>' if cleaned else '')
  caption='최초 정지 원본 · 추가 윤곽 보정' if reference.startswith('reference-static') else '정지 기준 · 흰 테두리 보정' if cleaned else '새 기준 캐릭터'
  cards.append(f'<article><h2>{c["label"]}</h2><div class="pair"><figure><img src="{name}/{reference}"><figcaption>{caption}</figcaption></figure><figure><img src="{name}/animation.webp"><figcaption>선택 12프레임 · 128px</figcaption></figure></div><p>{note}</p>{cleanup}<p><a href="{name}/sheet-grid.png">4×3 PNG 시트</a> · <a href="{name}/sheet.png">가로 시트</a> · <a href="{name}/frames.json">프레임 정보·표시 시간</a> · <a href="{name}/action-raw.mp4">생성 원본 영상</a></p><details><summary>선택 12프레임 시트</summary><img class="wide" src="{name}/sheet-grid.png"></details><details><summary>전체 73프레임 / 동작 검수</summary><img class="wide" src="{name}/all-contact.png"><img src="{name}/full-animation.webp"></details></article>')
 page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>여성 캐릭터 · 베기 / 머스킷 사격</title><style>body{background:#171b25;color:#eee;font:15px/1.6 system-ui;margin:24px}main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}article{padding:18px;background:#252b38;border-radius:12px;min-width:0}.pair{display:flex}figure{margin:4px;width:50%}img{max-width:100%;image-rendering:pixelated;background:repeating-conic-gradient(#ddd 0 25%,#f5f5f5 0 50%) 0/20px 20px}a{color:#c1bdff}.wide{width:100%}@media(max-width:900px){main{grid-template-columns:1fr}}</style><h1>여성 캐릭터 · 검 베기 / 머스킷 사격</h1><p>로컬 Qwen 기준 이미지 → MiniMax H3 영상 → 128px·공통 팔레트·시간축 보정. 영상 후처리 도트 실험이며 완성된 수작업 도트 애니메이션은 아닙니다. 원샷 동작을 미리보기에서 반복합니다.</p><p><a href="female-combat-sprites.zip" download>두 캐릭터 PNG 시트·전체 프레임·영상·설정 ZIP</a></p><main>'''+''.join(cards)+'</main></html>'
 (OUT/'preview.html').write_text(page,encoding='utf-8')
 with zipfile.ZipFile(OUT/'female-combat-sprites.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in OUT.rglob('*'):
   if p.is_file() and p.suffix in ('.png','.webp','.json','.mp4','.html'):z.write(p,p.relative_to(OUT))
 print('PREVIEW',OUT/'preview.html',flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['references','videos','export']);args=parser.parse_args();globals()[args.stage]()
