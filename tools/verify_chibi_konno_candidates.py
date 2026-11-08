"""Six original character still candidates with the accepted nonpixel chibi LoRA."""
import argparse, hashlib, html, json, sys, time
from pathlib import Path
import requests
import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import image_engine, image_background, idle_tool as engine
from tools import verify_pixel_minimax as executor
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_chibi_konno import FILE, digest, save

OUT=ROOT/'outputs/chibi-konno-candidates-20261020'
IDENTITY=(
 'masterpiece, best quality, chibi, 1girl, solo, full body, one original fantasy adventurer, '
 'compact three-head-tall body, short limbs, oversized head, '
 'auburn bob haircut, one small triangular brass hair clip, amber eyes with dark pupils, '
 'ivory blouse, moss green short cape, terracotta leather waistcoat, dark purple trousers, '
 'brown gloves, brown ankle boots, one small brown belt pouch, '
 'detailed anime eyes, finely drawn hair, delicate fabric folds and painted fabric shading. '
)
STANCE=(
 'She is STANDING STILL, with BOTH FEET FIRMLY PLANTED. Her two boots are visibly separated left and right, '
 'both boot soles flat at the SAME ground height. Her legs are uncrossed, with a small gap between both knees and ankles. '
 'Her weight is evenly balanced, torso upright, shoulders relaxed. Neither foot is lifted. '
 'Her body is turned slightly to SCREEN RIGHT in a three-quarter view, nose and gaze directed right. '
)
FINISH=(
 'One single complete character, entire head, both boots and all equipment visible with generous empty margins. '
 'Isolated on a perfectly plain WHITE background, no scenery, no visible floor and no cast shadow.'
)
NEGATIVE=(
 'worst quality, low quality, lowres, blurry, photo, photorealistic, 3d render, plastic, '
 'pixel art, pixelated, dithering, flat vector, thick black outline, sticker border, '
 'blank eyes, missing pupils, stick eyes, extra character, multiple characters, extra heads, inset portrait, '
 'character sheet, panels, grid, collage, close up, cropped, out of frame, '
 'crossed legs, raised foot, lifted leg, running, walking, tiptoe, jumping, balancing on one leg, '
 'curved sword, scimitar, katana, saber, bent blade, bow, rapier, curved guard, '
 'extra arms, extra hands, extra weapon, two swords, floating weapon, detached blade, bad hands, '
 'large breasts, cleavage, high heels, underwear, halo, text, logo, watermark, floor, cast shadow'
)
POSES={
 'low':('낮춘 검 · 준비 자세',
  'Her RIGHT gloved hand holds ONE SHORT STRAIGHT DOUBLE-EDGED silver sword with a simple straight brass crossguard. '
  'The flat symmetrical blade has straight parallel edges and ONE central point, no curve. '
  'Her sword hand rests just in front of the right hip; the blade points diagonally DOWN AND RIGHT into empty space, clear of both legs. '
  'Her left hand is empty and relaxed beside the left hip. There is no scabbard or second weapon. '),
 'sheathed':('검 수납 · 빈손 준비 자세',
  'ONE short sword is fully SHEATHED in a straight dark brown scabbard secured to the belt behind the left hip. '
  'Only its small brass hilt is visible above the scabbard; NO EXPOSED BLADE. '
  'Both hands are empty with relaxed closed fingers. Both elbows are slightly bent and held away from the torso. '
  'There is only one sword in total. '),
 'guard':('몸 앞 세운 검 · 준비 자세',
  'Both gloved hands grip the hilt of ONE SHORT STRAIGHT DOUBLE-EDGED silver sword in front of the abdomen. '
  'The simple straight brass crossguard is clearly visible. '
  'The symmetrical rigid blade extends diagonally UP AND RIGHT through empty space to the RIGHT of the face, never across the eyes. '
  'The blade has straight parallel edges and one central pointed tip, no curve. '
  'Both elbows stay bent low near the torso. There is no scabbard or second weapon. '),
}
CASES={f'{pose}-{n}':dict(pose=pose,label=f'{POSES[pose][0]} {n}',strength=.8,seed=2026102700+i*2+n)
 for i,pose in enumerate(POSES) for n in (1,2)}
SIMPLE_PROMPT=(
 'masterpiece, best quality, chibi, 1girl, solo, full body, standing, feet apart, '
 'three-quarter view, facing right, auburn bob hair, brass triangle hair clip, amber eyes, '
 'ivory blouse, green short cape, brown leather waistcoat, purple trousers, brown gloves, brown boots, '
 'holding a sword in right hand, sword pointing down, left hand empty, '
 'detailed eyes, detailed clothing, white background, simple background'
)
SIMPLE_NEGATIVE=(
 'worst quality, low quality, blurry, cropped, multiple characters, dual wielding, '
 'extra weapon, extra arms, crossed legs, raised leg, walking, running, '
 'curved blade, 3d render, pixel art, text, watermark, shadow'
)
for key,strength in [('simple065',.65),('simple080',.8)]:
 CASES[key]=dict(pose='simple',label=f'짧은 설명 · 강도 {strength}',strength=strength,seed=2026102721,
  prompt=SIMPLE_PROMPT,negativePrompt=SIMPLE_NEGATIVE)

def graph(key):
 c=CASES[key]
 prompt=c['prompt'] if 'prompt' in c else IDENTITY+STANCE+POSES[c['pose']][1]+FINISH
 negative=c.get('negativePrompt',NEGATIVE+(', exposed blade, drawn sword, holding weapon' if c['pose']=='sheathed' else ''))
 p=image_engine.validate(dict(model='anima-base',mode='text',preset='illustration',prompt=prompt,negativePrompt=negative,
  width=1024,height=1216,steps=30,cfg=4.,seed=c['seed'],background='keep'))
 g=image_engine.build_workflow(p,c['seed'])
 g['11']=dict(class_type='LoraLoaderModelOnly',inputs=dict(model=['1',0],lora_name=str(Path(FILE)),strength_model=c['strength']))
 g['7']['inputs']['model']=['11',0];g['9']['inputs']['filename_prefix']='chibi_konno_candidates/'+key
 return g

def generate():
 OUT.mkdir(exist_ok=True)
 manifest=json.loads((ROOT/'outputs/chibi-konno-test-20261020/model.json').read_text(encoding='utf-8'))
 assert digest(engine.COMFY_ROOT/'models/loras'/FILE)==manifest['sha256']
 save(OUT/'model.json',manifest)
 save(OUT/'site-before.json',dict(catalogSha256=digest(ROOT/'web/assets/sprite-examples/catalog.json')))
 ensure_idle()
 for port in (8190,8191):requests.post(f'http://127.0.0.1:{port}/free',json=dict(unload_models=True,free_memory=True),timeout=30).raise_for_status()
 for key,c in CASES.items():
  folder=OUT/key;folder.mkdir(exist_ok=True)
  if (folder/'reference.png').exists():continue
  ensure_idle();g=graph(key);executor.OUT=folder
  save(folder/'settings.json',dict({**c,'prompt':g['4']['inputs']['text'],'negativePrompt':g['5']['inputs']['text']},model='anima-base',lora=FILE,
   width=1024,height=1216,steps=30,cfg=4.,originalCharacter=True,referenceImageUsed=False,pixelOutput=False,
   postGenerationRepaint=False,backgroundRemoval='CPU anime segmentation + sprite boundary cleanup'))
  started=time.monotonic();record=executor.execute(g,engine.COMFY_URL,'still-v1')
  r=requests.get(engine.COMFY_URL+'/view',params=record['outputs']['9']['images'][0],timeout=60);r.raise_for_status();(folder/'raw.png').write_bytes(r.content)
  with Image.open(folder/'raw.png') as im:
   assert im.size==(1024,1216)
   image_background.remove_sprite(im).save(folder/'reference.png')
  save(folder/'timing.json',dict(seconds=round(time.monotonic()-started,1)))
  build();print('CHIBI_CANDIDATE_READY',key,flush=True)
 ensure_idle();requests.post(engine.COMFY_URL+'/free',json=dict(unload_models=True,free_memory=True),timeout=30).raise_for_status()

def build():
 review=json.loads((OUT/'review.json').read_text(encoding='utf-8')) if (OUT/'review.json').exists() else {}
 cards=[];panel=Image.new('RGB',(512*3,660*((len(CASES)+2)//3)),'#263247');draw=ImageDraw.Draw(panel)
 for i,(key,c) in enumerate(CASES.items()):
  folder=OUT/key
  if not (folder/'reference.png').exists():continue
  im=Image.open(folder/'reference.png').convert('RGBA');im=im.crop(im.getchannel('A').getbbox());im.thumbnail((460,580),Image.Resampling.LANCZOS)
  tile=Image.new('RGBA',(512,612));tile.alpha_composite(im,((512-im.width)//2,(612-im.height)//2));tile.save(folder/'preview.png')
  x=i%3*512;y=i//3*660;panel.paste(tile,(x,y+32),tile);draw.text((x+12,y+12),key,fill='white')
  note=review.get('cases',{}).get(key,'생성 완료 · 검토 전')
  cards.append(f'<article><h2>{c["label"]}</h2><img src="{key}/preview.png"><p>{html.escape(note)}</p><small>그림체 강도{c["strength"]} · 시드{c["seed"]}</small><p><a href="{key}/raw.png">생성 원본</a> · <a href="{key}/reference.png">투명 PNG</a> · <a href="{key}/settings.json">프롬프트·설정</a></p></article>')
 panel.save(OUT/'comparison.webp',quality=95)
 page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>치비 원화 · 추가 후보 6종</title><style>body{margin:24px;background:#171e2b;color:#eef0f6;font:15px/1.65 system-ui}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}article{padding:18px;background:#263247;border-radius:15px}img{width:100%;background:repeating-conic-gradient(#263247 0 25%,#3c4960 0 50%) 0/24px 24px}a{color:#c6c3ff}h2{font-size:20px}small{color:#b5c1d6}</style><h1>치비 원화 · 추가 후보 6종</h1><p>선택한 Anima Base + 비도트 치비 그림체 강도0.8을 유지하고, 같은 오리지널 지도 제작자의 준비 자세와 시드를 바꿨습니다. 각 자세의 두 장은 같은 설명에 다른 시드입니다. 서로 다른 자세끼리는 프롬프트도 다르므로 시드만의 비교가 아닙니다.</p><p>1024×1216 실제 로컬 생성 → CPU 배경 제거. 다른 AI로 재도색·얼굴 보정·도트화는 하지 않았습니다. 발·손·검의 실수도 원본 그대로 확인할 수 있습니다. 원화 후보 단계이며 동작 생성과 사이트 등록은 아직 하지 않았습니다.</p><p><a href="../chibi-konno-test-20261020/preview.html">이전 강도 비교</a> · <a href="comparison.webp">6장 한눈에 보기</a></p><main>'''+''.join(cards)+'</main></html>'
 page=page.replace('6종',str(len(CASES))+'종').replace('6장 한눈에',str(len(CASES))+'장 한눈에')
 page=page.replace('<main>','<p>같은 캐릭터 설명을 사용했어도 의상·머리핀·장비 디자인은 달라집니다. 마지막 두 장은 설명을 짧게 바꾼 재시험입니다. 두 장끼리는 같은 설명·시드에서 강도0.65/0.8만 비교하며, 앞의 여섯 장과는 프롬프트도 달라 강도만의 차이로 해석하지 않습니다.</p><main>')
 selected=review.get('selectedForComparison',[])
 if selected:
  best=Image.new('RGBA',(512*len(selected),650));label=ImageDraw.Draw(best)
  for i,key in enumerate(selected):
   im=Image.open(OUT/key/'preview.png').convert('RGBA');best.alpha_composite(im,(i*512,32));label.text((i*512+12,10),key,fill='white')
  best.save(OUT/'selected.png')
  page=page.replace('<main>','<p><a href="selected.png">우선 비교할 두 후보</a></p><main>')
 (OUT/'preview.html').write_text(page,encoding='utf-8')

def check():
 from html.parser import HTMLParser
 class Links(HTMLParser):
  def handle_starttag(self,tag,attrs):
   for k,v in attrs:
    if k in ('src','href'):assert (OUT/v).is_file(),v
 Links().feed((OUT/'preview.html').read_text(encoding='utf-8'))
 manifest=json.loads((OUT/'model.json').read_text(encoding='utf-8'));assert digest(engine.COMFY_ROOT/'models/loras'/FILE)==manifest['sha256']
 before=json.loads((OUT/'site-before.json').read_text(encoding='utf-8'));assert digest(ROOT/'web/assets/sprite-examples/catalog.json')==before['catalogSha256']
 records={}
 for key,c in CASES.items():
  folder=OUT/key;g=json.loads((folder/'still-v1-workflow.json').read_text(encoding='utf-8'))
  assert g==graph(key)
  history=json.loads((folder/'still-v1-history.json').read_text(encoding='utf-8'));assert history['status']['status_str']=='success'
  raw=Image.open(folder/'raw.png').convert('RGB');cut=Image.open(folder/'reference.png').convert('RGBA');a=np.asarray(cut.getchannel('A'))
  assert raw.size==cut.size==(1024,1216) and a.min()==0 and a.max()>240
  edge=bool(a[0].any() or a[-1].any() or a[:,0].any() or a[:,-1].any())
  records[key]=dict(rawSha256=digest(folder/'raw.png'),cutoutSha256=digest(folder/'reference.png'),bbox=cut.getchannel('A').getbbox(),edgeContact=edge)
 save(OUT/'validation.json',dict(passed=True,loraHashVerified=True,workflowAndHistoriesVerified=True,previewLinksExist=True,
  rawSize=[1024,1216],generatedLocally=True,siteCatalogUnchanged=True,published=False,cases=records))
 print('CHIBI_CANDIDATES_VALIDATED',len(records),flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['generate','build','check']);args=p.parse_args();globals()[args.stage]()
