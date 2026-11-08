"""Replace chest-driven idle with an explicit forearm/grip-check action."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import submit_character_variations_20261101 as batch

batch.OUT = ROOT / 'outputs/blonde-grip-retry-20261101'
batch.SOURCES = {'blonde': Path('C:/Users/SKYLIGHT/AppData/Local/Temp/codex-clipboard-47bf9e25-9d7f-4cf9-b9d2-bf38cefee72f.png')}
batch.STYLE = (
    'Animate the exact supplied adult game character as a hand-inked TWO-DIMENSIONAL anime '
    'sprite, with original face, proportions, sharp contours, painted cel shadows and fixed '
    'lighting. The black plate carrier is a RIGID solid armor shell: its outer contour, width, '
    'depth, plate spacing, pouch sizes and relation to the ribcage stay constant. It can '
    'translate and rotate as ONE rigid block with the torso, never swell or shrink locally. '
    'Motion is produced by shoulder/elbow/wrist joint rotation and the specified body '
    'weight transfer, not image warping, chest expansion or cloth inflation. ')
batch.MOTIONS = [
    dict(id='01-blonde-idle-grip', character='blonde', action='idle', label='금발 Idle · 지지 손 그립 확인', motion=(
        'A small purposeful LOW-READY GRIP-CHECK IDLE, NOT a breathing cycle. The original '
        'black shotgun stays diagonally DOWN-LEFT at waist level, supported by the same '
        'trigger hand and the same hand beneath the ribbed fore-end. Both boots, knees '
        'and pelvis stay at the original coordinates; the head and gaze remain left. '
        '0.0-0.5s: hold the opening low-ready posture, then gently relax the SUPPORT-HAND '
        'fingers under the fore-end without releasing the weapon. 0.5-1.25s: the support '
        'wrist changes angle slightly and those fingers visibly RE-CLOSE once in a firmer '
        'grip at the SAME fore-end location. At the same time, rotate the support elbow '
        'a few centimeters down and inward, letting the whole RIGID shotgun trace one '
        'small smooth downward muzzle arc of about FOUR degrees. Trigger hand, receiver, '
        'stock and fore-end remain connected and move as one rigid assembly. 1.25-2.5s: '
        'rotate that elbow/wrist back and restore the exact opening gun angle and grip. '
        'The torso makes only a very small rigid counterrotation to balance the arms; '
        'armor and blouse shape remain constant. Hair ends and skirt hem respond with '
        'a very small delayed settling caused by that arm adjustment. 2.5-3.0s: settle '
        'back into the opening ready stance and same hand positions for looping. '
        'Keep the pump/fore-end itself fixed to the gun; no pumping stroke or reload. '
        'One visible grip-check only. No breathing pulse, chest movement, head bob, '
        'hip rocking, knee exercise, shoulder pumping, muzzle raise, firing or eye aura.')),
    dict(id='02-blonde-fire-v2', character='blonde', action='attack', label='금발 사격 · 눈 기운과 전신 반동', motion=(
        'ONE crisp physical shotgun shot toward SCREEN LEFT, followed by complete recovery '
        'to the original LOW-READY stance. 0.0-0.4s: firmly raise the original shotgun '
        'to the shoulder, align the long barrel LEFT, flex the front knee and transfer '
        'the pelvis a short distance forward. Both hands stay at the trigger and '
        'support grips. The rigid plate carrier follows the moving torso as one solid '
        'shell, without local shape change. 0.4-0.8s: fire ONE sharp shot from the '
        'ACTUAL leftmost barrel mouth, a brief COMPACT orange-white muzzle flash '
        'extending no more than a quarter-head length and a small dissipating smoke '
        'puff. The whole rigid weapon kicks straight back into the shoulder with '
        'slight muzzle rise; elbows fold to receive the impulse, upper torso and '
        'hips counterrotate briefly and knees absorb the force while feet remain '
        'planted. The full body participates naturally rather than the gun tip '
        'trembling alone. At that shot, TWO THIN CRIMSON ENERGY WISPS flow from the '
        'outer corner of the visible GREEN EYE and stream BACKWARD RIGHT beside '
        'the temple. They visibly emanate and taper as fluid smoke, maximum ONE '
        'HEAD-WIDTH long, never a thick red band over the face. Keep the original '
        'green iris, eyelids, forehead and skin visible. No eye laser, red face '
        'paint, huge spiral, floating ring or aura covering both eyes. The fine '
        'red eye stream flares with the shot, trails the actual small head motion '
        'then rapidly thins. Hair and skirt follow recoil with a short delay. '
        '0.8-1.4s: restore the leftward sight line and stable balance. 1.4-2.6s: '
        'LOWER the same shotgun back to its original diagonal DOWN-LEFT low-ready '
        'angle, eye wisps fading completely; restore original elbow positions, '
        'pelvis and knee angles. 2.6-3.0s: settle in the EXACT opening low-ready '
        'posture. One shot then return, no sustained firing, gun replacement, '
        'breast or armor inflation, repeated squats, head turn or camera move.')),
]


def correct_metadata():
    p = batch.OUT / 'generation-submissions.json'
    if p.exists():
        d = json.loads(p.read_text(encoding='utf-8'))
        d['expectedJobs'] = 2
        batch.save(p, d)
    p = batch.OUT / 'batch-plan.json'
    if p.exists():
        d = json.loads(p.read_text(encoding='utf-8'))
        d['expectedJobs'] = 2
        batch.save(p, d)
    p = batch.OUT / 'preview.html'
    if p.exists():
        text = p.read_text(encoding='utf-8').replace('캐릭터 동작 바리에이션 · 9개', '금발 재생성 · 그립 확인 Idle / 사격')
        text = text.replace('../comfy/character_variations_20261101/', '../comfy/blonde_grip_retry_20261101/')
        p.write_text(text, encoding='utf-8')


def next_job():
    # The shared runner uses this prefix for output recovery; replace only its
    # task-local output path and prefix, keeping the original batch untouched.
    import inspect
    source = inspect.getsource(batch.next_job)
    source = source.replace("'outputs/comfy/character_variations_20261101'", "'outputs/comfy/blonde_grip_retry_20261101'")
    source = source.replace("'character_variations_20261101/'", "'blonde_grip_retry_20261101/'")
    source = source.replace('ALL_NINE_COMPLETE', 'BOTH_COMPLETE')
    scope = dict(batch.__dict__)
    exec(compile(source, __file__, 'exec'), scope)
    scope['next_job']()
    correct_metadata()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=('prepare', 'next'))
    args = parser.parse_args()
    if args.stage == 'prepare':
        batch.prepare()
        correct_metadata()
    else:
        next_job()
