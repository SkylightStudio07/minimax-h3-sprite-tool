"""Two separate pixel attack tests using one accepted corrected still."""
import argparse,hashlib,json,shutil,sys,time
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import pixel_attack_prompts as prompts
OUT=ROOT/'outputs/pixel-attack-actions-20261019'
SOURCE=ROOT/'outputs/pixel-static-source-20261019/swordswoman/corrected.png'
WIDTH=HEIGHT=192
SCALE=3
OFFSET=(32,56)

def save(folder,name,data):(folder/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def prepare():
 OUT.mkdir(exist_ok=True);original=Image.open(SOURCE).convert('RGBA');assert original.size==(128,128)
 oldmeta=json.loads((ROOT/'outputs/pixel-female-combat-20261019/swordswoman/reference-settings.json').read_text(encoding='utf-8'))
 templates={}
 for key,item in prompts.TEMPLATES.items():
  folder=OUT/key;folder.mkdir(exist_ok=True)
  canvas=Image.new('RGBA',(WIDTH,HEIGHT));canvas.paste(original,OFFSET)
  assert np.array_equal(np.array(canvas)[56:184,32:160],np.array(original))
  canvas.save(folder/'reference.png');shutil.copyfile(SOURCE,folder/'source-cleaned-still.png')
  enlarged=canvas.resize((WIDTH*SCALE,HEIGHT*SCALE),Image.Resampling.NEAREST)
  matte=Image.new('RGB',enlarged.size,(128,128,128));matte.paste(enlarged,mask=enlarged.getchannel('A'));matte.save(folder/'video-input.png')
  config=dict(id=key,label=item['label'],source=str(SOURCE),sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),spriteSize=[WIDTH,HEIGHT],offset=list(OFFSET),videoSize=[WIDTH*SCALE,HEIGHT*SCALE],scale=SCALE,palette=oldmeta['palette'][:32]+[[213,244,255],[119,205,236],[54,133,198],[255,228,145]],seed=item['seed'],originalRGBAUnchanged=True,requestedPhases=item['requestedPhases'],allowFacingChange=item['allowFacingChange'],templateStatus='experimental; observed motion review pending')
  save(folder,'source-settings.json',config);templates[key]=dict(**item,status=config['templateStatus'])
 save(OUT,'templates.json',templates);print('PREPARED two independent actions; same corrected still, 192px square with upper headroom',flush=True)

def videos():
 import idle_tool as engine
 from tools.verify_rpg_sprite_styles import ensure_idle
 from tools.verify_pixel_female_combat import release
 from tools import verify_pixel_minimax as exp
 ensure_idle();engine.start_comfy()
 for key,item in prompts.TEMPLATES.items():
  folder=OUT/key
  if (folder/'action-raw.mp4').exists():continue
  ensure_idle();release((8190,8191));exp.OUT=folder
  signature=hashlib.sha256((folder/'video-input.png').read_bytes()).hexdigest();record=folder/'upload.json'
  if record.exists():
   old=json.loads(record.read_text(encoding='utf-8'));assert old['sha256']==signature;name=old['name']
  else:
   name=engine.upload_image((folder/'video-input.png').read_bytes(),f'pixel-action-{key}.png');save(folder,'upload.json',dict(name=name,sha256=signature))
  graph=engine.build_workflow(name,item['motion'],4,WIDTH*SCALE,HEIGHT*SCALE,item['seed'],animation_type='custom',loop=True,facing='preserve',flat_background=True,motion_strength='high',sampling_mode='quality',workflow_id='standard')
  graph['6']['inputs']['prompt']=prompts.build_prompt(key,engine.frame_length(4)/24)
  graph['16']['inputs']['filename_prefix']='pixel_attack_actions/'+key
  graph['15']['inputs'].pop('audio',None);graph.pop('14');graph.pop('5')
  save(folder,'video-settings.json',dict(steps=20,seed=item['seed'],width=WIDTH*SCALE,height=HEIGHT*SCALE,frames=engine.frame_length(4),fps=24,loopKeyframe=True,prompt=graph['6']['inputs']['prompt']))
  start=time.monotonic();history=exp.execute(graph,engine.COMFY_URL,'action-video');shutil.copyfile(engine.find_saved_video(history),folder/'action-raw.mp4');save(folder,'video-timing.json',dict(seconds=round(time.monotonic()-start,2)));print('ACTION VIDEO READY',key,flush=True)
 release((8189,))

def configure_export(key):
 from tools import export_pixel_sword_combo as ep
 ep.OUT=OUT/key;ep.WIDTH=WIDTH;ep.HEIGHT=HEIGHT;ep.SCALE=SCALE;ep.RAW_VIDEO='action-raw.mp4';ep.ENCLOSED_MATTE_MIN_AREA=16*SCALE*SCALE
 return ep

def process(key):configure_export(key).process()
def selected(key):configure_export(key).selected()

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','videos','process','selected']);p.add_argument('--action',choices=list(prompts.TEMPLATES));args=p.parse_args()
 if args.stage in ('process','selected'):
  if not args.action:p.error('--action required')
  globals()[args.stage](args.action)
 else:globals()[args.stage]()
