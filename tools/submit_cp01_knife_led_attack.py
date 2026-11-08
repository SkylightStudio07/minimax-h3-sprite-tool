"""One knife-led attack retry. The accepted idle is never resubmitted."""
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

PREVIOUS = ROOT / 'outputs/cp01-blood-retry-20261026'
OUT = ROOT / 'outputs/cp01-knife-led-attack-20261026'
PROMPT = (
    'Animate the exact adult woman from Picture 1, preserving the original right-facing profile, '
    'white bob and narrow red streak, red eyes, white blouse with red cuff piping, black tie, '
    'gray flared trousers, black platform boots, red gloves, inked 2D anime contours and cel shading. '
    'ONE short black triangular ring-pommel DAGGER remains firmly gripped in the SAME initially '
    'RAISED HAND near her shoulder for the entire clip. That KNIFE-HOLDING ARM is the attacking '
    'arm and MUST visibly execute the complete slash. Keep the original blade length and shape '
    'and its attachment to the grip. The other initially LOWERED EMPTY HAND stays near her hip '
    'and ribs as a passive counterbalance. It never sweeps outward, casts, whips, conducts a '
    'ribbon or leads the attack. This is a physical KNIFE CUT enhanced with blood, not an empty-hand spell. '
    '0.0-0.5s: load a compact windup by drawing the KNIFE-HOLDING ELBOW back slightly with the '
    'dagger clear of her neck, soft knees and a small shoulder/hip coil. The lowered empty hand '
    'tucks near her waist and stays there. 0.5-1.0s: drive the KNIFE-HOLDING SHOULDER forward '
    'RIGHT, unfold that elbow and visibly carry the gripping fist AND its attached dagger '
    'through ONE broad fast DIAGONAL DOWN-RIGHT CUT from shoulder height to waist height. '
    'The metal knife sweeps in a curved cutting path across the front of the torso, never parked '
    'in guard while the empty hand moves. Show the existing short rigid blade distinctly at '
    'windup, mid-cut and low forward follow-through. Hips transfer forward over the front foot, '
    'front knee absorbs the short lunge, rear heel pivots, torso leans modestly into the cut. '
    'A compact dark-crimson fluid crescent forms DIRECTLY ON THE MOVING KNIFE EDGE, extends '
    'only 1-2 original knife lengths past its TIP and trails precisely behind the metal blade '
    'as it cuts. The blood effect originates from and stays attached to that KNIFE EDGE; it '
    'does not originate from the empty hand or circle the whole character. Keep the real '
    'metal blade readable within the effect. One short narrow blood crescent plus a few small '
    'red droplets; no giant circle, free-floating whip, huge scythe or screen-filling ribbon. '
    '1.0-1.4s: the KNIFE-HOLDING arm completes the low forward follow-through; blood follows '
    'its direction and quickly retracts onto the blade. 1.4-3.0s: that SAME knife hand draws '
    'the dagger back into its original shoulder-height guard and the body returns to the '
    'opening stance. The empty hand settles back down only during recovery. Keep the original '
    'thin blood strand and small blood pool as secondary effects; they do not perform the '
    'attack and never become a stationary giant floor decal. Keep the chest/blouse shape and '
    'volume consistent through joint rotation, no local bust morphing. Fixed right-facing '
    'profile and camera; no frontal face turn, 3D transformation, zoom, spin, jump, extra knife '
    'or repeated combo. Keep the full head, boots, blade and compact blood effect inside '
    'the canvas. Uniform flat medium-grey background in every empty limb gap, no floor, '
    'shadow, white outline, scenery or target. Purple-gray trousers remain solid and opaque. '
    'No victim or injury.\n\noverall_soundscape: N/A\n\nnon_diegetic_music: N/A'
)


def main():
    OUT.mkdir(exist_ok=True)
    for name in ('source-original.png', 'reference.png', 'source.json'):
        if not (OUT / name).exists():
            shutil.copy2(PREVIOUS / name, OUT / name)
    folder = OUT / 'attack'
    folder.mkdir(exist_ok=True)
    pending = folder / 'native-v1-pending.json'
    if pending.exists():
        print('ALREADY_SUBMITTED', pending.read_text(encoding='utf-8'))
        return
    ensure_idle()
    release((8190, 8191))
    engine.start_comfy()
    prepared = (PREVIOUS / 'attack/reference-prepared.png').read_bytes()
    (folder / 'reference-prepared.png').write_bytes(prepared)
    uploaded = engine.upload_image(prepared, 'cp01-knife-led-attack-20261026.png')
    seed = 2026102683
    graph = engine.build_workflow(uploaded, PROMPT, 3, 768, 768, seed,
        animation_type='attack', loop=False, facing='preserve', flat_background=True,
        blink_mode='none', motion_strength='high', sampling_mode='quality', workflow_id='standard',
        subject_type='human', image_guided=True)
    graph['6']['inputs']['prompt'] = PROMPT
    graph['10']['inputs']['steps'] = 40
    graph['15']['inputs'].pop('audio', None)
    graph.pop('14', None)
    graph.pop('5', None)
    prefix = 'cp01_knife_led_attack_20261026/attack'
    graph['16']['inputs']['filename_prefix'] = prefix
    def save(path, obj):
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    save(folder / 'native-v1-workflow.json', graph)
    settings = json.loads((PREVIOUS / 'attack/settings.json').read_text(encoding='utf-8'))
    settings.update(seed=seed, prompt=PROMPT, actualPrompt=PROMPT, outputPrefix=prefix,
        knifeLedAttack=True, acceptedIdleSource=str(PREVIOUS / 'idle'),
        backgroundRemoval='deferred; use blood and opaque trouser pipeline', published=False)
    settings.pop('postProcessing', None)
    save(folder / 'settings.json', settings)
    response = requests.post(engine.COMFY_URL + '/prompt', json=dict(prompt=graph), timeout=60)
    response.raise_for_status()
    info = response.json()
    record = dict(action='attack', promptId=info['prompt_id'], queueNumber=info.get('number'))
    save(pending, record)
    save(OUT / 'generation-submissions.json', dict(comfyUrl=engine.COMFY_URL, records=[record],
        progressPolling=False, acceptedIdlePreserved=True, backgroundRemovalDeferred=True))
    print('ATTACK_SUBMITTED', record['promptId'], flush=True)


if __name__ == '__main__':
    main()
