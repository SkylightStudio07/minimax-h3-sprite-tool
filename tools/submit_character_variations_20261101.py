"""Prepare nine reviewed motion recipes; submit one at a time for Luna."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import requests
from PIL import Image
import image_background
import idle_tool as engine
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release

OUT = ROOT / 'outputs/character-variations-20261101'
ART = Path('C:/Users/SKYLIGHT/Documents/Graduation/Project-Vertex/Assets/Art/Characters/Joining Characters')
SOURCES = {
    'blonde': ART / 'Chara1/Chara1 - 복사본.png',
    'pistol': ART / 'Player/Player_F/Player_F.png',
    'kunai': Path('C:/Users/SKYLIGHT/AppData/Local/Temp/codex-clipboard-8a1e35cb-3a4d-4053-91e6-24e867ed8cb3.png'),
}
STYLE = (
    'Animate the EXACT SAME adult game character in Picture 1. Preserve the supplied hand-inked '
    '2D anime illustration, drawn outlines, flat painted cel shadows, face, costume colors, '
    'body proportions and original weapon design. Constant painted illumination and camera '
    'scale; no glossy 3D rendering, realistic relighting, character redesign or camera orbit. '
    'Chest, bust outline, blouse and armor retain constant volume and shape during joint '
    'motion: no local inflation, deflation, elastic torso or bust morphing. ')
IDENTITY = {
    'blonde': (
        'Same blonde woman, long straight golden hair and bangs, GREEN eyes, white short-sleeve '
        'collared shirt, black plate carrier and pouches, dark navy pleated skirt, dark tights, '
        'black gloves and black tactical boots. The original long black SHOTGUN is held in '
        'both hands and points SCREEN LEFT. Preserve its original long upper barrel and lower '
        'tube, metal receiver and ribbed fore-end, exact weapon length, black stock and two '
        'existing grip points. Do not replace it with a rifle or pistol. Her facing remains '
        'LEFT in the original three-quarter view; no turn toward the viewer. '),
    'pistol': (
        'Same white/lavender short-bob woman with BLUE eyes, original black beret and silver '
        'badge, white short-sleeve uniform shirt with original patches, black undershirt, '
        'navy pleated skirt, black gloves, dark legwear, strapped thigh holsters and tall '
        'black boots. Original right-facing profile. ONE original long-barreled silver '
        'REVOLVER with dark cylinder and brown grip stays in the same originally raised '
        'gloved hand. Keep the cylinder, slender long barrel, grip and trigger guard rigid '
        'and recognizable. Never draw a holstered second gun. No semiautomatic slide, '
        'magazine swapping, invented suppressor or ejected cartridge stream. '),
    'kunai': (
        'Same white bob with one red hair streak, red eyes, right-facing profile, white '
        'long-sleeve blouse with red cuff piping, black tie, gray flared trousers, red gloves '
        'and black platform boots. ONE original short dark triangular ring-pommel KUNAI '
        'stays in the originally raised hand near the shoulder. The LOWERED hand is empty. '
        'The red liquid strand and small pool are her controlled blood ability; preserve '
        'them as secondary fluid motion. No victim or injury. '),
}
QUIET = (
    'A restrained ready IDLE LOOP. Keep both soles at their original contact positions, '
    'knees and pelvis at constant height, head angle and gaze steady. No chest breathing '
    'deformation, torso pumping, squats, marching, bouncing, repeated weight transfer or '
    'deliberate head nodding. Life comes from the small hand/weapon/loose-cloth adjustments '
    'specified below, with the torso maintaining its original solid silhouette. Smooth '
    'unhurried motion, matching start/end stance and phase over three seconds. ')
MOTIONS = [
    dict(id='01-blonde-idle', character='blonde', action='idle', label='금발 · 조용한 산탄총 경계', motion=QUIET +
         'Keep the shotgun at its original low LEFTWARD angle with both original grip points. '
         'A tiny two-to-four-pixel forearm and muzzle settling, a slight delayed movement of '
         'long hair tips and skirt hem, no wind flapping. Eyes stay green; no eye aura, firing, '
         'recoil, aiming gesture, reload or raised stock in this idle.'),
    dict(id='02-blonde-fire', character='blonde', action='attack', label='금발 · 붉은 눈 기운 사격', motion=
         'ONE dynamic shotgun firing action toward SCREEN LEFT. 0.0-0.55s: raise the EXISTING '
         'shotgun from low ready to a leftward shouldered aim, seat the stock at the shoulder, '
         'lean the pelvis and shoulders slightly forward while flexing the front knee. Both '
         'hands retain their trigger and fore-end grips. As she commits to aiming, dark '
         'CRIMSON ENERGY begins to flow from the visible EYE: thin red smoky wisps and a '
         'short red comet-like trail stream backward toward screen RIGHT beside her temple '
         'and hair. Keep the original green iris readable under this red emitted aura; '
         'it is flowing eye energy, NOT a laser beam, muzzle flash or red face repaint. '
         '0.55-1.0s: fire ONE punchy shotgun shot from the actual LEFTMOST barrel mouth. '
         'Compact orange-white muzzle flash, small smoke puff, strong short backward '
         'weapon recoil into the shoulder. Elbows, shoulders, hips and flexed knees absorb '
         'the impulse as a coordinated body, with a small rear-heel pivot; hair and skirt '
         'trail the acceleration. The RED EYE AURA flares briefly during this shot and '
         'continues flowing backward, separate from the muzzle flash. 1.0-1.6s: recover '
         'the shouldered aim and balance. 1.6-3.0s: lower the original shotgun back to low '
         'ready, the eye wisps fade completely. No repeated body pumping, extra weapon, '
         'laser, spin, jump or facial turn. Keep the full long barrel and all eye effects '
         'inside the canvas.'),
    dict(id='03-pistol-idle-a', character='pistol', action='idle', label='권총 A · 어깨 경계', motion=QUIET +
         'Keep the revolver near the original shoulder-height ready angle. Tiny wrist settling '
         'and short hair-tip movement; free gloved hand rests lowered as in the original. '
         'Maintain the beret and original stance. No aim raise, firing, eye glow or spinning the gun.'),
    dict(id='04-pistol-fire-a', character='pistol', action='attack', label='권총 A · 두 손 조준 사격', motion=
         'ONE dynamic RIGHTWARD revolver shot from the original shoulder-level ready pose. '
         '0.0-0.5s: bring the free hand up to SUPPORT the original gun hand; extend both '
         'forearms together toward SCREEN RIGHT, bend the front knee slightly and lean '
         'the shoulders into the aim. 0.5-0.9s: fire ONE precise shot from the actual '
         'RIGHTMOST long-barrel tip with compact muzzle flash. The rigid revolver kicks '
         'up and back, both elbows and shoulders absorb recoil with a small controlled '
         'hip counterrotation. Hair, tie-free collar cloth and skirt lag slightly. '
         '0.9-1.4s: return the muzzle to the rightward sight line; 1.4-3.0s: withdraw '
         'the revolver into the original shoulder-ready pose, lower the free hand and '
         'recover the opening stance. Readable anticipation, sharp execution and full '
         'recovery, not just a vibrating gun tip. No foot travel, gun swap or reload.'),
    dict(id='05-pistol-idle-b', character='pistol', action='idle', label='권총 B · 작은 조준 조정', motion=QUIET +
         'One very small deliberate adjustment of the existing revolver angle: the gun hand '
         'makes a smooth five-to-eight-pixel settling arc then returns to original shoulder '
         'ready. Free hand softly opens and relaxes once near the hip without a large arm '
         'gesture. Head and hips remain quiet; slight hair-tip follow-through, no firing.'),
    dict(id='06-pistol-fire-b', character='pistol', action='attack', label='권총 B · 전진 한 손 점사', motion=
         'ONE assertive RIGHTWARD step-in shooting action, TWO separate revolver shots. '
         '0.0-0.5s: take one SHORT forward step toward SCREEN RIGHT, drive the hips over '
         'the landing front foot and extend the ORIGINAL gun arm into a one-handed aim. '
         'The empty hand draws near the ribs as counterbalance. 0.5-1.2s: two quick '
         'distinct shots from the actual rightmost barrel tip, each with a small separate '
         'flash and clear upward/backward gun recoil. The gun-side elbow, shoulder and '
         'upper torso react naturally and recover aim between shots; the rear heel '
         'pivots, front knee absorbs the forward weight. Skirt and hair trail the motion. '
         '1.2-1.7s: firm follow-through at the forward stance; 1.7-3.0s: make one short '
         'controlled recovery step back to the original position and retract the gun '
         'to the original ready guard. No running, hopping, repeated squats, camera '
         'movement, extra gun or cylinder reload. Entire step remains inside the canvas.'),
    dict(id='07-pistol-idle-c', character='pistol', action='idle', label='권총 C · 그립 확인', motion=QUIET +
         'The lowered free hand slowly rises only to the lower edge of the existing gun '
         'wrist, gives one light grip-support check, then settles back to its original '
         'lowered position. Keep the revolver near its opening angle without aiming or '
         'twirling. No large elbow sweep, torso bob or face turn. Hair and skirt settle gently.'),
    dict(id='08-pistol-fire-c', character='pistol', action='attack', label='권총 C · 낮은 자세 사격', motion=
         'ONE dynamic low-stance RIGHTWARD revolver shot and recovery. 0.0-0.55s: flex both '
         'knees into one controlled shallow drop, lower pelvis about 30 pixels on this '
         '768px canvas, hinge the solid torso forward slightly and extend the ORIGINAL '
         'gun arm toward SCREEN RIGHT. The free hand supports the shooting wrist, '
         'both boots stay near their original contacts. 0.55-1.0s: fire ONE shot from '
         'the actual rightmost muzzle with a compact flash. Recoil travels through '
         'wrist, elbow and shoulder, torso counterrotates slightly while the front '
         'knee bears weight. 1.0-1.5s: recover the low aimed sight line; 1.5-3.0s: '
         'rise ONCE back into the original standing shoulder-ready guard and lower '
         'the free hand. This is a single purposeful low combat maneuver, not rhythmic '
         'exercise, repeated squatting, kneeling, sliding, spinning or a new weapon.'),
    dict(id='09-kunai-horizontal', character='kunai', action='attack', label='쿠나이 · 전신 횡베기', motion=
         'ONE powerful physical HORIZONTAL KUNAI SLASH toward SCREEN RIGHT. The originally '
         'RAISED KUNAI-HOLDING HAND is the sole attacking hand. The original black metal '
         'blade remains visibly attached to its grip for the entire action. The lowered '
         'EMPTY hand tucks near the ribs and only balances the torso; it NEVER swings, '
         'casts, whips or leads a blood ribbon. 0.0-0.5s: move the raised kunai safely '
         'away from the neck and draw its elbow BACK to load the shoulder; bend both '
         'knees slightly, turn the hips into the windup. 0.5-1.05s: push through the '
         'rear leg, transfer pelvis RIGHT over the receiving front knee, rotate hips '
         'and shoulders together and drive the KUNAI-HOLDING SHOULDER, ELBOW, FIST '
         'AND METAL BLADE through a wide FAST WAIST-TO-CHEST-HEIGHT HORIZONTAL '
         'CUTTING ARC across the front of the body. The grip travels in a SIDEWAYS '
         'CURVE like a backhand cutting stroke; no point-first straight jab. Keep the '
         'blade readable at windup, mid-sweep and follow-through. The knife arm '
         'unfolds, front knee receives the lunge, rear heel pivots, torso visibly '
         'turns while head/profile still faces RIGHT. Hair and tie whip behind the '
         'shoulder motion. The free hand stays out of the blade path near the ribs. '
         'A SHORT narrow crimson fluid trail attaches to the MOVING KUNAI EDGE, '
         'extends only one-to-two knife lengths, follows the real blade arc and '
         'quickly retracts onto that edge. No empty-hand spell, giant blood circle, '
         'free-floating whip or new long sword. 1.05-1.5s: low forward follow-through '
         'with the actual kunai extended after cutting; 1.5-3.0s: draw the SAME '
         'knife hand back to the opening shoulder guard, recover the original feet '
         'and balanced stance. Keep the original thin blood strand and small pool '
         'alive with restrained fluid movement as secondary effects. One cut only, '
         'no spin, jump, new weapon, victim, injury or body morphing.'),
]


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    OUT.mkdir(exist_ok=True)
    for key, source in SOURCES.items():
        folder = OUT / 'references' / key
        folder.mkdir(parents=True, exist_ok=True)
        if not (folder / 'source-original.png').exists():
            shutil.copy2(source, folder / 'source-original.png')
        assert digest(source) == digest(folder / 'source-original.png')
        if (folder / 'reference.png').exists():
            continue
        with Image.open(source) as im:
            original = im.convert('RGBA')
        if key == 'kunai':
            # The original alpha already contains fine blood strands. Do not
            # ask segmentation to discard these as background decoration.
            reference = original
        else:
            clean = image_background.remove(original)
            a = np.array(clean)
            a[a[:, :, 3] < 16] = 0
            clean = Image.fromarray(a)
            box = clean.getchannel('A').getbbox()
            assert box
            clean = clean.crop(box)
            reference = Image.new('RGBA', (clean.width + 64, clean.height + 64))
            reference.paste(clean, (32, 32))
        reference.save(folder / 'reference.png')
        save(folder / 'source.json', dict(sourcePath=str(source), sourceSha256=digest(source),
            sourceUnchanged=True, originalPreserved=True, referenceSha256=digest(folder / 'reference.png'),
            preparation='Original alpha preserved including blood' if key == 'kunai' else 'CPU segmentation and low-confidence fringe cleanup in a copy; original RGB and source retained', published=False))
    for index, motion in enumerate(MOTIONS):
        folder = OUT / motion['id']
        folder.mkdir(exist_ok=True)
        ref = OUT / 'references' / motion['character']
        for name in ('source-original.png', 'reference.png', 'source.json'):
            if not (folder / name).exists():
                shutil.copy2(ref / name, folder / name)
        prompt = STYLE + IDENTITY[motion['character']] + motion['motion'] + (
            ' Fixed camera, framing and scale. Entire character, boots, original weapon '
            'and compact generated effects fit inside the frame with clear margins. '
            'Uniform flat medium neutral GREY backdrop, including every empty gap '
            'between limbs, gun, hands, skirt and torso. Dark garments and gray fabric '
            'remain opaque with their original colors. No floor plane, cast shadow, '
            'white sticker outline, scenery, text, new subjects or invented equipment. '
            'The kunai character retains only her original small blood pool; other '
            'characters have no floor decoration.\n\noverall_soundscape: N/A\n\nnon_diegetic_music: N/A')
        save(folder / 'recipe.json', dict(**motion, prompt=prompt, seed=2026110101 + index,
            width=768, height=768, duration=3, fps=24, steps=40, motionPadding=30))
    save(OUT / 'batch-plan.json', dict(expectedJobs=9, order=[m['id'] for m in MOTIONS],
        onlyOneSubmittedAtATime=True, supervision='Luna', backgroundRemovalDeferred=True))
    cards = ''.join(f'<article><h2>{m["label"]}</h2><video controls muted loop preload="none" poster="{m["id"]}/reference.png" src="../comfy/character_variations_20261101/{m["id"]}_00001_.mp4"></video></article>' for m in MOTIONS)
    (OUT / 'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>캐릭터 동작 바리에이션</title><style>body{background:#18202c;color:#eee;font:16px system-ui;margin:24px}main{display:flex;flex-wrap:wrap;gap:20px}article{width:420px}video{width:100%}</style><h1>캐릭터 동작 바리에이션 · 9개</h1><p>768×768 · 24FPS · 40스텝. 생성 원본, 배경 제거 전입니다.</p><main>' + cards + '</main>', encoding='utf-8')
    print('PREPARED_NINE_RECIPES', flush=True)


def next_job():
    engine.start_comfy()
    q = requests.get(engine.COMFY_URL + '/queue', timeout=10).json()
    if q.get('queue_running') or q.get('queue_pending'):
        raise RuntimeError('Queue busy; refusing to overlap')
    for motion in MOTIONS:
        folder = OUT / motion['id']
        pending = folder / 'native-v1-pending.json'
        output = ROOT / 'outputs/comfy/character_variations_20261101' / f"{motion['id']}_00001_.mp4"
        if output.exists():
            try:
                import cv2
                cap = cv2.VideoCapture(str(output))
                meta = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                        cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
                cap.release()
                if meta == (768, 768, 24.0, 73):
                    print('VERIFIED_EXISTING_OUTPUT', motion['id'], flush=True)
                    continue
            except Exception:
                pass
        if pending.exists():
            record = json.loads(pending.read_text(encoding='utf-8'))
            h = requests.get(engine.COMFY_URL + '/history/' + record['promptId'], timeout=10).json().get(record['promptId'])
            if not h:
                archive = pending.with_name(f"native-v1-pending-lost-{record['promptId']}.json")
                shutil.copy2(pending, archive)
                pending.unlink()
                submissions = OUT / 'generation-submissions.json'
                if submissions.exists():
                    data = json.loads(submissions.read_text(encoding='utf-8'))
                    data.setdefault('interrupted', []).append(dict(record, status='missing-history-no-output', archivedPending=str(archive)))
                    save(submissions, data)
                print('ARCHIVED_LOST_PENDING', motion['id'], record['promptId'], flush=True)
                # The same reviewed recipe may now be resubmitted once queue is confirmed empty.
            else:
                if h.get('status', {}).get('status_str') != 'success':
                    raise RuntimeError('Previous job failed; no automatic retry: ' + motion['id'])
                continue
        ensure_idle()
        release((8190, 8191))
        q = requests.get(engine.COMFY_URL + '/queue', timeout=10).json()
        if q.get('queue_running') or q.get('queue_pending'):
            raise RuntimeError('Queue busy; refusing to overlap')
        recipe = json.loads((folder / 'recipe.json').read_text(encoding='utf-8'))
        prepared = engine.prepare_reference_image((folder / 'reference.png').read_bytes(), 768, 768, 30)
        (folder / 'reference-prepared.png').write_bytes(prepared)
        uploaded = engine.upload_image(prepared, motion['id'] + '-20261101.png')
        graph = engine.build_workflow(uploaded, recipe['prompt'], 3, 768, 768, recipe['seed'],
            animation_type=motion['action'], loop=motion['action'] == 'idle', facing='preserve',
            flat_background=True, blink_mode='none', motion_strength='low' if motion['action'] == 'idle' else 'high',
            sampling_mode='quality', workflow_id='standard', subject_type='human', image_guided=True)
        graph['6']['inputs']['prompt'] = recipe['prompt']
        graph['10']['inputs']['steps'] = 40
        graph['15']['inputs'].pop('audio', None)
        graph.pop('14', None)
        graph.pop('5', None)
        prefix = 'character_variations_20261101/' + motion['id']
        graph['16']['inputs']['filename_prefix'] = prefix
        save(folder / 'native-v1-workflow.json', graph)
        save(folder / 'settings.json', dict(animationType=motion['action'], seed=recipe['seed'],
            width=768, height=768, duration=3, fps=24, steps=40, frameCount=24,
            loop=motion['action'] == 'idle', facing='preserve', motionPadding=30, referenceOffsetX=0,
            motionStrength='low' if motion['action'] == 'idle' else 'high', workflowId='standard',
            samplingMode='quality', prompt=recipe['prompt'], actualPrompt=recipe['prompt'],
            outputPrefix=prefix, backgroundRemoval='deferred', published=False))
        response = requests.post(engine.COMFY_URL + '/prompt', json=dict(prompt=graph), timeout=60)
        response.raise_for_status()
        info = response.json()
        record = dict(id=motion['id'], action=motion['action'], label=motion['label'],
            promptId=info['prompt_id'], queueNumber=info.get('number'))
        save(pending, record)
        records = [json.loads(p.read_text(encoding='utf-8')) for p in sorted(OUT.glob('*/native-v1-pending.json'))]
        save(OUT / 'generation-submissions.json', dict(comfyUrl=engine.COMFY_URL, records=records,
            expectedJobs=9, sequential=True, backgroundRemovalDeferred=True))
        print('SUBMITTED_ONE', motion['id'], info['prompt_id'], flush=True)
        return
    print('ALL_NINE_COMPLETE', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=('prepare', 'next'))
    args = parser.parse_args()
    globals()['next_job' if args.stage == 'next' else 'prepare']()
