"""Submit the supplied three bosses in order; no step polling or export."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import requests
from PIL import Image
import image_background
import idle_tool as engine
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release

INPUT=Path('C:/Users/SKYLIGHT/Documents/Graduation/Project-Vertex/Assets/Art/Characters/Enemy/Boss/Big Three')
OUT=ROOT/'outputs/big-three-motion-20261024'
STYLE=(
    'Animate the EXACT SAME single character from this reference as a hand-drawn 2D game sprite. '
    'Preserve the original ink contours, cel-painted shadow shapes, costume colors and proportions. '
    'Same SCREEN LEFT facing three-quarter side view, fixed camera, scale and lighting. '
    'No glossy 3D rendering, photorealistic relighting, redesign, camera orbit or full turn. '
    'Existing clothing markings remain attached to their original surfaces; no new text. '
    'Both boots remain at their original ground contact positions, with natural small ankle and knee flexion. '
    'Keep pelvis height mostly steady; no squatting exercise, exaggerated pumping, marching or foot sliding. '
    'Head, shoulders, arms and existing equipment should move in coordinated rounded paths, '
    'not a texture-flickering frozen cutout. ')
CASES=[
    dict(id='01-etienne-vasseur',label='에티엔 바쇠르',padding=20,seed=2026102481,
        identity=(
            'Same adult masked operative in a dark blue-grey suit over a dark plate carrier, black '
            'head-covering respirator mask, bright GREEN visor, charcoal scarf, brown shoulder straps, '
            'belt radio units, dark gloves and brown leather shoes. Keep the one original black '
            'SUPPRESSED PISTOL held in the extended screen-left hand. The opposite hand holds the '
            'original rectangular grey hard briefcase down beside the screen-right thigh. The '
            'case stays CLOSED, intact and hanging from its existing handle throughout. Keep its '
            'brown straps and pale metal corners. No face reveal, new eyes, extra gun, opening '
            'case, changing case into a shield or weapon. The visor is a lens, not a laser cannon. '),
        idle=(
            'A calm threatening pistol-ready IDLE LOOP. Maintain the pistol aimed screen LEFT. '
            'The masked head makes one small purposeful leftward aim check with a gentle tilt, '
            'while the extended wrist and elbow guide the muzzle through a tiny smooth 8-12 pixel '
            'aim correction and back. The shoulder follows with quiet breathing, jacket hem and '
            'scarf settle naturally, and the briefcase makes a very small delayed pendulum sway '
            'from the holding hand. Its handle stays in that hand. Keep the original boot and '
            'leg placement; the body does not bob rhythmically. One continuous three-second '
            'cycle returning to the opening ready pose and motion phase. No firing, flash, '
            'smoke, lowering both arms, case swing attack or looking toward camera.'),
        attack=(
            'Perform ONE controlled TWO-SHOT suppressed pistol attack toward SCREEN LEFT, then '
            'recover. At 0.0-0.5 seconds brace the existing extended pistol arm with a slight '
            'forward shoulder inclination. At 0.5-1.2 seconds fire TWO quick separate shots '
            'from the ACTUAL LEFTMOST TIP of the original suppressor. Each has a very small '
            'brief orange muzzle flash and a tiny recoil kick followed by an immediate return '
            'to aim. Keep the suppressor rigid and attached, and the trigger hand on the grip. '
            'Elbow, shoulder and torso naturally absorb both impulses. The briefcase stays '
            'down in the opposite hand, making only a tiny secondary sway. At 1.2-3.0 seconds '
            'settle back to the original extended leftward aim and original stance. No reload, '
            'case opening, giant fireball, laser from the green visor, teleport or new props.')),
    dict(id='02-desmond-kilroy',label='데즈먼드 킬로이',padding=20,seed=2026102483,
        identity=(
            'Same adult soldier with tan digital-camouflage uniform, tan plate carrier and belt '
            'pouches, tan helmet with original folded twin night-vision tubes, ear protection, '
            'black full-face gas mask with RED lens, tan knee pads and tactical boots. Preserve '
            'the original rifle and attached long suppressor, optic and grip. Both gloved '
            'hands stay on their original rifle grip points. Keep the old pale enamel mug '
            'hanging from the screen-right hip, existing shoulder patches and waist equipment. '
            'The helmet and mask always cover the face; no new facial features, new weapon, '
            'changed barrel count or muzzle firing from the red mask lens. '),
        idle=(
            'A quiet alert LOW-READY IDLE LOOP. Keep the rifle directed diagonally DOWN-LEFT '
            'near its original low-ready angle. The masked head slowly checks a small leftward '
            'sector, then returns; shoulders and elbows make one subtle coordinated correction '
            'of the rigid rifle, about 10-15 pixels at its muzzle. The support hand remains on '
            'the fore-end, trigger hand on the grip. Gentle breathing and small cloth follow-through, '
            'the hip mug moves slightly with its attachment. Keep pelvis and both boot contacts '
            'steady, no knee-pumping workout, marching, repeated large gun raising or scanning '
            'toward camera. One three-second cycle smoothly matching the initial low-ready pose. '
            'No shooting, muzzle flash, smoke, reload, helmet change or detached equipment.'),
        attack=(
            'Raise the existing rifle from the original diagonal down-left low ready, fire ONE '
            'SHORT THREE-ROUND BURST toward SCREEN LEFT and return. At 0.0-0.7 seconds both '
            'hands lift the SAME rigid rifle to the shoulder, muzzle now aimed approximately '
            'horizontal LEFT, with stock pressed into the shoulder and elbows naturally bent. '
            'The head follows the optic without removing the mask. At 0.7-1.4 seconds fire '
            'three quick small separate orange flashes precisely from the actual suppressor '
            'TIP. Rifle recoil travels backward into the shoulder, with slight muzzle rise, '
            'elbow give and coordinated forward body bracing. Both feet remain planted. At '
            '1.4-3.0 seconds stop firing, let the tiny smoke disappear and lower the rifle '
            'smoothly to its original diagonal low-ready pose. No new rifle, reloading, long '
            'laser beam, huge explosion, firing from the mask, magazine swap or face reveal.')),
    dict(id='03-van-rieden',label='반 리든',padding=20,seed=2026102485,
        identity=(
            'Same mature white-bearded hunter, stern left-facing profile, swept-back grey hair, '
            'wide tan safari hat with leopard-print hatband, cigar held at the mouth corner, '
            'leopard-pattern shoulder cape with long trailing panel, tan safari shirt and '
            'trousers, crossed brass ammunition belts, chest medals, brown gloves and tall '
            'dark green-black boots. Keep the original gold-topped long cane in the extended '
            'screen-left hand, tip planted at its original spot. The other gloved hand rests '
            'beside the original silver REVOLVER in the brown hip holster. The original '
            'wood-stock long rifle remains SLUNG ON THE BACK throughout; do not draw it. '
            'Keep hat, cape, cane, holster, beard and cigar intact; no younger face, new '
            'weapon, changed outfit or extra arms. '),
        idle=(
            'A composed veteran hunter IDLE LOOP. He keeps the cane tip firmly planted and '
            'makes one slight deliberate head inclination while watching screen LEFT. '
            'Small chest breathing, a quiet shift in the cane hand pressure and subtle '
            'finger movement beside the holstered revolver. The leopard cape settles '
            'with a little delayed cloth movement and the slung rifle follows the back '
            'as a rigid object. A very small thin cigar-smoke curl rises from the actual '
            'cigar tip and dissipates, never a frozen painted cloud. No bobbing body, '
            'exercise, walking, cane twirling, gun draw, shooting or exaggerated cigar '
            'puff. Return to the same opening stance after one unhurried three-second cycle.'),
        attack=(
            'Perform ONE revolver QUICK-DRAW SHOT toward SCREEN LEFT while the opposite '
            'hand keeps the original cane planted. At 0.0-0.7 seconds the gloved hand beside '
            'the brown hip holster grasps and draws the EXISTING SILVER REVOLVER, lifting '
            'the barrel toward screen LEFT. Cane hand never lets go of its handle. At '
            '0.7-1.1 seconds extend the revolver arm across the front of the body and fire '
            'ONE shot, a compact orange flash at the actual revolver BARREL TIP. Small '
            'wrist rise and elbow recoil, chest counter-rotation and restrained shoulder '
            'follow-through; hat and bearded head remain facing left. At 1.1-3.0 seconds '
            'lower and return that same revolver to its original holster, settling into '
            'the original cane-supported ready stance. Keep the back rifle slung and '
            'motionless relative to the back. No firing cane, sword, added gun, hat removal, '
            'giant smoke cloud, repeated shots, stepping, spin or camera movement.')),
]

def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def prepare(case):
    folder=OUT/case['id'];folder.mkdir(parents=True,exist_ok=True)
    source=INPUT/(case['label']+'.png');assert source.is_file()
    if not (folder/'source-original.png').exists():shutil.copy2(source,folder/'source-original.png')
    assert digest(source)==digest(folder/'source-original.png')
    if not (folder/'reference.png').exists():
        image=Image.open(source).convert('RGBA')
        cleaned=image_background.remove(image)
        pixels=np.array(cleaned);pixels[pixels[:,:,3]<16]=0;cleaned=Image.fromarray(pixels)
        box=cleaned.getchannel('A').getbbox();assert box
        cropped=cleaned.crop(box)
        padded=Image.new('RGBA',(cropped.width+64,cropped.height+64));padded.paste(cropped,(32,32))
        padded.save(folder/'reference.png')
        save(folder/'source.json',dict(sourcePath=str(source),sourceSha256=digest(source),sourceUnchanged=True,
            referenceSha256=digest(folder/'reference.png'),cropBounds=list(box),
            preparation='CPU semantic alpha limited by original alpha, alpha<16 discarded, crop and 32px transparent border. Original foreground RGB retained; no generative redraw.',published=False))
    return folder

def main():
    OUT.mkdir(exist_ok=True)
    folders={c['id']:prepare(c) for c in CASES}
    needed=any(not (folders[c['id']]/a/'native-v1-pending.json').exists() for c in CASES for a in ['idle','attack'])
    if needed:ensure_idle();engine.start_comfy();release((8190,8191))
    records=[]
    for case in CASES:
        casefolder=folders[case['id']]
        for action in ['idle','attack']:
            folder=casefolder/action;folder.mkdir(exist_ok=True);pending=folder/'native-v1-pending.json'
            if pending.exists():
                records.append(dict(case=case['id'],label=case['label'],action=action,**json.loads(pending.read_text(encoding='utf-8'))));continue
            prepared=engine.prepare_reference_image((casefolder/'reference.png').read_bytes(),768,768,case['padding'])
            (folder/'reference-prepared.png').write_bytes(prepared)
            uploaded=engine.upload_image(prepared,case['id']+'-'+action+'.png')
            prompt=STYLE+case['identity']+case[action]+(
                ' Uniform flat medium-GREY extraction matte in every empty gap, including between '
                'legs, arms, equipment and weapons. No floor, cast shadow, white sticker border, '
                'scenery or additional characters. Entire hat, weapon muzzle, cane tip, briefcase, '
                'boots and compact effects stay INSIDE the canvas with a clear safety margin.')
            seed=case['seed']+(action=='attack');strength='normal' if action=='idle' else 'high'
            graph=engine.build_workflow(uploaded,prompt,3,768,768,seed,animation_type='custom',
                loop=action=='idle',facing='left',flat_background=True,blink_mode='none',
                motion_strength=strength,sampling_mode='quality',workflow_id='standard',subject_type='human')
            graph['10']['inputs']['steps']=40
            graph['6']['inputs']['prompt']=graph['6']['inputs']['prompt'].replace(
                engine.FACING_PROMPTS['left'],
                'Head and gaze remain screen LEFT in the original three-quarter camera. Allow natural coordinated shoulder, torso, elbow and wrist articulation; no full view turn toward the viewer.')
            if action=='idle':
                graph['6']['inputs']['prompt']=graph['6']['inputs']['prompt'].replace(
                    engine.MOTION_PROMPTS['normal'],
                    'Quiet purposeful head and arm adjustments, small breathing and delayed cloth motion. Pelvis height and boot contacts remain steady; no exercise-like knee pumping.')
            graph['15']['inputs'].pop('audio',None);graph.pop('14',None);graph.pop('5',None)
            prefix='big_three_motion_20261024/'+case['id']+'/'+action
            graph['16']['inputs']['filename_prefix']=prefix
            save(folder/'native-v1-workflow.json',graph)
            save(folder/'settings.json',dict(animationType=action,generationPromptType='custom',subjectType='human',
                caseId=case['id'],label=case['label'],seed=seed,width=768,height=768,duration=3,fps=24,steps=40,
                loop=action=='idle',facing='left',motionPadding=case['padding'],referenceOffsetX=0,
                motionStrength=strength,workflowId='standard',samplingMode='quality',prompt=prompt,
                actualPrompt=graph['6']['inputs']['prompt'],sourceSha256=digest(casefolder/'source-original.png'),
                referenceSha256=digest(casefolder/'reference.png'),outputPrefix=prefix,
                backgroundRemoval='deferred until user requests it',published=False))
            signature=hashlib.sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest()
            response=requests.post(engine.COMFY_URL+'/prompt',json=dict(prompt=graph),timeout=60)
            if not response.ok:raise RuntimeError(response.text[:2000])
            info=response.json();record=dict(signature=signature,promptId=info['prompt_id'],queueNumber=info.get('number'))
            save(pending,record);records.append(dict(case=case['id'],label=case['label'],action=action,**record))
            save(OUT/'generation-submissions.json',dict(comfyUrl=engine.COMFY_URL,outputRoot=str(ROOT/'outputs/comfy'),
                records=records,requestedNativeResolution=[768,768],steps=40,progressPolling=False,
                backgroundRemovalDeferred=True,order='attachment order, idle then attack for each'))
            print('SUBMITTED',case['id'],action,record['promptId'],flush=True)
    assert len(records)==6
    print('ALL_SIX_SUBMITTED_NO_POLLING',flush=True)

if __name__=='__main__':main()
