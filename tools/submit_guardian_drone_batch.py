"""Queue four supplied enemies in attachment order: idle then attack for each.

Submit only, with resumable prompt IDs. No progress polling or alpha export.
"""
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
from scipy import ndimage
import idle_tool as engine
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release

INPUT=Path('Z:/Vertex/적/NAI-images_(2026-09-08_16-39-14)_1-of-1')
OUT=ROOT/'outputs/guardian-drone-batch-20261024'
STYLE=(
    'Animate the EXACT SAME single subject in the supplied illustration. Retain its original '
    '2D ink contours, painted shadows, materials, proportions and colors in every frame. '
    'No new 3D render, photorealistic relighting, camera orbit or redesign. Keep the same '
    'screen-LEFT-facing three-quarter view, constant camera, magnification and lighting. '
    'Existing markings stay attached to their original plates; no new text or decals. '
    'Only animate structures already present. The articulated silhouette may change '
    'naturally, but rigid plates and crystals never inflate, melt, bend or stretch. ')
CASES=[
    dict(id='01-crystal-guardian',label='결정 수호자',file='0.2__artist_crimson comics___0.6__artist_dramz__, _0.5__artist_santa (sunflower) s-3063203790.png',padding=40,seed=2026102461,
        identity=(
            'This is the same floating ivory-armored crystal guardian with its angular closed '
            'helmet-like head facing upper-left, tall magenta crystal crown, red glowing core '
            'inside the dark round chest cavity, large ivory shards projecting behind the head '
            'and shoulders and two original enormous suspended armored forearms. The forearm '
            'on the LEFT of the picture has the same broad dark shield-like outer face and '
            'ivory rim; the other forearm on the RIGHT has the same magenta crystal spines '
            'and long hooked ivory claws. Keep the original tapered ivory torso and black '
            'internal connections. Small existing ivory fragments float near the same shoulder '
            'area. Preserve all these part counts and their relative arrangement. The core '
            'is a red energy cavity, not a mouth or human face. The construct hovers: no new '
            'legs, feet, wheels, head, wings, hands or weapons. '),
        idle=(
            'A slow guarded HOVER IDLE LOOP. Maintain the original floating pose with only '
            'about 6-10 pixels of smooth collective vertical drift and a small suspended '
            'forearm adjustment. The left shield-like forearm tilts inward a few degrees '
            'then returns; right hooked claws make one small closing/opening adjustment '
            'without changing length or number. Existing separated shoulder shards drift '
            'a few pixels and settle to the original arrangement. The red chest energy '
            'circulates subtly within its original cavity, with a small restrained brightness '
            'variation and tiny moving red sparks, never an expanding chest or constant '
            'painted beam stuck in screen space. One unhurried defensive check in three '
            'seconds, gently returning to the reference pose and motion phase. No attack, '
            'walking, rapid pumping, giant effects, ground contact or scenery.'),
        attack=(
            'Perform ONE heavy LEFTWARD SHIELD-FOREARM BASH, then recover the floating guard. '
            'During the first 0.5 seconds draw the existing large dark-faced forearm on the '
            'LEFT side of the image slightly back toward the torso, tilting its shield face '
            'toward the empty space at screen LEFT. At 0.5-1.1 seconds drive that SAME rigid '
            'forearm forward-left in one powerful compact battering shove, about 45-65 '
            'pixels of forearm travel on the 768px canvas, with the central torso pitching '
            'slightly forward as a coherent counterweight. The other crystal-spined hooked '
            'forearm stays close as a guard. The red core flares briefly inside its cavity '
            'and existing loose shards lag behind the acceleration. One short narrow red '
            'impact spark at the leading shield rim is enough, no giant beam or explosion. '
            'At 1.1-3.0 seconds draw the forearm back and recover the exact original floating '
            'stance. ONE attack, no full spin, second bash, limb detachment, walking, new '
            'anatomy or victim. Keep every armor edge, crown shard and hooked claw inside '
            'the frame with clear margins.')),
    dict(id='02-defensive-guardian',label='관문 수호자 · 방어형',file='관문 수호자_방어형.png',padding=40,seed=2026102463,
        identity=(
            'This is the same floating defensive gate guardian, with angular ivory shell '
            'plates around a dark mechanical interior, the original helmet-like head looking '
            'LEFT, large magenta crystal spines rising behind the shoulders and the red '
            'star-like energy core centered in its black chest cavity. Keep its TWO existing '
            'massive suspended forearms and original joint connections: the smaller forearm '
            'on the LEFT side ends in dark plates and curled magenta crystal claws, while '
            'the huge ivory-crystal armored forearm on the RIGHT ends in the same long '
            'magenta claw tips. Same tapered central armor under the core, same floating '
            'ivory fragments and soft violet edge wisps. This construct hovers; no invented '
            'legs, feet, wings, handheld weapons, exposed human face or additional limbs. '),
        idle=(
            'A restrained DEFENSIVE HOVER IDLE LOOP. The rigid central assembly makes one '
            'slow smooth 6-10 pixel hover adjustment without bouncing. The huge forearm on '
            'the RIGHT side tilts slightly inward to cover more of the chest, then returns '
            'to its original position. The left curled crystal-claw forearm adjusts slightly '
            'as a counterbalance. Original hard claw segments stay constant in number and '
            'length. Small original floating ivory fragments make a slow tiny orbit near '
            'their own starting positions. Violet wisps drift gently and red currents turn '
            'inside the same fixed-size core, never a rigid glowing sticker. Keep the core '
            'center visible and its cavity shape fixed. Return smoothly to the opening '
            'arrangement after one unhurried cycle. No attack, walking, rapid arm flapping, '
            'extreme core pulse, floor, cast shadow or environment.'),
        attack=(
            'Perform exactly ONE compact CRYSTAL-CLAW STRIKE toward SCREEN LEFT, followed '
            'by recovery. At 0.0-0.6 seconds draw the original LEFT-side dark forearm and '
            'its curled magenta claws slightly up and back beside the torso. The much '
            'larger RIGHT-side ivory forearm braces close to the chest as a defensive '
            'shield and keeps its original claw tips. At 0.6-1.2 seconds deliver ONE '
            'quick downward-forward claw rake toward empty space at screen LEFT, using '
            'the original left forearm joints and a small forward torso inclination. '
            'Compact arc and only 45-65 pixels of forward claw travel at 768px. Rigid '
            'ivory plates and magenta claws keep their form and stay connected. A narrow '
            'brief magenta trace follows only the attacking claw tips; no screen-filling '
            'energy wave. Red core brightens briefly within its existing cavity as the '
            'other arm guards. At 1.2-3.0 seconds retract the attacking arm and return '
            'to the original floating defensive stance, wisps and fragments settling. '
            'One strike only, no spinning, two-handed giant sweep, new weapon, limb '
            'duplication, exploding armor, victim or background. Whole subject stays '
            'inside the canvas, including the highest crystals and longest claws.')),
    dict(id='03-heavy-gun-drone',label='중형 비행 포대',file='0.2__artist_crimson comics___0.6__artist_dramz__, _0.5__artist_santa (sunflower) s-1422223565.png',padding=40,seed=2026102465,
        identity=(
            'The exact same bulky dark charcoal armored hovering gun drone from the image: '
            'wide angular wedge hull, red circular sensor at the forward LEFT nose, small '
            'cyan window on the raised roof module, the original thin roof-mounted gun '
            'pointing left, original rear antenna arrangement and existing white company '
            'decals. Keep the TWO original heavy articulated gun pods suspended beneath '
            'the hull. Each retains its original multiple bronze-toned parallel barrels '
            'with black muzzle tips. Preserve each pod shape and barrel count exactly '
            'as visible; the muzzles point diagonally DOWN-LEFT along their ORIGINAL '
            'camera-relative axes. The FRONT RED CIRCULAR DEVICE IS A SENSOR, not a cannon. '
            'No legs, feet, wheels, rotor, human pilot or new weapons. '),
        idle=(
            'A steady HOVER IDLE LOOP, same left-facing three-quarter camera. The entire '
            'rigid hull rises and falls slowly only about 6-10 pixels on the 768px canvas. '
            'The two existing lower gun mounts make very small coordinated gimbal '
            'corrections while the barrels stay straight, parallel, constant length '
            'and aimed down-left. Roof gun, antennae and decals remain rigidly attached '
            'to the hull. Red forward sensor glow changes only faintly; any existing '
            'red scan wisp follows the sensor rather than staying frozen on screen. '
            'One calm hover cycle with the same opening and closing pose and phase. '
            'No shooting, recoil, smoke, big light pulses, body stretching, camera '
            'movement, ground, floor shadow or new background.'),
        attack=(
            'Fire ONE SHORT CANNON BURST from the TWO EXISTING LOWER GUN PODS along '
            'their original diagonal DOWN-LEFT axes, then return to the hover guard. '
            'At 0.0-0.5 seconds the mounts brace and the hull stabilizes at its original '
            'height. At 0.5-1.3 seconds the lower pods fire three short alternating '
            'muzzle-flash pulses, precisely at the black tips of their EXISTING bronze '
            'barrels. Compact orange-white flashes and tiny quickly fading smoke puffs. '
            'Each pod kicks back along its own straight barrel axis and returns on its '
            'existing joint. Heavy hull rocks slightly backward from recoil as one '
            'rigid shape. The roof gun stays still and DOES NOT fire; the red nose '
            'sensor remains a sensor and NEVER fires a laser or beam. No new barrel, '
            'moving muzzle to the wrong side, missiles or giant explosions. At '
            '1.3-3.0 seconds the smoke disappears, mounts settle and hull returns '
            'to its opening hover height. Keep all muzzle flashes inside the frame '
            'with clear lower-left margins, no target, shells covering the hull, '
            'camera shake, spin, full view change or invented supports.')),
    dict(id='04-fast-gun-drone',label='기동 비행 포대',file='0.2__artist_crimson comics___0.6__artist_dramz__, _0.5__artist_santa (sunflower) s-2281066227.png',padding=40,seed=2026102467,
        identity=(
            'The exact same long low-profile dark armored hovering gun drone, pointed '
            'wedge nose at screen LEFT, red rectangular nose sensor with one bright red '
            'lens, broad swept armored shell, two original tall slender antenna masts, '
            'existing rear circular thruster openings and original white hull decals. '
            'Keep the TWO original lower side-mounted gun assemblies, their angular '
            'mounts, original parallel black barrels and long thin outer support rails. '
            'All existing gun muzzles point diagonal DOWN-LEFT along the original '
            'axes in this three-quarter view. Retain the EXACT visible gun/rail count '
            'and shape, no added weapons. The red nose lens is a SENSOR, NOT a weapon. '
            'No legs, feet, wheels, propeller, human pilot or new equipment. '),
        idle=(
            'A controlled HOVER IDLE LOOP with one small smooth 6-10 pixel vertical '
            'stabilization cycle and a very slight rigid-body pitch correction. The '
            'two existing gun mounts subtly compensate to preserve their down-left '
            'aim, with no bending or changing the spacing of the barrels and rails. '
            'Both long antennae remain rigidly attached and travel with the hull, '
            'never waving like hair. Red nose lens stays an intact sensor with a '
            'small steady glow. Original hull plates and markings keep their form. '
            'End in the original hover pose and motion phase. No firing, muzzle '
            'flash, smoke, rapid pumping, flight across the screen, floor, ground '
            'shadow, environment or camera orbit.'),
        attack=(
            'Perform ONE SHORT burst from the existing TWO LOWER SIDE GUN ASSEMBLIES '
            'toward diagonal DOWN-LEFT, exactly along the original barrel axes. '
            'At 0.0-0.5 seconds the craft braces in the air and the two gun mounts '
            'stabilize their original aim. At 0.5-1.3 seconds fire three quick '
            'alternating small orange-white muzzle flashes at the actual open '
            'LEFTMOST barrel tips. A brief compact smoke puff follows each flash '
            'and quickly disappears. The rigid barrels recoil backward together '
            'along their axes on the original mount, and the rigid hull gives a '
            'small backward/upward reaction before settling. Retain the original '
            'outer rails and antenna shape, no flexible barrel bending. The red '
            'nose lens NEVER shoots; all fire originates at the lower black '
            'barrel muzzles. At 1.3-3.0 seconds stop firing, clear the smoke and '
            'return to the original hover and aim. One short burst only, no '
            'sustained beam, missiles, extra guns, gigantic effects, victim, '
            'camera shake or turning toward camera. Entire hull, antenna tips, '
            'gun rails, barrels and compact flashes stay inside the canvas.')),
]


def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(case):
    folder=OUT/case['id'];folder.mkdir(parents=True,exist_ok=True)
    source=INPUT/case['file'];assert source.is_file()
    if not (folder/'source-original.png').exists():shutil.copy2(source,folder/'source-original.png')
    assert digest(source)==digest(folder/'source-original.png')
    if not (folder/'reference.png').exists():
        im=Image.open(source).convert('RGBA');a=np.array(im);rgb=a[:,:,:3].astype(float);alpha=a[:,:,3].copy()
        # Pure exterior white sticker pixels, not the ivory/lavender armor.
        white=(rgb.min(2)>=245)&(np.ptp(rgb,axis=2)<18);allowed=white|(alpha<16)
        seeds=alpha<16;seeds[0]|=allowed[0];seeds[-1]|=allowed[-1];seeds[:,0]|=allowed[:,0];seeds[:,-1]|=allowed[:,-1]
        exterior=ndimage.binary_propagation(seeds,mask=allowed)
        removed=white&exterior&(alpha>0);alpha[removed]=0;alpha[alpha<16]=0
        a[:,:,3]=alpha;a[alpha==0,:3]=0;im=Image.fromarray(a);box=im.getchannel('A').getbbox();assert box
        im=im.crop(box);padded=Image.new('RGBA',(im.width+64,im.height+64));padded.paste(im,(32,32));padded.save(folder/'reference.png')
        save(folder/'source.json',dict(sourcePath=str(source),sourceSha256=digest(source),sourceUnchanged=True,
            referenceSha256=digest(folder/'reference.png'),removedExteriorPureWhitePixels=int(removed.sum()),
            preparation='Exterior-connected pure-white sticker removal, alpha crop and 32px transparent border; original armor and colored glow retained.',published=False))
    return folder


def main():
    OUT.mkdir(exist_ok=True)
    folders={case['id']:prepare(case) for case in CASES}
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
                ' Uniform flat neutral medium-GREY matte in EVERY empty gap between components, '
                'including all openings inside the silhouette. No white sticker rim, floor, '
                'cast shadow, scenery, text outside existing decals or extra subjects. '
                'Keep all original parts and compact action effects inside the canvas.')
            seed=case['seed']+(action=='attack');strength='normal' if action=='idle' else 'high'
            graph=engine.build_workflow(uploaded,prompt,3,768,768,seed,animation_type='custom',
                loop=action=='idle',facing='left',flat_background=True,blink_mode='none',
                motion_strength=strength,sampling_mode='quality',workflow_id='standard',subject_type='hover_machine')
            graph['10']['inputs']['steps']=40
            graph['6']['inputs']['prompt']=graph['6']['inputs']['prompt'].replace(
                'The original subject scale, composition, silhouette, component proportions, linework and painted shading are retained.',
                'Retain the original overall scale, component proportions, construction, ink contours and painted shading. Existing joints, gun mounts or suspended forearms may articulate within the fixed camera.')
            graph['15']['inputs'].pop('audio',None);graph.pop('14',None);graph.pop('5',None)
            prefix='guardian_drone_batch_20261024/'+case['id']+'/'+action
            graph['16']['inputs']['filename_prefix']=prefix
            save(folder/'native-v1-workflow.json',graph)
            save(folder/'settings.json',dict(animationType=action,generationPromptType='custom',subjectType='hover_machine',
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
                records=records,progressPolling=False,backgroundRemovalDeferred=True,order='attachment order, idle then attack for each'))
            print('SUBMITTED',case['id'],action,record['promptId'],flush=True)
    assert len(records)==8
    print('ALL_EIGHT_SUBMITTED_NO_POLLING',flush=True)


if __name__=='__main__':main()
