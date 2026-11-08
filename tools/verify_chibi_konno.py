"""Private nonpixel chibi reference comparison using the selected LoRA."""
import argparse, hashlib, html, json, os, shutil, sys, time
from pathlib import Path
import requests
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import image_engine, image_background, idle_tool as engine
from tools import verify_pixel_minimax as job
from tools.verify_rpg_sprite_styles import ensure_idle

OUT=ROOT/'outputs/chibi-konno-test-20261020'
FILE='chibi/konno-takashi-anima-base-v1.safetensors'
MODEL=2604230;VERSION=3175539;SEED=2026102601
PROMPT=(
 'masterpiece, best quality, 1girl, solo, chibi, full body, original fantasy adventurer, '
 'three and a half heads tall, compact body, short limbs, large head, '
 'auburn bob haircut, small triangular brass hair clip, amber eyes with visible dark pupils, '
 'ivory blouse, moss green short cape, terracotta leather waistcoat, dark purple trousers, '
 'brown gloves, brown ankle boots, small brown belt pouch, '
 'holding one short straight silver sword with brass crossguard in her right hand, sword lowered beside her body, '
 'relaxed battle ready stance, knees slightly bent, three-quarter side view, facing right, looking right, '
 'detailed anime eyes, intricate clothing folds, subtle fabric shading, finely drawn hair, '
 'single complete character, entire head both boots and whole sword visible, generous empty margins, '
 'isolated on plain white background, simple background'
)
NEGATIVE=(
 'worst quality, low quality, lowres, blurry, photo, realistic, 3d render, doll, plastic, '
 'pixel art, pixelated, dithering, thick black outline, flat vector, icon, sticker border, '
 'blank eyes, missing pupils, dot eyes, stick eyes, '
 'multiple characters, extra heads, inset portrait, duplicate, character sheet, grid, collage, split screen, '
 'close up, cropped, out of frame, long legs, realistic proportions, '
 'extra arms, extra hands, extra weapon, two swords, detached blade, bad hands, '
 'cleavage, large breasts, high heels, underwear, halo, text, logo, watermark, floor, cast shadow'
)
CASES={
 'base':dict(label='기본 모델 · 비교 기준',strength=0.,seed=SEED),
 'style080':dict(label='선택한 치비 · 강도 0.8',strength=.8,seed=SEED),
 'style100':dict(label='선택한 치비 · 강도 1.0',strength=1.,seed=SEED),
 'variant':dict(label='선택한 치비 · 다른 후보',strength=.9,seed=SEED+1),
}

def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def download():
 from dotenv import load_dotenv
 OUT.mkdir(exist_ok=True);load_dotenv(ROOT/'.env')
 r=requests.get(f'https://civitai.com/api/v1/models/{MODEL}',timeout=30);r.raise_for_status();card=r.json();save(OUT/'creator-card.json',card)
 v=next(v for v in card['modelVersions'] if v['id']==VERSION);assert v['baseModel']=='Anima' and v['name']=='BaseV1.0'
 file=next(f for f in v['files'] if f['type']=='Model' and f['name'].endswith('.safetensors'))
 expected=file['hashes']['SHA256'].lower();target=engine.COMFY_ROOT/'models/loras'/FILE;target.parent.mkdir(exist_ok=True)
 if not target.exists():
  key=os.getenv('CIVITAI_API_KEY');headers={'Authorization':'Bearer '+key} if key else {};partial=target.with_suffix('.download')
  print('DOWNLOADING',round(file['sizeKB']/1024,1),'MiB',flush=True)
  with requests.get(file['downloadUrl'],headers=headers,stream=True,timeout=(20,90)) as response:
   response.raise_for_status()
   with partial.open('wb') as f:
    for block in response.iter_content(4*1024*1024):f.write(block)
  assert partial.stat().st_size==round(file['sizeKB']*1024)
  assert digest(partial)==expected,'LoRA download hash mismatch'
  partial.replace(target)
 assert digest(target)==expected
 save(OUT/'model.json',dict(modelId=MODEL,versionId=VERSION,baseModel='Anima Base 1.0',file=FILE,
  sha256=expected,bytes=target.stat().st_size,source=f'https://civitai.com/models/{MODEL}?modelVersionId={VERSION}',
  triggers=v['trainedWords'],recommendedStrength=[.8,1.],permissions={k:card.get(k) for k in ('allowCommercialUse','allowNoCredit','allowDerivatives')},status='Private still test, not enabled in site presets'))
 print('LORA_VERIFIED',target,flush=True)

def graph(key):
 c=CASES[key];p=image_engine.validate(dict(model='anima-base',mode='text',preset='illustration',prompt=PROMPT,negativePrompt=NEGATIVE,
  width=1024,height=1216,steps=30,cfg=4.,seed=c['seed'],background='keep'))
 g=image_engine.build_workflow(p,c['seed'])
 if c['strength']:
  g['11']=dict(class_type='LoraLoaderModelOnly',inputs=dict(model=['1',0],lora_name=str(Path(FILE)),strength_model=c['strength']))
  g['7']['inputs']['model']=['11',0]
 g['9']['inputs']['filename_prefix']='chibi_konno_test/'+key
 return g

def generate():
 OUT.mkdir(exist_ok=True);assert (OUT/'model.json').exists();ensure_idle()
 for port in (8190,8191):requests.post(f'http://127.0.0.1:{port}/free',json=dict(unload_models=True,free_memory=True),timeout=30).raise_for_status()
 for key,c in CASES.items():
  folder=OUT/key;folder.mkdir(exist_ok=True)
  if (folder/'reference.png').exists():continue
  ensure_idle();g=graph(key);job.OUT=folder
  save(folder/'settings.json',dict(model='anima-base',lora=FILE if c['strength'] else None,**c,
   prompt=g['4']['inputs']['text'],negativePrompt=g['5']['inputs']['text'],width=1024,height=1216,steps=30,cfg=4.,
   originalCharacter=True,referenceImageUsed=False,pixelOutput=False,postGenerationRepaint=False))
  start=time.monotonic();record=job.execute(g,engine.COMFY_URL,'still-v1')
  r=requests.get(engine.COMFY_URL+'/view',params=record['outputs']['9']['images'][0],timeout=60);r.raise_for_status();(folder/'raw.png').write_bytes(r.content)
  requests.post(engine.COMFY_URL+'/free',json=dict(unload_models=True,free_memory=True),timeout=30).raise_for_status()
  with Image.open(folder/'raw.png') as im:
   assert im.size==(1024,1216)
   image_background.remove_sprite(im).save(folder/'reference.png')
  save(folder/'timing.json',dict(seconds=round(time.monotonic()-start,1)));build();print('CHIBI_STILL_READY',key,flush=True)

def build():
 rows=[];panel=Image.new('RGB',(512*4,660),'#263247');draw=ImageDraw.Draw(panel)
 review=json.loads((OUT/'review.json').read_text(encoding='utf-8')) if (OUT/'review.json').exists() else {}
 for i,(key,c) in enumerate(CASES.items()):
  folder=OUT/key;source=folder/'reference.png'
  if not source.exists():continue
  im=Image.open(source).convert('RGBA');im=im.crop(im.getchannel('A').getbbox());im.thumbnail((460,580),Image.Resampling.LANCZOS)
  tile=Image.new('RGBA',(512,612));tile.alpha_composite(im,((512-im.width)//2,(612-im.height)//2));tile.save(folder/'preview.png')
  panel.paste(tile,(512*i,32),tile);draw.text((512*i+12,12),f'{key} / {c["strength"]}',fill='white')
  note=review.get('cases',{}).get(key,'생성 후 검토 대기')
  rows.append(f'<article><h2>{c["label"]}</h2><img src="{key}/preview.png"><p>{html.escape(note)}</p><p><a href="{key}/raw.png">생성 원본</a> · <a href="{key}/reference.png">투명 PNG</a> · <a href="{key}/settings.json">프롬프트·설정</a></p></article>')
 panel.save(OUT/'comparison.webp',quality=95)
 page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>선택한 치비 그림체 · 실제 원화 시험</title><style>body{margin:24px;background:#171e2b;color:#eef0f6;font:15px/1.65 system-ui}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}article{padding:18px;background:#263247;border-radius:15px}img{width:100%;background:repeating-conic-gradient(#263247 0 25%,#3c4960 0 50%) 0/24px 24px}a{color:#c6c3ff}h2{font-size:20px}</style><h1>선택한 치비 그림체 · 실제 생성 비교</h1><p>제작자 샘플이 아닌 로컬에서 새로 생성한 오리지널 캐릭터입니다. 선택한 비도트 치비 LoRA를 Anima Base 1.0에 적용했습니다. 1024×1216 생성 후 CPU 배경 제거만 적용했고, 다른 AI로 다시 그리기·얼굴 보정·도트화는 하지 않았습니다.</p><p>기준/0.8/1.0은 동일 프롬프트·시드이며 마지막은 시드도 바꾼 별도 후보입니다. 원화 비교 단계로, 아직 동작 생성이나 사이트 예시 등록은 하지 않았습니다.</p><main>'''+''.join(rows)+'</main></html>'
 (OUT/'preview.html').write_text(page,encoding='utf-8')

def check():
 import numpy as np
 from html.parser import HTMLParser
 class Links(HTMLParser):
  def handle_starttag(self,tag,attrs):
   for k,v in attrs:
    if k in ('src','href'):assert (OUT/v).is_file(),v
 Links().feed((OUT/'preview.html').read_text(encoding='utf-8'))
 manifest=json.loads((OUT/'model.json').read_text(encoding='utf-8'))
 assert digest(engine.COMFY_ROOT/'models/loras'/FILE)==manifest['sha256']
 records={}
 for key,c in CASES.items():
  folder=OUT/key;g=json.loads((folder/'still-v1-workflow.json').read_text(encoding='utf-8'))
  assert (g['6']['inputs']['width'],g['6']['inputs']['height'])==(1024,1216)
  assert g['7']['inputs']['seed']==c['seed']
  assert ('11' in g)==bool(c['strength'])
  if c['strength']:assert g['11']['inputs']['strength_model']==c['strength'] and g['11']['inputs']['lora_name']==str(Path(FILE))
  history=json.loads((folder/'still-v1-history.json').read_text(encoding='utf-8'));assert history['status']['status_str']=='success'
  raw=Image.open(folder/'raw.png').convert('RGB');cut=Image.open(folder/'reference.png')
  assert raw.size==cut.size==(1024,1216) and cut.mode=='RGBA'
  alpha=np.asarray(cut.getchannel('A'));assert alpha.min()==0 and alpha.max()>240
  assert not any(alpha[0]) and not any(alpha[-1]) and not any(alpha[:,0]) and not any(alpha[:,-1])
  assert np.asarray(raw).std()>5
  records[key]=dict(rawSha256=digest(folder/'raw.png'),cutoutSha256=digest(folder/'reference.png'),size=list(raw.size),bbox=cut.getchannel('A').getbbox())
 first=[json.loads((OUT/k/'settings.json').read_text(encoding='utf-8')) for k in ('base','style080','style100')]
 assert len({p['prompt'] for p in first})==len({p['seed'] for p in first})==1
 save(OUT/'validation.json',dict(passed=True,loraHashVerified=True,matchedPromptAndSeedForStrengths=True,
  rawSize=[1024,1216],cutoutEdgeContact=False,previewLinksExist=True,generatedLocally=True,published=False,cases=records))
 print('CHIBI_KONNO_VALIDATED',len(records),'actual outputs',flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['download','generate','build','check']);args=p.parse_args();globals()[args.stage]()
