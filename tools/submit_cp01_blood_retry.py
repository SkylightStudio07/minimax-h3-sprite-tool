"""New takes using the untouched blood-ability reference; no step polling."""
import hashlib
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

OUT = ROOT / 'outputs/cp01-blood-retry-20261026'
SOURCE = ROOT / 'outputs/cp01-new-reference-20261026/source-original.png'
IDENTITY = (
    'Use Picture 1 as the exact character and visual style reference. A single adult blood-magic '
    'woman, original right-facing profile, white bob with one red streak, red eyes, white blouse '
    'with red cuff piping, black tie, gray flared trousers, black platform boots and red gloves. '
    'ONE short dark triangular ring-pommel dagger in the raised hand. The red liquid streaming '
    'from the other glove and pooled at her feet is her CONTROLLED BLOOD ABILITY, an essential '
    'part of this character. Preserve it and animate it as fluid magic, not a stationary painted '
    'decal. No victim, injury or dismemberment. Preserve the original inked two-dimensional anime '
    'art, sharp drawn contours, flat cel shading, costume, face and proportions; no 3D or relighting. '
    'The blouse, chest, bust contour, waist and pelvis retain their EXACT opening shape and volume '
    'throughout: no expanding breasts, local chest deformation, elastic torso, inflation or morphing. ')
MOTION = {
    'idle': (
        'A restrained composed IDLE of a blood-magic fighter waiting. Torso and bust are an almost '
        'motionless solid drawing with no breathing deformation; do NOT simulate chest breathing. '
        'Both boots, knees, pelvis height, neck and shoulder-level dagger guard remain stationary '
        'at their original coordinates. Keep gaze right and head still. Give life through tiny '
        'hair-tip and loose tie-tip settling, a slight finger adjustment of the lowered hand, and '
        'SLOW continuous fluid movement of the thin crimson strand linking that glove to the '
        'small blood pool. The strand subtly curves and flows downward; concentric thin ripples '
        'in the original small blood pool gently expand then disappear and reform. Keep the pool '
        'at the original scale with constant contained volume, not a giant circle or opaque floor. '
        'Glove and fingers remain intact and opaque. One quiet three-second seamless loop with '
        'matching opening and closing pose and phase. No hip rocking, bouncing, squats, arm '
        'waving, head nodding, rhythmic body pumping or weapon flourish. '),
    'attack': (
        'ONE decisive RIGHTWARD BLOOD-ENHANCED KNIFE SLASH with a readable whole-body action. '
        '0.0-0.5 seconds: bring the existing dagger safely away from her neck into a compact '
        'windup, soften both knees, coil shoulders and shift weight onto rear support. The lowered '
        'free gloved hand draws the existing blood strand UP out of the small pool; the pool '
        'visibly contracts as the liquid rises. 0.5-1.05 seconds: push through the rear ankle, '
        'transfer hips and chest forward RIGHT, turn shoulders through a fast diagonal cutting '
        'arc from shoulder height DOWN-RIGHT to waist height with the SAME short dagger. The '
        'blood stream accelerates into ONE distinct glossy dark-crimson curved blade-like ribbon '
        'extending just beyond the dagger toward SCREEN RIGHT, about half a body height long. '
        'It is dynamic red fluid with a crisp red silhouette and a few small red droplets, not '
        'white light, orange fire, smoke, a long metal sword or a giant full-screen slash. The '
        'ribbon changes curvature as it follows the moving hand and blade, trailing the actual '
        'cutting arc; never frozen on the ground or in midair. The free hand guides the liquid '
        'clear of her legs, face and torso. Front knee receives the short lunge; rear heel pivots. '
        '1.05-1.5 seconds: follow through with knees flexed, hips and shoulders moving together, '
        'hair and tie trailing; body remains anatomically rigid without blouse/bust morphing. '
        '1.5-3.0 seconds: the crimson ribbon retracts into the guiding hand and returns down the '
        'thin flowing strand to the original small pool; settle into the opening knife guard '
        'and original balanced stance. One slash then recovery, no repeated combo, spin, jump '
        'or camera turn. Keep the face in right-facing profile throughout. '),
}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    OUT.mkdir(exist_ok=True)
    for name in ('source-original.png', 'reference.png'):
        if not (OUT / name).exists():
            shutil.copy2(SOURCE, OUT / name)
        assert (OUT / name).read_bytes() == SOURCE.read_bytes()
    save(OUT / 'source.json', dict(sourceUnchanged=True, referenceIdenticalToOriginal=True,
        sourceSha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(), bloodAbilityPreserved=True,
        previousTakesPreserved=True, published=False))
    needed = any(not (OUT / a / 'native-v1-pending.json').exists() for a in MOTION)
    if needed:
        ensure_idle()
        release((8190, 8191))
        engine.start_comfy()
    records = []
    for i, (action, motion) in enumerate(MOTION.items()):
        folder = OUT / action
        folder.mkdir(exist_ok=True)
        pending = folder / 'native-v1-pending.json'
        if pending.exists():
            records.append(dict(action=action, **json.loads(pending.read_text(encoding='utf-8'))))
            continue
        prepared = engine.prepare_reference_image(SOURCE.read_bytes(), 768, 768, 20)
        (folder / 'reference-prepared.png').write_bytes(prepared)
        uploaded = engine.upload_image(prepared, 'cp01-blood-retry-' + action + '.png')
        prompt = IDENTITY + motion + (
            ' Fixed camera, size, framing and illumination. Full head, boots, flowing blood and '
            'all attack effects stay entirely inside the image with clear margins. Empty areas '
            'including EVERY gap between trouser legs, boots, arms and torso are uniform flat '
            'medium neutral GREY, clearly distinct from the purple-gray trouser fabric. Solid '
            'trousers retain opaque unbroken surfaces. No floor plane, cast shadow, white rim, '
            'scenery, new character, text or extra weapon. The only thing below the boots is '
            'the original small animated crimson blood pool; empty space inside its rings '
            'is the same neutral grey as the rest of the backdrop.\n\noverall_soundscape: N/A\n\nnon_diegetic_music: N/A')
        seed = 2026102661 + i
        graph = engine.build_workflow(uploaded, prompt, 3, 768, 768, seed,
            animation_type=action, loop=action == 'idle', facing='preserve', flat_background=True,
            blink_mode='none', motion_strength='low' if action == 'idle' else 'high',
            sampling_mode='quality', workflow_id='standard', subject_type='human', image_guided=True)
        # Use the complete reviewed prompt, without the generator's default chest
        # breathing or generic effect prohibitions contradicting this character.
        graph['6']['inputs']['prompt'] = prompt
        graph['10']['inputs']['steps'] = 40
        graph['15']['inputs'].pop('audio', None)
        graph.pop('14', None)
        graph.pop('5', None)
        prefix = 'cp01_blood_retry_20261026/' + action
        graph['16']['inputs']['filename_prefix'] = prefix
        save(folder / 'native-v1-workflow.json', graph)
        save(folder / 'settings.json', dict(animationType=action, subjectType='human', seed=seed,
            width=768, height=768, duration=3, fps=24, steps=40, frameCount=24, loop=action == 'idle',
            facing='preserve', motionPadding=20, referenceOffsetX=0,
            motionStrength='low' if action == 'idle' else 'high', workflowId='standard', samplingMode='quality',
            prompt=prompt, actualPrompt=prompt, outputPrefix=prefix, bloodAbility=True,
            backgroundRemoval='deferred; preserve gray trousers and red fluid separately', published=False))
        response = requests.post(engine.COMFY_URL + '/prompt', json=dict(prompt=graph), timeout=60)
        response.raise_for_status()
        info = response.json()
        record = dict(promptId=info['prompt_id'], queueNumber=info.get('number'))
        save(pending, record)
        records.append(dict(action=action, **record))
        save(OUT / 'generation-submissions.json', dict(comfyUrl=engine.COMFY_URL, records=records,
            progressPolling=False, backgroundRemovalDeferred=True, originalBloodReference=True))
        print('SUBMITTED', action, record['promptId'], flush=True)
    (OUT / 'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>CP01 혈계 재생성</title><style>body{background:#18202c;color:#eee;font:16px system-ui}img{height:560px}a{color:#ccbfff}</style><h1>CP01 혈계 · Idle / Attack 재생성</h1><p>원본 혈계 능력 보존 · 가슴 호흡 변형 금지 · 768px / 24FPS / 40스텝</p><img src="reference.png"><p><a href="../comfy/cp01_blood_retry_20261026/idle_00001_.mp4">idle 원본</a> · <a href="../comfy/cp01_blood_retry_20261026/attack_00001_.mp4">attack 원본</a></p>', encoding='utf-8')
    print('BOTH_SUBMITTED_NO_POLLING', flush=True)


if __name__ == '__main__':
    main()
