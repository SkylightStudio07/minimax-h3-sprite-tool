"""Read creator cards, verify LoRA downloads, compare anime pixel sprite recipes."""
import argparse,hashlib,html,json,re,shutil,sys,time,zipfile
from pathlib import Path
import requests,numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import idle_tool as engine
OUT=ROOT/'outputs/anime-pixel-chibi-20261019'
RESEARCH=ROOT/'outputs/chibi-anime-research-20261019'
CASES={
 'elin':dict(label='작은 치비 도트',modelId=1084875,versionId=1218194,file='pixel/elin-chibi-v1.safetensors',trigger='pixel art, chibi, white background, simple background',strength=.9,body='super deformed, 2 heads tall, oversized head, tiny short torso, very short arms and legs'),
 'rpg':dict(label='JRPG 전신 도트',modelId=1043663,versionId=1334272,file='pixel/rpg-turn-v21c.safetensors',trigger='ROSPRITE, pixel art',strength=.85,body='small stylized game character, 3 heads tall, large head, short compact body, short legs'),
 'deep':dict(label='아니메 도트 화풍',modelId=1493875,versionId=1729809,file='pixel/deep-anime-v2.safetensors',trigger='pixel art',strength=.9,body='chibi, 2.5 heads tall, oversized head, short compact torso, short arms and legs'),
}
COMMON=('1girl, solo, full body, standing in a simple game idle stance, three-quarter view, facing slightly right, '
 'auburn hair, high ponytail, green eyes, cream military jacket, teal skirt, dark trousers, brown gloves, brown boots, '
 'small straight sword held at her side pointing down, readable anime eyes, small anime nose and mouth, '
 'compact square pixel clusters, clean dark outline, limited palette, simple cel shading, '
 'single character centered with head and both feet visible, empty margin around every side, plain white background, simple background')
NEGATIVE=('worst quality, low quality, blurry, jpeg artifacts, photo, realistic, 3d, render, smooth painting, gradient, '
 'adult realistic proportions, long legs, long torso, pinup, cleavage, large breasts, high heels, '
 'close up, portrait, cropped, multiple people, multiple views, sprite sheet, grid, text, watermark, shadow, floor')
REVIEWS={
 'elin':dict(status='candidate',summary='큰 머리·짧은 몸통과 아니메 눈이 읽히는 작은 치비 도트 후보입니다.',limitations='검이 옆으로 뻗고 얼굴/머리 비중이 큽니다. 작은 출력은 눈·칼날 일부가 빠지므로 48·64px을 비교하세요. 방향/동작 일관성을 시험한 결과는 아닙니다.'),
 'rpg':dict(status='candidate',summary='전신 비율이 조금 더 긴 JRPG 도트 후보입니다. 세부 의상은 64·96px에서 더 잘 남습니다.',limitations='요청한 검이 제대로 나오지 않고 가리키는 손처럼 보입니다. 화풍 비교 후보이며 완성 게임 에셋이나 방향 시트가 아닙니다.'),
 'deep':dict(status='rejected-current-output',summary='이번 결과 제외: 단일 캐릭터 지시에도 여러 인물이 한 장에 나왔습니다.',limitations='선이 촘촘한 일러스트 표현이 강하고, 아래 도트는 다인물 이미지를 그대로 축소한 실패 비교입니다. 단일 스프라이트 성공 사례로 사용하지 않습니다.'),
}

def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def download():
 from dotenv import load_dotenv
 import os
 load_dotenv(ROOT/'.env');key=os.getenv('CIVITAI_API_KEY');headers={'Authorization':'Bearer '+key} if key else {}
 OUT.mkdir(exist_ok=True);manifest={}
 for name,case in CASES.items():
  card=json.loads((RESEARCH/f'model-{case["modelId"]}.json').read_text(encoding='utf-8'))
  version=next(v for v in card['modelVersions'] if v['id']==case['versionId']);assert version['baseModel']=='Illustrious'
  entry=next(f for f in version['files'] if f['type']=='Model' and f['name'].endswith('.safetensors'))
  expected=entry['hashes']['SHA256'].lower();target=engine.COMFY_ROOT/'models/loras'/case['file'];target.parent.mkdir(exist_ok=True,parents=True)
  misplaced=engine.COMFY_ROOT/'models'/case['file']
  if not target.exists() and misplaced.exists():
   with misplaced.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==expected
   misplaced.rename(target)
  if not target.exists():
   partial=target.with_suffix('.download')
   with requests.get(entry['downloadUrl'],headers=headers,stream=True,timeout=(20,60)) as response:
    response.raise_for_status()
    with partial.open('wb') as out:
     for chunk in response.iter_content(4*1024*1024):out.write(chunk)
   assert partial.stat().st_size==round(entry['sizeKB']*1024)
   with partial.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==expected
   partial.replace(target)
  with target.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==expected
  folder=OUT/name;folder.mkdir(exist_ok=True);shutil.copyfile(RESEARCH/f'model-{case["modelId"]}.json',folder/'creator-card.json')
  manifest[name]=dict(**case,sha256=expected,size=target.stat().st_size,source=f'https://civitai.com/models/{case["modelId"]}?modelVersionId={case["versionId"]}',description=re.sub('<[^>]*>',' ',card.get('description') or ''),commercialUseFlags=card.get('allowCommercialUse'),usageStatus='Private reference test; not enabled as public service preset',base='waiIllustriousSDXL_v170.safetensors')
  save(OUT/'models.json',manifest);print('VERIFIED',name,target.name,flush=True)

def generate():
 from tools.verify_rpg_sprite_styles import ensure_idle
 from tools.verify_pixel_female_combat import release
 from tools import verify_pixel_minimax as job
 ensure_idle();engine.start_comfy();release((8190,8191))
 for n,(name,case) in enumerate(CASES.items()):
  folder=OUT/name
  if (folder/'raw.png').exists():
   with Image.open(folder/'raw.png') as existing:valid=float(np.array(existing.convert('RGB')).std())>5
   if valid:continue
   invalid=folder/'raw-invalid.png'
   if not invalid.exists():(folder/'raw.png').rename(invalid)
   else:(folder/'raw.png').unlink()
  ensure_idle();seed=2026101991;prompt='masterpiece, best quality, '+case['trigger']+', '+case['body']+', '+COMMON
  graph={
   '1':dict(class_type='CheckpointLoaderSimple',inputs=dict(ckpt_name='waiIllustriousSDXL_v170.safetensors')),
   '2':dict(class_type='LoraLoader',inputs=dict(model=['1',0],clip=['1',1],lora_name=str(Path(case['file'])),strength_model=case['strength'],strength_clip=case['strength'])),
   '3':dict(class_type='CLIPSetLastLayer',inputs=dict(clip=['2',1],stop_at_clip_layer=-2)),
   '4':dict(class_type='CLIPTextEncode',inputs=dict(clip=['3',0],text=prompt)),
   '5':dict(class_type='CLIPTextEncode',inputs=dict(clip=['3',0],text=NEGATIVE)),
   '6':dict(class_type='EmptyLatentImage',inputs=dict(width=1024,height=1024,batch_size=1)),
   '7':dict(class_type='KSampler',inputs=dict(model=['2',0],positive=['4',0],negative=['5',0],latent_image=['6',0],seed=seed,steps=28,cfg=5.,sampler_name='euler_ancestral',scheduler='normal',denoise=1.)),
   '10':dict(class_type='VAELoader',inputs=dict(vae_name='illustriousXLV10_v10.safetensors')),
   '8':dict(class_type='VAEDecode',inputs=dict(samples=['7',0],vae=['10',0])),
   '9':dict(class_type='SaveImage',inputs=dict(images=['8',0],filename_prefix='anime_pixel_chibi/'+name)),
  }
  save(folder/'settings.json',dict(prompt=prompt,negativePrompt=NEGATIVE,seed=seed,steps=28,cfg=5,clipSkip=2,clipSkipReason='WAI v17 CLIP-L final layer contains non-finite weights; use penultimate layer. Deep Pixel card recommends clip skip 1 on its training base, not this checkpoint.',width=1024,height=1024,loraStrength=case['strength'],vae='illustriousXLV10_v10.safetensors',referenceImageUsed=False))
  save(folder/'engine-settings.json',requests.get(engine.COMFY_URL+'/system_stats',timeout=5).json().get('system',{}))
  job.OUT=folder;start=time.monotonic();history=job.execute(graph,engine.COMFY_URL,'still-clip2-validated')
  entry=history['outputs']['9']['images'][0];url=engine.COMFY_URL+'/view';r=requests.get(url,params=entry,timeout=30);r.raise_for_status();(folder/'raw.png').write_bytes(r.content)
  with Image.open(folder/'raw.png') as image:
   if float(np.array(image.convert('RGB')).std())<=5:raise RuntimeError('Blank or invalid image output; do not treat as completed generation')
  save(folder/'timing.json',dict(seconds=round(time.monotonic()-start,2)));print('GENERATED',name,flush=True)
 release((8189,))

def finish():
 import image_background,image_pixel
 from tools.sprite_matte import clean_flat_matte
 results=[]
 for name,case in CASES.items():
  folder=OUT/name
  if not (folder/'raw.png').exists():continue
  with Image.open(folder/'raw.png') as im:raw=im.convert('RGBA')
  # Existing CPU foreground model then local white-edge unmatting. No global erosion.
  cut=image_background.remove(raw);clean,matte=clean_flat_matte(raw,tolerance=24,radius=3)
  a=np.array(cut);b=np.array(clean);a[:,:,3]=np.minimum(a[:,:,3],b[:,:,3]);a[:,:,:3]=b[:,:,:3];a[a[:,:,3]==0,:3]=0
  cut=Image.fromarray(a);cut.save(folder/'cutout.png')
  box=cut.getchannel('A').point(lambda v:255 if v>=128 else 0).getbbox();assert box
  # The same cutout and crop are used for every requested output size.
  content=cut.crop(box);side=max(content.size);canvas=Image.new('RGBA',(side,side));canvas.paste(content,((side-content.width)//2,(side-content.height)//2));records=[]
  for size in [32,48,64,96]:
   fitted=canvas.resize((round(size*.82),round(size*.82)),Image.Resampling.NEAREST);target=Image.new('RGBA',(size,size));target.paste(fitted,((size-fitted.width)//2,(size-fitted.height)//2))
   result=image_pixel.finish(target,size,32);result.save(folder/f'sprite-{size}.png');result.resize((size*6,size*6),Image.Resampling.NEAREST).save(folder/f'sprite-{size}-6x.png')
   a=np.array(result);assert set(np.unique(a[:,:,3]))<={0,255};colors=len(np.unique(a[:,:,:3][a[:,:,3]>0],axis=0));assert colors<=32
   records.append(dict(size=size,colors=colors,opaquePixels=int((a[:,:,3]>0).sum())))
  results.append(dict(id=name,label=case['label'],outputs=records,crop=list(box),backgroundMethod='existing local Anime ISNet + known white-matte edge cleanup',matte=matte,review=REVIEWS[name]))
 save(OUT/'results.json',results);build()

def build():
 results=json.loads((OUT/'results.json').read_text(encoding='utf-8'));cards=[]
 for r in results:
  name=r['id'];images=''.join(f'<article><h3>{v["size"]}×{v["size"]} · {v["colors"]}색</h3><img src="{name}/sprite-{v["size"]}-6x.png"><p><a href="{name}/sprite-{v["size"]}.png" download>PNG 저장</a></p></article>' for v in r['outputs'])
  review=REVIEWS[name]
  cards.append(f'<section><h2>{html.escape(r["label"])}</h2><p><strong>{html.escape(review["summary"])}</strong><br>{html.escape(review["limitations"])}</p><div class="row">{images}</div><p><a href="{name}/raw.png">1024px 생성 원본</a> · <a href="{name}/cutout.png">배경 제거 원본</a> · <a href="{name}/settings.json">프롬프트·설정</a></p></section>')
 page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>아니메 치비 도트 · 모델 비교</title><style>body{font:15px/1.6 system-ui;background:#151b26;color:#eee;margin:24px}a{color:#c8c4ff}.row{display:flex;gap:16px;flex-wrap:wrap}article{background:#252d3b;padding:14px;border-radius:10px;overflow:auto}img{image-rendering:pixelated;background:repeating-conic-gradient(#202632 0 25%,#455069 0 50%) 0/24px 24px;max-width:none}h3{font-size:16px}section{margin-bottom:36px}</style><h1>아니메 치비 도트 · 실제 로컬 모델 비교</h1><p>같은 캐릭터 외형 설명·시드로 각 그림체를 생성했습니다. 참고 이미지를 직접 입력한 변형이 아니며 캐릭터 동일성은 보장하지 않습니다. 각 행의 크기별 결과는 하나의 생성 이미지를 정리한 것입니다.</p><p>1024px 생성 → CPU 배경 제거 → 정사각형 정렬 → 최근접 축소·32색 제한. 원래부터 저해상도 픽셀을 하나씩 그리는 모델은 아닙니다. 모델은 연구용 비교 상태이며 운영 사이트 프리셋에 아직 추가하지 않았습니다.</p><p><a href="anime-pixel-chibi.zip" download>PNG·원본·설정 ZIP</a></p>'''+''.join(cards)+'</html>'
 (OUT/'preview.html').write_text(page,encoding='utf-8')
 with zipfile.ZipFile(OUT/'anime-pixel-chibi.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in OUT.rglob('*'):
   if p.is_file() and p.suffix in ('.png','.json','.html') and 'invalid' not in p.name and 'diagnostics' not in p.parts:z.write(p,p.relative_to(OUT))
 print('PREVIEW',OUT/'preview.html',flush=True)

def check():
 results=json.loads((OUT/'results.json').read_text(encoding='utf-8'));assert {r['id'] for r in results}==set(CASES)
 models=json.loads((OUT/'models.json').read_text(encoding='utf-8'));report={};panel=Image.new('RGB',(3*430,530),'#202632');draw=ImageDraw.Draw(panel)
 for col,r in enumerate(results):
  folder=OUT/r['id'];m=models[r['id']];weights=engine.COMFY_ROOT/'models/loras'/m['file']
  with weights.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==m['sha256']
  with Image.open(folder/'raw.png') as im:assert im.size==(1024,1024) and float(np.array(im).std())>5
  settings=json.loads((folder/'settings.json').read_text(encoding='utf-8'));assert settings['vae']=='illustriousXLV10_v10.safetensors'
  for v in r['outputs']:
   size=v['size'];a=np.array(Image.open(folder/f'sprite-{size}.png').convert('RGBA'));b=np.array(Image.open(folder/f'sprite-{size}-6x.png').convert('RGBA'))
   assert a.shape==(size,size,4) and np.array_equal(b,np.repeat(np.repeat(a,6,axis=0),6,axis=1))
   visible=a[:,:,3]>0;assert visible.any() and (~visible).any() and set(np.unique(a[:,:,3]))<={0,255}
   assert len(np.unique(a[:,:,:3][visible],axis=0))<=32
  im=Image.open(folder/'sprite-64-6x.png').convert('RGBA');panel.paste(im,(col*430+20,55),im);draw.text((col*430+20,15),r['id']+' 64px / 6x',fill='white')
  report[r['id']]=dict(sha256=m['sha256'],sizes=[v['size'] for v in r['outputs']],maxColors=32,binaryAlpha=True,integerPreviewExact=True)
 panel.save(OUT/'comparison-64px.png')
 for url in re.findall(r'(?:src|href)="([^"]+)"',(OUT/'preview.html').read_text(encoding='utf-8')):assert (OUT/url).exists(),url
 save(OUT/'validation.json',dict(passed=True,models=report,actualBrowserVerified=False));build()
 with zipfile.ZipFile(OUT/'anime-pixel-chibi.zip') as z:
  assert z.testzip() is None
  assert z.read('validation.json')==(OUT/'validation.json').read_bytes()
 print('PASS model hashes, 12 PNGs, exact 6x previews, alpha, palette, links and ZIP',flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['download','generate','finish','build','check']);p.add_argument('--url');a=p.parse_args()
 if a.url:engine.COMFY_URL=a.url
 globals()[a.stage]()
