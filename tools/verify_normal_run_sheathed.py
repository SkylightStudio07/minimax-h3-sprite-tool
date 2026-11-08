"""Hands-free sprint comparison using a visibly sheathed weapon."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from PIL import Image
import rigging_engine as rig,image_background
from tools import verify_normal_action_snap as snap
SOURCE=snap.OUT/'run/reference.png'
snap.OUT=ROOT/'outputs/normal-run-sheathed-20261020'
snap.CASES={'run':dict(frames=24,loop=True,strength='high',padding=20,revision='run-sheathed-v1',seed=2026102096,
 width=512,height=512,workflowId='fasth3-sprite',motionSpeed=1.5,trimAction=False,prompt=(
 'Run vigorously IN PLACE toward screen RIGHT with alternating long running strides and a short airborne phase between contacts. '
 'The sword is fully SHEATHED and firmly strapped to the waist belt; the hilt and scabbard move rigidly with the pelvis. Both hands are EMPTY closed fists. '
 'Pump BOTH bent arms forward and backward opposite their corresponding legs. Drive one knee forward while the opposite heel folds behind, then SWITCH legs completely. '
 'Each foot lands underneath the hip, pushes back, lifts and passes forward; neither leg stays permanently in front. '
 'Lean the torso forward and counterrotate the shoulders and hips, with rhythmic small vertical rise and fall. Ponytail and skirt whip after each push-off. '
 'Maintain the exact same adult woman, face, costume, colors and cel shading, rightward gaze and static side-view camera. '
 'No drawing the weapon, sword in hands, hopping on one foot, skating, walking, pauses or camera motion. Continue a clear alternating gait throughout the ending.'))}
def reference():
 snap.OUT.mkdir(exist_ok=True);folder=snap.OUT/'run';folder.mkdir(exist_ok=True)
 if (folder/'reference.png').exists():return
 snap.ensure_idle();snap.release((8189,8191))
 raw=Image.open(SOURCE).convert('RGBA');white=Image.new('RGB',raw.size,'white');white.paste(raw,mask=raw.getchannel('A'));name='normal_run_sheathed.png';white.save(rig.INPUT_ROOT/name)
 graph=rig.qwen21_workflow(name,'normal_run_sheathed/reference',768,20,2026102095);graph['6']['inputs'].update(device='cpu',dtype='default')
 graph['5']['inputs']['prompt']=('Keep the EXACT same adult female character, auburn ponytail, green eye, cream jacket, dark teal skirt, dark leggings, brown boots and gloves, anime linework and the same full-body RUNNING pose facing RIGHT. CHANGE THE WEAPON AND HANDS ONLY: the sword is now fully inserted inside a straight DARK BROWN SCABBARD firmly attached to the waist belt, trailing down behind the hip. NO exposed silver blade. The decorated hilt sticks out just above the belt. Both hands are EMPTY CLOSED FISTS, bent elbows held in a natural running arm swing; no hand touches the sword. Retain the forward torso lean, raised bent knee and folded rear leg. Keep the same scale, body placement and clothing. Whole body, both boots and whole scabbard inside generous margins. Uniform pure WHITE background, no floor, no shadow, no text.')
 graph['5']['inputs']['negative_prompt']='drawn sword, bare blade, sword in hand, extra weapon, altered outfit, front view, facing left, cropped, pixel art, text'
 snap.executor.OUT=folder;record=snap.executor.execute(graph,rig.COMFY_URL,'sheathed-anchor-v1')
 raw=Image.open(rig._saved_image(record,'9')).convert('RGBA');raw.save(folder/'reference-raw.png');snap.release((8190,));image_background.remove_sprite(raw).save(folder/'reference.png');print('SHEATHED_REFERENCE_READY',flush=True)
if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['reference','motion','export']);a=p.parse_args()
 if a.stage=='reference':reference()
 else:getattr(snap,a.stage)()
