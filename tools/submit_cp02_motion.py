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

SOURCE=Path('C:/Users/SKYLIGHT/Documents/Graduation/Project-Vertex/Assets/Art/Characters/Joining Characters/CP_02/3e156965-dd93-4aa9-b4e7-aa2f9bd8814e.png')
OUT=ROOT/'outputs/cp02-polearm-motion-20261024'
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
    'idle':dict(seed=2026102431,loop=True,strength='normal',prompt=(
        'A restrained purposeful guard-check IDLE LOOP in the supplied pose. Maintain the '
        'original supporting leg and the bent raised knee at nearly constant heights. Do not '
        'pump up and down, squat, march, kick or bounce. The shield stays forward-right covering '
        'the torso with its original curve and size. Make one small defensive shield-angle '
        'adjustment with the shield elbow, then return. The spear hand and elbow make a small '
        'smooth aim correction, moving the long spear tip a few degrees down-right and back '
        'to its original upward-right angle, never spinning the polearm. Both grips stay attached '
        'and the long shaft stays straight at constant length. A small head inclination follows '
        'the guarded aim; body height stays steady. The short hair tips, coat tails, gold cords '
        'and trailing white gear ornaments sway softly with delayed follow-through, not a rigid '
        'whole-image wobble. Small shallow breathing in the shoulders without chest inflation. '
        'One unhurried check in three seconds, naturally closing at the original pose. '
        'No attack, step, jump, speaking, glowing effects or costume transformation.')),
    'attack':dict(seed=2026102432,loop=False,strength='high',prompt=(
        'Perform exactly ONE powerful POLEARM SWEEP toward SCREEN RIGHT and recover. Not a '
        'static arm twitch or simple forward poke. At 0.0-0.6 seconds draw the polearm hand '
        'back and raise the spearhead slightly above and behind the right shoulder as a windup, '
        'rotating the shoulders and hips naturally. Keep the shield forward-right protecting '
        'the chest, never covering the face. At 0.6-1.3 seconds plant the bent raised foot into '
        'one short forward supporting step, transfer weight toward screen right and drive the '
        'same rigid polearm in ONE fast diagonal downward-forward sweeping cut toward empty '
        'space on the RIGHT. The torso, shoulder and weapon arm clearly participate, spine '
        'upright and balanced. Shield arm counterbalances without dropping or growing the '
        'shield. The spear is long and rigid, never a flexible whip or short sword. Its original '
        'blade and cog cluster follow the shaft as one assembly at fixed length. One narrow '
        'brief pale cyan motion trace follows the silver blade for the strike only; modest '
        'and smaller than the torso, no giant fireball hiding the weapon. Hair, coat tails '
        'and trailing hair ornaments follow the acceleration, then settle. At 1.3-3.0 seconds '
        'recover the original right-facing shield guard and upward-right spear angle. One '
        'sweep only, no repeated combo, full spin, running, jump, deep waist bow, victim or '
        'blood. Keep the COMPLETE spearhead, polearm butt, shield and both feet inside the '
        'canvas with clear margins through the entire action.'))}


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
        prepared=engine.prepare_reference_image((OUT/'reference.png').read_bytes(),768,768,40)
        (folder/'reference-prepared.png').write_bytes(prepared)
        uploaded=engine.upload_image(prepared,'cp02-polearm-'+name+'.png')
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
        prefix='cp02_polearm_20261024/'+name;graph['16']['inputs']['filename_prefix']=prefix
        save(folder/'native-v1-workflow.json',graph)
        save(folder/'settings.json',dict(animationType=name,generationPromptType='custom',seed=item['seed'],
            width=768,height=768,duration=3,fps=24,steps=40,loop=item['loop'],facing='right',motionPadding=40,
            referenceOffsetX=0,motionStrength=item['strength'],workflowId='standard',samplingMode='quality',
            prompt=prompt,actualPrompt=text,sourceSha256=digest(SOURCE),referenceSha256=digest(OUT/'reference.png'),
            outputPrefix=prefix,backgroundRemoval='deferred until user requests it',published=False))
        signature=hashlib.sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest()
        response=requests.post(engine.COMFY_URL+'/prompt',json=dict(prompt=graph),timeout=60)
        if not response.ok:raise RuntimeError(response.text[:2000])
        info=response.json();record=dict(signature=signature,promptId=info['prompt_id'],queueNumber=info.get('number'))
        save(pending,record);records.append(dict(action=name,**record));print('SUBMITTED',name,record['promptId'],flush=True)
    save(OUT/'generation-submissions.json',dict(comfyUrl=engine.COMFY_URL,outputRoot=str(engine.COMFY_ROOT/'output'),
        records=records,progressPolling=False,backgroundRemovalDeferred=True))
    print('BOTH_MOTIONS_SUBMITTED_NO_POLLING',flush=True)


if __name__=='__main__':main()
