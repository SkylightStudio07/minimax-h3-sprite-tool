"""Two sequential blonde motion variants, reusing the reviewed reference."""
import inspect
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import submit_blonde_grip_retry_20261101 as previous

batch = previous.batch
batch.OUT = ROOT / 'outputs/blonde-natural-step-20261102'
batch.MOTIONS = [
    dict(id='01-blonde-natural-idle', character='blonde', action='idle', label='금발 Idle · 자연스러운 호흡과 그립', motion=(
        'A quiet living low-ready idle, one continuous relaxed three-second loop. '
        'Both boots stay in contact with the ground, gaze left, original shotgun diagonally down-left. '
        'Let a slow shallow breath produce an almost imperceptible WHOLE-BODY vertical rise and fall '
        '(roughly two pixels at this framing), carried gently through ankles, pelvis, spine, shoulders '
        'and head together. The chest armor keeps its exact solid shape throughout. '
        'The knees are soft, never visibly dipping into a squat. The support wrist and elbow '
        'make a tiny comfortable settling adjustment as fingers soften and regrip the SAME '
        'fore-end without sliding or pumping it. The rigid shotgun follows the hands in a '
        'small smooth arc, then settles with a slight delay after the shoulders. '
        'Hair tips and skirt hem lag gently behind the body. Avoid synchronized robotic motion: '
        'head, elbow and hair have subtly different easing and settle times. One slight blink '
        'may occur mid-cycle. Start settled, gently rise, exhale and return smoothly to the '
        'same stance and motion phase. No deliberate head nod, exaggerated sway, repeated '
        'grip demonstration, chest swelling, breast scaling, knee pumping, firing or eye aura.')),
    dict(id='02-blonde-step-fire', character='blonde', action='attack', label='금발 사격 · 전진 스텝과 반동', motion=(
        'A decisive single STEP-IN SHOT toward SCREEN LEFT with physically connected full-body motion. '
        '0.0-0.65s: from the original low-ready pose, lift and place the front boot ONE SHORT '
        'STEP toward screen left, visibly moving the pelvis and center of mass with it. '
        'The rear foot supports the push and its heel lifts slightly. Simultaneously raise '
        'the SAME shotgun into the shoulder, hands maintaining both original grips. '
        '0.65-1.05s: as the front foot plants and the body braces, fire ONE forceful shot '
        'from the actual barrel mouth to the left. Compact orange-white muzzle flash, '
        'brief smoke. Weapon recoils into shoulder; elbows fold, shoulders and hips receive '
        'the impulse, front knee yields slightly and rear leg stabilizes. The recoil must '
        'follow the planted step rather than being an isolated arm twitch. '
        'Two fine red energy wisps stream from the visible GREEN eye backward right, at most '
        'one head-width long, with the green iris and face unobscured. Wisps follow the '
        'head motion and fade after the shot. Hair and skirt trail the step and recoil. '
        '1.05-1.7s: recover steady aim with a forward-ready stance. '
        '1.7-2.65s: shift weight back, withdraw the same front boot to its original position '
        'and lower the shotgun to the original down-left low-ready angle. '
        '2.65-3.0s: settle naturally into the exact opening pose. Clear anticipation, fast '
        'step-and-shot accent, softer recovery. Rigid armor and weapon preserve their '
        'design and proportions. No sliding feet, multiple steps, squat exercise, '
        'camera movement, gun redesign, chest deformation or oversized red face aura.')),
]


def prepare():
    ref = batch.OUT / 'references/blonde'
    ref.mkdir(parents=True, exist_ok=True)
    old = ROOT / 'outputs/blonde-grip-retry-20261101/references/blonde'
    for name in ('source-original.png', 'reference.png', 'source.json'):
        shutil.copy2(old / name, ref / name)
    batch.prepare()
    for motion in batch.MOTIONS:
        p = batch.OUT / motion['id'] / 'recipe.json'
        import json
        recipe = json.loads(p.read_text(encoding='utf-8'))
        recipe['seed'] += 100
        batch.save(p, recipe)
    for name in ('batch-plan.json',):
        import json
        p = batch.OUT / name
        data = json.loads(p.read_text(encoding='utf-8'))
        data['expectedJobs'] = 2
        batch.save(p, data)
    p = batch.OUT / 'preview.html'
    html = p.read_text(encoding='utf-8').replace('캐릭터 동작 바리에이션 · 9개', '금발 · 자연스러운 Idle / 스텝 사격')
    html = html.replace('character_variations_20261101/', 'blonde_natural_step_20261102/')
    p.write_text(html, encoding='utf-8')


def next_job():
    source = inspect.getsource(batch.next_job).replace('character_variations_20261101', 'blonde_natural_step_20261102').replace('ALL_NINE_COMPLETE', 'BOTH_COMPLETE')
    scope = dict(batch.__dict__)
    exec(compile(source, __file__, 'exec'), scope)
    scope['next_job']()
    p = batch.OUT / 'generation-submissions.json'
    if p.exists():
        import json
        data = json.loads(p.read_text(encoding='utf-8'))
        data['expectedJobs'] = 2
        batch.save(p, data)


if __name__ == '__main__':
    {'prepare': prepare, 'next': next_job}[sys.argv[1]]()
