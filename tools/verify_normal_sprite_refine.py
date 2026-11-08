"""Isolated normal-motion revision; publish only after visual review."""
import argparse, io, json, shutil, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from PIL import Image
import idle_tool as engine, image_background
from tools import verify_pixel_minimax as executor
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release
OUT=ROOT/'outputs/normal-sprite-refine-20261020'
OLD=ROOT/'outputs/normal-sprite-examples-20261020'
CHARACTER='normal-anime-swordswoman-20261020'
ACTIONS={
 'attack':dict(frames=24,loop=False,strength='high',seed=2026102081,prompt=(
  'One athletic sword slash toward screen RIGHT. From the ready stance, flex the knees and load weight onto the rear leg, '
  'draw the sword just behind the shoulder, then PUSH OFF the rear boot and take one short forward step. '
  'The pelvis turns FIRST, the shoulders follow and the elbows extend to drive one fast powerful diagonal cut across the space in front. '
  'The spine stays long and the chest lifted: power comes from the legs and rotating hips, not bending double at the waist. '
  'The forward knee absorbs the weight while the rear heel pivots; the sword finishes forward and low. '
  'Hair and skirt whip behind the acceleration, then settle. Finish balanced in the forward follow-through. '
  'ONE strike only, no loop reset, no repeated chops, no shuffle, no slow stretching. '
  'Keep one straight rigid silver sword in the same two-handed grip, fixed blade length; retain the reference adult woman, face, costume and cel shading. '
  'Show the entire blade and both boots throughout. No magical effects.')),
 'walk':dict(frames=16,loop=True,strength='normal',seed=2026102082,prompt=(
  'A natural continuous right-facing walk cycle IN PLACE, two complete alternating strides at an even cadence. '
  'The feet roll heel-to-toe, knees flex during the passing phase, and each boot swings forward then sweeps backward on a fixed ground line. '
  'The pelvis rises and falls slightly above the supporting leg and the shoulders counterrotate naturally. '
  'Both elbows move rhythmically with the walking torso; the hands carry the ONE rigid sword steadily in the same grip in front of the body. '
  'The ponytail sways and the skirt hem follows each step with a delay. '
  'Keep the nose looking right and hips centered on screen. No rotating toward camera, no idle opening, no stopping at the end, no running. '
  'Preserve the adult proportions, original face, costume colors, smooth anime linework and the straight rigid sword length.')),
}
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def run(graph,folder,name):
 folder.mkdir(parents=True,exist_ok=True);executor.OUT=folder
 return executor.execute(graph,engine.COMFY_URL,name)
def reference():
 import rigging_engine as rig
 OUT.mkdir(parents=True,exist_ok=True)
 if (OUT/'reference.png').exists():return
 ensure_idle();release((8189,8191))
 raw=Image.open(OLD/'reference.png').convert('RGBA')
 canvas=Image.new('RGB',raw.size,'white');canvas.paste(raw,mask=raw.getchannel('A'))
 canvas.save(rig.INPUT_ROOT/'normal_refine_reference.png')
 graph=rig.qwen21_workflow('normal_refine_reference.png','normal_refine/reference',1024,20,2026102080)
 graph['6']['inputs'].update(device='cpu',dtype='default')
 graph['5']['inputs']['prompt']=(
  'Redraw the EXACT same adult female character as ONE full body anime combat sprite. '
  'Preserve the auburn high ponytail, green eye, cream military jacket, teal skirt, dark leggings and brown gloves and boots, and the clean cel shaded illustration style. '
  'CHANGE ONLY THE POSE AND SWORD: make a balanced athletic sword-ready stance facing screen RIGHT, knees softly flexed, '
  'rear boot behind and front boot ahead, torso upright. BOTH gloved hands firmly hold ONE sword hilt near the chest in front of the body. '
  'The ONE straight short silver blade points diagonally UP and RIGHT from the hands, fully visible and physically connected to its hilt. '
  'The free hand must NOT point forward. No open hand gesture. Nose and gaze point right, side view. '
  'Full body, both boots and the entire blade visible, generous empty margin. Uniform pure white background, no floor, no shadows, no text. '
  'One image, no panels or other characters.')
 graph['5']['inputs']['negative_prompt']='two swords, disconnected blade, pointing hand, sword behind back, bent spine, cropped, extra limbs, front view, pixel art, text, scenery'
 executor.OUT=OUT/'reference-generation';executor.OUT.mkdir(exist_ok=True)
 history=executor.execute(graph,rig.COMFY_URL,'ready-pose-v2')
 raw=Image.open(rig._saved_image(history,'9')).convert('RGBA');raw.save(OUT/'reference-raw.png')
 release((8190,));image_background.remove(raw).save(OUT/'reference.png')
 print('REFERENCE_READY',flush=True)
def motion():
 for action,item in ACTIONS.items():
  folder=OUT/action;folder.mkdir(exist_ok=True);target=folder/'raw.mp4'
  if target.exists():continue
  ensure_idle();release((8190,8191))
  padding=item.get('padding',30)
  revision=item.get('revision','motion-v2')
  width,height=item.get('width',768),item.get('height',768)
  workflow=item.get('workflowId','standard')
  prepared=engine.prepare_reference_image((OUT/'reference.png').read_bytes(),width,height,padding)
  (folder/'reference_prepared.png').write_bytes(prepared)
  uploaded=engine.upload_image(prepared,'normal-refine-'+action+'.png')
  graph=engine.build_workflow(uploaded,item['prompt'],3,width,height,item['seed'],animation_type=action,
   loop=item['loop'],facing='right',flat_background=True,blink_mode='none',motion_strength=item['strength'],sampling_mode='quality',workflow_id=workflow)
  graph['15']['inputs'].pop('audio',None);graph.pop('14',None);graph.pop('5',None)
  graph['16']['inputs']['filename_prefix']='normal_refine_20261020/'+action
  history=run(graph,folder,revision);shutil.copyfile(engine.find_saved_video(history),target)
  save(folder/'settings.json',dict(characterId=CHARACTER,width=width,height=height,duration=3,frameCount=item['frames'],workflowId=workflow,samplingMode='quality',
   animationType=action,prompt=item['prompt'],facing='right',motionStrength=item['strength'],motionPadding=padding,generationRevision=revision,pixelOutput=False,combatEffect='none',effectStrength='normal',
   effectDescription='',pixelColorLock=True,loop=item['loop'],stabilize=False,optimizeLoop=False,subjectType='human',blinkMode='none',negativeEnabled=False,
   removeBackground=True,backgroundRemoval='ai',seed=item['seed']))
  release((8189,));print('MOTION_READY',action,flush=True)

def export():
 import av,numpy as np
 from PIL import ImageDraw
 import sprite_gif,sprite_loop
 from tools.sprite_matte import clean_flat_matte
 for action,item in ACTIONS.items():
  folder=OUT/action
  if not (folder/'raw.mp4').exists():continue
  rematte=False
  if (folder/'frames.json').exists():
   review=json.loads((folder/'review.json').read_text(encoding='utf-8')) if (folder/'review.json').exists() else {}
   if review.get('publish') is False:continue
   if json.loads((folder/'frames.json').read_text(encoding='utf-8')).get('backgroundRemoval')==image_background.SPRITE_MATTE_REVISION:continue
   rematte=True
  with av.open(str(folder/'raw.mp4')) as video:frames=[f.to_image().convert('RGBA') for f in video.decode(video=0)]
  cuts=[];diagnostics=[];full=folder/'all-frames';full.mkdir(exist_ok=True)
  for i,raw in enumerate(frames):
   path=full/f'frame-{i:03d}.png'
   if path.exists() and not rematte:cut=Image.open(path).convert('RGBA')
   else:cut=image_background.remove_sprite(raw);cut.save(path)
   a=np.array(cut.getchannel('A'));flat,_=clean_flat_matte(raw,tolerance=24,radius=2)
   old=np.array(flat.getchannel('A'));rgb=np.array(raw)[:,:,:3].astype(float)
   border=np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1]));bg=np.median(border,axis=0)
   enclosed=(old>128)&(np.max(np.abs(rgb-bg),axis=2)<=24)
   diagnostics.append(dict(sourceFrame=i,clearedEnclosedMattePixels=int((enclosed&(a==0)).sum()),edgeContact=bool(a[0].any() or a[-1].any() or a[:,0].any() or a[:,-1].any())))
   cuts.append(cut)
  selected=sprite_loop.sample_indices(len(frames),item['frames'],item['loop'])
  columns=6;rows=(len(selected)+columns-1)//columns
  sheet=Image.new('RGBA',(768*columns,768*rows))
  contact=Image.new('RGB',(384*columns,384*rows),'#252936');draw=ImageDraw.Draw(contact)
  for n,index in enumerate(selected):
   im=cuts[index];im.save(folder/f'frame-{n:02d}.png');sheet.paste(im,(n%columns*768,n//columns*768))
   small=im.resize((384,384),Image.Resampling.LANCZOS);contact.paste(small,(n%columns*384,n//columns*384),small)
   draw.text((n%columns*384+8,n//columns*384+8),str(index),fill='white')
  sheet.save(folder/'sheet.png');contact.save(folder/'contact.webp');cuts[0].save(folder/'poster.png')
  preview=[im.resize((512,512),Image.Resampling.LANCZOS) for im in cuts]
  ticks=[round(i*1000/24) for i in range(len(cuts)+1)];timing=[b-a for a,b in zip(ticks,ticks[1:])]
  preview[0].save(folder/'animation.webp',save_all=True,append_images=preview[1:],duration=timing,loop=0,lossless=True)
  gif,info=sprite_gif.encode(preview,timing);(folder/'animation.gif').write_bytes(gif)
  bounds=[round(int(i)*1000/24) for i in selected]+[round(len(cuts)*1000/24)]
  save(folder/'frames.json',dict(frameWidth=768,frameHeight=768,sourceIndices=[int(i) for i in selected],durationMs=[b-a for a,b in zip(bounds,bounds[1:])],
   previewFrames=len(preview),previewTimingMs=timing,columns=columns,rows=rows,diagnostic=diagnostics,gif=info,backgroundRemoval=image_background.SPRITE_MATTE_REVISION))
  print('EXPORTED',action,flush=True)
if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['reference','motion','export']);a=p.parse_args();globals()[a.stage]()

