"""Fresh ComfyUI reference and normal-proportion motion examples for the site."""
import argparse, hashlib, io, json, shutil, sys
from pathlib import Path
import av
import numpy as np
import requests
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import idle_tool as engine
import image_engine,image_pose,image_background,sprite_gif,sprite_loop
from tools import verify_pixel_minimax as executor
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release
OUT=ROOT/'outputs/normal-sprite-examples-20261020'
CHARACTER='normal-anime-swordswoman-20261020'
PROMPT=('1girl, adult woman, solo, full body, (normal adult proportions:1.3), seven heads tall, '
 'auburn high ponytail, green eyes, cream fitted military jacket with dark teal collar, brown belt, '
 'dark teal short pleated battle skirt over opaque charcoal leggings, brown gloves, brown knee-high boots, '
 'holding ONE short straight silver sword in the near hand, blade diagonally down toward screen right, '
 '(strict side profile facing right:1.4), nose pointing right, one visible eye, shoulders and hips in profile, '
 'relaxed battle ready stance, slightly bent elbows and knees, staggered boots, free hand open near waist, '
 'clean sharp anime linework, detailed small face, crisp cel shading, readable costume panels, '
 'one isolated single character, head ponytail boots and whole sword visible, generous empty margins, '
 'plain pure white background, no floor, no shadow, no scenery, no text')
NEGATIVE=('worst quality, low quality, blurry, deformed face, missing pupils, extra fingers, extra arms, '
 'chibi, super deformed, giant head, child, pixel art, low resolution, mosaic, pixelated, '
 'front view, looking at viewer, facing left, back view, multiple swords, long sword, giant weapon, '
 'gun, shield, holding skirt, grabbing clothes, cropped, out of frame, multiple characters, '
 'reference sheet, turnaround, character sheet, panels, background scenery, floor, cast shadow, '
 'text, logo, watermark, halo, floating ring')
ACTIONS={
 'idle':dict(title='일반 · 대기',description='작은 호흡과 머리카락·의상 움직임',strength='low',frames=12,
   prompt='A subtle continuous combat-ready idle. Both boots remain planted. Small relaxed whole-torso sway and slight shoulder breathing, with hair tips and skirt hem following after the body. Keep the abdomen and jacket volume constant. Hold the same rigid sword in the opening diagonal-down ready pose. Preserve the normal adult proportions, exact face, single visible green eye, costume, colors and fine anime linework. No stepping, sword swings, speaking, blinking, chibi proportions or pixelation.'),
 'walk':dict(title='일반 · 걷기',description='오른쪽 제자리 걷기 · 팔·상체·의상이 함께 움직임',strength='normal',frames=16,
   prompt='Walk continuously in place toward SCREEN RIGHT. Short alternating heel-to-toe steps, a support boot on the same ground line at every moment. Gentle opposite free-arm swing, slight shoulder/pelvis counterrotation and torso rise and fall. Keep the rigid sword in the same near hand beside the hip and pointed down and forward, modest hand travel. Ponytail and skirt follow each step with a delay. Preserve normal adult proportions, exact reference face, single visible eye, costume shapes, smooth anime linework and colors. No running, jumping, body turn, forward screen travel, chibi deformation or pixelation.'),
 'attack':dict(title='일반 · 검 공격',description='검을 한 번 베고 준비 자세로 복귀',strength='normal',frames=24,
   prompt='Perform exactly ONE rightward sword attack and recovery. First 0.0-0.45 seconds bend both knees slightly and draw the sword hand back and up beside the rear shoulder. At 0.45-1.1 seconds deliver one fast decisive downward diagonal cut toward SCREEN RIGHT. The sword arm extends and shoulders and hips follow with one small grounded weight shift. At 1.1-1.6 seconds brake the low forward follow-through; ponytail and skirt trail briefly. By 2.5 seconds recover the exact opening ready stance and original screen placement. One rigid silver sword remains attached to the same hand, same length and hilt, empty hand stays empty. Preserve the exact normal adult body proportions, reference face, single visible eye, costume, colors, fine anime linework and cel shading. No second attack, spin, jump, walking, new weapon, chibi deformation or pixelation. No added magical effects; keep the physical cut readable.'),
}

def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def run(graph,folder,name):
 folder.mkdir(parents=True,exist_ok=True);executor.OUT=folder
 return executor.execute(graph,engine.COMFY_URL,name)

def reference():
 OUT.mkdir(exist_ok=True)
 if (OUT/'reference.png').is_file():return
 ensure_idle();release((8190,8191))
 points=[(.59,.16),(.51,.27),(.49,.28),(.53,.39),(.67,.40),(.52,.28),(.50,.41),(.59,.45),(.45,.55),(.40,.72),(.34,.89),(.51,.55),(.58,.72),(.63,.89),(.58,.15),(.57,.15),(.55,.16),(.54,.17)]
 pose=dict(points=[list(p) for p in points],strength=1.)
 p=image_engine.validate(dict(model='wai-cutscene-counter',mode='text',preset='sprite',prompt=PROMPT,
    negativePrompt=NEGATIVE,width=1024,height=1536,steps=32,cfg=4.5,seed=2026102051,
    pose=pose,counterMixStrength=.4,cutsceneMixStrength=1.,background='keep',
    assetSpec=dict(type='side',facing='right',directionCount=1)))
 buf=io.BytesIO();image_pose.render(p['pose'],(1024,1536)).save(buf,format='PNG')
 name=engine.upload_image(buf.getvalue(),'normal-sprite-reference-pose.png')
 g=image_engine.build_workflow(p,p['seed'],pose_image_name=name);g['9']['inputs']['filename_prefix']='normal_site_20261020/reference'
 history=run(g,OUT/'reference-generation','reference-v1')
 response=requests.get(engine.COMFY_URL+'/view',params=history['outputs']['9']['images'][0],timeout=60);response.raise_for_status()
 (OUT/'reference-raw.png').write_bytes(response.content);save(OUT/'reference-settings.json',p)
 release((8189,))
 raw=Image.open(OUT/'reference-raw.png').convert('RGBA');cut=image_background.remove(raw)
 box=cut.getchannel('A').getbbox()
 if not box:raise RuntimeError('Background removal returned an empty reference')
 cut.save(OUT/'reference.png');save(OUT/'reference-review.json',dict(characterId=CHARACTER,box=box,sourceSize=list(raw.size),newAIReference=True,poseControlled=True))
 print('REFERENCE_READY',OUT/'reference.png',flush=True)

def motion():
 source=OUT/'reference.png'
 if not source.exists():raise RuntimeError('Generate and inspect the new reference first')
 for index,(action,item) in enumerate(ACTIONS.items()):
  folder=OUT/action;target=folder/'raw.mp4'
  if target.exists():continue
  ensure_idle();release((8190,8191))
  # Fit reference onto the same 768x768 canvas, with ample attack margins.
  prepared=engine.prepare_reference_image(source.read_bytes(),768,768,20)
  folder.mkdir(exist_ok=True);(folder/'reference_prepared.png').write_bytes(prepared)
  uploaded=engine.upload_image(prepared,'normal-sprite-'+action+'.png')
  g=engine.build_workflow(uploaded,item['prompt'],3,768,768,2026102060+index,
     animation_type=action,loop=True,facing='right',flat_background=True,
     blink_mode='none',motion_strength=item['strength'],sampling_mode='quality',workflow_id='standard')
  g['15']['inputs'].pop('audio',None);g.pop('14',None);g.pop('5',None)
  g['16']['inputs']['filename_prefix']='normal_site_20261020/'+action
  history=run(g,folder,'native-motion-v1');shutil.copyfile(engine.find_saved_video(history),target)
  save(folder/'settings.json',dict(characterId=CHARACTER,width=768,height=768,duration=3,frameCount=item['frames'],
     workflowId='standard',samplingMode='quality',animationType=action,prompt=item['prompt'],facing='right',motionStrength=item['strength'],motionPadding=20,
     pixelOutput=False,combatEffect='none',effectStrength='normal',effectDescription='',pixelColorLock=True,loop=True,
     stabilize=False,optimizeLoop=False,subjectType='human',blinkMode='none',negativeEnabled=False,
     removeBackground=True,backgroundRemoval='flat',seed=2026102060+index))
  release((8189,));print('MOTION_READY',action,flush=True)

def export():
 from tools.sprite_matte import clean_flat_matte
 for action,item in ACTIONS.items():
  folder=OUT/action
  if not (folder/'raw.mp4').exists():continue
  completed=folder/'frames.json'
  if completed.exists() and all((folder/name).exists() for name in ('animation.webp','animation.gif','sheet.png','contact.webp')):
   if completed.stat().st_mtime>=(folder/'raw.mp4').stat().st_mtime and json.loads(completed.read_text()) .get('previewFrames')==73:
    print('EXPORT_CACHED',action,flush=True);continue
  with av.open(str(folder/'raw.mp4')) as clip:
   frames=[f.to_image().convert('RGBA') for f in clip.decode(video=0)]
  assert len(frames)==73
  selected=sprite_loop.sample_indices(len(frames),item['frames'],True)
  all_cuts=[];diagnostic=[]
  for index,frame in enumerate(frames):
   cut,meta=clean_flat_matte(frame,tolerance=24,radius=2);all_cuts.append(cut)
   a=np.array(cut.getchannel('A'));diagnostic.append(dict(sourceFrame=int(index),edgeContact=bool(a[0].any() or a[-1].any() or a[:,0].any() or a[:,-1].any())))
  cuts=[all_cuts[index] for index in selected]
  columns=6 if item['frames']>=12 else 4;rows=(len(cuts)+columns-1)//columns
  sheet=Image.new('RGBA',(768*columns,768*rows))
  for i,im in enumerate(cuts):im.save(folder/f'frame-{i:02d}.png');sheet.paste(im,((i%columns)*768,(i//columns)*768))
  sheet.save(folder/'sheet.png');cuts[0].save(folder/'poster.png')
  bounds=[round(int(i)*1000/24) for i in selected]+[round(len(frames)*1000/24)]
  durations=[b-a for a,b in zip(bounds,bounds[1:])]
  preview=[im.resize((384,384),Image.Resampling.LANCZOS) for im in all_cuts]
  ticks=[round(i*1000/24) for i in range(len(preview)+1)];preview_timing=[b-a for a,b in zip(ticks,ticks[1:])]
  preview[0].save(folder/'animation.webp',save_all=True,append_images=preview[1:],duration=preview_timing,loop=0,lossless=True)
  gif,info=sprite_gif.encode(preview,preview_timing);(folder/'animation.gif').write_bytes(gif)
  contact=Image.new('RGB',(384*6,384*rows),'#252936')
  for i,index in enumerate(selected):
   im=preview[index];contact.paste(im,((i%6)*384,(i//6)*384),im)
  contact.save(folder/'contact.webp')
  save(folder/'frames.json',dict(frameWidth=768,frameHeight=768,sourceIndices=[int(i) for i in selected],durationMs=durations,previewFrames=len(preview),previewTimingMs=preview_timing,columns=columns,rows=rows,diagnostic=diagnostic,gif=info))
  print('EXPORTED',action,len(cuts),flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['reference','motion','export']);a=p.parse_args();globals()[a.stage]()
