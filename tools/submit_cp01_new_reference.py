"""Submit the new October 26 reference pair; generation monitoring is separate."""
import hashlib
import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import requests
import idle_tool as engine
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release

OUT = ROOT / 'outputs/cp01-new-reference-20261026'
EDITED = Path('C:/Users/SKYLIGHT/.codex/generated_images/01a0943f-e4b7-7e11-af05-20d776c93f13/exec-7638b8ed-8c2c-4c9f-9601-a388cf4edebc.png')
IDENTITY = (
    'Animate the EXACT SAME adult woman in the supplied NEW reference illustration: short white bob '
    'with a single narrow crimson streak, red eyes, right-facing profile, original face and mature '
    'proportions, white long-sleeve collared blouse with red cuff piping, black necktie, high-waist '
    'gray flared trousers, black chunky platform lace-up boots, glossy red gloves. Keep ONE short '
    'dark triangular ring-pommel dagger in the original raised gloved hand. It is a short knife, '
    'never a long sword. Preserve the original hand-inked two-dimensional anime illustration and '
    'flat cel-painted shadows and colors. No glossy 3D, realistic relighting, redesign, change of '
    'face, costume, weapon, body proportions or camera angle. ')
MOTIONS = {
    'idle': (
        'A composed very small BREATHING IDLE LOOP in the exact original standing pose. Keep both '
        'platform boot contacts planted at the same screen coordinates, knees and pelvis at the '
        'same height, torso angle and head orientation almost constant. The dagger stays near its '
        'original shoulder-height guard at the original angle; keep its sharp blade away from the '
        'neck rather than sliding it across her skin. Only one unhurried shallow breathing cycle '
        'in the shoulders and collar cloth, approximately two to four pixels at 768px; do not inflate '
        'the chest or blouse. Tiny hair-tip and tie-tip settling with delayed follow-through. The '
        'lowered free red-gloved hand stays relaxed in its original position. No hip rocking, '
        'bouncing, squats, stepping, deliberate head nodding, scanning, large arm gestures or '
        'weapon demonstration. Begin and end in matching pose and motion phase, with motion gently '
        'ongoing across the boundary. No blood, dripping strings, liquid puddle or floor symbol. '),
    'attack': (
        'ONE forceful quick CROSS-BODY DIAGONAL KNIFE CUT toward SCREEN RIGHT, using coordinated '
        'hips, shoulders, elbow and wrist. Start from the original knife-near-shoulder stance. '
        '0.0-0.45s: move the knife safely AWAY from the neck and slightly back over the knife-side '
        'shoulder; soften the knees slightly and coil the torso, loading the rear support. '
        '0.45-0.95s: drive the pelvis and chest a short distance RIGHT over the forward foot and '
        'rotate the shoulders into one FAST cutting arc. The knife hand sweeps in a broad curved '
        'path from shoulder height down and FORWARD RIGHT to waist height. This is a slicing CUT, '
        'not an arm extended in a straight point-first stab. The shoulder, elbow, wrist and rigid '
        'short blade visibly travel together through the cut. The free red-gloved hand counterbalances '
        'behind and away from the cutting edge. The front knee absorbs the small lunge, rear heel '
        'pivots naturally, hair and tie trail the acceleration. 0.95-1.4s: short low follow-through '
        'with torso leaning forward slightly; 1.4-3.0s: draw the knife back into the original '
        'shoulder-height guard and recover the original balanced standing pose. Clear anticipation, '
        'snappy execution, full-body follow-through and complete recovery. One cut, no repeated '
        'combo, full spin, jump, thrown knife, new sword, target, victim, blood, dripping liquid, '
        'persistent ribbon, floor mark or energy effect. '),
}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=True)
    reference = OUT / 'reference.png'
    if not reference.exists():
        shutil.copy2(EDITED, reference)
    save(OUT / 'source.json', dict(sourceUnchanged=True, sourceSha256=digest(OUT / 'source-original.png'),
        referenceSha256=digest(reference), preparation='Built-in image edit of the NEW source removes hanging red liquid and floor puddle. Pose, gloves, weapon and character design retained visually; edited copy is not pixel-identical.',
        originalPreserved=True, published=False))
    needed = any(not (OUT / a / 'native-v1-pending.json').exists() for a in MOTIONS)
    if needed:
        ensure_idle()
        release((8190, 8191))
        engine.start_comfy()
    records = []
    for i, (action, motion) in enumerate(MOTIONS.items()):
        folder = OUT / action
        folder.mkdir(exist_ok=True)
        pending = folder / 'native-v1-pending.json'
        if pending.exists():
            records.append(dict(action=action, **json.loads(pending.read_text(encoding='utf-8'))))
            continue
        padding = 30
        prepared = engine.prepare_reference_image(reference.read_bytes(), 768, 768, padding)
        (folder / 'reference-prepared.png').write_bytes(prepared)
        uploaded = engine.upload_image(prepared, 'cp01-new-reference-' + action + '-20261026.png')
        prompt = IDENTITY + motion + (
            ' Fixed camera, magnification, framing and painted illumination. Maintain the original '
            'right-facing profile; eyes stay directed SCREEN RIGHT and never toward the viewer. '
            'Keep the entire body, both platform boots, free hand and complete knife inside the '
            'canvas with clear margins. Uniform flat medium-GREY background in all spaces '
            'between arms, torso and legs. No floor, ground plane, cast shadow, white sticker '
            'rim, scenery, text, particles or new objects.')
        seed = 2026102601 + i
        graph = engine.build_workflow(uploaded, prompt, 3, 768, 768, seed,
            animation_type=action, loop=action == 'idle', facing='preserve', flat_background=True,
            blink_mode='none', motion_strength='low' if action == 'idle' else 'high',
            sampling_mode='quality', workflow_id='standard', subject_type='human', image_guided=True)
        if action == 'idle':
            graph['6']['inputs']['prompt'] = graph['6']['inputs']['prompt'].replace(
                'Allow the described head inclination and natural shoulder/pelvis counterrotation and joint articulation.',
                'Maintain the starting head angle and pelvis height; allow only the subtle breathing described below.')
        else:
            graph['6']['inputs']['prompt'] = graph['6']['inputs']['prompt'].replace(
                engine.FACING_PROMPTS['preserve'],
                'Preserve the right-facing head profile and camera-relative view. Allow the small hip and shoulder rotation and forward body translation required for this knife cut; never turn toward the camera.')
        graph['10']['inputs']['steps'] = 40
        graph['15']['inputs'].pop('audio', None)
        graph.pop('14', None)
        graph.pop('5', None)
        prefix = 'cp01_new_reference_20261026/' + action
        graph['16']['inputs']['filename_prefix'] = prefix
        save(folder / 'native-v1-workflow.json', graph)
        save(folder / 'settings.json', dict(animationType=action, subjectType='human', seed=seed,
            width=768, height=768, duration=3, fps=24, steps=40, frameCount=24, loop=action == 'idle',
            facing='preserve', motionPadding=padding, referenceOffsetX=0,
            motionStrength='low' if action == 'idle' else 'high', workflowId='standard', samplingMode='quality',
            prompt=prompt, actualPrompt=graph['6']['inputs']['prompt'], outputPrefix=prefix,
            sourceSha256=digest(OUT / 'source-original.png'), referenceSha256=digest(reference),
            backgroundRemoval='deferred until user requests it', published=False))
        response = requests.post(engine.COMFY_URL + '/prompt', json=dict(prompt=graph), timeout=60)
        response.raise_for_status()
        info = response.json()
        record = dict(promptId=info['prompt_id'], queueNumber=info.get('number'),
            signature=hashlib.sha256(json.dumps(graph, sort_keys=True).encode()).hexdigest())
        save(pending, record)
        records.append(dict(action=action, **record))
        save(OUT / 'generation-submissions.json', dict(comfyUrl=engine.COMFY_URL, records=records,
            requestedNativeResolution=[768, 768], fps=24, steps=40, progressPolling=False,
            backgroundRemovalDeferred=True))
        print('SUBMITTED', action, record['promptId'], flush=True)
    (OUT / 'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>CP01 새 원화 · Idle / Attack</title><style>body{background:#18202c;color:#eee;font:16px system-ui;margin:24px}img{max-height:600px}a{color:#ccbcff}</style><h1>CP01 새 원화 · Idle / Attack</h1><p>768×768 · 24FPS · 40스텝. 생성 제출 완료, 누끼는 생성 후 별도 처리합니다.</p><img src="reference.png"><p>' + ' · '.join(f'<a href="../comfy/cp01_new_reference_20261026/{a}_00001_.mp4">{html.escape(a)} 생성 원본</a>' for a in MOTIONS), encoding='utf-8')
    print('BOTH_SUBMITTED_NO_POLLING', flush=True)


if __name__ == '__main__':
    main()
