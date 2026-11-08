"""Submit both CP02 motions, record IDs, and return without progress polling."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import requests
from PIL import Image
import idle_tool as engine
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release

SOURCE=Path('C:/Users/SKYLIGHT/Documents/Graduation/Project-Vertex/Assets/Art/Characters/Joining Characters/CP_02/ecc01147-ddc0-4694-b8f1-76c26f8a5fec.png')
OUT=ROOT/'outputs/cp02-grounded-motion-20261024'
IDENTITY=(
    'Animate the EXACT SAME single adult female armored polearm-and-shield fighter in the input '
    '2D anime illustration. Keep the same face, purple eye and short dark indigo bob with cyan '
    'underside, white long-sleeve shirt, black tie, fitted grey military tailcoat with gold '
    'epaulettes and braided cords, white pleated short skirt, silver gauntlets and tall silver '
    'armored boots. Keep ONE original rigid long black-shafted polearm with the large silver '
    'spear blade and black cog cluster immediately below its blade in the SAME original weapon '
    'hand, and ONE original tall curved dark shield with metal rim and rivets in the other hand. '
    'The gears and spearhead remain attached as one rigid weapon assembly. Keep the two original '
    'white gear ornaments trailing behind her hair on their existing cords. These are attached '
    'ornaments, never new weapons. Same SCREEN-RIGHT-facing three-quarter side view, face and '
    'gaze right, no turn toward viewer. Preserve original body proportions, ink contours, '
    'flat painted cel shadows and colours in EVERY frame; no 3D render or realistic relighting. '
    'Exactly two arms and two legs; no extra hands, shield, blade or weapon swapping. ')
ACTIONS={
    'idle':dict(seed=2026102441,loop=True,strength='normal',prompt=(
        'A quiet grounded defensive IDLE LOOP in the exact original stance with BOTH BOOTS '
        'planted at their original ground spots. Keep the head, hips and knees at nearly '
        'constant height. No squats, bouncing, marching or raised leg. She watches screen '
        'RIGHT over the top side of the original tall shield. Make ONE small purposeful '
        'shield-angle check by bending the shield elbow slightly, then return. The weapon '
        'hand makes a small smooth wrist-and-elbow adjustment, lowering the original spear '
        'tip a FEW DEGREES and returning to its upward-right starting angle. Only about '
        '8-14 pixels of spear-tip motion at 768px, no broad sweep or weapon spin. The spear '
        'shaft, gears and blade move as ONE rigid object at fixed length, same grip. The '
        'shield stays curved and constant in size. Small shoulder movement and a slight '
        'head inclination follow the defensive check; shallow breathing without torso '
        'inflation. Short hair tips, coat tails, gold cords and the two white hair ornaments '
        'sway softly with delayed follow-through. Keep the body and feet stable and make '
        'the life come from small purposeful guard adjustments, not a whole-image wobble. '
        'One unhurried check over three seconds; close in the same original pose and phase. '
        'No attack, step, jump, knee lifting, speaking, glow or face turn toward camera.')),
    'attack':dict(seed=2026102442,loop=False,strength='high',prompt=(
        'Perform exactly ONE forceful SHIELD-GUARDED SPEAR LUNGE toward SCREEN RIGHT, '
        'with readable preparation, fast committed thrust and smooth recovery. At 0.0-0.6 '
        'seconds briefly draw the spear hand back beside the ribs and rotate the shoulders '
        'a little rearward, lowering the spear from its opening diagonal into a nearly '
        'horizontal line aimed RIGHT. Keep the spearhead IN FRONT of the body throughout '
        'the windup; do not lift it over the head or behind the back. The shield stays '
        'forward in its original hand, guarding the torso without covering her face. '
        'At 0.6-1.2 seconds push from the rear boot, plant ONE short forward step with the '
        'lead boot, rotate hips and shoulders forward together and sharply extend the '
        'spear arm into a powerful straight thrust to SCREEN RIGHT. The front knee bends '
        'ONCE to accept the lunge. Whole body and both arms participate naturally; no '
        'wooden arm twitch, deep bow or collapsing spine. Keep the body translation '
        'compact, about 15-25 pixels, and spearhead travel about 50-75 pixels at 768px. '
        'The long black shaft remains STRAIGHT and rigid, with the original blade and '
        'black cog cluster firmly attached and the hand fixed to its grip. The shield '
        'arm braces and counterbalances; the shield retains its original size and shape. '
        'At 1.2-3.0 seconds retract the spear, straighten the front knee naturally and '
        'recover to the original BOTH-FEET-GROUNDED shield guard and upward-right spear '
        'angle. Hair, coat tails and trailing ornaments follow the acceleration then '
        'settle. ONE attack only, no second thrust, slash, overhead windmill, full spin, '
        'jump, raised-knee hopping or repeated bouncing. No energy beam, big slash wave, '
        'victim or blood. Keep the full spearhead, shaft butt, shield and boots INSIDE '
        'the canvas through the whole motion, with empty margins.'))}



def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=True)
    if not (OUT/'source-original.png').exists():shutil.copy2(SOURCE,OUT/'source-original.png')
    assert digest(SOURCE)==digest(OUT/'source-original.png')
    if not (OUT/'reference.png').exists():
        im=Image.open(SOURCE).convert('RGBA');box=im.getchannel('A').getbbox();assert box
        im=im.crop(box);canvas=Image.new('RGBA',(im.width+64,im.height+64));canvas.paste(im,(32,32));canvas.save(OUT/'reference.png')
    save(OUT/'source.json',dict(sourcePath=str(SOURCE),sourceSha256=digest(SOURCE),sourceUnchanged=True,
        referenceSha256=digest(OUT/'reference.png'),preparation='Alpha bounding crop and 32px transparent border; no repainting.',published=False))
    pending_all=all((OUT/name/'native-v1-pending.json').exists() for name in ACTIONS)
    if not pending_all:ensure_idle();engine.start_comfy();release((8190,8191))
    records=[]
    for name,item in ACTIONS.items():
        folder=OUT/name;folder.mkdir(exist_ok=True);pending=folder/'native-v1-pending.json'
        if pending.exists():
            records.append(dict(action=name,**json.loads(pending.read_text(encoding='utf-8'))));continue
        prepared=engine.prepare_reference_image((OUT/'reference.png').read_bytes(),768,768,50)
        (folder/'reference-prepared.png').write_bytes(prepared)
        uploaded=engine.upload_image(prepared,'cp02-grounded-'+name+'.png')
        prompt=IDENTITY+item['prompt']+' Fixed camera, constant scale and lighting. Uniform flat neutral medium-grey matte in every empty gap; no floor, cast shadow, scenery, text or additional people. Entire character, spear, shield and attached ornaments stay within the canvas.'
        graph=engine.build_workflow(uploaded,prompt,3,768,768,item['seed'],animation_type='custom',
            loop=item['loop'],facing='preserve',flat_background=True,blink_mode='none',motion_strength=item['strength'],
            sampling_mode='quality',workflow_id='standard')
        graph['10']['inputs']['steps']=40
        text=graph['6']['inputs']['prompt'].replace(engine.FACING_PROMPTS['preserve'],
            'The nose and gaze stay SCREEN RIGHT in the same three-quarter side view. Allow natural shoulder, elbow and wrist articulation without a full turn toward the viewer.')
        if name=='idle':text=text.replace(engine.MOTION_PROMPTS['normal'],
            'Small purposeful guard adjustments in the arms and head, with gentle hair and coat follow-through. Keep pelvis height and leg pose steady; no body pumping or marching.')
        graph['6']['inputs']['prompt']=text
        graph['15']['inputs'].pop('audio',None);graph.pop('14',None);graph.pop('5',None)
        prefix='cp02_grounded_20261024/'+name;graph['16']['inputs']['filename_prefix']=prefix
        save(folder/'native-v1-workflow.json',graph)
        save(folder/'settings.json',dict(animationType=name,generationPromptType='custom',seed=item['seed'],
            width=768,height=768,duration=3,fps=24,steps=40,loop=item['loop'],facing='right',motionPadding=50,
            referenceOffsetX=0,motionStrength=item['strength'],workflowId='standard',samplingMode='quality',
            prompt=prompt,actualPrompt=text,sourceSha256=digest(SOURCE),referenceSha256=digest(OUT/'reference.png'),
            outputPrefix=prefix,backgroundRemoval='deferred until user requests it',published=False))
        signature=hashlib.sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest()
        response=requests.post(engine.COMFY_URL+'/prompt',json=dict(prompt=graph),timeout=60)
        if not response.ok:raise RuntimeError(response.text[:2000])
        info=response.json();record=dict(signature=signature,promptId=info['prompt_id'],queueNumber=info.get('number'))
        save(pending,record);records.append(dict(action=name,**record));print('SUBMITTED',name,record['promptId'],flush=True)
    save(OUT/'generation-submissions.json',dict(comfyUrl=engine.COMFY_URL,outputRoot=str(ROOT/'outputs/comfy'),
        records=records,progressPolling=False,backgroundRemovalDeferred=True))
    print('BOTH_MOTIONS_SUBMITTED_NO_POLLING',flush=True)


if __name__=='__main__':main()
