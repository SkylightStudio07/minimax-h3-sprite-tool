"""Separate running/raised-sword anchors and time-controlled action tests."""
import argparse,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from PIL import Image
import rigging_engine as rig, image_background, idle_tool as engine
from tools import verify_pixel_minimax as executor
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release
from tools import verify_normal_sprite_refine as base
OUT=ROOT/'outputs/normal-action-snap-20261020'
SOURCE=ROOT/'outputs/normal-sprite-refine-20261020/reference.png'
CASES={
 'run':dict(frames=24,loop=True,strength='high',padding=30,revision='snap-run-v1',seed=2026102092,motionSpeed=1.25,trimAction=False,
  pose='An athletic RUNNING stride toward SCREEN RIGHT. Lean the whole straight torso forward from the ankles, one boot under the hip and the other leg folded behind with its heel lifted high. Near arm bent firmly carrying ONE sword hilt at the waist, blade trails diagonally down and back toward screen LEFT. Far arm is bent at 90 degrees and swings forward, the empty hand is a closed fist. Only one hand grips the sword. Ponytail trails backward. Show a clear side-running silhouette, no standing or two-handed guard.',
  prompt='SPRINT continuously IN PLACE toward SCREEN RIGHT, three energetic alternating running cycles, not walking. Lean the whole torso forward, drive each knee forward then fold the trailing leg sharply behind. There is a clear brief airborne phase between foot contacts. Each boot lands below the hip then pushes backward forcefully. Near hand carries the ONE rigid sword low beside the hip while the empty far arm pumps briskly opposite the legs. Shoulders and pelvis counterrotate, elbows travel, ponytail and skirt whip behind each push-off. Nose looks right throughout; keep the hip centered and camera static. Preserve the exact adult woman, face, costume, colors and illustration style. No slow marching, held upper body, turning toward camera or idle pause. Retain the same running phase and motion through the ending.'),
 'attack':dict(frames=16,loop=False,strength='high',padding=50,revision='snap-slam-v1',seed=2026102093,motionSpeed=2.,trimAction=True,
  pose='A fully LOADED overhead sword strike, facing screen RIGHT. BOTH gloved hands firmly grip ONE sword hilt just above and behind the head; elbows bent, one connected short straight silver blade pointing backward toward screen LEFT above the ponytail. Knees deeply flexed, weight on the rear leg, front boot ahead, chest lifted and spine straight. This is the split second BEFORE a powerful downward smash. No relaxed guard, no sword at waist level. Full body and whole blade within generous white space.',
  prompt='IMMEDIATELY execute ONE explosive downward sword SMASH toward screen RIGHT from the already raised sword pose. No extra preparation or slow lifting. During the first instant the rear leg drives, the front boot stamps down and the hips and shoulders snap together; both hands shoot from above the head sharply DOWN to the front hip. The rigid sword describes one fast steep downward arc, with impact reached almost immediately. Drop the pelvis by bending the knees, brace the front leg and stop the sword low just ahead of the front ankle. Keep the chest up and spine firm: do not bow, slump or hinge at the waist. Elbows fold at the finish. Ponytail and skirt whip violently then settle. One crisp strike only, no repeated swing, fencing thrust, shuffle, jumping or slow motion. Hold a grounded low finish briefly. Same exact adult character, face, outfit and colors, one rigid short sword in both hands, unchanged blade length. Keep the whole blade arc and both boots inside the empty canvas, no effects or camera movement.')}
def references():
 OUT.mkdir(exist_ok=True)
 for action,item in CASES.items():
  folder=OUT/action;folder.mkdir(exist_ok=True)
  if (folder/'reference.png').exists():continue
  ensure_idle();release((8189,8191))
  rgba=Image.open(SOURCE).convert('RGBA');white=Image.new('RGB',rgba.size,'white');white.paste(rgba,mask=rgba.getchannel('A'))
  name='normal_snap_'+action+'.png';white.save(rig.INPUT_ROOT/name)
  graph=rig.qwen21_workflow(name,'normal_snap/'+action,768,20,item['seed']-2)
  graph['6']['inputs'].update(device='cpu',dtype='default')
  graph['5']['inputs']['prompt']=('Edit the exact same adult female anime character into ONE full-body game sprite. Preserve her auburn high ponytail, green eye, cream military jacket, dark teal skirt, opaque dark leggings, brown gloves and boots, original adult proportions, fine cel shaded linework and face. CHANGE ONLY THE POSE: '+item['pose']+' Nose and gaze toward screen RIGHT, side view. All body parts and the entire weapon visible, generous margins, uniform pure WHITE background, no floor, shadow, text, panels or other characters.')
  graph['5']['inputs']['negative_prompt']='front view, facing left, two swords, disconnected weapon, extra limbs, bent spine, pointing fingers, cropped blade, pixel art, chibi, text, scenery'
  executor.OUT=folder
  history=executor.execute(graph,rig.COMFY_URL,'anchor-v1')
  raw=Image.open(rig._saved_image(history,'9')).convert('RGBA');raw.save(folder/'reference-raw.png')
  release((8190,));image_background.remove_sprite(raw).save(folder/'reference.png')
  print('ANCHOR_READY',action,flush=True)
def motion():
 for action in ('attack','run'):
  if action not in CASES:continue
  item=CASES[action]
  # Reuse the existing resumable native executor, with this action's own anchor.
  base.OUT=OUT;base.ACTIONS={action:item}
  shutil.copyfile(OUT/action/'reference.png',OUT/'reference.png')
  base.motion()
  p=OUT/action/'settings.json';data=json.loads(p.read_text(encoding='utf-8'));data.update(motionSpeed=item['motionSpeed'],trimAction=item['trimAction'])
  p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def export():
 import av,numpy as np,math
 from PIL import ImageDraw
 import motion_timing,sprite_gif,sprite_loop
 for action,item in CASES.items():
  folder=OUT/action
  if not (folder/'raw.mp4').exists():continue
  with av.open(str(folder/'raw.mp4')) as clip:native=[f.to_image().convert('RGBA') for f in clip.decode(video=0)]
  width,height=native[0].size
  report=motion_timing.retime_video(folder/'raw.mp4',folder/'motion.mp4',motion_timing.options(dict(item,animationType=action)))
  (folder/'motion_timing.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
  cuts=[];all_folder=folder/'all-frames';all_folder.mkdir(exist_ok=True);diagnostics=[]
  for i,raw in enumerate(native):
   target=all_folder/f'frame-{i:03d}.png'
   if target.exists():cut=Image.open(target).convert('RGBA')
   else:cut=image_background.remove_sprite(raw);cut.save(target)
   a=np.array(cut.getchannel('A'));diagnostics.append(dict(frame=i,edgeContact=bool(a[0].any() or a[-1].any() or a[:,0].any() or a[:,-1].any())))
   cuts.append(cut)
  indices=report['sourceIndices'];shown=[cuts[i] for i in indices]
  # One fixed presentation view across the entire reviewed action.
  boxes=[im.getchannel('A').getbbox() for im in shown];assert all(boxes)
  left,top,right,bottom=min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)
  side=math.ceil(max(right-left,bottom-top)*1.12);x=math.floor((left+right-side)/2);y=math.floor((top+bottom-side)/2);crop=(x,y,x+side,y+side)
  preview=[im.crop(crop).resize((512,512),Image.Resampling.LANCZOS) for im in shown];times=report['durationMs']
  preview[0].save(folder/'animation.webp',save_all=True,append_images=preview[1:],duration=times,loop=0,lossless=True)
  gif,info=sprite_gif.encode(preview,times);(folder/'animation.gif').write_bytes(gif)
  selected=sprite_loop.sample_indices(len(indices),min(item['frames'],len(indices)),item['loop']);source_indices=[indices[i] for i in selected]
  columns=4;rows=math.ceil(len(selected)/columns);sheet=Image.new('RGBA',(width*columns,height*rows));contact=Image.new('RGB',(512*columns,512*rows),'#252936');draw=ImageDraw.Draw(contact)
  for n,j in enumerate(selected):
   im=shown[j];im.save(folder/f'frame-{n:02d}.png');sheet.paste(im,(n%columns*width,n//columns*height));small=preview[j];contact.paste(small,(n%columns*512,n//columns*512),small);draw.text((n%columns*512+8,n//columns*512+8),f'raw {indices[j]} / {sum(times[:j])}ms',fill='white')
  sheet.save(folder/'sheet.png');contact.save(folder/'contact.webp');shown[0].save(folder/'poster.png')
  bounds=[sum(times[:j]) for j in selected]+[sum(times)]
  meta=dict(frameWidth=width,frameHeight=height,sourceIndices=source_indices,durationMs=[b-a for a,b in zip(bounds,bounds[1:])],previewFrames=len(preview),previewSourceIndices=indices,previewTimingMs=times,columns=columns,rows=rows,diagnostic=diagnostics,gif=info,backgroundRemoval=image_background.SPRITE_MATTE_REVISION,previewCropBounds=crop,timing=report)
  (folder/'frames.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
  settings=json.loads((folder/'settings.json').read_text(encoding='utf-8'));settings.update(frameCount=len(selected),motionSpeed=item['motionSpeed'],trimAction=item['trimAction']);(folder/'settings.json').write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding='utf-8')
  print('EXPORTED',action,'native frames',len(native),'shown frames',len(shown),'total ms',report['totalMs'],flush=True)
if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['references','motion','export']);a=p.parse_args();globals()[a.stage]()
