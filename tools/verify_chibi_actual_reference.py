"""Actual original illustration -> chibi geometry -> selected Anima style.

Both reference paths encode image pixels; no franchise character references.
"""
import argparse, hashlib, html, io, json, shutil, sys, time
from pathlib import Path
import requests
import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import idle_tool as engine, image_engine, image_background, rigging_engine as rig
from tools import verify_pixel_minimax as executor
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_chibi_konno import FILE,save,digest

OUT=ROOT/'outputs/chibi-actual-reference-20261020'
SOURCE=ROOT/'web/assets/asset-type-previews/original-cartographer.png'
SEED=2026102901;SIZE=(1024,1216)
PROMPT=(
 'masterpiece, best quality, chibi, 1girl, solo, full body, '
 'the same original female cartographer from the input image, compact three-head-tall body, short arms and legs, large head, '
 'short plum brown bob haircut, ONE small triangular brass hair clip, amber eyes, '
 'white collared blouse with small dark cuff buttons, tan brown fitted waistcoat, moss green cape with dark teal lining, '
 'purple trousers, brown leather belt, diagonal brown satchel strap, brown flap satchel at hip, '
 'gold star brooch at collar, round brass compass attached to shoulder strap, '
 'bare hands without gloves, holding ONE small golden star-tipped wand in her raised right hand, '
 'left hand relaxed near waist, standing with both feet separated on the same ground line, simple brown ankle boots, '
 'three-quarter view, warm gentle expression, detailed anime eyes, delicate painted clothing and hair detail, '
 'single complete character centered with empty margin, plain pure white background, simple background'
)
NEGATIVE=(
 'worst quality, low quality, blurry, pixel art, photo, 3d render, plastic, '
 'tall body, realistic proportions, long legs, portrait, cropped, out of frame, '
 'multiple characters, extra heads, inset portrait, collage, reference sheet, panels, '
 'extra arms, bad hands, gloves, duplicate hair clip, extra wand, sword, scabbard, armor, '
 'halo, magic circle, glowing beam, floating stars, background rays, radial lines, scenery, '
 'text, logo, watermark, floor, cast shadow'
)
CASES={
 'direct060':dict(label='원화 직접 변형 · 그림체0.6',stage='direct',strength=.6,denoise=.85),
 'direct080':dict(label='원화 직접 변형 · 그림체0.8',stage='direct',strength=.8,denoise=.85),
 'draft060-d045':dict(label='치비 초안 기반 · 그림체0.6 / 변형0.45',stage='draft',strength=.6,denoise=.45),
 'draft080-d045':dict(label='치비 초안 기반 · 그림체0.8 / 변형0.45',stage='draft',strength=.8,denoise=.45),
 'draft060-d065':dict(label='치비 초안 기반 · 그림체0.6 / 변형0.65',stage='draft',strength=.6,denoise=.65),
 'draft080-d065':dict(label='치비 초안 기반 · 그림체0.8 / 변형0.65',stage='draft',strength=.8,denoise=.65),
}

def fit(image,size=SIZE):
 im=image.convert('RGBA');im.thumbnail((size[0]-96,size[1]-96),Image.Resampling.LANCZOS)
 canvas=Image.new('RGBA',size,'white');canvas.alpha_composite(im,((size[0]-im.width)//2,(size[1]-im.height)//2))
 return canvas.convert('RGB')

def release(url):requests.post(url+'/free',json=dict(unload_models=True,free_memory=True),timeout=30).raise_for_status()
def execute(g,url,folder,name):folder.mkdir(parents=True,exist_ok=True);executor.OUT=folder;return executor.execute(g,url,name)

def prepare():
 OUT.mkdir(exist_ok=True)
 if not (OUT/'source-original.png').exists():shutil.copyfile(SOURCE,OUT/'source-original.png')
 assert digest(SOURCE)==digest(OUT/'source-original.png')
 with Image.open(SOURCE) as im:fit(im).save(OUT/'source-prepared.png')
 manifest=json.loads((ROOT/'outputs/chibi-konno-test-20261020/model.json').read_text(encoding='utf-8'))
 assert digest(engine.COMFY_ROOT/'models/loras'/FILE)==manifest['sha256'];save(OUT/'model.json',manifest)
 save(OUT/'source.json',dict(path=str(SOURCE.relative_to(ROOT)),sha256=digest(SOURCE),originalCharacter=True,
  provenance='Earlier locally generated original cartographer illustration; no franchise reference',
  missingInformation='Source is cropped above the feet; full legs/boots and hidden surfaces must be invented'))
 if not (OUT/'site-before.json').exists():save(OUT/'site-before.json',dict(catalogSha256=digest(ROOT/'web/assets/sprite-examples/catalog.json')))

def draft():
 prepare();folder=OUT/'draft'
 if (folder/'reference.png').exists():return
 ensure_idle();release(engine.COMFY_URL);release('http://127.0.0.1:8191')
 name='chibi_actual_reference_original_20261020.png';shutil.copyfile(SOURCE,rig.INPUT_ROOT/name)
 g=rig.qwen21_workflow(name,'chibi_actual_reference/geometry',1024,20,SEED-1)
 g['6']['inputs'].update(device='cpu',dtype='default')
 g['5']['inputs']['prompt']=(
  'Transform the SAME ORIGINAL WOMAN in image 1 into ONE full-body CHIBI game character. '
  'Use the input image as the source of the face, hairstyle, clothing, colors and all major accessories. '
  'Change body proportions to about THREE HEADS TALL: large head, very short compact torso, short arms and legs. '
  'Preserve her short plum-brown bob haircut, ONE triangular brass hair clip, amber eyes with dark pupils, white collared blouse, '
  'small dark cuff buttons, tan-brown fitted waistcoat, moss green cape with dark teal lining, purple trousers, brown belt, '
  'diagonal brown leather shoulder strap, brown flap satchel, golden star brooch at collar and round brass compass on the strap. '
  'Her bare RIGHT hand holds the SAME ONE short GOLD STAR-TIPPED WAND raised beside the right shoulder. '
  'Her bare LEFT hand rests near the waist. Keep the hands separate and readable, no gloves, no new weapons. '
  'Show the complete head and both feet in simple brown ankle boots. The source does not show boots; complete the missing lower legs naturally. '
  'Both boots are planted apart on the same ground line, not crossed, not walking. '
  'Slight three-quarter view with body and nose angled to SCREEN RIGHT. Preserve the warm gentle expression. '
  'Retain fine anime outlines, amber eye details and original costume colors while reducing the proportions. '
  'Remove the radiating background lines and all scenery. A PURE WHITE BACKGROUND, no floor, no shadow. '
  'Leave ample empty margin around the one whole character, including wand and boots. '
  'No inset heads, portraits, panels, duplicates, halo, floating stars, sword, extra wand, text or logo.')
 g['5']['inputs']['negative_prompt']='multiple characters, panels, collage, extra heads, extra wand, sword, gloves, duplicate hairclip, tall body, realistic proportions, long legs, crossed legs, pixel art, cropped, background rays, floating stars, text, cast shadow'
 record=execute(g,rig.COMFY_URL,folder,'geometry-v1')
 im=Image.open(rig._saved_image(record,'9')).convert('RGBA');im.save(folder/'raw.png');release(rig.COMFY_URL)
 cut=image_background.remove_sprite(im);cut.save(folder/'reference.png');fit(cut).save(folder/'prepared.png')
 save(folder/'settings.json',dict(model='Qwen Image 2.1 Edit',sourceSha256=digest(SOURCE),referenceImageUsed=True,
  prompt=g['5']['inputs']['prompt'],negativePrompt=g['5']['inputs']['negative_prompt'],steps=20,seed=SEED-1,resolution=1024,
  purpose='Full-body chibi proportion/identity draft, not final selected LoRA style'))
 build();print('REFERENCE_CHIBI_DRAFT_READY',flush=True)

def graph(case,image_name):
 c=CASES[case]
 # The production UI restricts Anima Base to text mode. This private graph
 # deliberately uses standard VAEEncode -> KSampler with the same model/vae.
 p=image_engine.validate(dict(model='anima-base',mode='text',preset='illustration',prompt=PROMPT,negativePrompt=NEGATIVE,
  width=SIZE[0],height=SIZE[1],steps=36,cfg=4.,seed=SEED,background='keep'))
 p.update(mode='reference',denoise=c['denoise'])
 g=image_engine.build_workflow(p,SEED,image_name=image_name)
 g['11']=dict(class_type='LoraLoaderModelOnly',inputs=dict(model=['1',0],lora_name=str(Path(FILE)),strength_model=c['strength']))
 g['7']['inputs']['model']=['11',0];g['9']['inputs']['filename_prefix']='chibi_actual_reference/'+case
 return g

def styles(stage):
 prepare();ensure_idle();release(rig.COMFY_URL);release('http://127.0.0.1:8191')
 for case,c in CASES.items():
  if c['stage']!=stage:continue
  folder=OUT/case
  if (folder/'reference.png').exists():continue
  source=OUT/('source-prepared.png' if stage=='direct' else 'draft/prepared.png')
  assert source.exists()
  ensure_idle();uploaded=engine.upload_image(source.read_bytes(),'chibi-reference-'+stage+'.png');g=graph(case,uploaded)
  folder.mkdir(exist_ok=True);shutil.copyfile(source,folder/'input.png')
  save(folder/'settings.json',dict(**c,model='anima-base',lora=FILE,seed=SEED,width=SIZE[0],height=SIZE[1],steps=36,cfg=4.,
   prompt=g['4']['inputs']['text'],negativePrompt=g['5']['inputs']['text'],referenceImageUsed=True,
   sourceSha256=digest(source),originalSourceSha256=digest(SOURCE),path='Original illustration -> '+('VAEEncode -> Anima LoRA' if stage=='direct' else 'Qwen chibi draft -> VAEEncode -> Anima LoRA'),
   originalCharacter=True,pixelOutput=False,postGenerationRepaint=False,privateExperimentalGraph=True))
  start=time.monotonic();record=execute(g,engine.COMFY_URL,folder,'reference-v1')
  r=requests.get(engine.COMFY_URL+'/view',params=record['outputs']['9']['images'][0],timeout=60);r.raise_for_status();(folder/'raw.png').write_bytes(r.content)
  with Image.open(folder/'raw.png') as im:
   assert im.size==SIZE;image_background.remove_sprite(im).save(folder/'reference.png')
  save(folder/'timing.json',dict(seconds=round(time.monotonic()-start,1)));build();print('REFERENCE_STYLE_READY',case,flush=True)
 ensure_idle();release(engine.COMFY_URL)

def thumb(path):
 im=Image.open(path).convert('RGBA');box=im.getchannel('A').getbbox();im=im.crop(box);im.thumbnail((440,550),Image.Resampling.LANCZOS)
 tile=Image.new('RGBA',(480,580));tile.alpha_composite(im,((480-im.width)//2,(580-im.height)//2));return tile

def build():
 review=json.loads((OUT/'review.json').read_text(encoding='utf-8')) if (OUT/'review.json').exists() else {}
 items=[('source', '입력 원화 · 오리지널',OUT/'source-original.png'),('draft','이미지 기반 치비 비율 초안',OUT/'draft/reference.png')]
 items.extend((case,c['label'],OUT/case/'reference.png') for case,c in CASES.items())
 cards=[];panel=Image.new('RGB',(480*4,620*2),'#263247');draw=ImageDraw.Draw(panel)
 for i,(key,label,path) in enumerate(items):
  if not path.exists():continue
  preview=OUT/(key+'-preview.png');tile=thumb(path);tile.save(preview)
  x=i%4*480;y=i//4*620;panel.paste(tile,(x,y+32),tile);draw.text((x+10,y+10),key,fill='white')
  note=review.get('cases',{}).get(key,'생성·검토 중')
  links=f'<a href="{html.escape(str(path.relative_to(OUT)))}">원본 크기 PNG</a>'
  if key in CASES:links+=f' · <a href="{key}/raw.png">배경 제거 전</a> · <a href="{key}/settings.json">실제 설정</a>'
  cards.append(f'<article><h2>{label}</h2><img src="{key}-preview.png"><p>{html.escape(note)}</p><p>{links}</p></article>')
 panel.save(OUT/'comparison.webp',quality=95)
 selected=review.get('selectedForComparison',[])
 if selected:
  chosen=Image.new('RGB',(480*len(selected),620),'#263247');chosen_draw=ImageDraw.Draw(chosen)
  by_key={key:path for key,_,path in items}
  for i,key in enumerate(selected):
   path=by_key[key]
   if not path.exists():continue
   tile=thumb(path);chosen.paste(tile,(480*i,32),tile);chosen_draw.text((480*i+10,10),key,fill='white')
  chosen.save(OUT/'selected-comparison.webp',quality=95)
 summary=review.get('summary','실제 참조 이미지를 입력한 생성 비교입니다. 결과별 외형·비율은 검토 중입니다.')
 page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>레퍼런스 이미지 → 치비 원화</title><style>body{background:#171e2b;color:#eef0f6;margin:24px;font:15px/1.65 system-ui}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}article{padding:18px;background:#263247;border-radius:15px}img{width:100%;background:repeating-conic-gradient(#263247 0 25%,#3c4960 0 50%) 0/24px 24px}a{color:#cbc4ff}h2{font-size:19px}p{overflow-wrap:anywhere}</style><h1>레퍼런스 이미지 → 치비 원화</h1><p>앞서 직접 생성한 오리지널 지도 제작자 원화를 사용했습니다. 특정 원작 캐릭터는 참조하지 않았습니다. 두 경로 모두 이미지 픽셀을 실제 입력하며, 텍스트 외형 설명만의 신규 생성과 다릅니다.</p><p>① 원화 → Anima 이미지 변형: 큰 비율 변경을 위해 변형0.85, 그림체0.6/0.8. ② 원화 → Qwen 치비 비율 초안 → Anima 이미지 변형: 그림체0.6/0.8 × 변형0.45/0.65. 각 경로 안의 Anima 결과는 같은 설명·시드·입력 캔버스입니다. 원화에서 보이지 않는 발·신발과 가려진 부분은 새로 생성됩니다.</p><p>그림체 강도와 이미지 변형량은 서로 다른 값입니다. 강도는 LoRA 화풍의 영향, 변형량은 입력 이미지를 얼마나 다시 그릴지 조절합니다. 표시용 배경 제거 외에 최종 재도색·얼굴 보정·도트화는 하지 않았습니다.</p><p><strong>'''+html.escape(summary)+'</strong></p><p><a href="comparison.webp">전체 비교 이미지</a></p><main>'+''.join(cards)+'</main></html>'
 if selected:page=page.replace('<main>','<p><a href="selected-comparison.webp">입력 원화 · 직접 변형 · 초안 기반 변형 비교</a></p><main>')
 (OUT/'preview.html').write_text(page,encoding='utf-8')

def check():
 from html.parser import HTMLParser
 class Links(HTMLParser):
  def handle_starttag(self,tag,attrs):
   for k,v in attrs:
    if k in ('src','href'):assert (OUT/v).is_file(),v
 Links().feed((OUT/'preview.html').read_text(encoding='utf-8'))
 assert digest(SOURCE)==digest(OUT/'source-original.png')
 manifest=json.loads((OUT/'model.json').read_text(encoding='utf-8'));assert digest(engine.COMFY_ROOT/'models/loras'/FILE)==manifest['sha256']
 draft_graph=json.loads((OUT/'draft/geometry-v1-workflow.json').read_text(encoding='utf-8'));assert draft_graph['5']['inputs']['images.image_1']==['1',0]
 records={}
 for case,c in CASES.items():
  folder=OUT/case;g=json.loads((folder/'reference-v1-workflow.json').read_text(encoding='utf-8'))
  assert g==graph(case,g['10']['inputs']['image'])
  assert g['6']['class_type']=='VAEEncode' and g['6']['inputs']['pixels']==['10',0] and g['7']['inputs']['latent_image']==['6',0]
  expected=OUT/('source-prepared.png' if c['stage']=='direct' else 'draft/prepared.png')
  assert digest(folder/'input.png')==digest(expected)
  settings=json.loads((folder/'settings.json').read_text(encoding='utf-8'));assert settings['sourceSha256']==digest(expected) and settings['referenceImageUsed']
  h=json.loads((folder/'reference-v1-history.json').read_text(encoding='utf-8'));assert h['status']['status_str']=='success'
  with Image.open(folder/'raw.png') as im:assert im.size==SIZE and np.asarray(im.convert('RGB')).std()>5
  cut=Image.open(folder/'reference.png').convert('RGBA');a=np.asarray(cut.getchannel('A'));assert cut.size==SIZE and a.min()==0 and a.max()>240
  records[case]=dict(rawSha256=digest(folder/'raw.png'),referenceInputSha256=digest(expected),edgeContact=bool(a[0].any() or a[-1].any() or a[:,0].any() or a[:,-1].any()))
 before=json.loads((OUT/'site-before.json').read_text(encoding='utf-8'));assert digest(ROOT/'web/assets/sprite-examples/catalog.json')==before['catalogSha256']
 save(OUT/'validation.json',dict(passed=True,actualPixelInput=True,qwenGeometryReference=True,animaVaeEncodeReference=True,
  originalSourceUnchanged=True,loraHashVerified=True,siteCatalogUnchanged=True,published=False,cases=records))
 print('ACTUAL_REFERENCE_VALIDATED',len(records),flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['draft','direct','styled','build','check']);a=p.parse_args()
 if a.stage in ('direct','styled'):styles('direct' if a.stage=='direct' else 'draft')
 else:globals()[a.stage]()
