"""Original non-pixel chibi references and native video motion examples."""
import argparse
import hashlib
import html
import io
import json
import math
from pathlib import Path
import shutil
import sys

import av
import numpy as np
import requests
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import idle_tool as engine
import image_engine,image_background,rigging_engine as rig
import motion_timing,sprite_loop,sprite_gif,sprite_vfx_matte
from tools import verify_pixel_minimax as executor
from tools.verify_rpg_sprite_styles import ensure_idle

OUT=ROOT/'outputs/chibi-illustration-20261020'
CHARACTER='original-chibi-cartographer-20261020'
CHARACTER_TEXT=(
 'original female fantasy adventurer, (chibi:1.5), (super deformed:1.25), '
 '(three heads tall:1.3), oversized round head, short compact torso and short limbs, '
 'wavy shoulder-length plum bob hair, brass triangular hair clip, bright amber irises with distinct dark pupils, '
 'ivory high collar blouse, moss green short shoulder cape, terracotta fitted waistcoat, '
 'purple trousers, brown leather belt, small brown satchel, brown gloves and ankle boots, '
 'ONE short straight silver sword, small brass crossguard, brown sword grip, '
 'single full body character, nose and gaze toward screen right, three-quarter side view, '
 'head both boots and whole sword visible, generous empty margins, '
 'clean smooth anime linework, crisp cel shading, detailed clear anime eyes, '
 'plain pure white background, isolated, no ground, no floor shadow'
)
NEGATIVE=(
 'worst quality, low quality, blurry, bad hands, extra fingers, extra arms, two swords, '
 'realistic proportions, long legs, tall body, photorealistic, 3d, pixel art, pixelated, '
 'mosaic, dithering, front view, looking at viewer, facing left, cropped, panels, '
 'multiple characters, blank eyes, missing pupils, halo, text, watermark, floor, shadow'
)
ACTIONS={
 'idle':dict(title='치비 · 대기',frames=12,loop=True,padding=20,speed=1.,trim=False,strength='low',effect='none',seed=2026102331,
  prompt='A small relaxed battle-ready idle in place. Both boots stay planted, with gentle shoulder breathing and tiny torso sway. Loose clothing and hair tips settle softly. Keep the exact same large chibi head, short body and limbs, eye shapes and original pupil colors, costume, colors and clean smooth anime illustration. Keep the one rigid short sword in its opening lowered grip. Maintain the right-facing orientation. No walking, growing taller, weapon swing, speaking, new effects or camera motion.'),
 'run':dict(title='치비 · 뛰기',frames=24,loop=True,padding=30,speed=1.5,trim=False,strength='high',effect='none',seed=2026102332,
  pose='Change the pose to a clear athletic RUNNING stride facing SCREEN RIGHT. Lean the short compact torso forward, lift one bent knee in front and fold the other heel behind. Both bent arms pump in opposite directions with EMPTY CLOSED FISTS. Put the ONE sword fully inside a dark brown scabbard strapped securely to the belt, with just its brass hilt visible; no exposed blade. Preserve the exact large chibi head and short legs. The cape trails toward the left.',
  prompt='Run continuously IN PLACE toward screen RIGHT. Alternate both short legs in lively running strides with brief airborne phases. Drive one knee forward while the other heel folds behind, then exchange legs. Pump both bent arms opposite the legs. The sword remains fully SHEATHED on the belt; both hands stay empty. Lean the compact torso forward, counterrotate shoulders and hips, and let loose clothing and hair bounce after each push-off. Maintain the exact large chibi head and short compact body and limbs, reference face and eyes, costume and smooth cel shading. Keep the hip centered, fixed camera and steady rightward gaze. No slow walking, single-leg hopping, skating, turns, weapon drawing, added effects or idle pause.'),
 'attack':dict(title='치비 · 작은 검기 베기',frames=24,loop=False,padding=50,speed=1.5,trim=True,strength='high',effect='subtle',seed=2026102333,
  pose='Change ONLY the pose to the instant BEFORE a quick overhead sword strike toward screen RIGHT. BOTH brown-gloved hands grip ONE short sword hilt above and just behind the large head. The single rigid silver blade points upward and back to the left, fully visible and connected to the hilt. Bend both short knees, front boot slightly ahead, compact chest lifted. Keep the short chibi body and oversized head. No forward pointing fingers, no sword at the hip, no second sword.',
  prompt='Immediately make ONE quick downward sword cut to screen right from the raised opening pose. Drive the two short arms from overhead down to the forward hip. Stamp the front boot, bend both short knees, turn the shoulders with the hips and keep the chest lifted. Stop in a compact balanced low finishing stance and hold while hair and clothing settle. Preserve the opening oversized chibi head and short body proportions; do not grow taller. One connected rigid sword stays in both hands. Keep the whole character and blade arc inside the canvas.')
}
ACTIONS['attack-clean']={**ACTIONS['attack'],
 'title':'치비 · 내려베기','animationType':'attack','effect':'none','seed':2026102334,
 'prompt':('Immediately perform ONE quick physical downward sword strike toward screen RIGHT from the raised starting pose. '
  'The front boot plants, the short knees flex and both hands drive down from above the head to just ahead of the front hip. '
  'The single straight metal sword moves rigidly with the two-handed grip. Keep the torso upright and follow the strike with the shoulders and hips. '
  'Finish with the sword low and forward and hold a stable compact stance. Hair and cloak settle after the body stops. '
  'Keep the reference oversized chibi head, short body and limbs, same face, costume, proportions and illustration style. '
  'Plain physical motion only: no magical trails, sword light, spark, flash, beam, crescent, duplicate sword or new scene. '
  'No second strike, thrust, slow lifting, extra preparation, spin, walking or camera movement.')}

def save(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def execute(graph,url,folder,name):
 folder.mkdir(parents=True,exist_ok=True);executor.OUT=folder
 return executor.execute(graph,url,name)
def release(url):
 requests.post(url+'/free',json={'unload_models':True,'free_memory':True},timeout=30).raise_for_status()

def reference():
 OUT.mkdir(parents=True,exist_ok=True)
 if (OUT/'reference.png').exists():return
 ensure_idle()
 p=image_engine.validate(dict(model='flanime-xl',mode='text',preset='illustration',
   prompt=CHARACTER_TEXT+', standing ready, knees slightly bent, holding the short sword in the near hand pointed diagonally down toward screen right, free hand relaxed by the hip',
   negativePrompt=NEGATIVE,width=1024,height=1024,steps=36,cfg=5.,seed=2026102321,count=1,background='keep'))
 graph=image_engine.build_workflow(p,p['seed']);graph['9']['inputs']['filename_prefix']='chibi_illustration_20261020/reference'
 record=execute(graph,image_engine.COMFY_URL,OUT/'reference-generation','original-v1')
 r=requests.get(image_engine.COMFY_URL+'/view',params=record['outputs']['9']['images'][0],timeout=60);r.raise_for_status()
 (OUT/'reference-raw.png').write_bytes(r.content);save(OUT/'reference-settings.json',p)
 release(image_engine.COMFY_URL)
 with Image.open(OUT/'reference-raw.png') as raw:image_background.remove_sprite(raw).save(OUT/'reference.png')
 print('ORIGINAL_CHIBI_READY',flush=True)

def reference_retry():
 """Keep the rejected collage; use a single original illustration as identity input."""
 folder=OUT/'reference-retry';folder.mkdir(exist_ok=True)
 if (folder/'reference.png').exists():return
 ensure_idle();release(engine.COMFY_URL)
 source=ROOT/'web/assets/asset-type-previews/original-cartographer.png'
 name='original_cartographer_chibi_source.png';shutil.copyfile(source,rig.INPUT_ROOT/name)
 g=rig.qwen21_workflow(name,'chibi_illustration_20261020/clean_reference',768,20,2026102325)
 g['6']['inputs'].update(device='cpu',dtype='default')
 g['5']['inputs']['prompt']=(
  'Create ONE isolated full-body CHIBI game character based on this original woman. '
  'Preserve the same plum-brown bob haircut, small brass triangular hair clip, amber eyes with dark pupils, '
  'ivory blouse, short moss green cape, terracotta waistcoat, purple trousers, brown belt and satchel. '
  'Change the proportions to THREE HEADS TALL: a very large round head, a short compact torso, short arms, short legs and brown ankle boots. '
  'Turn her entire body and nose to face SCREEN RIGHT in a side-on three-quarter battle-ready stance. '
  'In the near brown-gloved hand she holds ONE short straight silver sword with a brass crossguard and brown grip, blade lowered diagonally forward toward the right. '
  'The far hand rests near the belt. Both boots are visible on the same ground line. '
  'Only the one complete character is present. Remove the star wand, charts, all floating stars, all background lines and all scenery. '
  'Use smooth clean anime outlines and polished flat cel shading with clear eyes, not pixel art. '
  'Plain pure WHITE background, no floor or shadow. Center the whole character and sword with ample empty space on every side. '
  'No extra heads, no inset portraits, no miniature duplicates, no panels, no logo or text.')
 g['5']['inputs']['negative_prompt']='multiple characters, extra heads, floating face, inset portrait, miniature, collage, sheet, front view, facing left, long legs, realistic proportions, pixel art, shadow, scenery, text'
 record=execute(g,rig.COMFY_URL,folder,'clean-original-v2')
 raw=Image.open(rig._saved_image(record,'9')).convert('RGBA');raw.save(folder/'reference-raw.png');release(rig.COMFY_URL)
 image_background.remove_sprite(raw).save(folder/'reference.png')
 save(folder/'identity.json',dict(originalCharacter=True,source=str(source.relative_to(ROOT)),referenceKind='Original locally generated cartographer; no franchise reference'))
 print('CHIBI_REFERENCE_RETRY_READY',flush=True)

def poses(only=None):
 for action,item in ACTIONS.items():
  if only and action!=only:continue
  folder=OUT/action;folder.mkdir(exist_ok=True)
  if (folder/'reference.png').exists():continue
  if action=='idle':shutil.copyfile(OUT/'reference.png',folder/'reference.png');continue
  ensure_idle();release(engine.COMFY_URL)
  raw=Image.open(OUT/'reference.png').convert('RGBA');white=Image.new('RGB',raw.size,'white');white.paste(raw,mask=raw.getchannel('A'))
  name='chibi_illustration_'+action+'.png';white.save(rig.INPUT_ROOT/name)
  g=rig.qwen21_workflow(name,'chibi_illustration_20261020/'+action,768,20,item['seed']-10)
  g['6']['inputs'].update(device='cpu',dtype='default')
  g['5']['inputs']['prompt']=('Edit the EXACT same original chibi character, keeping the same plum bob haircut, triangular brass hair clip, amber eyes with dark pupils, ivory blouse, green short cape, terracotta waistcoat, purple trousers, brown boots, belt and satchel, smooth clean anime cel shading. Retain the large round head and three-head-tall short compact body. '+item['pose']+' One isolated full-body character, head both boots and whole weapon inside generous empty margins. Plain pure WHITE background, no floor, no cast shadow, no text, no panels.')
  g['5']['inputs']['negative_prompt']='pixel art, pixelated, realistic proportions, taller body, long legs, front view, facing left, extra limbs, extra sword, detached blade, cropped, shadow, text'
  record=execute(g,rig.COMFY_URL,folder,'pose-v1')
  image=Image.open(rig._saved_image(record,'9')).convert('RGBA');image.save(folder/'reference-raw.png');release(rig.COMFY_URL)
  image_background.remove_sprite(image).save(folder/'reference.png')
  print('CHIBI_POSE_READY',action,flush=True)

def settings(action):
 item=ACTIONS[action]
 return dict(characterId=CHARACTER,width=768,height=768,duration=3,seed=item['seed'],
  frameCount=item['frames'],workflowId='standard',samplingMode='quality',animationType=item.get('animationType',action),
  prompt=item['prompt'],loop=item['loop'],facing='right',subjectType='human',motionStrength=item['strength'],
  motionPadding=item['padding'],motionSpeed=item['speed'],trimAction=item['trim'],blinkMode='none',negativeEnabled=False,
  pixelOutput=False,pixelColorLock=True,combatEffect=item['effect'],effectStrength='low',effectDescription='',
  stabilize=False,optimizeLoop=False,removeBackground=True,backgroundRemoval='flat' if item['effect']=='subtle' else 'ai')

def frame_references():
 """Trim empty transparent margins once, preserving the original cutout."""
 for action in ACTIONS:
  folder=OUT/action;source=folder/'reference.png';original=folder/'reference-uncropped.png'
  if (folder/'reference-framing.json').exists():continue
  if not original.exists():shutil.copyfile(source,original)
  im=Image.open(original).convert('RGBA');box=im.getchannel('A').getbbox()
  if not box:raise RuntimeError('Empty reference '+action)
  border=24;crop=im.crop(box);canvas=Image.new('RGBA',(crop.width+border*2,crop.height+border*2));canvas.paste(crop,(border,border));canvas.save(source)
  save(folder/'reference-framing.json',dict(sourceSize=list(im.size),cropBounds=box,border=border,outputSize=list(canvas.size)))

def motion(only=None):
 for action,item in ACTIONS.items():
  if only and action!=only:continue
  folder=OUT/action
  if (folder/'raw.mp4').exists():continue
  ensure_idle();release(rig.COMFY_URL);release(image_engine.image_soya.URL)
  p=settings(action);save(folder/'settings.json',p)
  prepared=engine.prepare_reference_image((folder/'reference.png').read_bytes(),768,768,item['padding'])
  (folder/'reference_prepared.png').write_bytes(prepared);uploaded=engine.upload_image(prepared,'chibi-illustration-'+action+'.png')
  graph=engine.build_workflow(uploaded,item['prompt'],3,768,768,item['seed'],animation_type=p['animationType'],loop=item['loop'],
   facing='right',flat_background=True,blink_mode='none',motion_strength=item['strength'],sampling_mode='quality',workflow_id='standard',combat_settings=p)
  graph['15']['inputs'].pop('audio',None);graph.pop('14',None);graph.pop('5',None)
  graph['16']['inputs']['filename_prefix']='chibi_illustration_20261020/'+action
  record=execute(graph,engine.COMFY_URL,folder,'native-v1');shutil.copyfile(engine.find_saved_video(record),folder/'raw.mp4')
  release(engine.COMFY_URL);print('CHIBI_MOTION_READY',action,flush=True)

def export(only=None):
 for action,item in ACTIONS.items():
  if only and action!=only:continue
  folder=OUT/action
  if not (folder/'raw.mp4').exists():continue
  if (folder/'frames.json').exists():continue
  raw_hash=hashlib.sha256((folder/'raw.mp4').read_bytes()).hexdigest()
  with av.open(str(folder/'raw.mp4')) as video:native=[f.to_image().convert('RGBA') for f in video.decode(video=0)]
  p=settings(action);report=motion_timing.retime_video(folder/'raw.mp4',folder/'motion.mp4',motion_timing.options(p))
  all_folder=folder/'all-frames';all_folder.mkdir(exist_ok=True);cuts=[];diagnostics=[]
  for i,raw in enumerate(native):
   target=all_folder/f'frame-{i:03d}.png'
   if target.exists():cut=Image.open(target).convert('RGBA')
   else:
    cut=sprite_vfx_matte.remove(raw)[0] if item['effect']=='subtle' else image_background.remove_sprite(raw)
    cut.save(target)
   alpha=np.asarray(cut.getchannel('A'));box=cut.getchannel('A').getbbox()
   diagnostics.append(dict(frame=i,bbox=box,edgeContact=bool(alpha[0].any() or alpha[-1].any() or alpha[:,0].any() or alpha[:,-1].any())))
   cuts.append(cut)
  indices=report['sourceIndices'];shown=[cuts[i] for i in indices];times=report['durationMs'];boxes=[im.getchannel('A').getbbox() for im in shown]
  assert all(boxes)
  l,t,r,b=min(x[0] for x in boxes),min(x[1] for x in boxes),max(x[2] for x in boxes),max(x[3] for x in boxes)
  side=math.ceil(max(r-l,b-t)*1.12);x=math.floor((l+r-side)/2);y=math.floor((t+b-side)/2);crop=(x,y,x+side,y+side)
  preview=[im.crop(crop).resize((512,512),Image.Resampling.LANCZOS) for im in shown]
  preview[0].save(folder/'animation.webp',save_all=True,append_images=preview[1:],duration=times,loop=0,lossless=True)
  gif,gif_info=sprite_gif.encode(preview,times);(folder/'animation.gif').write_bytes(gif)
  chosen=sprite_loop.sample_indices(len(shown),min(item['frames'],len(shown)),item['loop']);width,height=native[0].size
  columns=4;rows=math.ceil(len(chosen)/columns);sheet=Image.new('RGBA',(width*columns,height*rows));contact=Image.new('RGB',(384*columns,384*rows),'#232b38');draw=ImageDraw.Draw(contact)
  for n,j in enumerate(chosen):
   im=shown[j];im.save(folder/f'frame-{n:02d}.png');sheet.paste(im,(n%columns*width,n//columns*height));small=preview[j].resize((384,384),Image.Resampling.LANCZOS)
   contact.paste(small,(n%columns*384,n//columns*384),small);draw.text((n%columns*384+8,n//columns*384+8),f'raw {indices[j]} / {sum(times[:j])} ms',fill='white')
  sheet.save(folder/'sheet.png');contact.save(folder/'contact.webp');preview[chosen[min(2,len(chosen)-1)]].save(folder/'poster.png')
  bounds=[sum(times[:j]) for j in chosen]+[sum(times)]
  save(folder/'frames.json',dict(frameWidth=width,frameHeight=height,sourceFrames=len(native),sourceIndices=[indices[j] for j in chosen],durationMs=[b-a for a,b in zip(bounds,bounds[1:])],
   previewTimingMs=times,previewCropBounds=crop,columns=columns,rows=rows,diagnostics=diagnostics,gif=gif_info,timing=report,rawSha256=raw_hash))
  save(folder/'settings.json',dict(p,frameCount=len(chosen)))
  assert hashlib.sha256((folder/'raw.mp4').read_bytes()).hexdigest()==raw_hash
  print('CHIBI_EXPORTED',action,len(native),'native frames',report['totalMs'],'ms',flush=True)

def build():
 rows=[]
 for action,item in ACTIONS.items():
  folder=OUT/action
  if not (folder/'animation.webp').exists():continue
  review=json.loads((folder/'review.json').read_text(encoding='utf-8')) if (folder/'review.json').exists() else {'note':'생성 후 시각 검토 대기'}
  if review.get('publish') is False:continue
  rows.append(f'<section><h2>{item["title"]}</h2><p>{html.escape(review.get("note",""))}</p><img src="{action}/animation.webp"><div><a href="{action}/animation.gif" download>GIF 저장</a> · <a href="{action}/sheet.png" target="_blank">PNG 시트</a> · <a href="{action}/reference.png" target="_blank">입력 원화</a> · <a href="{action}/contact.webp" target="_blank">프레임 검토</a></div></section>')
 page='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>일러스트 치비 동작 예시</title><style>body{background:#171b26;color:#eee;margin:24px;font:15px/1.6 system-ui}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}section{background:#262e3c;padding:16px;border-radius:14px}img{width:100%;max-width:512px;background:repeating-conic-gradient(#272d39 0 25%,#414a5c 0 50%) 0/24px 24px}a{color:#c5bdff}</style><h1>오리지널 치비 · 대기 / 뛰기 / 검 공격</h1><p>도트가 아닌 매끈한 선과 채색의 치비 원화로 만든 실제 영상 기반 동작입니다. PNG 시트는 원래 캔버스 좌표를 유지하고 표시용 애니메이션만 고정 구도로 확대합니다.</p><main>'+''.join(rows)+'</main></html>'
 (OUT/'preview.html').write_text(page,encoding='utf-8')

def posters():
 for action,item in ACTIONS.items():
  folder=OUT/action
  if not (folder/'frames.json').exists():continue
  if (folder/'review.json').exists() and json.loads((folder/'review.json').read_text(encoding='utf-8')).get('publish') is False:continue
  m=json.loads((folder/'frames.json').read_text(encoding='utf-8'));indices=m['timing']['sourceIndices']
  target=0 if action=='idle' else 12 if action=='run' else 16
  index=min(indices,key=lambda i:abs(i-target))
  with Image.open(folder/'all-frames'/f'frame-{index:03d}.png') as im:
   im.crop(m['previewCropBounds']).resize((512,512),Image.Resampling.LANCZOS).save(folder/'poster.png')
  m['posterSourceIndex']=index;save(folder/'frames.json',m)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['reference','reference_retry','poses','frame_references','motion','export','posters','build']);p.add_argument('--case',choices=list(ACTIONS));a=p.parse_args()
 OUT.mkdir(parents=True,exist_ok=True)
 if a.stage in ('poses','motion','export'):globals()[a.stage](a.case)
 else:globals()[a.stage]()
