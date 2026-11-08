"""Nonpixel chibi LoRA comparison and a physically legible rightward cut.

Private revision: never publish unreviewed candidates to the site catalog.
"""
import argparse, hashlib, html, json, shutil, sys, time
from pathlib import Path
import requests
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_engine, image_background, idle_tool as engine
from tools import verify_pixel_minimax as executor
from tools.verify_rpg_sprite_styles import ensure_idle

OUT=ROOT/'outputs/chibi-style-revision-20261020'
SEED=2026102441
PROMPT=(
 'masterpiece, best quality, (one original character:1.2), 1girl, solo, full body, '
 '(chibi:1.4), super deformed, three heads tall, oversized head, short compact torso, short arms and legs, '
 '(side view:1.2), facing right, nose pointing right, looking right, '
 'auburn bob haircut, small brass triangular hair clip, amber eyes, visible black pupils, sharp confident eyes, '
 'ivory blouse, moss green short cape, terracotta fitted waistcoat, purple trousers, brown gloves, brown ankle boots, small belt pouch, '
 'battle stance, front foot to the right, rear foot to the left, knees bent, '
 'holding ONE short straight silver sword with both gloved hands, '
 'hands raised in front of the forehead, sword blade pointing diagonally UP AND RIGHT, '
 'sword hilt and both hands clearly visible in front of the face, '
 'expressive hand drawn anime lineart, distinct dark upper eyelids, crisp two tone cel shading, strong color separation, '
 'entire head both boots and sword visible, single isolated character centered, generous white margin, '
 'plain pure white background, simple background, no floor, no shadow'
)
NEGATIVE=(
 'worst quality, low quality, lowres, blurry, photorealistic, 3d render, plastic, airbrush, soft gradient, '
 'pixel art, pixelated, dithering, watercolor, painting, realistic proportions, tall body, long legs, large breasts, cleavage, '
 'multiple characters, duplicate, extra heads, inset face, panels, sprite sheet, collage, cropped, close up, '
 'blank eyes, missing pupils, front view, looking at viewer, facing left, rear view, '
 'extra arms, extra hands, extra sword, two swords, detached blade, sword behind head, '
 'halo, floating ring, magic, glow, beam, sword trail, text, watermark, floor, cast shadow'
)
CASES={
 'bold-cel':dict(label='굵은 선 · 단단한 셀 채색',description='굵은 선 0.65 + 평면 채색 0.25 · 선이 과하게 굵어 비교용으로 보존',base='anima-base',loras=[('soya-import/anima-boldline-v13.safetensors',.65),('sprite-lab/anima-base-1-flat-color-v3.safetensors',.25)],triggers='flat color'),
 'crisp-anime':dict(label='선명한 애니 선화',description='애니 선화 0.75 + 선 정리 0.20 · 새 공격 시험에 사용',base='anima-base',loras=[('soya-import/@ix7.safetensors',.75),('sprite-lab/AnimaMythSmo0thL1nes.safetensors',.2)],triggers='@ixy, @ix7, Smo0thL1nes'),
 'cel-game':dict(label='게임 셀 채색 · 두꺼운 윤곽',description='셀 채색 0.90 + 두꺼운 윤곽 0.30 · 방향과 무기 자세가 부적합해 제외',base='wai',loras=[('requested/blue-archive-cutscene-illustrious.safetensors',.9),('requested/fsthicc-illustrious-v4.safetensors',.3)],triggers='official art, game cg, thick black outline'),
}

def save(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def release(url):requests.post(url+'/free',json=dict(unload_models=True,free_memory=True),timeout=30).raise_for_status()
def node(kind,**inputs):return dict(class_type=kind,inputs=inputs)

def graph(key):
 c=CASES[key]
 if c['base']=='anima-base':
  p=image_engine.validate(dict(model='anima-base',mode='text',prompt=PROMPT,negativePrompt=NEGATIVE,width=1024,height=1024,steps=28,cfg=4.,seed=SEED))
  g=image_engine.build_workflow(p,SEED);model=['1',0];clip=['2',0]
  for i,(file,strength) in enumerate(c['loras'],20):
   g[str(i)]=node('LoraLoaderModelOnly',model=model,lora_name=str(Path(file)),strength_model=strength);model=[str(i),0]
 else:
  g={'1':node('CheckpointLoaderSimple',ckpt_name='waiIllustriousSDXL_v170.safetensors'),
     '2':node('CLIPSetLastLayer',clip=['1',1],stop_at_clip_layer=-2),
     '4':node('CLIPTextEncode',clip=['2',0],text=''), '5':node('CLIPTextEncode',clip=['2',0],text=NEGATIVE),
     '6':node('EmptyLatentImage',width=1024,height=1024,batch_size=1),
     '7':node('KSampler',model=['1',0],positive=['4',0],negative=['5',0],latent_image=['6',0],seed=SEED,steps=32,cfg=5.,sampler_name='euler_ancestral',scheduler='normal',denoise=1.),
     '8':node('VAEDecode',samples=['7',0],vae=['1',2]),'9':node('SaveImage',images=['8',0],filename_prefix='')}
  model=['1',0];clip=['2',0]
  for i,(file,strength) in enumerate(c['loras'],20):
   g[str(i)]=node('LoraLoader',model=model,clip=clip,lora_name=str(Path(file)),strength_model=strength,strength_clip=strength);model=[str(i),0];clip=[str(i),1]
 for file,_ in c['loras']:assert (engine.COMFY_ROOT/'models/loras'/file).exists(),file
 g['7']['inputs']['model']=model
 g['4']['inputs'].update(clip=clip,text=PROMPT+', '+c['triggers'])
 g['5']['inputs'].update(clip=clip,text=NEGATIVE)
 g['9']['inputs']['filename_prefix']='chibi_style_revision/'+key
 return g

def generate():
 OUT.mkdir(parents=True,exist_ok=True);ensure_idle()
 for url in ('http://127.0.0.1:8190','http://127.0.0.1:8191'):release(url)
 for key,c in CASES.items():
  folder=OUT/key;folder.mkdir(exist_ok=True)
  if (folder/'raw.png').exists():continue
  ensure_idle();g=graph(key);executor.OUT=folder
  save(folder/'settings.json',dict(**c,seed=SEED,prompt=g['4']['inputs']['text'],negativePrompt=NEGATIVE,originalCharacter=True,referenceImageUsed=False,pixelOutput=False,width=1024,height=1024,postGenerationRepaint=False))
  start=time.monotonic();record=executor.execute(g,engine.COMFY_URL,'still-v1')
  r=requests.get(engine.COMFY_URL+'/view',params=record['outputs']['9']['images'][0],timeout=60);r.raise_for_status();(folder/'raw.png').write_bytes(r.content)
  release(engine.COMFY_URL)
  with Image.open(folder/'raw.png') as im:
   assert im.size==(1024,1024)
   image_background.remove_sprite(im).save(folder/'reference.png')
  save(folder/'timing.json',dict(seconds=round(time.monotonic()-start,1)))
  build();print('CHIBI_STYLE_READY',key,flush=True)

def build():
 cards=[];comparison=Image.new('RGB',(512*4,560),'#273344');draw=ImageDraw.Draw(comparison)
 previous=ROOT/'outputs/chibi-illustration-20261020/reference.png'
 rows=[('previous',dict(label='이전 · 비교 기준'),previous)]+[(k,c,OUT/k/'reference.png') for k,c in CASES.items()]
 for i,(key,c,path) in enumerate(rows):
  if not path.exists():continue
  im=Image.open(path).convert('RGBA');box=im.getchannel('A').getbbox();im=im.crop(box);im.thumbnail((460,460),Image.Resampling.LANCZOS)
  tile=Image.new('RGBA',(512,512));tile.alpha_composite(im,((512-im.width)//2,(512-im.height)//2));tile.save(OUT/(key+'-preview.png'))
  comparison.paste(tile,(512*i,35),tile);draw.text((512*i+12,10),key,fill='white')
  note='기존 원화 · 교체 검토 중' if key=='previous' else c['description']
  cards.append(f'<article><h2>{html.escape(c["label"])}</h2><img src="{key}-preview.png"><p>{html.escape(note)}</p>'+(f'<a href="{key}/raw.png">1024px 원본</a> · <a href="{key}/settings.json">프롬프트·조합</a>' if key!='previous' else '')+'</article>')
 comparison.save(OUT/'comparison.webp')
 page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>치비 그림체 · 내려베기 재시험</title><style>body{background:#171c28;color:#eee;font:15px/1.6 system-ui;margin:24px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}article{background:#273344;padding:16px;border-radius:14px}img{width:100%;max-width:512px;background:repeating-conic-gradient(#273344 0 25%,#3a4557 0 50%) 0/24px 24px}a{color:#c7baff}p{overflow-wrap:anywhere}</style><h1>치비 그림체와 공격 방향 재시험</h1><p>오리지널 캐릭터만 생성했습니다. 새 후보는 로컬 이미지 모델 + 그림체 LoRA를 직접 적용했으며 생성 뒤 전체를 다시 그리는 편집은 하지 않았습니다. 모델이 달라 외형과 포즈까지 동일하지는 않습니다. 기존 치비 예시는 사이트에서 제외하고 비교용으로 보존했습니다.</p><main>'''+''.join(cards)+'</main>'
 motion=OUT/'attack'
 if (motion/'start.png').exists() and (motion/'end.png').exists():page+='<h2>공격의 시작 → 끝 자세</h2><p>선화 후보의 팔·검만 부분 편집한 두 자세를 영상의 시작·끝 참조로 함께 사용했습니다.</p><img src="attack/start.png"><img src="attack/end.png">'
 if (motion/'animation.webp').exists():
  review=json.loads((motion/'review.json').read_text(encoding='utf-8')) if (motion/'review.json').exists() else {'note':'생성 완료 · 프레임 검토 중'}
  page+='<h2>새 원화 · 오른쪽 내려베기</h2><p>'+html.escape(review['note'])+'</p><img src="attack/animation.webp"><p><a href="attack/animation.gif">GIF</a> · <a href="attack/sheet.png">PNG 시트</a> · <a href="attack/contact.webp">프레임 검토</a> · <a href="attack/strike-detail.webp">칼 궤적 확대</a> · <a href="attack/reference.png">동작 입력</a> · <a href="attack/raw.mp4">후처리 전 영상</a></p>'
 (OUT/'preview.html').write_text(page,encoding='utf-8')

def poses():
 """Limit the edit to the arm/sword pose; retain the LoRA-rendered drawing."""
 import rigging_engine as rig
 ensure_idle();release(engine.COMFY_URL);release('http://127.0.0.1:8191')
 source=Image.open(OUT/'crisp-anime/raw.png').convert('RGB')
 source.thumbnail((800,800),Image.Resampling.LANCZOS)
 canvas=Image.new('RGB',(1024,1024),'white');canvas.paste(source,((1024-source.width)//2,(1024-source.height)//2))
 name='chibi_crisp_anime_pose_source_20261020.png';canvas.save(rig.INPUT_ROOT/name)
 instructions={
  'start':('Bend and raise BOTH elbows and both gloved hands ABOVE the forehead, on the RIGHT side of the head. '
   'Both hands grip the ONE sword hilt together. The hilt is ABOVE eye level and to the RIGHT of the face. '
   'The straight silver blade extends UPWARD from the hilt, almost vertical and tilted slightly toward the top RIGHT. '
   'The blade tip is ABOVE the head, entirely visible with empty margin. The blade must NOT cross the eyes or point horizontally. '
   'This is the raised preparation for a sword chop DOWN toward an opponent on screen RIGHT.'),
  'end':('Lower BOTH gloved hands together to just in front of the forward RIGHT hip, gripping the ONE sword hilt. '
   'The single straight silver blade extends from this hilt diagonally DOWN AND RIGHT into the empty space in front of the character, '
   'with its tip just above the boots ground line. Both elbows are low. This is the low finishing pose AFTER one downward sword chop toward screen RIGHT. '
   'Keep the head and boots at the SAME locations as the input; do not turn or translate the character.'),
 }
 folder=OUT/'attack';folder.mkdir(exist_ok=True)
 for key,instruction in instructions.items():
  if (folder/(key+'-raw.png')).exists():continue
  ensure_idle();g=rig.qwen21_workflow(name,'chibi_style_revision/'+key,768,20,SEED+10+(key=='end'))
  g['6']['inputs'].update(device='cpu',dtype='default')
  g['5']['inputs']['prompt']=(
   'Make a very localized POSE EDIT of this exact original anime chibi drawing. '
   'Preserve the original thin dark anime outlines, flat two-tone cel shading, sharp expressive amber eye and black pupil, '
   'large head, short body, plum red bob, triangular gold hair clip, green cape, ivory sleeves, terracotta vest, purple trousers and brown boots. '
   'Do NOT repaint or redesign the character. Keep the exact right-facing SIDE PROFILE, head location, head size, body proportions and feet positions. '
   'Change ONLY the bent arms, gloved hands and ONE sword: '+instruction+
   ' ONE complete character, whole head boots and blade inside the image, plain pure white background, no floor or shadow. '
   'Do not add any effects, sparkles, rings, text, inset faces, panels or duplicates.')
  g['5']['inputs']['negative_prompt']='front view, facing left, looking at viewer, extra arms, extra sword, horizontal sword, sword behind head, sword crossing face, tall body, realistic shading, gradient, 3d render, pixel art, text, glow, shadow'
  executor.OUT=folder;record=executor.execute(g,rig.COMFY_URL,'pose-'+key+'-v1')
  raw=Image.open(rig._saved_image(record,'9')).convert('RGBA');raw.save(folder/(key+'-raw.png'));release(rig.COMFY_URL)
  image_background.remove_sprite(raw).save(folder/(key+'.png'))
  print('CHIBI_ANCHOR_READY',key,flush=True)
 save(folder/'pose-provenance.json',dict(source='crisp-anime/raw.png',sourceKind='Anima Base + two nonpixel style LoRAs',editing='Qwen Image 2.1 localized arms/sword edit',originalCharacter=True))

ATTACK=(
 'Perform exactly ONE fast downward sword chop into the open space on SCREEN RIGHT. '
 'Begin with the upright raised sword shown in the first image. Do not move the sword behind the head. '
 'During the first 0.2 seconds brace the rear boot and flex the knees. '
 'From 0.2 to 0.7 seconds drive both hands DOWN AND FORWARD from eye level toward the forward hip. '
 'The rigid sword tip sweeps CLOCKWISE as viewed on screen: from ABOVE the hands, through the open space to their RIGHT, '
 'then finishes BELOW AND RIGHT of the hands. This is a forward downward chop, never a backward swing or an upward cut. '
 'Turn the shoulders and hips together and transfer weight onto the front right boot, without changing the facing direction. '
 'From 0.7 to 1.1 seconds brake in the low rightward finishing pose of the final image. '
 'Hold that pose for the remainder while hair and cloak settle. '
 'Keep the same chibi head and body proportions, one visible amber eye, thin anime outlines, flat costume colors, '
 'one rigid sword firmly attached to the two-handed grip, and fixed camera. '
 'No second strike, spin, thrust, walking, backward motion, magic, sword glow, flash or added effect.'
)

def attack_settings():
 return dict(characterId='original-chibi-cartographer-style-revision-20261020',width=768,height=768,duration=3,
  seed=SEED+20,frameCount=24,workflowId='standard',samplingMode='quality',animationType='attack',prompt=ATTACK,
  loop=False,facing='right',subjectType='human',motionStrength='high',motionPadding=20,motionSpeed=1.5,trimAction=True,
  blinkMode='none',negativeEnabled=False,pixelOutput=False,pixelColorLock=True,combatEffect='none',effectStrength='low',
  effectDescription='',stabilize=False,optimizeLoop=False,removeBackground=True,backgroundRemoval='ai',
  experimentalLastFrame='end.png')

def motion():
 ensure_idle();folder=OUT/'attack'
 if (folder/'raw.mp4').exists():return
 import rigging_engine as rig
 release(rig.COMFY_URL);release('http://127.0.0.1:8191')
 assert Image.open(folder/'start.png').size==Image.open(folder/'end.png').size
 for key in ('start','end'):
  prepared=engine.prepare_reference_image((folder/(key+'.png')).read_bytes(),768,768,20)
  (folder/(key+'-prepared.png')).write_bytes(prepared)
 shutil.copyfile(folder/'start.png',folder/'reference.png')
 shutil.copyfile(folder/'start-prepared.png',folder/'reference_prepared.png')
 first=engine.upload_image((folder/'start-prepared.png').read_bytes(),'chibi-revision-start.png')
 last=engine.upload_image((folder/'end-prepared.png').read_bytes(),'chibi-revision-end.png')
 p=attack_settings();save(folder/'settings.json',p)
 g=engine.build_workflow(first,ATTACK,3,768,768,p['seed'],animation_type='attack',loop=False,facing='right',flat_background=True,
  blink_mode='none',motion_strength='high',sampling_mode='quality',workflow_id='standard',combat_settings=p)
 g['18']=node('LoadImage',image=last);g['6']['inputs']['last_frame']=['18',0]
 g['6']['inputs']['prompt']=g['6']['inputs']['prompt'].replace('\n\nintegrated_multimodal_description:',
  '\n<Picture 2> supplies the final low rightward sword pose of [Shot 1] at 3.00 seconds.\n\nintegrated_multimodal_description:')
 g['15']['inputs'].pop('audio',None);g.pop('14',None);g.pop('5',None)
 g['16']['inputs']['filename_prefix']='chibi_style_revision/right_downstroke'
 executor.OUT=folder;record=executor.execute(g,engine.COMFY_URL,'native-anchors-v1')
 shutil.copyfile(engine.find_saved_video(record),folder/'raw.mp4');release(engine.COMFY_URL)
 print('CHIBI_REVISED_ATTACK_READY',flush=True)

def export():
 from tools import verify_chibi_illustration_examples as reusable
 reusable.OUT=OUT;reusable.CHARACTER='original-chibi-cartographer-style-revision-20261020'
 reusable.ACTIONS={'attack':dict(title='오른쪽 내려베기 재시험',frames=24,loop=False,padding=20,speed=1.5,trim=True,strength='high',effect='none',seed=SEED+20,prompt=ATTACK)}
 reusable.export('attack')
 p=attack_settings();current=json.loads((OUT/'attack/settings.json').read_text(encoding='utf-8'));p['frameCount']=current['frameCount'];save(OUT/'attack/settings.json',p)
 build()

def check():
 from html.parser import HTMLParser
 class Links(HTMLParser):
  def handle_starttag(self,tag,attrs):
   for k,v in attrs:
    if k in ('href','src'):assert (OUT/v).is_file(),v
 page=(OUT/'preview.html').read_text(encoding='utf-8');Links().feed(page)
 assert not any(s in page.lower() for s in ('blue-archive','counter-side','epic-seven'))
 hashes={}
 for c in CASES.values():
  for file,_ in c['loras']:
   if file in hashes:continue
   with (engine.COMFY_ROOT/'models/loras'/file).open('rb') as f:hashes[file]=hashlib.file_digest(f,'sha256').hexdigest()
 save(OUT/'lora-hashes.json',hashes)
 for key in CASES:
  assert Image.open(OUT/key/'raw.png').size==(1024,1024)
  assert Image.open(OUT/key/'reference.png').mode=='RGBA'
 old=json.loads((ROOT/'outputs/chibi-illustration-20261020/previous-site-hashes.json').read_text(encoding='utf-8'))
 assert all(hashlib.sha256((ROOT/'web/assets/sprite-examples'/n).read_bytes()).hexdigest()==h for n,h in old.items())
 catalog=ROOT/'web/assets/sprite-examples/catalog.json';data=json.loads(catalog.read_text(encoding='utf-8'))
 assert len(data['examples'])==9 and not any(e['category']=='chibi' for e in data['examples'])
 public=requests.get('https://bcsd-nai.mywire.org:18444/assets/sprite-examples/catalog.json',timeout=20);public.raise_for_status();assert public.content==catalog.read_bytes()
 details={}
 folder=OUT/'attack'
 if (folder/'frames.json').exists():
  m=json.loads((folder/'frames.json').read_text(encoding='utf-8'))
  assert m['frameWidth']==m['frameHeight']==768 and m['sourceFrames']==73
  assert not any(f['edgeContact'] for f in m['diagnostics'])
  assert hashlib.sha256((folder/'raw.mp4').read_bytes()).hexdigest()==m['rawSha256']
  assert Image.open(folder/'sheet.png').size==(768*m['columns'],768*m['rows'])
  with Image.open(folder/'animation.gif') as gif:
   duration=0
   for i in range(gif.n_frames):gif.seek(i);duration+=gif.info['duration']
  assert abs(duration-sum(m['previewTimingMs']))<=10
  details=dict(nativeFrames=73,selectedFrames=len(m['sourceIndices']),durationMs=sum(m['previewTimingMs']),gifDurationMs=duration,edgeContact=False,rawHashUnchanged=True)
 save(OUT/'validation.json',dict(passed=True,previewLinksExist=True,localMediaInspected=True,browserScreenshotVerified=False,
  previousMediaUnchanged=len(old),publicCatalogMatches=True,unreviewedChibiAbsent=True,styleCandidates=3,motion=details))
 print('CHIBI_REVISION_VALIDATED',details,flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['generate','poses','motion','export','build','check']);a=p.parse_args();globals()[a.stage]()
