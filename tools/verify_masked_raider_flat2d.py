"""Private style-retention comparison after the video output became too volumetric."""
import argparse
import html
import json
import shutil
import sys
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import av
import numpy as np
from PIL import Image,ImageDraw
import idle_tool as engine
import sprite_gif
from tools import verify_masked_raider_motion as exporter
from tools import verify_pixel_minimax as executor
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release

OUT=ROOT/'outputs/masked-raider-flat2d-20261023'
PREVIOUS=ROOT/'outputs/masked-raider-motion-20261023'
SEED=2026102310
STYLE=(
 'Animate the supplied TWO-DIMENSIONAL HAND-DRAWN GAME SPRITE as a flat ink-and-cel illustration. '
 'Every frame keeps the same dark ink outline, angular drawn details, flat painted color regions and '
 'hard-edged cel-shadow shapes as the source artwork. The helmet, face mask, clothes, pouches, weapon '
 'and ammunition remain DRAWN SHAPES with the original line thickness and painted details. '
 'Keep every existing light patch and dark shadow attached to the drawing, with constant colors. '
 'Use the input illustration as the appearance source. Do not reinterpret its gear into new physical '
 'materials or volumetric surfaces. Original left-facing three-quarter view, completely masked face, '
 'same single club in the lowered pose, pistol stays holstered. '
 'A very small 2D idle: shift the drawn head, shoulders and upper torso together by only a few pixels, '
 'with a tiny delayed movement of the coat hem. Both feet stay on their original pixels. '
 'The chest keeps the original silhouette and the vest details move together as one painted surface. '
 'The helmet, lens highlights, respirator outline, hands and club stay stable. '
 'No perspective rotation or foreshortening, no change in the drawn shadow shapes, no moving light, '
 'no new smooth tonal gradients or glossy reflections, no change in art style. '
 'Fixed camera, framing and magnification. A perfectly flat uniform grey matte including all limb gaps. '
 'Keep the whole drawing inside the image; no floor, cast shadow, scenery, text, speaking or blinking.'
)
NEGATIVE=(
 '3D render, CGI, photorealistic object, physically based rendering, plastic figurine, realistic metal '
 'materials, glossy plastic, smooth volumetric shading, ambient occlusion, moving specular reflections, '
 'changing illumination, cinematic lighting, rounded sculpted surfaces, perspective rotation, camera '
 'orbit, changing ink outlines, disappearing lineart, new costume details, scenery, textured background'
)
CASES={
 'flat':dict(title='선·셀 채색 우선',negative=False,cfg=1.),
 'flat-cfg':dict(title='선·셀 채색 + 입체 표현 억제',negative=True,cfg=1.3),
}
ATTACK_STYLE=(STYLE.split('A very small 2D idle:')[0].replace('same single club in the lowered pose',
 'same single drawn club in the same drawn gloved hand')+
 'A HAND-DRAWN 2D ATTACK POSE SEQUENCE toward SCREEN LEFT. Keep the original left-facing three-quarter '
 'head and torso view throughout. Anticipation drawing: bend the knees briefly and draw the club arm '
 'back and up beside the shoulder toward screen right, empty hand counterbalances near the chest. '
 'Impact drawing: immediately drive the club DOWN and LEFT in one sharp image-plane arc, while the '
 'whole drawn torso leans slightly left and the front knee bends to receive the weight. '
 'The shoulder and belt lines countertilt as flat drawn shapes; keep the same visible front planes '
 'of the helmet, respirator and vest. One strong clear cut near the middle, then a low balanced '
 'follow-through and short held finish. The coat tails whip as flat illustrated folds. '
 'Keep a single rigid wooden club attached to the same hand. Keep the gun holstered. '
 'No volumetric body turn, perspective orbit, new views of the face, repeated attack, material changes, '
 '3D lighting, smooth relighting, gloss, motion blur or new costume details. '
 'Inked outlines and the original cel-shadow color patches remain visible throughout the moving poses. '
 'Fixed camera, no zoom or pan. Whole body, coat and club stay inside the canvas. '
 'Flat uniform grey background, no floor, shadow, scenery, text, victim or effects.')


def attack():
 prepare()
 folder=OUT/'attack-flat';folder.mkdir(exist_ok=True)
 if not (folder/'raw.mp4').exists():
  if (folder/'attack-v1-pending.json').exists():
   graph=json.loads((folder/'attack-v1-workflow.json').read_text(encoding='utf-8'))
  else:
   ensure_idle();engine.start_comfy();release((8190,8191))
   prepared=(PREVIOUS/'attack/reference-prepared.png').read_bytes()
   (folder/'reference-prepared.png').write_bytes(prepared)
   uploaded=engine.upload_image(prepared,'masked-flat2d-attack.png')
   graph=engine.build_workflow(uploaded,ATTACK_STYLE,2.,768,768,2026102311,
    animation_type='attack',loop=False,facing='preserve',flat_background=True,blink_mode='none',
    motion_strength='normal',sampling_mode='quality',negative_enabled=True,negative_prompt=NEGATIVE,
    cfg_scale=1.3,workflow_id='standard')
   graph['15']['inputs'].pop('audio',None);graph.pop('14',None);graph.pop('5',None)
   graph['16']['inputs']['filename_prefix']='masked_flat2d_20261023/attack'
   save(folder/'settings.json',dict(seed=2026102311,width=768,height=768,length=56,steps=20,
    cfg=1.3,positivePrompt=graph['6']['inputs']['prompt'],negativePrompt=NEGATIVE,
    styleExperiment=True,postStyleRepaint=False,published=False))
  executor.OUT=folder
  history=executor.execute(graph,engine.COMFY_URL,'attack-v1')
  shutil.copyfile(engine.find_saved_video(history),folder/'raw.mp4')
  ensure_idle();release((8189,))
  print('FLAT_ATTACK_VIDEO_READY',flush=True)
 exporter.OUT=OUT
 exporter.ACTIONS={'attack-flat':dict(title='선·셀 채색 우선 · 방망이 공격',frames=24,loop=False,padding=40)}
 exporter.build=lambda:None
 exporter.export('attack-flat')
 # Match the earlier attack's presentation crop for the style comparison.
 meta=json.loads((folder/'frames.json').read_text(encoding='utf-8'))
 crop=json.loads((PREVIOUS/'attack/game-frames.json').read_text(encoding='utf-8'))['commonPresentationCrop']
 frames=[Image.open(folder/'all-frames'/f'frame-{i:03d}.png').convert('RGBA').crop(crop).resize((512,512),Image.Resampling.LANCZOS)
  for i in meta['previewSourceIndices']]
 frames[0].save(folder/'compare.webp',save_all=True,append_images=frames[1:],duration=meta['previewDurationMs'],loop=0,lossless=True)
 data,gif=sprite_gif.encode(frames,meta['previewDurationMs']);(folder/'compare.gif').write_bytes(data)
 build()


def save(path,value):
 path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def prepare():
 OUT.mkdir(parents=True,exist_ok=True)
 for name in ('source-original.png','reference.png','source.json'):
  if not (OUT/name).exists():shutil.copyfile(PREVIOUS/name,OUT/name)
 for name in CASES:(OUT/name).mkdir(exist_ok=True)


def export(name):
 exporter.OUT=OUT
 exporter.ACTIONS={n:dict(title=c['title'],frames=16,loop=True,padding=10) for n,c in CASES.items()}
 exporter.build=lambda:None
 folder=OUT/name
 save(folder/'selection.json',dict(start=0,end=engine.frame_length(1.5)-2,note='Remove final repeated reference frame for the loop.'))
 exporter.export(name)


def generate():
 prepare()
 for name,case in CASES.items():
  folder=OUT/name
  if (folder/'raw.mp4').exists():
   export(name)
   continue
  pending=folder/'short-v1-pending.json'
  if pending.exists():
   graph=json.loads((folder/'short-v1-workflow.json').read_text(encoding='utf-8'))
  else:
   ensure_idle();engine.start_comfy();release((8190,8191))
   # Identical actual reference pixels, seed, geometry and length in both new cases.
   prepared=(PREVIOUS/'idle/reference-prepared.png').read_bytes()
   (folder/'reference-prepared.png').write_bytes(prepared)
   uploaded=engine.upload_image(prepared,'masked-flat2d-'+name+'.png')
   graph=engine.build_workflow(uploaded,STYLE,1.5,768,768,SEED,animation_type='idle',loop=True,
    facing='preserve',flat_background=True,blink_mode='none',motion_strength='low',sampling_mode='quality',
    negative_enabled=case['negative'],negative_prompt=NEGATIVE,cfg_scale=case['cfg'],workflow_id='standard')
   graph['15']['inputs'].pop('audio',None);graph.pop('14',None);graph.pop('5',None)
   graph['16']['inputs']['filename_prefix']='masked_flat2d_20261023/'+name
   save(folder/'settings.json',dict(case=case,seed=SEED,width=768,height=768,length=engine.frame_length(1.5),
    nominalSeconds=1.5,actualSeconds=engine.frame_length(1.5)/24,steps=20,referenceInput='same earlier prepared idle pixels',
    positivePrompt=graph['6']['inputs']['prompt'],negativePrompt=NEGATIVE if case['negative'] else '',
    cfg=case['cfg'],postStyleRepaint=False,pixelOutput=False,published=False))
  executor.OUT=folder
  history=executor.execute(graph,engine.COMFY_URL,'short-v1')
  shutil.copyfile(engine.find_saved_video(history),folder/'raw.mp4')
  print('STYLE_VIDEO_READY',name,flush=True)
  export(name)
  build()
 ensure_idle();release((8189,))


def build():
 prepare()
 sources={'baseline':PREVIOUS/'idle',**{n:OUT/n for n in CASES}}
 loaded={}
 for name,folder in sources.items():
  path=folder/'frames.json'
  if not path.exists():continue
  meta=json.loads(path.read_text(encoding='utf-8'))
  frames=[Image.open(folder/'all-frames'/f'frame-{i:03d}.png').convert('RGBA') for i in meta['previewSourceIndices']]
  loaded[name]=(meta,frames)
 boxes=[f.getchannel('A').getbbox() for _,frames in loaded.values() for f in frames]
 original_control=OUT/'source-pixel-idle/reference.png'
 if original_control.exists():boxes.append(Image.open(original_control).convert('RGBA').getchannel('A').getbbox())
 if not boxes:return
 l,t,r,b=min(x[0] for x in boxes),min(x[1] for x in boxes),max(x[2] for x in boxes),max(x[3] for x in boxes)
 side=int(np.ceil(max(r-l,b-t)*1.10))
 x,y=int(np.floor((l+r-side)/2)),int(np.floor((t+b-side)/2))
 crop=(x,y,x+side,y+side)
 save(OUT/'comparison-crop.json',dict(bounds=crop))
 cards=[]
 if (OUT/'source-pixel-idle/animation.webp').exists():
  cards.append('<article><h2>원화 픽셀 보존 · 2D 대기</h2><p>AI 재생성 없이 원화에 작은 2D 변형을 적용했습니다. '
   '첨부 원본의 윤곽 테두리까지 유지하고 어깨와 코트 끝만 조금 움직입니다. 발은 원본 픽셀 그대로 고정됩니다. 명암을 새로 계산하거나 새 자세를 그리는 방식은 아닙니다.</p>'
   '<img src="source-pixel-idle/animation.webp" alt="원화 픽셀 보존 대기"><p><a href="source-pixel-idle/animation.gif">GIF</a> · '
   '<a href="source-pixel-idle/sheet.png">PNG 시트</a> · <a href="source-pixel-idle/frames.json">프레임 시간</a></p></article>')
 for name,(meta,frames) in loaded.items():
  previews=[f.crop(crop).resize((512,512),Image.Resampling.LANCZOS) for f in frames]
  target=OUT/(name+'-compare.webp')
  previews[0].save(target,save_all=True,append_images=previews[1:],duration=meta['previewDurationMs'],loop=0,lossless=True)
  gif,gifmeta=sprite_gif.encode(previews,meta['previewDurationMs'])
  (OUT/(name+'-compare.gif')).write_bytes(gif)
  title='이전 결과 · 입체감이 강했던 버전' if name=='baseline' else CASES[name]['title']
  review_path=OUT/name/'review.json'
  review=json.loads(review_path.read_text(encoding='utf-8')) if review_path.exists() else {}
  note=review.get('note','시각 검토 전입니다.' if name!='baseline' else '사용자가 지적한 이전 결과입니다. 비교용으로 같은 크기로 표시합니다.')
  link=f'<a href="{name}-compare.gif">GIF</a>'
  if name!='baseline':link+=f' · <a href="{name}/raw.mp4">생성 원본 영상</a> · <a href="{name}/contact.webp">프레임 비교</a> · <a href="{name}/settings.json">실제 설정</a>'
  cards.append(f'<article><h2>{title}</h2><p>{html.escape(note)}</p><img src="{name}-compare.webp" alt="{title}"><p>{link}</p></article>')
  indices=np.linspace(0,len(previews)-1,8).round().astype(int).tolist()
  strip=Image.new('RGB',(1280,640),'#263247');draw=ImageDraw.Draw(strip)
  for n,j in enumerate(indices):
   frame=previews[j].resize((320,320),Image.Resampling.LANCZOS)
   strip.paste(frame,(n%4*320,n//4*320),frame)
   draw.text((n%4*320+8,n//4*320+8),str(meta['previewSourceIndices'][j]),fill='white')
  strip.save(OUT/(name+'-strip.webp'),quality=95)
 attack_card=''
 if (OUT/'attack-flat/compare.webp').exists():
  attack_card=('<h1>공격 표현 비교</h1><main><article><h2>이전 공격</h2>'
   '<img src="../masked-raider-motion-20261023/attack/game-animation.webp" alt="이전 공격"></article>'
   '<article><h2>선·셀 채색 유지 지시 + 입체 표현 억제</h2><p>실험 결과이며 시각 검토가 필요합니다.</p>'
   '<img src="attack-flat/compare.webp" alt="2D 표현 유지 공격 시험"><p><a href="attack-flat/compare.gif">GIF</a> · '
   '<a href="attack-flat/raw.mp4">원본 영상</a> · <a href="attack-flat/settings.json">설정</a></p></article></main>')
 page=('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
  '<title>원화의 2D 표현 유지 시험</title><style>body{margin:24px;background:#171e2b;color:#eef0f6;font:15px/1.6 system-ui}'
  'main{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}article{padding:18px;border-radius:16px;background:#263247}'
  'img{width:100%;background:repeating-conic-gradient(#263247 0 25%,#43516a 0 50%) 0/24px 24px}.source{width:auto;max-width:100%;height:360px}'
  'a{color:#c9c0ff}</style><h1>원화의 2D 선·셀 채색 유지 시험</h1><p>먼저 짧은 대기 동작으로 그림체를 비교합니다. '
  '두 새 시험은 같은 입력 픽셀·시드·길이·해상도이며, 입체 표현 억제 조건만 다릅니다. 이전 결과는 3초, 새 시험은 약 1.6초입니다.</p>'
  '<p>같은 동작끼리 같은 확대 영역으로 표시합니다. AI 시험 결과는 그림체를 덮어 그리거나 색 단계를 줄이는 후처리를 하지 않았으며, 배경 제거와 표시 크기 조정만 적용했습니다. '
  '설정 지시가 원본 스타일 보존을 보장하지 않으므로 결과를 따로 검토합니다.</p><img class="source" src="reference.png" alt="입력 원화 사본"><main>'+''.join(cards)+'</main>'+attack_card+'</html>')
 (OUT/'preview.html').write_text(page,encoding='utf-8')


def check():
 assert (OUT/'reference.png').read_bytes()==(PREVIOUS/'reference.png').read_bytes()
 reports={}
 for name,c in CASES.items():
  folder=OUT/name
  assert (folder/'reference-prepared.png').read_bytes()==(PREVIOUS/'idle/reference-prepared.png').read_bytes()
  graph=json.loads((folder/'short-v1-workflow.json').read_text(encoding='utf-8'))
  assert graph['6']['inputs']['length']==39 and graph['10']['inputs']['steps']==20
  assert (graph['11']['class_type']=='CFGGuider')==c['negative']
  history=json.loads((folder/'short-v1-history.json').read_text(encoding='utf-8'))
  assert history['status']['status_str']=='success'
  with av.open(str(folder/'raw.mp4')) as clip:
   assert sum(1 for _ in clip.decode(video=0))==39
  meta=json.loads((folder/'frames.json').read_text(encoding='utf-8'))
  assert len(meta['sourceIndices'])==16 and len(meta['previewSourceIndices'])==38
  reports[name]=dict(generated=True,frames=39,cfg=c['cfg'],postStyleRepaint=False,visualApproval=False)
 save(OUT/'validation.json',dict(passed=True,sameReferencePixels=True,cases=reports,published=False))
 print('STYLE_COMPARISON_GENERATED',reports,flush=True)


if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8')
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','generate','attack','build','check','all'])
 a=p.parse_args()
 if a.stage=='all':generate();build();check()
 else:globals()[a.stage]()
