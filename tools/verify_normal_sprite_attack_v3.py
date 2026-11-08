"""Retry a real diagonal cut with additional motion space; keep v2 archived."""
import argparse,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import verify_normal_sprite_refine as run
SOURCE=run.OUT
run.OUT=ROOT/'outputs/normal-sprite-attack-v3-20261020'
run.ACTIONS={'attack':dict(frames=24,loop=False,strength='high',padding=50,revision='motion-v3',seed=2026102083,prompt=(
 'Perform ONE compact, forceful DIAGONAL SWORD CUT toward screen RIGHT. '
 'Anticipation: bend the knees and draw the two-handed hilt briefly above the rear shoulder, loading the rear leg. '
 'Execution: push off the rear boot and pivot the hips, then the shoulders. '
 'The sword BLADE sweeps in ONE clear circular arc from above the shoulder DOWN through the space in front to below waist height. '
 'The hands descend diagonally from the shoulder toward the front hip; elbows then fold in to brake the swing. '
 'End with hands CLOSE to the pelvis and blade pointing diagonally DOWN and RIGHT near the front ankle, NOT extended forward at shoulder height. '
 'This is a CUT, never a stab, thrust, jab or fencing lunge. Only a short forward weight shift, no large leap. '
 'Keep the spine long, chest lifted, front knee flexed and rear heel pivoting; legs and hip rotation drive the cut, not bowing at the waist. '
 'Hair and skirt follow with a sharp delayed whip, then settle in the low balanced follow-through. '
 'Do not return to the starting pose or attack again. '
 'Keep the exact original adult woman, face, costume and cel shaded illustration. ONE rigid silver sword of unchanged length, both hands attached to the same hilt. '
 'Maintain the small character size of the reference and fixed camera: retain all the surrounding empty space. '
 'Keep the entire overhead blade arc, ponytail and both boots at least a generous margin INSIDE the canvas. No effects or scenery.'))}
if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['motion','export']);a=p.parse_args()
 run.OUT.mkdir(exist_ok=True)
 for name in ('reference.png','reference-raw.png'):
  if not (run.OUT/name).exists():shutil.copyfile(SOURCE/name,run.OUT/name)
 getattr(run,a.stage)()
