"""Isolated, resumable joint sword-action/VFX test. No production asset replacement."""
import argparse, hashlib, io, json, math, shutil, sys, time, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from PIL import Image, ImageDraw
import idle_tool as engine, sprite_combat
from tools import verify_pixel_minimax as executor
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release
from tools.sprite_matte import clean_flat_matte
OUT=ROOT/'outputs/normal-sword-vfx-20261020'
KEY=(255,0,255)
REFERENCE_SCALE=.50
EFFECT_STRENGTH='high'
MIN_EFFECT_PIXELS=1000
COMMON=(
 'One full-body adult anime swordswoman, exactly the supplied character and cel-shaded illustration style. '
 'Preserve auburn high ponytail, green eye, cream jacket, dark teal skirt, dark leggings and brown gloves and boots. '
 'ONE rigid straight sword physically connected to its hilt in the same two-handed grip. '
 'Fixed side-view camera, no zoom, pan, cut or camera orbit. Keep the entire body, blade and all energy arcs inside the canvas. '
 'The character stays the same scale. Use the generous empty space for the effects. '
 'Uniform SOLID PURE MAGENTA background RGB 255,0,255, including all spaces between limbs. '
 'This magenta is an exclusive removable background, never a costume or effect color. No floor, scenery, shadow, ground debris or text. '
 'All energy is cyan, blue, white and gold, never pink or purple. Keep clear crisp anime edges, no cinematic bloom or motion blur. ')
EFFECT=(
 'Spectacular oversized CYAN-BLUE SWORD ENERGY generated together with the physical attack. '
 'A thin cyan charge races along the blade immediately before the cut. At the fast cut, a HUGE broad luminous crescent '
 'follows the real blade path, roughly the character full height, with a brilliant white core, thick saturated cyan body, '
 'a sharp deep-blue rim and two shorter trailing energy ribbons. '
 'A large gold-white impact starburst erupts at the end of the cut toward screen right, throwing a dense short fan of golden sparks '
 'and angular blue shards. Very strong readable game VFX, not a tiny glimmer. '
 'Keep the face and torso visible through the empty center of the arc. All effects stay at least eight percent inside the canvas. '
 'Energy breaks into bright fragments, then vanishes completely during recovery. One synchronized energy attack only, no repeated explosion, '
 'continuous beam, permanent ring, costume recoloring or background change.')
CASES={
 'slash':dict(label='강한 검기 · 내려베기',seed=2026102201,speed=1.5,source='outputs/normal-action-snap-20261020/attack/reference.png',motion=(
  'From the supplied ALREADY RAISED sword pose, IMMEDIATELY perform ONE explosive diagonal downward sword slash to SCREEN RIGHT. '
  'No extra lifting or long anticipation. Rear boot pushes, front boot stamps, hips and shoulders snap, both hands drive sharply '
  'from above the head down past the chest toward the forward hip. Reach the low impact during the first half second. '
  'The knees bend to absorb force while the spine stays firm and chest lifted; never bow double at the waist. '
  'The bright energy crescent sweeps from above her head down and forward to the right in exact sync with the sword. '
  'Hold a planted low finishing stance, let the sparks scatter and hair settle, then recover without another attack. '
  'Face and gaze stay right. One powerful strike, no fencing thrust, shuffle, slow motion or repeated chops. ')),
 'spin':dict(label='강한 검기 · 회전베기',seed=2026102202,speed=1.25,source='outputs/normal-sprite-refine-20261020/reference.png',motion=(
  'ONE COMPLETE GROUNDED BODY TURN driving a powerful horizontal spinning sword slash toward screen RIGHT. '
  'First sink onto bent knees, pull the hilt to the waist and load the rear foot for just 0.2 seconds. '
  'Push off and turn the pelvis, chest and head together through ONE full 360 degree rotation during the next one second. '
  'Her face MUST turn away: visibly show the BACK of her ponytail and cream jacket, then the opposite profile, then face RIGHT again. '
  'Take two short grounded steps through the turn with both knees flexed, never an upright one-legged pirouette or skating slide. '
  'The sword sweeps horizontally around waist level during the body turn; its cyan energy crescent wraps around that physical path '
  'as a wide transient sweeping arc, not a static floating ring. At the end of the turn plant the leading boot and release the '
  'last powerful rightward cut with a gold-white impact burst. STOP rotating completely in a wide right-facing lunge by 1.5 seconds. '
  'Hold the grounded finish as the energy fragments fade, then recover at that position. ONE full turn only. '
  'No repeated spinning, dance, figure skating, jumps, facing lock, camera orbit or sliding back. '))}

def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def read(path):return json.loads(path.read_text(encoding='utf-8'))

def matte_frame(raw,neutral_glow=False):
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

def video():
 OUT.mkdir(parents=True,exist_ok=True)
 for name,item in CASES.items():
  folder=OUT/name;folder.mkdir(exist_ok=True)
  if (folder/'raw.mp4').exists():continue
  ensure_idle();release((8190,8191))
  source=Image.open(ROOT/item['source']).convert('RGBA')
  assert source.getchannel('A').getextrema()[0]<255
  # Fixed centered scale, with room for a character-height energy crescent.
  source.save(folder/'reference.png');size=tuple(max(1,round(v*min(768/source.width,768/source.height)*REFERENCE_SCALE)) for v in source.size)
  resized=source.resize(size,Image.Resampling.LANCZOS)
  canvas=Image.new('RGB',(768,768),KEY);canvas.paste(resized,((768-size[0])//2,(768-size[1])//2),resized.getchannel('A'))
  stream=io.BytesIO();canvas.save(stream,format='PNG');data=stream.getvalue();(folder/'reference-prepared.png').write_bytes(data)
  digest=hashlib.sha256(data).hexdigest();record=folder/'upload.json'
  if record.exists():
   prior=read(record);assert prior['sha256']==digest;uploaded=prior['name']
  else:
   uploaded=engine.upload_image(data,'normal-sword-vfx-'+name+'.png');save(record,dict(sha256=digest,name=uploaded))
  settings=dict(combatEffect='custom',effectStrength=EFFECT_STRENGTH,effectDescription=EFFECT,pixelOutput=False,pixelColorLock=True,
   removeBackground=True,backgroundRemoval='flat')
  graph=engine.build_workflow(uploaded,item['motion'],3,768,768,item['seed'],animation_type='custom',loop=False,
   facing='preserve',flat_background=True,motion_strength='high',sampling_mode='quality',workflow_id='standard',combat_settings=settings)
  # A full turn requires deliberately removing the usual side-facing constraint.
  prompt=item.get('fullPrompt') or ('<Picture 1> is the opening reference at 0.00 seconds.\n\nintegrated_multimodal_description: [Shot 1] '
   +COMMON+item['motion']+sprite_combat.prompt(settings)+'\n\noverall_soundscape: N/A\n\nnon_diegetic_music: N/A')
  graph['6']['inputs']['prompt']=prompt;graph['16']['inputs']['filename_prefix']='normal_sword_vfx/'+name
  save(folder/'settings.json',dict(settings,seed=item['seed'],prompt=prompt,width=768,height=768,duration=3,
   animationType='custom',loop=False,motionSpeed=item['speed'],trimAction=False,workflowId='standard',steps=20,
   backgroundKey=list(KEY),referencePath=item['source'],referenceScale=REFERENCE_SCALE,motionPadding=round((1-REFERENCE_SCALE)*100),fullBodyTurn=name=='spin',proceduralOverlay=False))
  executor.OUT=folder;start=time.monotonic();history=executor.execute(graph,engine.COMFY_URL,'joint-vfx-v1')
  shutil.copyfile(engine.find_saved_video(history),folder/'raw.mp4');save(folder/'generation-time.json',dict(seconds=round(time.monotonic()-start,2)))
  release((8189,));export_case(name);build();print('READY',name,flush=True)

def export_case(name):
 import av, sprite_gif, sprite_loop, motion_timing
 folder=OUT/name;item=CASES[name]
 with av.open(str(folder/'raw.mp4')) as clip:native=[f.to_image().convert('RGBA') for f in clip.decode(video=0)]
 report=motion_timing.retime_video(folder/'raw.mp4',folder/'motion.mp4',dict(motionSpeed=item['speed'],trimAction=False,animationType='custom',loop=False))
 save(folder/'motion-timing.json',report);cuts=[];diagnostics=[];all_folder=folder/'all-frames';all_folder.mkdir(exist_ok=True)
 for n,raw in enumerate(native):
  cut,meta=matte_frame(raw,neutral_glow=item.get('neutralGlowMatte',False))
  cut.save(all_folder/f'frame-{n:03d}.png');cuts.append(cut)
  a=np.array(cut.getchannel('A'));rgb=np.array(raw)[:,:,:3]
  effect=(rgb[:,:,1]>150)&(rgb[:,:,2]>160)&(rgb[:,:,0]<140)&(a>128)
  diagnostics.append(dict(frame=n,edgeContact=bool(a[0].any() or a[-1].any() or a[:,0].any() or a[:,-1].any()),
   opaqueEdgeContact=bool((a[0]>128).any() or (a[-1]>128).any() or (a[:,0]>128).any() or (a[:,-1]>128).any()),cyanPixels=int(effect.sum()),matte=meta))
 indices=report['sourceIndices'];shown=[cuts[i] for i in indices];times=report['durationMs']
 # Preserve native canvas for GIF/WebP: no per-frame cropping, scaling or registration.
 shown[0].save(folder/'animation.webp',save_all=True,append_images=shown[1:],duration=times,loop=0,lossless=True)
 gif,info=sprite_gif.encode(shown,times);(folder/'animation.gif').write_bytes(gif)
 selected=sprite_loop.sample_indices(len(shown),24,False);columns=6;rows=4
 sheet=Image.new('RGBA',(768*columns,768*rows));contact=Image.new('RGB',(320*columns,320*rows),'#232936');draw=ImageDraw.Draw(contact)
 for n,j in enumerate(selected):
  im=shown[j];im.save(folder/f'frame-{n:02d}.png');sheet.paste(im,(n%columns*768,n//columns*768))
  small=im.resize((320,320),Image.Resampling.LANCZOS);contact.paste(small,(n%columns*320,n//columns*320),small)
  draw.text((n%columns*320+6,n//columns*320+6),f'{indices[j]} / {sum(times[:j])}ms',fill='white')
 sheet.save(folder/'sheet.png');contact.save(folder/'contact.webp');shown[0].save(folder/'poster.png')
 bounds=[sum(times[:j]) for j in selected]+[sum(times)]
 save(folder/'frames.json',dict(frameWidth=768,frameHeight=768,columns=columns,rows=rows,sourceIndices=[indices[j] for j in selected],
  durationMs=[b-a for a,b in zip(bounds,bounds[1:])],previewSourceIndices=indices,previewTimingMs=times,gif=info,diagnostic=diagnostics,
  backgroundRemoval='flat-key-VFX-unmatting-plus-semantic-character-protection',proceduralOverlay=False))
 print('EXPORTED',name,'frames',len(native),'duration',sum(times),'ms; edge frames',[d['frame'] for d in diagnostics if d['edgeContact']],flush=True)

def build():
 cards=[]
 for name,item in CASES.items():
  if not (OUT/name/'animation.gif').exists():continue
  cards.append(f'<article><h2>{item["label"]}</h2><img src="{name}/animation.webp"><p><a href="{name}/animation.gif" download>GIF</a> · <a href="{name}/sheet.png" download>PNG 시트</a> · <a href="{name}/raw.mp4">생성 원본 영상</a> · <a href="{name}/settings.json">생성 설정</a></p><details><summary>프레임 확인</summary><img class="contact" src="{name}/contact.webp"></details></article>')
 (OUT/'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>검기 · 내려베기와 회전베기</title><style>body{background:#111722;color:#edf2ff;font:16px system-ui;margin:32px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:24px}article{background:#202838;padding:20px;border-radius:16px}img{width:100%;background:repeating-conic-gradient(#252e40 0 25%,#303b50 0 50%) 0/24px 24px}a{color:#91d9ff}.contact{max-width:100%}p{line-height:1.7}</style><h1>검격 이펙트 강화 시험</h1><p>캐릭터 동작과 검기·섬광을 함께 AI 생성했습니다. 일반 일러스트 스타일이며 도트 변환은 하지 않았습니다.<br>단색 배경 제거와 재생 속도 조정만 적용했습니다. 화면의 반복은 단발 동작을 다시 재생하는 표시입니다. 아직 사이트 예시는 교체하지 않았습니다.</p><main>'+''.join(cards)+'</main>',encoding='utf-8')

def check():
 import av
 report={}
 for name in CASES:
  folder=OUT/name;settings=read(folder/'settings.json');meta=read(folder/'frames.json')
  saved=engine.find_saved_video(read(folder/'joint-vfx-v1-history.json'))
  assert hashlib.sha256(saved.read_bytes()).hexdigest()==hashlib.sha256((folder/'raw.mp4').read_bytes()).hexdigest()
  with av.open(str(folder/'raw.mp4')) as clip:frames=list(clip.decode(video=0))
  assert len(frames)==73 and all((f.width,f.height)==(768,768) for f in frames)
  assert settings['proceduralOverlay'] is False and 'last_frame' not in read(folder/'joint-vfx-v1-workflow.json')['6']['inputs']
  assert len(meta['sourceIndices'])==24 and len(meta['durationMs'])==24
  with Image.open(folder/'animation.gif') as gif:
   gif_times=[]
   for i in range(gif.n_frames):gif.seek(i);gif_times.append(gif.info.get('duration',0))
  assert abs(sum(gif_times)-sum(meta['previewTimingMs']))<=10
  assert max(d['cyanPixels'] for d in meta['diagnostic'])>MIN_EFFECT_PIXELS
  report[name]=dict(nativeFrames=73,nativeVideoUnmodified=True,cyanPeak=max(d['cyanPixels'] for d in meta['diagnostic']),edgeContactFrames=[d['frame'] for d in meta['diagnostic'] if d['edgeContact']],opaqueEdgeContactFrames=[d['frame'] for d in meta['diagnostic'] if d.get('opaqueEdgeContact')],gifMs=sum(gif_times),reviewRequired=True)
 save(OUT/'validation.json',report)
 with zipfile.ZipFile(OUT/'sword-vfx-handoff.zip','w',zipfile.ZIP_DEFLATED) as archive:
  for name in CASES:
   for filename in ('animation.gif','animation.webp','sheet.png','frames.json','settings.json','raw.mp4'):
    archive.write(OUT/name/filename,f'{name}/{filename}')
 print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['video','export','build','check']);args=parser.parse_args()
 if args.stage=='export':
  for name in CASES:
   if (OUT/name/'raw.mp4').exists():export_case(name)
  build()
 else:globals()[args.stage]()
