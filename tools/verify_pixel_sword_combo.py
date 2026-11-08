"""Private corrected pixel still -> MiniMax triple slash combo."""
import argparse,hashlib,json,shutil,sys,time
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'outputs/pixel-sword-combo-20261019'
SOURCE=ROOT/'outputs/pixel-static-source-20261019/swordswoman/corrected.png'
WIDTH,HEIGHT,SCALE=192,128,4
OFFSET=(8,0)
SEED=2026101951
PROMPT=(
 'A spectacular but readable side-scrolling game SWORD COMBO: exactly THREE successive different sword cuts by the same woman, all attacking SCREEN RIGHT. '
 'The actions chain immediately into one another, not one swing followed by a long idle. '
 'At 0.0-0.35 seconds she lowers her centre of gravity and coils her shoulder with the sword drawn back. '
 'FIRST CUT at 0.35-1.15 seconds: an explosive diagonal downward slash from above her head toward the lower right, a small forward step and a crisp stop at the end of the cut. '
 'SECOND CUT at 1.15-2.05 seconds: immediately reverse the sword into an upward rising diagonal slash from the low right to above the head, extending knees and torso into the rising motion. '
 'THIRD CUT at 2.05-3.25 seconds: draw the weapon back and finish with a strong wide horizontal rightward cut, front knee bent, torso and sword arm rotating into the follow-through. '
 'At 3.25-4.1 seconds the ponytail and split skirt follow through as she brakes. At 4.1-5.0 seconds recover to the opening ready stance and opening screen position. '
 'Three distinct readable acceleration and impact beats: DOWN, UP, then HORIZONTAL. Show visible movement of the sword arm, balancing free arm, shoulders, hips, knees, ponytail and skirt. '
 'Stay a strict screen-right side view; a short grounded step only, no full body spin, no somersault, no facing viewer, no camera shake. '
 'ONE rigid straight silver sword in her same near hand, constant blade and handle length; the empty hand stays empty, no duplicates, no weapon stretching, no lost grip. '
 'Each cut leaves a SHORT clean pale cyan crescent afterimage following the blade, which disappears before the next cut; a few tiny warm spark pixels at the last cut. '
 'Keep effects compact, legible square pixel clusters, no giant energy ball or continuous beam and no smoke cloud covering the character. '
 'Preserve the EXACT small pixel-art character from the input: auburn ponytail, cream short jacket, dark teal split skirt, dark trousers, brown gloves and boots, modest adult build. '
 'Keep face, head size, clothing volume and palette stable, with no body inflation or melting limbs. '
 'The character retains the input screen scale; do not enlarge or shrink her. Use the generous EMPTY space to the right for the blade arcs; leave all weapons/effects inside the canvas. '
 'Fixed orthographic camera and framing, whole head and both boots visible, no cuts, zoom, pan, scene or ground shadow. '
 'Same flat uniform medium grey background, including the gaps between arms and legs. Preserve chunky native pixel clusters, no smooth anime redraw or painted texture.')

def save(name,value):(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def prepare():
 OUT.mkdir(exist_ok=True)
 original=Image.open(SOURCE).convert('RGBA');assert original.size==(128,128)
 canvas=Image.new('RGBA',(WIDTH,HEIGHT));canvas.paste(original,OFFSET)
 assert np.array_equal(np.array(canvas)[0:128,8:136],np.array(original))
 canvas.save(OUT/'reference.png');shutil.copyfile(SOURCE,OUT/'source-cleaned-still.png')
 enlarged=canvas.resize((WIDTH*SCALE,HEIGHT*SCALE),Image.Resampling.NEAREST)
 matte=Image.new('RGB',enlarged.size,(128,128,128));matte.paste(enlarged,mask=enlarged.getchannel('A'));matte.save(OUT/'video-input.png')
 refmeta=json.loads((ROOT/'outputs/pixel-female-combat-20261019/swordswoman/reference-settings.json').read_text(encoding='utf-8'))
 palette=refmeta['palette'][:32]+[[213,244,255],[119,205,236],[54,133,198],[255,228,145]]
 save('source-settings.json',dict(source=str(SOURCE),sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),spriteSize=[WIDTH,HEIGHT],offset=OFFSET,originalRGBAUnchanged=True,videoSize=[WIDTH*SCALE,HEIGHT*SCALE],palette=palette,seed=SEED,requestedAction='three connected cuts: downward, rising, horizontal',prompt=PROMPT))
 print('PREPARED corrected still, widened canvas',flush=True)

def video():
 import idle_tool as engine
 from tools.verify_rpg_sprite_styles import ensure_idle
 from tools.verify_pixel_female_combat import release
 from tools import verify_pixel_minimax as exp
 ensure_idle();engine.start_comfy();release((8190,8191));exp.OUT=OUT
 digest=hashlib.sha256((OUT/'video-input.png').read_bytes()).hexdigest();record=OUT/'upload.json'
 if record.exists():
  previous=json.loads(record.read_text(encoding='utf-8'));assert previous['sha256']==digest;name=previous['name']
 else:
  name=engine.upload_image((OUT/'video-input.png').read_bytes(),'pixel-sword-combo-cleaned.png');save('upload.json',dict(name=name,sha256=digest))
 graph=engine.build_workflow(name,PROMPT,5,WIDTH*SCALE,HEIGHT*SCALE,SEED,animation_type='custom',loop=True,facing='right',flat_background=True,motion_strength='high',sampling_mode='quality',workflow_id='standard')
 graph['16']['inputs']['filename_prefix']='pixel_sword_combo/triple_slash'
 graph['15']['inputs'].pop('audio',None);graph.pop('14');graph.pop('5')
 save('video-settings.json',dict(steps=20,seed=SEED,width=WIDTH*SCALE,height=HEIGHT*SCALE,frames=engine.frame_length(5),fps=24,loopKeyframe=True,prompt=graph['6']['inputs']['prompt']))
 start=time.monotonic();history=exp.execute(graph,engine.COMFY_URL,'combo-video');shutil.copyfile(engine.find_saved_video(history),OUT/'combo-raw.mp4');save('video-timing.json',dict(seconds=round(time.monotonic()-start,2)));release((8189,));print('COMBO VIDEO READY',flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','video']);args=p.parse_args();globals()[args.stage]()
