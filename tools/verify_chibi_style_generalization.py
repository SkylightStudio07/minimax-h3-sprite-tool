"""Controlled still comparison of appearance adherence, not a proof of memorization."""
import argparse, html, json, struct, sys, time
from pathlib import Path
import requests
import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import image_engine, image_background, idle_tool as engine
from tools import verify_pixel_minimax as executor
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_chibi_konno import FILE, save, digest

OUT=ROOT/'outputs/chibi-generalization-20261020'
STRENGTHS=(0.,.4,.6,.8)
CHARACTERS={
 'mechanic':dict(label='짙은 피부의 노년 남성 정비사',seed=2026102811,
  description='1man, elderly man, dark brown skin, bald head, thick white beard, brown eyes, orange work overalls, navy blue undershirt, heavy black work boots, utility belt, holding one small steel wrench in his right hand, empty left hand',
  targets=['남성·노년·짙은 피부','대머리·흰 수염','주황 작업복·남색 셔츠','작은 렌치·검 없음']),
 'scholar':dict(label='은빛 긴 땋은 머리의 여성 학자',seed=2026102812,
  description='1woman, adult woman, pale skin, long silver hair in one thick braid hanging over her shoulder, violet eyes, thin round glasses, white scholar robe with cyan trim, blue ankle length skirt, white ankle boots, holding one closed dark blue book at her waist with both hands',
  targets=['성인 여성·밝은 피부','은색 긴 땋은 머리·보라 눈·안경','흰 로브·청록 장식·파란 치마','파란 책·검 없음']),
 'sentinel':dict(label='검은 짧은 머리의 남성 창병',seed=2026102813,
  description='1man, adult man, tan skin, short spiky black hair, blue eyes, stern angular eyebrows, red plate armor, black fitted trousers, red armored boots, holding one long straight spear with a small steel spearhead upright in his right hand, empty left hand',
  targets=['성인 남성·구릿빛 피부','검은 짧은 머리·파란 눈','붉은 판금 갑옷·검은 바지','창·검 없음']),
}
COMMON='masterpiece, best quality, chibi, solo, full body, one original character, compact body, short limbs, large head, '
ENDING=', standing still, feet apart, both boots on the same ground line, three-quarter view, looking toward screen right, detailed eyes, entire head feet and equipment visible, centered with empty margin, plain white background, simple background'
NEGATIVE='worst quality, low quality, blurry, cropped, out of frame, multiple characters, extra head, portrait inset, character sheet, grid, text, watermark, extra arms, bad hands, extra weapon, sword, scabbard, pixel art, 3d render, photo, shadow'

def key(name,strength):return f'{name}-{round(strength*100):03d}'
def graph(name,strength):
 c=CHARACTERS[name]
 p=image_engine.validate(dict(model='anima-base',mode='text',preset='illustration',prompt=COMMON+c['description']+ENDING,
  negativePrompt=NEGATIVE,width=1024,height=1216,steps=30,cfg=4.,seed=c['seed'],background='keep'))
 g=image_engine.build_workflow(p,c['seed'])
 if strength:
  g['11']=dict(class_type='LoraLoaderModelOnly',inputs=dict(model=['1',0],lora_name=str(Path(FILE)),strength_model=strength));g['7']['inputs']['model']=['11',0]
 g['9']['inputs']['filename_prefix']='chibi_generalization/'+key(name,strength)
 return g

def prepare():
 OUT.mkdir(exist_ok=True)
 manifest=json.loads((ROOT/'outputs/chibi-konno-test-20261020/model.json').read_text(encoding='utf-8'))
 path=engine.COMFY_ROOT/'models/loras'/FILE;assert digest(path)==manifest['sha256'];save(OUT/'model.json',manifest)
 with path.open('rb') as f:n=struct.unpack('<Q',f.read(8))[0];metadata=json.loads(f.read(n)).get('__metadata__',{})
 save(OUT/'training-metadata.json',metadata)
 subsets=json.loads(metadata['ss_datasets'])[0]['subsets']
 save(OUT/'training-summary.json',dict(uniqueImages=sum(s['img_count'] for s in subsets),subsets=subsets,
  steps=metadata.get('ss_steps'),epochs=metadata.get('ss_num_epochs'),
  limitations='Self-reported training metadata; captions are not original images, no withheld validation images available'))
 if not (OUT/'site-before.json').exists():save(OUT/'site-before.json',dict(catalogSha256=digest(ROOT/'web/assets/sprite-examples/catalog.json')))

def generate():
 prepare();ensure_idle()
 for port in (8190,8191):requests.post(f'http://127.0.0.1:{port}/free',json=dict(unload_models=True,free_memory=True),timeout=30).raise_for_status()
 for name,c in CHARACTERS.items():
  for strength in STRENGTHS:
   folder=OUT/key(name,strength);folder.mkdir(exist_ok=True)
   if (folder/'reference.png').exists():continue
   ensure_idle();g=graph(name,strength);executor.OUT=folder
   save(folder/'settings.json',dict(character=name,label=c['label'],seed=c['seed'],strength=strength,model='anima-base',
    lora=FILE if strength else None,prompt=g['4']['inputs']['text'],negativePrompt=g['5']['inputs']['text'],
    width=1024,height=1216,steps=30,cfg=4.,referenceImageUsed=False,originalCharacter=True,pixelOutput=False,postGenerationRepaint=False))
   start=time.monotonic();record=executor.execute(g,engine.COMFY_URL,'still-v1')
   r=requests.get(engine.COMFY_URL+'/view',params=record['outputs']['9']['images'][0],timeout=60);r.raise_for_status();(folder/'raw.png').write_bytes(r.content)
   with Image.open(folder/'raw.png') as raw:
    assert raw.size==(1024,1216);image_background.remove_sprite(raw).save(folder/'reference.png')
   save(folder/'timing.json',dict(seconds=round(time.monotonic()-start,1)));build();print('GENERALIZATION_READY',key(name,strength),flush=True)
 ensure_idle();requests.post(engine.COMFY_URL+'/free',json=dict(unload_models=True,free_memory=True),timeout=30).raise_for_status()

def build():
 review=json.loads((OUT/'review.json').read_text(encoding='utf-8')) if (OUT/'review.json').exists() else {}
 sections=[];panel=Image.new('RGB',(384*4,540*len(CHARACTERS)),'#263247');draw=ImageDraw.Draw(panel)
 for row,(name,c) in enumerate(CHARACTERS.items()):
  cards=[]
  for col,strength in enumerate(STRENGTHS):
   k=key(name,strength);folder=OUT/k
   if not (folder/'reference.png').exists():continue
   im=Image.open(folder/'reference.png').convert('RGBA');im=im.crop(im.getchannel('A').getbbox());im.thumbnail((350,465),Image.Resampling.LANCZOS)
   tile=Image.new('RGBA',(384,490));tile.alpha_composite(im,((384-im.width)//2,(490-im.height)//2));tile.save(folder/'preview.png')
   x=col*384;y=row*540;panel.paste(tile,(x,y+38),tile);draw.text((x+10,y+10),f'{name} / {strength}',fill='white')
   note=review.get('cases',{}).get(k,'생성 완료 · 시각 검토 전')
   label='미적용 · 기준' if strength==0 else f'그림체 강도 {strength}'
   cards.append(f'<article><h3>{label}</h3><img src="{k}/preview.png"><p>{html.escape(note)}</p><p><a href="{k}/raw.png">생성 원본</a> · <a href="{k}/reference.png">투명 PNG</a> · <a href="{k}/settings.json">프롬프트·설정</a></p></article>')
  sections.append(f'<section><h2>{c["label"]}</h2><p>지시한 외형: '+html.escape(' / '.join(c['targets']))+'</p><div class="row">'+''.join(cards)+'</div></section>')
 panel.save(OUT/'comparison.webp',quality=95)
 examples=Image.new('RGBA',(384*len(CHARACTERS),530));examples_draw=ImageDraw.Draw(examples)
 for i,name in enumerate(CHARACTERS):
  example=OUT/key(name,.4)/'preview.png'
  if not example.exists():continue
  examples.alpha_composite(Image.open(example).convert('RGBA'),(i*384,32));examples_draw.text((i*384+10,8),f'{name} / 0.4',fill='white')
 examples.save(OUT/'strength040-examples.png')
 summary=review.get('summary','생성·검토 진행 중입니다. 미적용 기준과 같은 행을 비교해 주세요.')
 page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>치비 그림체 · 외형 지시 비교</title><style>body{background:#171e2b;color:#eef0f6;margin:24px;font:15px/1.65 system-ui}.row{display:grid;grid-template-columns:repeat(4,minmax(210px,1fr));gap:14px;overflow:auto}article{background:#263247;padding:14px;border-radius:14px}img{width:100%;max-width:384px;background:repeating-conic-gradient(#263247 0 25%,#3c4960 0 50%) 0/24px 24px}a{color:#cbc4ff}section{margin:36px 0}h3{font-size:17px}p{overflow-wrap:anywhere}@media(max-width:800px){.row{grid-template-columns:repeat(2,minmax(0,1fr))}}</style><h1>치비 그림체 · 외형 지시를 얼마나 따르는가?</h1><p>외형이 다른 오리지널 캐릭터 3명 × 미적용·0.4·0.6·0.8 = 12장. 같은 행은 프롬프트·시드·해상도·샘플러를 고정하고 LoRA 적용 여부/강도만 바꿨습니다. 다른 캐릭터끼리는 설명과 시드가 다릅니다.</p><p>모든 그림은 실제 로컬 생성입니다. 1024×1216 원본과 CPU 배경 제거 PNG를 보존했습니다. 다른 AI로 재도색·얼굴 보정·도트화하지 않았습니다. 특정 원작 캐릭터나 참조 이미지도 사용하지 않았습니다.</p><p>이 실험은 외형 지시 반영과 스타일에 따른 변화를 보는 비교입니다. 원본 학습 이미지와 검증 세트가 없어 특정 캐릭터 암기나 과적합 자체를 확정할 수는 없습니다. 캐릭터마다 시드는 하나이므로 일반화할 수 있는 범위도 제한됩니다.</p><p><strong>'''+html.escape(summary)+'</strong></p><p><a href="comparison.webp">12장 한눈에 보기</a></p>'+''.join(sections)+'</html>'
 page=page.replace('<p><a href="comparison.webp">','<p><a href="strength040-examples.png">강도0.4의 서로 다른 캐릭터 3종</a> · <a href="comparison.webp">')
 (OUT/'preview.html').write_text(page,encoding='utf-8')

def check():
 from html.parser import HTMLParser
 class Links(HTMLParser):
  def handle_starttag(self,tag,attrs):
   for k,v in attrs:
    if k in ('href','src'):assert (OUT/v).is_file(),v
 Links().feed((OUT/'preview.html').read_text(encoding='utf-8'))
 rows={};records={}
 for name,c in CHARACTERS.items():
  control=[]
  for strength in STRENGTHS:
   k=key(name,strength);folder=OUT/k;g=json.loads((folder/'still-v1-workflow.json').read_text(encoding='utf-8'));assert g==graph(name,strength)
   history=json.loads((folder/'still-v1-history.json').read_text(encoding='utf-8'));assert history['status']['status_str']=='success'
   control.append((g['4']['inputs']['text'],g['5']['inputs']['text'],g['7']['inputs']['seed']))
   with Image.open(folder/'raw.png') as im:assert im.size==(1024,1216) and np.asarray(im.convert('RGB')).std()>5
   cut=Image.open(folder/'reference.png').convert('RGBA');a=np.asarray(cut.getchannel('A'));assert cut.size==(1024,1216) and a.min()==0 and a.max()>240
   records[k]=dict(rawSha256=digest(folder/'raw.png'),cutoutSha256=digest(folder/'reference.png'),edgeContact=bool(a[0].any() or a[-1].any() or a[:,0].any() or a[:,-1].any()))
  assert len(set(control))==1;rows[name]=dict(fixedPromptAndSeed=True,strengths=list(STRENGTHS))
 manifest=json.loads((OUT/'model.json').read_text(encoding='utf-8'));assert digest(engine.COMFY_ROOT/'models/loras'/FILE)==manifest['sha256']
 before=json.loads((OUT/'site-before.json').read_text(encoding='utf-8'));assert digest(ROOT/'web/assets/sprite-examples/catalog.json')==before['catalogSha256']
 save(OUT/'validation.json',dict(passed=True,outputs=len(records),rows=rows,cases=records,loraHashVerified=True,siteCatalogUnchanged=True,published=False))
 print('GENERALIZATION_VALIDATED',len(records),flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['generate','build','check']);args=p.parse_args();globals()[args.stage]()
