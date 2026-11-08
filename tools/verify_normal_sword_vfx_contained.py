"""Second pass: neutral backdrop and strong but bounded energy, separate provenance."""
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import verify_normal_sword_vfx as base
base.OUT=ROOT/'outputs/normal-sword-vfx-contained-20261020'
base.KEY=(128,128,128)
base.REFERENCE_SCALE=.42
base.COMMON=base.COMMON.replace(
 'Uniform SOLID PURE MAGENTA background RGB 255,0,255, including all spaces between limbs. This magenta is an exclusive removable background, never a costume or effect color. ',
 'Uniform completely flat MEDIUM GREY background RGB 128,128,128 throughout the entire shot, including all spaces between limbs. No background color changes or background lighting. ')
base.EFFECT=(
 'Generate a powerful sharply drawn cyan-blue energy sword arc WITH the physical attack, very vivid and high contrast. '
 'A white-hot core, thick saturated cyan crescent, cobalt blue outer rim and two short parallel trailing ribbons follow the blade path. '
 'The crescent closely hugs the moving blade: its TOTAL height is at most the character height, with only ONE sword length extension '
 'beyond the blade. It must fit wholly in the central two thirds of the image, surrounded by empty GREY margin on all sides. '
 'Do not make a screen-filling wave, gigantic pillar, background wash or beam. '
 'At the final rightward cut create one bright white-gold starburst about the head size, with many fine golden sparks and cyan shards. '
 'Strong luminous colors and layered arcs make the effect spectacular; do not increase its size beyond those bounds. '
 'Keep the face and torso readable. Effects appear exactly during the blade sweep, then fragment and vanish completely before recovery. '
 'No effects over the canvas border. No costume recoloring, colored background, realistic bloom, floor or camera movement.')
for key,item in base.CASES.items():
 item['seed']+=10
 if key=='slash':item['motion']=item['motion'].replace('The bright energy crescent sweeps from above her head down and forward to the right in exact sync with the sword. ', 'A blade-length cyan crescent follows this fast sword sweep directly beside her, in exact sync. ')
if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['video','export','build','check']);p.add_argument('--case',choices=['slash','spin']);a=p.parse_args()
 if a.case:base.CASES={a.case:base.CASES[a.case]}
 if a.stage=='export':
  for name in base.CASES:
   if (base.OUT/name/'raw.mp4').exists():base.export_case(name)
  base.build()
 else:getattr(base,a.stage)()
