"""Concise positive description of a local sword highlight, after failed relative-size prompting."""
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import verify_normal_sword_vfx_small as small
from tools import verify_normal_sword_vfx as base
base.OUT=ROOT/'outputs/normal-sword-vfx-subtle-20261020'
base.EFFECT='A fine pale cyan highlight stays on the metal blade. A short translucent forearm-length streak follows just behind its tip for an instant, with a few tiny gold specks.'
COMMON=(
 'A fixed full-body anime game-sprite view of the reference swordswoman. '
 'Keep the same auburn ponytail, cream jacket, dark teal skirt, dark leggings, gloves and boots. '
 'The camera and character scale stay constant on a uniform flat medium-grey background. '
 'The sword remains a straight rigid silver metal blade firmly gripped in both hands. ')
MOTIONS={
 'slash':('Immediately make one quick downward sword cut to screen right from the raised starting pose. '
  'Plant the forward boot, flex the knees and drive both hands from overhead down to the forward hip. '
  'The cut happens during the first half second. Keep the chest lifted and stop in a stable low finishing stance. '
  'Hold the finish as the ponytail settles. '),
 'spin':('Sink onto bent knees, then make one quick full-body turn on two short planted steps. '
  'Show the back of her head and jacket during the turn, then face screen right again. '
  'The hips, shoulders and sword rotate together. Finish by planting the front boot and cutting horizontally to the right. '
  'Stop in a low balanced lunge and hold the finish. ')}
for name,item in base.CASES.items():
 item['label']='작은 검기 · '+('검 휘두르기' if name=='slash' else '회전베기')
 item['neutralGlowMatte']=name=='spin'
 item['motion']=MOTIONS[name]
 item['fullPrompt']=('<Picture 1> is the opening reference.\n\nintegrated_multimodal_description: [Shot 1] '
  +COMMON+MOTIONS[name]+base.EFFECT+' Most of the picture stays empty grey. This is a regular physical sword attack with a subtle local blade highlight. '
  'The short highlight fades completely as the hands stop.\n\noverall_soundscape: N/A\n\nnon_diegetic_music: N/A')

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['video','export','build','check','review']);p.add_argument('--case',choices=['slash','spin']);a=p.parse_args()
 if a.case:base.CASES={a.case:base.CASES[a.case]}
 if a.stage=='export':
  for name in base.CASES:
   if (base.OUT/name/'raw.mp4').exists():base.export_case(name)
  base.build()
 elif a.stage=='review':small.review()
 else:getattr(base,a.stage)()
