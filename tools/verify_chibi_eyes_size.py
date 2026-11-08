"""Private chibi size/eye comparison; keeps the accepted JRPG source unchanged."""
import argparse, hashlib, html, json, shutil, sys, zipfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import verify_anime_pixel_chibi as base

OUT=ROOT/'outputs/chibi-eyes-size-20261020'
OLD=ROOT/'outputs/anime-pixel-chibi-20261019'
SIZES=(64,96,128)
CASES={
 'balanced':dict(**{k:v for k,v in base.CASES['elin'].items() if k not in ('label','body')},label='치비 · 비율 조정 A',body='chibi, 2.5 heads tall, large head, compact torso, short but clearly separated arms and legs'),
 'taller':dict(**{k:v for k,v in base.CASES['elin'].items() if k not in ('label','body','strength')},label='치비 · 비율 조정 B',strength=.8,body='chibi, 2.75 heads tall, moderately large head, compact body, clearly separated short arms and legs'),
}
LABELS={'original':'기존 치비 · 같은 원본 크기 비교','balanced':CASES['balanced']['label'],'taller':CASES['taller']['label']}

def save(path,value):base.save(path,value)

def prepare():
 OUT.mkdir(parents=True,exist_ok=True)
 sources={}
 for name in ('elin','rpg'):
  for p in (OLD/name).glob('*.png'):
   sources[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
 previous=OUT/'source-hashes.json'
 if previous.exists():assert json.loads(previous.read_text())==sources,'Prior sources changed'
 else:save(previous,sources)
 for name in LABELS:(OUT/name).mkdir(exist_ok=True)
 for filename in ('raw.png','cutout.png','settings.json'):
  shutil.copyfile(OLD/'elin'/filename,OUT/'original'/filename)

def generate():
 prepare()
 base.OUT=OUT;base.CASES=CASES
 base.COMMON=('1girl, solo, full body, standing in a simple game idle stance, three-quarter view, facing slightly right, '
  'auburn hair, high ponytail, green eyes, cream military jacket, teal skirt, dark trousers, brown gloves, brown boots, '
  'small straight sword held at her side pointing down, '
  '(simple readable anime eyes:1.2), (clear dark upper eyelids:1.15), solid green irises, small dark pupils, '
  'one small highlight per eye, distinct eye whites, both eyes looking in the same direction, '
  'bangs above the eyes, small anime nose and mouth, '
  'compact square pixel clusters, clean dark outline, limited palette, two-tone cel shading, '
  'single character centered with head and both feet visible, empty margin around every side, plain white background, simple background')
 base.NEGATIVE=base.NEGATIVE.replace('long legs, long torso, ','')+', detailed irises, sparkling eyes, multiple eye highlights, mismatched pupils, cross-eyed, hair covering eyes, oversized eyes, tiny body'
 base.generate()

def finish():
 import image_background,image_pixel
 from tools.sprite_matte import clean_flat_matte
 prepare();records=[]
 for name,label in LABELS.items():
  folder=OUT/name
  if name!='original':
   with Image.open(folder/'raw.png') as im:raw=im.convert('RGBA')
   cut=image_background.remove(raw);clean,matte=clean_flat_matte(raw,tolerance=24,radius=3)
   a=np.array(cut);b=np.array(clean);a[:,:,3]=np.minimum(a[:,:,3],b[:,:,3]);a[:,:,:3]=b[:,:,:3];a[a[:,:,3]==0,:3]=0
   Image.fromarray(a).save(folder/'cutout.png');save(folder/'matte.json',matte)
  with Image.open(folder/'cutout.png') as im:cut=im.convert('RGBA')
  box=cut.getchannel('A').point(lambda v:255 if v>=128 else 0).getbbox();assert box
  content=cut.crop(box);side=max(content.size);canvas=Image.new('RGBA',(side,side));canvas.paste(content,((side-content.width)//2,(side-content.height)//2))
  sizes=[]
  for size in SIZES:
   extent=round(size*.82);fitted=canvas.resize((extent,extent),Image.Resampling.NEAREST)
   target=Image.new('RGBA',(size,size));target.paste(fitted,((size-extent)//2,(size-extent)//2))
   result=image_pixel.finish(target,size,32);result.save(folder/f'sprite-{size}.png')
   result.resize((size*4,size*4),Image.Resampling.NEAREST).save(folder/f'sprite-{size}-4x.png')
   a=np.array(result);sizes.append(dict(size=size,colors=len(np.unique(a[:,:,:3][a[:,:,3]>0],axis=0))))
  records.append(dict(id=name,label=label,crop=list(box),outputs=sizes))
 save(OUT/'results.json',records)
 # Common 4x zoom keeps the different native resolutions visible, rather than equalizing display height.
 panel=Image.new('RGB',(1710,3*590),'#263344');draw=ImageDraw.Draw(panel)
 for row,name in enumerate(LABELS):
  for col,size in enumerate(SIZES):
   x=col*570;y=row*590;draw.text((x+12,y+12),f'{name} / {size}px / 4x',fill='white')
   im=Image.open(OUT/name/f'sprite-{size}-4x.png').convert('RGBA')
   panel.paste(im,(x+6,y+48),im)
 panel.save(OUT/'comparison.png')
 build()

def build():
 records=json.loads((OUT/'results.json').read_text(encoding='utf-8'));rows=[]
 for r in records:
  name=r['id'];cards=[]
  for item in r['outputs']:
   size=item['size'];cards.append(f'<article><h3>{size}×{size} · {item["colors"]}색</h3><div class="sprite"><img src="{name}/sprite-{size}-4x.png" width="{size*4}" height="{size*4}"></div><a href="{name}/sprite-{size}.png" download>투명 PNG 저장</a></article>')
  rows.append(f'<section><h2>{html.escape(r["label"])}</h2><div class="row">'+''.join(cards)+f'</div><p><a href="{name}/raw.png">생성 원본</a> · <a href="{name}/settings.json">프롬프트·설정</a></p></section>')
 review=json.loads((OUT/'review.json').read_text(encoding='utf-8')) if (OUT/'review.json').exists() else {}
 page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>치비 크기·눈 비교</title><style>body{margin:24px;background:#151b26;color:#eee;font:15px/1.6 system-ui}a{color:#c8c4ff}.row{display:flex;gap:16px;flex-wrap:wrap}article{padding:16px;background:#252d3b;border-radius:12px}.sprite{overflow:auto;max-width:84vw}img{display:block;image-rendering:pixelated;background:repeating-conic-gradient(#202632 0 25%,#455069 0 50%) 0/24px 24px}section{margin:30px 0}button{padding:8px 16px}</style><h1>치비 · 크기와 눈 표현 비교</h1><p>64 → 96 → 128px은 실제 저장 PNG의 크기입니다. 미리보기는 모두 정확한 4배 최근접 확대입니다.</p><p>첫 행은 기존 생성 이미지를 크기만 달리 내보낸 결과입니다. A/B는 같은 외형 설명·시드로 새로 생성한 결과라 포즈·의상 세부도 달라집니다. 원본 1024px → 배경 제거/경계 정리 → 최근접 축소 → 32색 이하·이진 투명도. 참고 이미지를 직접 입력한 변형은 아닙니다.</p><p>JRPG 후보는 이전 결과 그대로 유지합니다. 새 치비는 비교 실험이며 사이트 기본값으로 등록하지 않았습니다.</p>'''
 page+='<p>'+html.escape(review.get('summary',''))+'</p><p>64px에서는 여전히 눈 세부가 줄어듭니다. 기존 배경 제거가 검 대부분을 지워 이번 결과는 얼굴·비율 비교용입니다.</p><p><a href="chibi-eyes-size.zip" download>전체 PNG·설정 ZIP 저장</a></p><p>배경: <button onclick="bg(\'#263344\')">어두움</button> <button onclick="bg(\'#e5e5e5\')">밝음</button> <button onclick="bg(\'\')">체크</button></p>'+''.join(rows)+'''<script>function bg(v){document.querySelectorAll('img').forEach(i=>{i.style.background=v||''})}</script></html>'''
 (OUT/'preview.html').write_text(page,encoding='utf-8')
 with zipfile.ZipFile(OUT/'chibi-eyes-size.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in OUT.rglob('*'):
   if p.is_file() and p.suffix in ('.png','.json','.html'):z.write(p,p.relative_to(OUT))

def check():
 sources=json.loads((OUT/'source-hashes.json').read_text())
 for p,digest in sources.items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest
 for name in LABELS:
  for size in SIZES:
   a=np.array(Image.open(OUT/name/f'sprite-{size}.png').convert('RGBA'))
   b=np.array(Image.open(OUT/name/f'sprite-{size}-4x.png').convert('RGBA'))
   assert a.shape==(size,size,4) and set(np.unique(a[:,:,3]))=={0,255}
   assert len(np.unique(a[:,:,:3][a[:,:,3]>0],axis=0))<=32
   assert np.array_equal(b,np.repeat(np.repeat(a,4,axis=0),4,axis=1))
  if name=='original':
   for size in (64,96):assert np.array_equal(np.array(Image.open(OUT/name/f'sprite-{size}.png')),np.array(Image.open(OLD/'elin'/f'sprite-{size}.png')))
 import re
 for link in re.findall(r'(?:href|src)="([^"]+)"',(OUT/'preview.html').read_text(encoding='utf-8')):assert (OUT/link).exists(),link
 save(OUT/'validation.json',dict(passed=True,pngs=9,maxColors=32,binaryAlpha=True,exact4x=True,acceptedSourcesUnchanged=True,actualBrowserVerified=False))
 build()
 with zipfile.ZipFile(OUT/'chibi-eyes-size.zip') as z:
  assert z.testzip() is None
  assert z.read('validation.json')==(OUT/'validation.json').read_bytes()
 print('PASS 9 PNGs, palette/alpha, exact 4x, unchanged sources, links, ZIP',flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['generate','finish','build','check']);args=p.parse_args();globals()[args.stage]()
