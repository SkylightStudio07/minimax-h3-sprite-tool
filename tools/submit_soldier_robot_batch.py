"""Queue the user's six enemies in attachment order; no generation polling."""
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

INPUT=Path('Z:/Vertex/적/NAI-images_(2026-09-08_16-39-14)_1-of-1')
OUT=ROOT/'outputs/soldier-robot-batch-20261025'
PREFIX='0.2__artist_crimson comics___0.6__artist_dramz__, _0.5__artist_santa (sunflower) s-'
STYLE=(
    'Animate the EXACT SAME single subject in the supplied reference, in its original '
    'hand-inked 2D comic illustration and painted cel-shadow style. Preserve the '
    'original colours, contours, materials, part proportions and camera-relative '
    'three-quarter view facing SCREEN LEFT. Fixed camera, framing, magnification '
    'and lighting. No glossy 3D transformation, realistic relighting, camera orbit '
    'or redesign. Existing markings remain on their original surfaces. ')
HUMAN_IDLE=(
    'A very restrained ready IDLE LOOP in the exact opening stance. Keep pelvis '
    'height, knee angles and both boot contact positions stationary. Keep head '
    'angle and gaze almost still, without independent nodding, scanning or head '
    'shaking. Only quiet one-to-two-pixel shoulder breathing and tiny two-to-four '
    'pixel weapon-tip drift on this 768px canvas. The plate carrier keeps its '
    'shape and volume, no armour inflation or whole-body pumping. No repeated '
    'weight transfer, crouching exercise, squatting, marching, large torso sway, '
    'weapon raise, reload, firing, flash or smoke. Keep grips and original weapon '
    'angle. Loose cloth settles only slightly. One smooth unhurried three-second '
    'breathing cycle connecting opening and closing pose and motion phase. ')
MACHINE_IDLE=(
    'A restrained stationary mechanical IDLE LOOP. All original feet stay planted '
    'at the exact opening contact points; existing leg joint angles and hull '
    'height stay almost constant. Allow only a tiny one-to-two-pixel stabilizing '
    'correction at the existing upper weapon mount, keeping the gun aimed along '
    'its original screen-left axis. The hull and armour plates remain rigid with '
    'constant spacing. Keep the red sensors at a small steady glow. No stepping, '
    'alternating leg movement, hydraulic squat cycle, chassis pumping, organic '
    'breathing, head bobbing, firing, muzzle flash, smoke, invented appendages or '
    'camera motion. End in the same quiet pose and motion phase after three seconds. ')
CASES=[
 dict(id='01-gatling-walker',label='상부 개틀링 사족 기계',sourceSeed='794555317',subject='ground_machine',padding=30,seed=2026102501,
  identity=(
    'Same olive-green quadrupedal military robot, broad angular animal-like forward '
    'head at screen LEFT, one red round head sensor, two small raised box sensors, '
    'heavy riveted armour, exposed dark mechanical joints and original multi-toed '
    'feet. Preserve every visible near/far leg and original attachment, without '
    'inventing another leg. Keep the grey-and-black GATLING TURRET on TOP of its '
    'back, with the original parallel black barrel cluster pointed diagonally '
    'UP-LEFT. This upper barrel cluster is the weapon. The red head lens is only '
    'a sensor and NEVER emits a projectile or beam. Retain the original RSAA '
    'hull markings and plate details. '),
  idle=MACHINE_IDLE,
  attack=(
    'Fire ONE short GATLING BURST from the existing TOP-MOUNTED black barrel '
    'cluster toward its original UP-LEFT direction. At 0.0-0.5s brace the existing '
    'mount while all feet remain firmly planted and the hull height stays steady. '
    'At 0.5-1.3s the same barrel cluster makes a brief rigid axial motor rotation '
    'and fires three small separate orange-white muzzle-flash pulses at the actual '
    'open LEFTMOST barrel tips. Keep barrel count, spacing and lengths unchanged. '
    'Short straight recoil through the upper mount; the rigid hull absorbs a tiny '
    'reaction without bending armour or repeatedly squatting. At 1.3-3.0s the '
    'rotation stops, tiny muzzle smoke dissipates, and the turret returns to its '
    'opening position. No fire from the red head sensor, new gun, missile, '
    'screen-filling blast, giant tracer, foot lift, turn or body lunge.')),
 dict(id='02-knife-soldier',label='단검 병사',sourceSeed='3042426051',subject='human',padding=30,seed=2026102503,
  identity=(
    'Same adult knife soldier in the original low combat guard facing LEFT: '
    'black balaclava with the original one visible eye, orange-lens goggles resting '
    'on the FOREHEAD, patterned brown neck scarf, rolled-sleeve tan desert-camouflage '
    'uniform, tan plate carrier, black gloves, tan knee pads and boots, original '
    'thigh pouches, red-marked cylindrical belt grenades. Keep the single silver '
    'combat KNIFE in its original gloved hand, tip directed down-left in the '
    'opening pose. The other hand is a guard hand, not holding the blade. Keep '
    'the black suppressed rifle SLUNG ON THE BACK for both motions; it is never '
    'drawn or fired. Preserve the original crouched knee angles at rest, face '
    'covering, gloves and blade shape. '),
  idle=HUMAN_IDLE+'Keep the knife in the same low guard, never drawing back for a strike. The back rifle and belt grenades remain attached and nearly still. ',
  attack=(
    'Deliver ONE fast compact KNIFE SLASH into SCREEN LEFT, then recover to the '
    'original low guard. At 0.0-0.5s draw the existing knife hand slightly inward '
    'and upward, loading the bent elbow as the opposite hand guards the chest. '
    'At 0.5-1.1s rotate the shoulders and upper torso a modest amount and drive '
    'a decisive leftward slightly downward cutting arc with that SAME knife. '
    'The shoulder, elbow and wrist work together; do not merely twitch the '
    'blade tip. The rigid blade keeps its original length and remains connected '
    'to the original knife grip. The off hand stays away from the cutting edge. '
    'At 1.1-1.5s absorb a short natural arm follow-through, allowing only a small '
    'forward weight shift with feet near their original contacts. At 1.5-3.0s '
    'return to the original crouched knife guard. The back rifle stays slung. '
    'One slash only, no new sword, second blade, gunfire, spin, jump, target, '
    'blood, energy trail or exaggerated knee-pumping recovery.')),
 dict(id='03-suppressed-rifleman',label='소음 소총 병사',sourceSeed='4085389655',subject='human',padding=30,seed=2026102505,
  identity=(
    'Same masked adult tactical rifleman facing LEFT, black helmet with folded '
    'twin night-vision tubes, tan ear protection, black full-face respirator mask '
    'and red lens, dark plate carrier, brown/green camouflage sleeves and '
    'trousers, black gloves, elbow and knee pads, tan boots, original patches '
    'and backpack. Keep ONE original TAN assault rifle with long black '
    'SUPPRESSOR, top optic, underbarrel foregrip and the original magazine. '
    'Both hands remain at the original trigger grip and support grip; stock '
    'stays braced at the shoulder and muzzle points LEFT. Retain the straight '
    'barrel and exact suppressor length. Mask and helmet remain on; red lens '
    'is not a weapon and no uncovered face appears. '),
  idle=HUMAN_IDLE+'Maintain the original shouldered horizontal leftward aim throughout, without lowering and raising the rifle. ',
  attack=(
    'Fire ONE short THREE-ROUND rifle BURST toward SCREEN LEFT from the actual '
    'LEFTMOST TIP of the existing suppressor. At 0.0-0.5s quietly brace the '
    'shouldered rifle and lean the shoulders slightly into the stock. At '
    '0.5-1.3s fire three quick small separate orange-white flashes at the '
    'suppressor tip. Each shot gives a short backward rifle impulse into '
    'the shoulder and very slight muzzle rise; bent elbows and upper torso '
    'absorb each impulse then return the rigid rifle to aim. Maintain both '
    'grip points, original planted boots and steady pelvis height. At '
    '1.3-3.0s stop firing, tiny muzzle smoke disappears, and settle into '
    'the original shouldered aim. No reload, new magazine, sensor beam, '
    'long projectile streak, giant explosion, foot step or face reveal.')),
 dict(id='04-cloaked-marksman',label='망토 저격 병사',sourceSeed='3531496554',subject='human',padding=30,seed=2026102507,
  identity=(
    'Same adult masked desert marksman with tan wrapped head covering, visible '
    'left-looking eye, black lower-face cloth, long patterned beige cloak, tan '
    'plate carrier, rolled sleeves, black gloves and wristwatch, tan desert '
    'camouflage trousers, dark thigh straps and tan boots. Keep the original '
    'LONG pale silver/ivory rifle with small gold ornament, brown stock, '
    'black scope with a gold objective ring and TWO deployed bipod struts '
    'hanging beneath the front of the barrel. Both hands hold the rifle as '
    'in the source, stock at the shoulder and muzzle aimed LEFT. The bipod '
    'is attached to the rifle and does NOT contact the ground; its struts '
    'move rigidly with the gun rather than becoming walking legs. Preserve '
    'the full scope, barrel length, cloak hem and visible hands. '),
  idle=HUMAN_IDLE+'Keep the scope aligned with the original sight line; cloak edges settle by only a few pixels and the hanging bipod stays rigid with the rifle. ',
  attack=(
    'Fire exactly ONE precise shot from the original long rifle toward SCREEN '
    'LEFT, then recover the sight picture. At 0.0-0.6s settle the existing '
    'shouldered aim without moving the boots. At 0.6-1.0s one small brief '
    'orange-white muzzle flash appears at the ACTUAL LEFTMOST BARREL TIP, '
    'not at the scope or bipod. The whole rigid rifle kicks a short distance '
    'straight back into the shoulder, with slight muzzle rise; both elbows '
    'and upper torso absorb the impulse naturally. Scope, stock and both '
    'bipod struts remain attached with unchanged dimensions. At 1.0-1.7s '
    'the cloak has a restrained delayed follow-through and a tiny muzzle '
    'smoke puff dissipates. At 1.7-3.0s return smoothly to the opening '
    'aimed pose. One shot only, no reload, dramatic bolt animation, new '
    'weapon, laser beam, giant tracer, camera shake or crouching exercise.')),
 dict(id='05-mast-gun-walker',label='상부 장총열 사족 기계',sourceSeed='3642133107',subject='ground_machine',padding=30,seed=2026102509,
  identity=(
    'Same olive-green armoured quadrupedal walker in the original LEFT-facing '
    'three-quarter view, angular narrow animal-like head, red forward sensors, '
    'broad RSAA-marked back armour, exposed paired neck pistons, original '
    'near/far articulated mechanical legs and multi-toed feet. Keep the '
    'original tall rectangular sensor-and-weapon mast on TOP of the back, '
    'with its red optic and one slender straight perforated gun barrel '
    'projecting horizontally LEFT from the mount beneath the optic. This '
    'existing TOP BARREL is the weapon. The red lens on the mast and red '
    'head sensors are sensors only, never muzzle openings. No new gun, '
    'extra leg, wheel, wing, rotor or human pilot. '),
  idle=MACHINE_IDLE+'The tall mast remains upright; only a very small gimbal correction of its existing barrel is allowed. ',
  attack=(
    'Fire ONE short THREE-PULSE burst from the original thin TOP-MOUNTED '
    'BARREL toward SCREEN LEFT. At 0.0-0.5s the upper gun mount steadies '
    'while the hull, mast and planted legs retain their original position. '
    'At 0.5-1.3s three brief compact orange flashes appear precisely at '
    'the actual LEFTMOST tip of the perforated metal barrel. The barrel '
    'and its existing mount kick back a few pixels along the barrel axis '
    'and return after each shot. Keep the long narrow barrel straight '
    'and constant in length, without bending or multiplying it. The '
    'rigid hull has only a tiny recoil response, no repeated leg squat. '
    'At 1.3-3.0s stop firing, tiny muzzle smoke clears and return to the '
    'opening guard. The red mast optic and head sensors NEVER shoot. '
    'No beam, giant flare, missile, long tracer, new weapon or foot lift.')),
 dict(id='06-compact-turret-walker',label='상부 소형포 사족 기계',sourceSeed='3356599944',subject='ground_machine',padding=30,seed=2026102511,
  identity=(
    'Same olive-green stocky armoured quadrupedal robot with its angular '
    'animal-like head facing LEFT, RSAA marking, heavy shoulder/hip plates, '
    'visible dark neck piston, back equipment boxes and original mechanical '
    'legs and broad multi-toed feet. Keep the existing compact TOP TURRET '
    'with its large round red optic and small raised square red sensor. '
    'A short slender straight gun barrel projects LEFT past the red round '
    'optic: this LEFTMOST small barrel is the only firing muzzle. The '
    'large red round lens is a SENSOR, never the gun opening. Retain the '
    'original turret profile and all near/far legs; no extra limb or weapon. '),
  idle=MACHINE_IDLE,
  attack=(
    'Fire exactly TWO short controlled shots from the existing small '
    'TOP-TURRET BARREL toward SCREEN LEFT. At 0.0-0.5s the turret steadies '
    'at the opening aim and all feet remain planted. Fire the first shot '
    'near 0.6s and second near 1.1s, each a small separate orange-white '
    'flash at the actual LEFTMOST metal barrel tip, clearly separate from '
    'the neighbouring red optic. The barrel and mount recoil straight '
    'back a few pixels, then settle between shots. The upper hull absorbs '
    'a tiny mechanical reaction with no height change or walking legs. '
    'At 1.4-3.0s smoke dissipates and the turret returns to its opening '
    'ready pose. Keep both red sensors intact and softly glowing; they '
    'never emit shots, laser beams or projectiles. No giant cannon blast, '
    'invented missiles, extra barrel, knee pumping, foot lift or body lunge.')),
]

def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def prepare(case):
    folder=OUT/case['id'];folder.mkdir(parents=True,exist_ok=True)
    source=INPUT/(PREFIX+case['sourceSeed']+'.png');assert source.is_file()
    if not (folder/'source-original.png').exists():shutil.copy2(source,folder/'source-original.png')
    assert digest(source)==digest(folder/'source-original.png')
    if not (folder/'reference.png').exists():
        image=Image.open(source).convert('RGBA');clean=image_background.remove(image)
        rgba=np.array(clean);rgba[rgba[:,:,3]<16]=0;clean=Image.fromarray(rgba)
        bounds=clean.getchannel('A').getbbox();assert bounds
        cropped=clean.crop(bounds);padded=Image.new('RGBA',(cropped.width+64,cropped.height+64))
        padded.paste(cropped,(32,32));padded.save(folder/'reference.png')
        save(folder/'source.json',dict(sourcePath=str(source),sourceSha256=digest(source),sourceUnchanged=True,
            referenceSha256=digest(folder/'reference.png'),cropBounds=list(bounds),
            preparation='CPU semantic alpha limited by source alpha; low-confidence alpha<16 discarded, crop and 32px transparent border. Original RGB retained. No source repaint.',published=False))
    return folder

def main():
    OUT.mkdir(exist_ok=True);folders={c['id']:prepare(c) for c in CASES}
    needed=any(not (folders[c['id']]/a/'native-v1-pending.json').exists() for c in CASES for a in ['idle','attack'])
    if needed:ensure_idle();engine.start_comfy();release((8190,8191))
    records=[]
    for case in CASES:
        root=folders[case['id']]
        for action in ['idle','attack']:
            folder=root/action;folder.mkdir(exist_ok=True);pending=folder/'native-v1-pending.json'
            if pending.exists():
                records.append(dict(case=case['id'],label=case['label'],action=action,**json.loads(pending.read_text(encoding='utf-8'))));continue
            prepared=engine.prepare_reference_image((root/'reference.png').read_bytes(),768,768,case['padding'])
            (folder/'reference-prepared.png').write_bytes(prepared)
            uploaded=engine.upload_image(prepared,case['id']+'-'+action+'-20261025.png')
            prompt=(STYLE+case['identity']+case[action]+ ' Uniform flat medium-GREY extraction matte in EVERY empty gap '
                'between legs, body, arms, equipment, barrels and bipod struts. No floor, '
                'ground shadow, white sticker rim, scenery or new subjects. Keep all original '
                'parts and compact effects inside the canvas with a clear margin. No scene-wide flash relighting.')
            strength='low' if action=='idle' else 'high';seed=case['seed']+(action=='attack')
            graph=engine.build_workflow(uploaded,prompt,3,768,768,seed,animation_type=action,
                loop=action=='idle',facing='preserve',flat_background=True,blink_mode='none',
                motion_strength=strength,sampling_mode='quality',workflow_id='standard',
                subject_type=case['subject'],image_guided=True)
            if action=='idle':
                graph['6']['inputs']['prompt']=graph['6']['inputs']['prompt'].replace(
                    'Allow the described head inclination and natural shoulder/pelvis counterrotation and joint articulation.',
                    'Keep the starting head angle, pelvis and planted supports steady; allow only the small idle adjustments specified below.')
            graph['10']['inputs']['steps']=40
            graph['15']['inputs'].pop('audio',None);graph.pop('14',None);graph.pop('5',None)
            prefix='soldier_robot_batch_20261025/'+case['id']+'/'+action;graph['16']['inputs']['filename_prefix']=prefix
            save(folder/'native-v1-workflow.json',graph)
            save(folder/'settings.json',dict(animationType=action,subjectType=case['subject'],caseId=case['id'],
                label=case['label'],seed=seed,width=768,height=768,duration=3,fps=24,steps=40,
                loop=action=='idle',facing='preserve',motionPadding=case['padding'],referenceOffsetX=0,
                motionStrength=strength,workflowId='standard',samplingMode='quality',motionPromptMode='image-guided',
                prompt=prompt,actualPrompt=graph['6']['inputs']['prompt'],sourceSha256=digest(root/'source-original.png'),
                referenceSha256=digest(root/'reference.png'),outputPrefix=prefix,
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
    assert len(records)==12
    print('ALL_TWELVE_SUBMITTED_NO_POLLING',flush=True)

if __name__=='__main__':main()
