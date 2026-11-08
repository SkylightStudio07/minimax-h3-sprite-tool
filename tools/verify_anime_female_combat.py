"""One local anime musket animation at 768px, plus flat-matte edge review."""
import argparse,hashlib,json,shutil,sys,time,zipfile
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.sprite_matte import clean_flat_matte
OUT=ROOT/'outputs/anime-female-combat-20261019'
PIXEL=ROOT/'outputs/pixel-female-combat-20261019'

def save(p,value):p.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def neutralize_key_spill(image):
 # This burgundy/white/charcoal design has no green cloth or green VFX. Use only
 # for this reviewed character, not for arbitrary anime characters or palettes.
 a=np.array(image.convert('RGBA'));limit=np.maximum(a[:,:,0],a[:,:,2]).astype(int)
 affected=(a[:,:,3]>0)&(a[:,:,1].astype(int)>limit+15)
 a[affected,1]=limit[affected].astype(np.uint8)
 return Image.fromarray(a),int(affected.sum())

def reference():
 import rigging_engine as rig
 from tools import verify_pixel_minimax as exp
 from tools.verify_pixel_female_combat import release
 from tools.verify_rpg_sprite_styles import ensure_idle
 OUT.mkdir(exist_ok=True);rig.start_comfy();ensure_idle();release((8189,8191));exp.OUT=OUT
 source=Image.open(PIXEL/'musketeer/reference.png').convert('RGBA').resize((1024,1024),Image.Resampling.NEAREST)
 matte=Image.new('RGB',source.size,'white');matte.paste(source,mask=source.getchannel('A'))
 path=rig.INPUT_ROOT/'anime_musket_design.png';matte.save(path)
 graph=rig.qwen21_workflow(path.name,'anime_female_combat/reference',1024,24,2026101921)
 graph['6']['inputs'].update(device='cpu',dtype='default')
 graph['5']['inputs']['prompt']=(
  'Redraw the adult female musketeer in image 1 as a HIGH RESOLUTION 2D ANIME GAME BATTLE SPRITE. '
  'This is a complete clean anime redraw, NOT pixel art, NOT an enlarged pixel sprite. Refined smooth dark lineart, sharp cel shading, detailed readable anime eye and face, natural adult woman proportions about 6.5 heads tall, elegant practical uniform. '
  'Keep her silver-white short low ponytail, dark burgundy tricorne hat, burgundy long military coat with gold trim and brass buttons, cream cuffs, brown leather belt, charcoal fitted trousers and black knee-high boots. '
  'A strict SIDE PROFILE FACING SCREEN RIGHT, nose and eye looking right. Both feet planted in a balanced firing stance. '
  'Both hands hold ONE long historical flintlock musket horizontally aimed right, buttstock against shoulder, rear hand at trigger and front hand supporting wooden fore-end. '
  'A single straight dark steel barrel with brown wooden stock, no scope, no bayonet. Clear anatomy and hand grip. '
  'Full body and ENTIRE weapon visible in a SQUARE 1024x1024 canvas. Character height about 65 percent of canvas; hat around y=18 percent and boot soles around y=83 percent. '
  'Body centered at x=35 percent, gun muzzle no farther right than x=77 percent, leaving at least 20 percent EMPTY SPACE at right for a later muzzle flash. '
  'Isolated over a PURE UNIFORM BRIGHT GREEN background RGB 0,255,0. Background green is a flat chroma key colour, never a light source: no green rim lighting, no green reflected light. '
  'One character, no scene, no ground, no cast shadow, no text, no special effects, no muzzle flash yet.')
 graph['5']['inputs']['negative_prompt']='pixel art, pixelated, blocky, low resolution, chibi, front view, looking at viewer, facing left, cropped gun, cropped feet, giant breasts, bikini, high heels, extra fingers, double barrel, green lighting, green outline, text, watermark'
 started=time.monotonic();hist=exp.execute(graph,rig.COMFY_URL,'anime-reference')
 raw=Image.open(rig._saved_image(hist,'9')).convert('RGBA');raw.save(OUT/'reference-raw.png')
 cut,meta=clean_flat_matte(raw,tolerance=60,radius=5,chroma_key=True);cut.save(OUT/'reference-full.png')
 cut.resize((768,768),Image.Resampling.LANCZOS).save(OUT/'reference.png')
 save(OUT/'reference-settings.json',dict(seconds=round(time.monotonic()-started,2),matte=meta,graph=graph));release((8190,));print('ANIME REFERENCE READY',flush=True)

def video():
 import idle_tool as engine
 from tools import verify_pixel_minimax as exp
 from tools.verify_pixel_female_combat import CASES,release
 from tools.verify_rpg_sprite_styles import ensure_idle
 engine.start_comfy();ensure_idle();release((8190,8191));exp.OUT=OUT
 ref=Image.open(OUT/'reference.png').convert('RGBA');matte=Image.new('RGB',ref.size,(128,128,128));matte.paste(ref,mask=ref.getchannel('A'));matte.save(OUT/'video-input.png')
 digest=hashlib.sha256((OUT/'video-input.png').read_bytes()).hexdigest();upload=OUT/'upload.json'
 if upload.exists():
  old=json.loads(upload.read_text());assert old['sha256']==digest;name=old['name']
 else:
  name=engine.upload_image((OUT/'video-input.png').read_bytes(),'anime-musketeer-768.png');save(upload,dict(name=name,sha256=digest))
 prompt=(CASES['musketeer']['action']+' Preserve the high-resolution clean ANIME illustration style, detailed face, smooth thin dark lineart, exact same character and practical costume. '
  'This is NOT pixel art: no blocky edges, no mosaic and no new pixel-art texture. '
  'Strict screen-right side view; constant body proportions and costume, adult woman, no body inflation. '
  'ONE readable shot, short upper-body backward kick, stable rigid musket held with both hands, subtle coat and ponytail follow-through. '
  'Keep both feet planted, no stepping, do not turn toward the camera. Do not change the gun length or bend the barrel. '
  'Full character, entire barrel and compact muzzle flash inside the original square canvas. Keep smoke close to muzzle, avoid the right edge. '
  'Fixed orthographic camera, identical scale, flat uniform medium grey background, no scene, no shadow, no camera motion.')
 graph=engine.build_workflow(name,prompt,3,768,768,2026101941,animation_type='custom',loop=True,facing='right',flat_background=True,motion_strength='normal',sampling_mode='quality',workflow_id='standard')
 graph['16']['inputs']['filename_prefix']='anime_female_combat/musket_768';graph['15']['inputs'].pop('audio',None);graph.pop('14');graph.pop('5')
 save(OUT/'video-settings.json',dict(width=768,height=768,steps=20,seed=2026101941,frames=73,fps=24,graph=graph))
 started=time.monotonic();hist=exp.execute(graph,engine.COMFY_URL,'anime-video');shutil.copyfile(engine.find_saved_video(hist),OUT/'action-raw.mp4')
 save(OUT/'video-timing.json',dict(seconds=round(time.monotonic()-started,2)));release((8189,));print('ANIME VIDEO READY',flush=True)

def pixel_edges():
 import image_pixel
 target=OUT/'pixel-edge-review';target.mkdir(parents=True,exist_ok=True)
 records={};compare=Image.new('RGB',(1024,1024),'#202632');draw=ImageDraw.Draw(compare)
 for row,name in enumerate(['swordswoman','musketeer']):
  source=PIXEL/name;raw=Image.open(source/'reference-raw.png').convert('RGBA');old=Image.open(source/'reference.png').convert('RGBA')
  clean,meta=clean_flat_matte(raw,radius=5)
  # Keep the established palette; change only edge sampling/alpha for this static comparison.
  palette=np.array(json.loads((source/'reference-settings.json').read_text(encoding='utf-8'))['palette'][:32],np.float32)
  small=np.array(clean.resize((128,128),Image.Resampling.NEAREST));rgb=small[:,:,:3].astype(np.float32)
  distance=((rgb[:,:,None,:]-palette[None,None,:,:])**2).sum(axis=3)
  a=np.dstack((palette[distance.argmin(axis=2)].astype(np.uint8),np.where(small[:,:,3]>=128,255,0).astype(np.uint8)));a[a[:,:,3]==0,:3]=0
  original=np.array(old);raw_small=np.array(raw.resize((128,128),Image.Resampling.NEAREST))
  affected=((np.any(small[:,:,:3]!=raw_small[:,:,:3],axis=2))&((original[:,:,3]>0)|(a[:,:,3]>0)))|(small[:,:,3]!=original[:,:,3])
  # The old palette exporter used a different RGB lookup. Preserve its exact
  # interior pixels rather than recolouring them as a side effect of this fix.
  a[~affected]=original[~affected]
  assert np.array_equal(a[~affected],original[~affected])
  corrected=Image.fromarray(a);corrected.save(target/f'{name}-clean.png');corrected.save(source/'reference-clean.png')
  corrected.resize((512,512),Image.Resampling.NEAREST).save(source/'reference-clean-large.png')
  old.save(target/f'{name}-before.png')
  for col,im in enumerate([old,corrected]):
   large=im.resize((512,512),Image.Resampling.NEAREST);compare.paste(large,(col*512,row*512),large)
   draw.text((col*512+12,row*512+10),name+(' / BEFORE' if col==0 else ' / EDGE UNMATTE'),fill='white')
  previous=np.array(old);visible=(a[:,:,3]>0)|(previous[:,:,3]>0)
  meta['changed128VisiblePixels']=int((np.any(a!=previous,axis=2)&visible).sum());meta['unchangedInteriorVerified']=True;records[name]=meta
 compare.save(target/'comparison.png');compare.save(PIXEL/'source-cleanup-comparison.png');save(target/'results.json',records)
 from tools.verify_pixel_female_combat import package
 package()
 print('PIXEL EDGE COMPARISON READY',records,flush=True)

def export():
 import av
 OUT.mkdir(exist_ok=True);folder=OUT/'all-frames';folder.mkdir(exist_ok=True)
 display,count=neutralize_key_spill(Image.open(OUT/'reference.png'));display.save(OUT/'reference-display.png')
 frames=[];records=[]
 with av.open(str(OUT/'action-raw.mp4')) as video:
  for i,f in enumerate(video.decode(video=0)):
   im,meta=clean_flat_matte(f.to_image(),tolerance=26,radius=3);im,despilled=neutralize_key_spill(im);meta['residualGreenPixelsNeutralized']=despilled;im.save(folder/f'frame-{i:03d}.png');frames.append(im);records.append(meta)
 contact=Image.new('RGB',(8*192,10*212),'#252b38');draw=ImageDraw.Draw(contact)
 for i,im in enumerate(frames):
  thumb=im.resize((192,192),Image.Resampling.LANCZOS);x=(i%8)*192;y=(i//8)*212;contact.paste(thumb,(x,y+20),thumb);draw.text((x+5,y+3),str(i),fill='white')
 contact.save(OUT/'all-contact.jpg',quality=93)
 frames[0].save(OUT/'full-animation.webp',save_all=True,append_images=frames[1:],duration=42,loop=0,lossless=True)
 save(OUT/'matte-results.json',records)
 selection=OUT/'selection.json';review=json.loads(selection.read_text(encoding='utf-8')) if selection.exists() else {}
 indices=review.get('indices',np.linspace(0,len(frames)-1,12).round().astype(int).tolist());durations=review.get('durationMs',[150]*12)
 strip=Image.new('RGBA',(768*12,768));grid=Image.new('RGBA',(768*4,768*3))
 selected=[]
 for i,index in enumerate(indices):
  im=frames[index];im.save(OUT/f'frame-{i:02d}.png');strip.paste(im,(i*768,0));grid.paste(im,((i%4)*768,(i//4)*768));selected.append(im)
 strip.save(OUT/'sheet.png');grid.save(OUT/'sheet-grid.png')
 selected[0].save(OUT/'animation.webp',save_all=True,append_images=selected[1:],duration=durations,loop=0,lossless=True)
 selected[0].save(OUT/'animation.png',save_all=True,append_images=selected[1:],duration=durations,loop=0,disposal=0,blend=0)
 save(OUT/'frames.json',dict(frameWidth=768,frameHeight=768,columns=4,rows=3,sourceIndices=indices,sourceFPS=24,durationMs=durations,sourceTimeMs=[round(i/24*1000) for i in indices],review=review,method='Native 768px video; no pixel quantization. Conservative flat matte and local edge unmatting; green colour cleanup only for this green-free character palette. No global erosion; translucent smoke still needs review.'))
 package()

def package():
 page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>아니메 여총사 · 768px</title><style>body{background:#171b25;color:#eee;font:15px/1.6 system-ui;margin:24px}main{display:grid;grid-template-columns:1fr 1fr;gap:20px}article{background:#252b38;padding:16px;border-radius:12px;min-width:0}img{width:100%;background:repeating-conic-gradient(#243046 0 25%,#192232 0 50%) 0/24px 24px}a{color:#c4c0ff}details img{max-width:1200px}@media(max-width:800px){main{grid-template-columns:1fr}}</style><h1>아니메 여총사 · 머스킷 사격 · 768px</h1><p>동일한 의상을 참고해 Qwen으로 새로 그린 아니메 원화 → 기본 MiniMax H3 768×768 영상 → 배경/경계색 제거. 도트 확대본이 아닙니다. 원샷 동작을 미리보기에서 반복합니다.</p><p><a href="anime-musket-sprites.zip" download>전체 ZIP</a> · <a href="sheet-grid.png">4×3 PNG 시트</a> · <a href="frames.json">프레임 정보</a> · <a href="action-raw.mp4">생성 원본 영상</a></p><main><article><h2>기준 캐릭터 · 투명 배경</h2><img src="reference-display.png"></article><article><h2>사격 · 선택 12프레임</h2><img src="animation.webp"></article></main><details><summary>전체 73프레임 / 동작 검토</summary><img src="all-contact.jpg"><img src="full-animation.webp"></details><h2>기존 픽셀 캐릭터의 흰 테두리 보정</h2><p>왼쪽 기존 / 오른쪽 경계에 섞인 바탕색 제거. 기존 영상과 입력 원본은 보존했습니다. 새 정지 스프라이트만 수정했으며 칼날처럼 가는 밝은 부품은 여전히 수동 검수가 필요합니다.</p><img src="pixel-edge-review/comparison.png"><p><a href="pixel-edge-review/swordswoman-clean.png">여검사 보정 PNG</a> · <a href="pixel-edge-review/musketeer-clean.png">여총사 보정 PNG</a></p></html>'''
 page=page.replace('<main><article>','<p>검수: 얼굴·총열·코트 움직임은 읽히지만 발광/연기 일부가 오른쪽에서 잘립니다. 이 첫 비교본은 해당 장면을 포함합니다. 다음 생성은 가로 캔버스와 더 작은 인물 배치가 필요합니다. 반투명 효과의 회색 바탕색은 별도 처리가 남았습니다.</p><main><article>',1)
 (OUT/'preview.html').write_text(page,encoding='utf-8')
 with zipfile.ZipFile(OUT/'anime-musket-sprites.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in OUT.rglob('*'):
   if p.is_file() and p.suffix in ('.png','.webp','.jpg','.json','.mp4','.html'):z.write(p,p.relative_to(OUT))
 print('PREVIEW',OUT/'preview.html',flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['reference','video','pixel_edges','export']);args=parser.parse_args();globals()[args.stage]()
