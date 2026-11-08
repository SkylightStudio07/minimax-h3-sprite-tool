"""Private comparison of the two user-selected pixel chibi LoRAs."""
import argparse, hashlib, html, json, os, shutil, sys, time, zipfile
from pathlib import Path
import requests, numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import idle_tool as engine
from tools import verify_pixel_minimax as job
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release
OUT=ROOT/'outputs/chibi-alternatives-20261020'
SOURCE=ROOT/'outputs/chibi-eyes-size-20261020/balanced'
CASES={
 'game':dict(label='1 · 게임용 도트 치비',modelId=1936887,versionId=2192164,base='Illustrious',file='pixel/game-character-chibi-v1.safetensors',strength=.7,trigger='pixel_character_sprite, pxlchrctrsprt, sprite art, pixel art, retro game, chibi'),
 'anima':dict(label='3 · 치비 Anima판',modelId=2565918,versionId=2948181,base='Anima',file='pixel/chibi-anima-base-v1.safetensors',strength=.9,trigger='pixel art, chibi, white background, simple background'),
}
LABELS={'previous':'이전 치비 A · 비교 기준',**{k:v['label'] for k,v in CASES.items()}}
COMMON=('1girl, solo, full body, standing in a simple game idle stance, three-quarter view, facing slightly right, '
 'auburn hair, high ponytail, green eyes, cream military jacket, teal skirt, dark trousers, brown gloves, brown boots, '
 'small straight sword held at her side pointing down, chibi, 2.5 heads tall, compact body, '
 '(small black pupils inside green irises:1.25), distinct white sclera, dark upper eyelids, one small eye highlight, '
 'both pupils looking in the same direction, small anime nose and mouth, compact square pixel clusters, '
 'clean dark outline, limited palette, two-tone cel shading, single character centered, head and both feet visible, '
 'empty margin around every side, plain white background, simple background')
NEGATIVE=('worst quality, low quality, blurry, jpeg artifacts, photo, realistic, 3d, render, smooth painting, gradient, '
 'adult realistic proportions, pinup, cleavage, large breasts, high heels, close up, portrait, cropped, multiple people, '
 'multiple views, sprite sheet, grid, text, watermark, shadow, floor, blank eyes, no pupils, empty eyes, '
 'glowing eyes, cross-eyed, mismatched pupils, detailed irises, multiple eye highlights, hair covering eyes')

def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def prepare():
 OUT.mkdir(parents=True,exist_ok=True)
 sources={str(p.relative_to(ROOT)):digest(p) for folder in [SOURCE,ROOT/'outputs/anime-pixel-chibi-20261019/rpg'] for p in folder.glob('*.png')}
 old=OUT/'source-hashes.json'
 if old.exists():assert json.loads(old.read_text(encoding='utf-8'))==sources
 else:save(old,sources)
 for name in LABELS:(OUT/name).mkdir(exist_ok=True)
 for f in ('raw.png','cutout.png','settings.json'):shutil.copyfile(SOURCE/f,OUT/'previous'/f)

def download():
 from dotenv import load_dotenv
 prepare();load_dotenv(ROOT/'.env');key=os.getenv('CIVITAI_API_KEY');headers={'Authorization':'Bearer '+key} if key else {}
 cached=json.loads((ROOT/'outputs/chibi-anime-research-20261020/search.json').read_text(encoding='utf-8'));manifest={}
 for name,c in CASES.items():
  card=next(m for m in cached['items'] if m['id']==c['modelId']);v=next(v for v in card['modelVersions'] if v['id']==c['versionId']);assert v['baseModel']==c['base']
  file=next(f for f in v['files'] if f['type']=='Model' and f['name'].endswith('.safetensors'))
  expected=file['hashes']['SHA256'].lower();target=engine.COMFY_ROOT/'models/loras'/c['file'];target.parent.mkdir(parents=True,exist_ok=True)
  save(OUT/name/'creator-card.json',card)
  if not target.exists():
   partial=target.with_suffix('.download');print('DOWNLOADING',name,round(file['sizeKB']/1024,1),'MiB',flush=True)
   with requests.get(file['downloadUrl'],headers=headers,stream=True,timeout=(20,60)) as r:
    r.raise_for_status()
    with partial.open('wb') as f:
     for chunk in r.iter_content(4*1024*1024):f.write(chunk)
   assert partial.stat().st_size==round(file['sizeKB']*1024)
   assert digest(partial)==expected,'Download hash mismatch'
   partial.replace(target)
  assert digest(target)==expected
  manifest[name]=dict(**c,sha256=expected,bytes=target.stat().st_size,commercialUseFlags=card.get('allowCommercialUse'),source=f'https://civitai.com/models/{c["modelId"]}?modelVersionId={c["versionId"]}',status='Private comparison; not enabled as public preset')
  save(OUT/'models.json',manifest);print('VERIFIED',name,flush=True)
 print('DOWNLOADS_COMPLETE',flush=True)

def graph(name):
 c=CASES[name];prompt='masterpiece, best quality, '+c['trigger']+', '+COMMON
 if name=='game':
  g=json.loads((SOURCE/'still-clip2-validated-workflow.json').read_text(encoding='utf-8'))
  g['2']['inputs'].update(lora_name=str(Path(c['file'])),strength_model=c['strength'],strength_clip=c['strength'])
  g['4']['inputs']['text']=prompt;g['5']['inputs']['text']=NEGATIVE
 else:
  def n(kind,**inputs):return dict(class_type=kind,inputs=inputs)
  g={'1':n('UNETLoader',unet_name='anima_baseV10.safetensors',weight_dtype='default'),
   '2':n('CLIPLoader',clip_name='qwen_3_06b_base.safetensors',type='stable_diffusion'),
   '3':n('VAELoader',vae_name='qwen_image_vae.safetensors'),
   '11':n('LoraLoaderModelOnly',model=['1',0],lora_name=str(Path(c['file'])),strength_model=c['strength']),
   '4':n('CLIPTextEncode',clip=['2',0],text=prompt),'5':n('CLIPTextEncode',clip=['2',0],text=NEGATIVE),
   '6':n('EmptyLatentImage',width=1024,height=1024,batch_size=1),
   '7':n('KSampler',model=['11',0],positive=['4',0],negative=['5',0],latent_image=['6',0],seed=2026101991,steps=28,cfg=4.,sampler_name='euler',scheduler='simple',denoise=1.),
   '8':n('VAEDecode',samples=['7',0],vae=['3',0]),'9':n('SaveImage',images=['8',0],filename_prefix='chibi_alternatives/anima')}
 g['9']['inputs']['filename_prefix']='chibi_alternatives/'+name
 return g

def retry():
 """Keep first outputs intact; test lower style strengths and explicit pupil/solo cues."""
 ensure_idle();engine.start_comfy();release((8190,8191))
 manifest=json.loads((OUT/'models.json').read_text(encoding='utf-8'))
 try:
  for name,parent,strength,label in [('game-solo','game',.45,'1 · 재시험 · 강도 0.45'),('anima-pupils','anima',.7,'3 · 재시험 · 동공 강조')]:
   folder=OUT/name;folder.mkdir(exist_ok=True);g=graph(parent)
   if parent=='game':g['2']['inputs'].update(strength_model=strength,strength_clip=strength)
   else:g['11']['inputs']['strength_model']=strength
   g['4']['inputs']['text']=g['4']['inputs']['text'].replace('(small black pupils inside green irises:1.25)','(distinct black pupils:1.5), green irises, white sclera')
   g['4']['inputs']['text']='(solo:1.4), (one human girl alone:1.3), '+g['4']['inputs']['text']
   g['5']['inputs']['text']+=', goblin, monster, creature, companion, background character, extra character, duplicate, collage, collection, floating head'
   g['9']['inputs']['filename_prefix']='chibi_alternatives/'+name
   manifest[name]={**manifest[parent], 'label':label,'strength':strength,'parent':parent}
   save(OUT/'models.json',manifest);shutil.copyfile(OUT/parent/'creator-card.json',folder/'creator-card.json')
   save(folder/'settings.json',dict(model=CASES[parent]['base'],lora=CASES[parent]['file'],strength=strength,prompt=g['4']['inputs']['text'],negativePrompt=g['5']['inputs']['text'],seed=2026101991,width=1024,height=1024,sampling=g['7']['inputs'],referenceImageUsed=False,clipSkip=2 if parent=='game' else None,retryReason='First game output had extra creatures; first Anima pupils were not distinct black dots'))
   if (folder/'raw.png').exists():continue
   job.OUT=folder;started=time.monotonic();history=job.execute(g,engine.COMFY_URL,'retry-solo-pupils-v1')
   r=requests.get(engine.COMFY_URL+'/view',params=history['outputs']['9']['images'][0],timeout=30);r.raise_for_status();(folder/'raw.png').write_bytes(r.content)
   with Image.open(folder/'raw.png') as im:assert im.size==(1024,1024) and np.array(im.convert('RGB')).std()>5
   save(folder/'timing.json',dict(seconds=round(time.monotonic()-started,2)));print('GENERATED',name,flush=True)
 finally:release((8189,))

def include_retries():
 for name,label in [('game-solo','1 · 재시험 · 강도 0.45'),('anima-pupils','3 · 재시험 · 동공 강조')]:
  if (OUT/name/'raw.png').exists():LABELS[name]=label
 ordered={name:LABELS[name] for name in ['previous','game-solo','anima-pupils','anima','game'] if name in LABELS}
 LABELS.clear();LABELS.update(ordered)

def generate():
 ensure_idle();engine.start_comfy();release((8190,8191))
 try:
  for name,c in CASES.items():
   folder=OUT/name;g=graph(name);weights=engine.COMFY_ROOT/'models/loras'/c['file']
   manifest=json.loads((OUT/'models.json').read_text(encoding='utf-8'));assert digest(weights)==manifest[name]['sha256']
   if (folder/'raw.png').exists():continue
   save(folder/'settings.json',dict(model=c['base'],lora=c['file'],strength=c['strength'],prompt=g['4']['inputs']['text'],negativePrompt=NEGATIVE,seed=2026101991,width=1024,height=1024,sampling=g['7']['inputs'],referenceImageUsed=False,clipSkip=2 if name=='game' else None))
   job.OUT=folder;start=time.monotonic();history=job.execute(g,engine.COMFY_URL,'still-pupils-v1')
   r=requests.get(engine.COMFY_URL+'/view',params=history['outputs']['9']['images'][0],timeout=30);r.raise_for_status();(folder/'raw.png').write_bytes(r.content)
   with Image.open(folder/'raw.png') as im:assert im.size==(1024,1024) and np.array(im.convert('RGB')).std()>5
   save(folder/'timing.json',dict(seconds=round(time.monotonic()-start,2)));print('GENERATED',name,flush=True)
 finally:release((8189,))

def finish():
 # Reuse the established crop, matte, 32-color, binary-alpha exports, with no new face painting.
 include_retries()
 from tools import verify_chibi_eyes_size as size
 size.OUT=OUT;size.LABELS=LABELS;size.prepare=prepare;size.build=build
 # Its reference branch is keyed by 'original'; mark our preserved cutout similarly while processing.
 size.LABELS={'original':LABELS['previous'],**{k:v for k,v in LABELS.items() if k!='previous'}}
 (OUT/'original').mkdir(exist_ok=True)
 for f in ('raw.png','cutout.png','settings.json'):shutil.copyfile(OUT/'previous'/f,OUT/'original'/f)
 size.finish()
 # Keep one reference name throughout the deliverable.
 records=json.loads((OUT/'results.json').read_text(encoding='utf-8'))
 for r in records:
  if r['id']=='original':r['id']='previous'
 save(OUT/'results.json',records)
 for p in (OUT/'original').glob('sprite-*.png'):shutil.copyfile(p,OUT/'previous'/p.name)
 build();print('EXPORTED',OUT/'preview.html',flush=True)

def build():
 if not (OUT/'results.json').exists():return
 records=json.loads((OUT/'results.json').read_text(encoding='utf-8'));review=json.loads((OUT/'review.json').read_text(encoding='utf-8')) if (OUT/'review.json').exists() else {'summary':'생성·내보내기 완료. 동공과 전체 외형의 시각 검토 전 비교 결과입니다.'}
 rows=[]
 panel=Image.new('RGB',(1710,590*len(records)),'#263344');draw=ImageDraw.Draw(panel)
 for row,r in enumerate(records):
  name=r['id'];cards=''.join(f'<article><h3>{v["size"]}×{v["size"]} · {v["colors"]}색</h3><img src="{name}/sprite-{v["size"]}-4x.png"><p><a href="{name}/sprite-{v["size"]}.png" download>PNG 저장</a></p></article>' for v in r['outputs'])
  note=review.get('cases',{}).get(name,{}).get('summary','')
  rows.append(f'<section><h2>{html.escape(r["label"])}</h2><p>{html.escape(note)}</p><div class="row">{cards}</div><p><a href="{name}/raw.png">1024px 생성 원본 · 눈 확인</a> · <a href="{name}/settings.json">프롬프트·설정</a></p></section>')
  for col,v in enumerate(r['outputs']):
   size=v['size'];x=col*570;y=row*590;draw.text((x+12,y+12),f'{name} / {size}px / 4x',fill='white');im=Image.open(OUT/name/f'sprite-{size}-4x.png').convert('RGBA');panel.paste(im,(x+6,y+48),im)
 panel.save(OUT/'comparison.png')
 page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>치비 후보 1·3 비교</title><style>body{margin:24px;background:#151b26;color:#eee;font:15px/1.6 system-ui}a{color:#c8c4ff}.row{display:flex;gap:16px;flex-wrap:wrap}article{padding:16px;background:#252d3b;border-radius:12px;overflow:auto;max-width:86vw}img{image-rendering:pixelated;background:repeating-conic-gradient(#202632 0 25%,#455069 0 50%) 0/24px 24px}section{margin:32px 0}</style><h1>치비 후보 1·3 · 동공 비교</h1><p>기존 치비 A / 1번 게임용 도트 치비 / 3번 Anima판입니다. 같은 외형 설명·시드로 새로 생성했지만 베이스·학습 데이터가 달라 동일 캐릭터나 포즈를 보장하지 않습니다. 새 조합에는 검은 동공을 명시했습니다. 기준 A는 이전 결과 그대로라 프롬프트까지 통제한 실험은 아닙니다. 재시험은 LoRA 강도를 낮추면서 단독 인물·검은 동공 지시도 강화했으므로 강도 변화만의 효과로 해석하지 않습니다.</p><p>64·96·128px 저장 PNG, 정확한 4배 최근접 미리보기. 1024px 생성 → 기존 CPU 배경 제거/경계 정리 → 최근접 축소 → 최대 32색·이진 알파. 눈을 따로 그려 넣거나 얼굴 보정을 하지는 않았습니다. 배경 제거의 가는 무기 누락 가능성도 남습니다.</p>'''
 page+='<p><strong>'+html.escape(review['summary'])+'</strong></p><p><a href="chibi-alternatives.zip" download>전체 PNG·원본·설정 ZIP</a></p>'+''.join(rows)+'</html>'
 (OUT/'preview.html').write_text(page,encoding='utf-8')
 with zipfile.ZipFile(OUT/'chibi-alternatives.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in OUT.rglob('*'):
   if p.is_file() and p.suffix in ('.png','.json','.html') and 'original' not in p.relative_to(OUT).parts:z.write(p,p.relative_to(OUT))

def check():
 include_retries()
 for p,h in json.loads((OUT/'source-hashes.json').read_text(encoding='utf-8')).items():assert digest(ROOT/p)==h
 records=json.loads((OUT/'results.json').read_text(encoding='utf-8'));assert {r['id'] for r in records}==set(LABELS)
 for r in records:
  with Image.open(OUT/r['id']/'raw.png') as raw:assert raw.size==(1024,1024) and np.array(raw.convert('RGB')).std()>5
  for v in r['outputs']:
   size=v['size'];a=np.array(Image.open(OUT/r['id']/f'sprite-{size}.png').convert('RGBA'));b=np.array(Image.open(OUT/r['id']/f'sprite-{size}-4x.png').convert('RGBA'))
   assert a.shape==(size,size,4) and set(np.unique(a[:,:,3]))=={0,255} and len(np.unique(a[:,:,:3][a[:,:,3]>0],axis=0))<=32
   assert np.array_equal(b,np.repeat(np.repeat(a,4,axis=0),4,axis=1))
   if r['id']=='previous':assert np.array_equal(a,np.array(Image.open(SOURCE/f'sprite-{size}.png').convert('RGBA')))
 import re
 for link in re.findall(r'(?:href|src)="([^"]+)"',(OUT/'preview.html').read_text(encoding='utf-8')):assert (OUT/link).exists(),link
 save(OUT/'validation.json',dict(passed=True,pngs=sum(len(r['outputs']) for r in records),sourceHashesUnchanged=True,maxColors=32,binaryAlpha=True,exact4x=True,actualBrowserVerified=False));build()
 with zipfile.ZipFile(OUT/'chibi-alternatives.zip') as z:
  assert z.testzip() is None
  assert z.read('validation.json')==(OUT/'validation.json').read_bytes()
  if (OUT/'review.json').exists():assert z.read('review.json')==(OUT/'review.json').read_bytes()
 print('PASS sprites, source hashes, alpha/palette, exact 4x, links and ZIP',flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['download','generate','retry','finish','build','check','all']);args=p.parse_args()
 if args.stage=='all':
  for step in (download,generate,finish,check):step()
 else:globals()[args.stage]()
