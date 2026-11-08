"""Local Anima chibi -> reference-conditioned MiniMax idle/walk -> pixel sheets."""
import argparse,hashlib,html,json,shutil,sys,time,zipfile
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'outputs/chibi-motion-20261020'
SOURCE=ROOT/'outputs/chibi-alternatives-20261020/anima-pupils'
CASES={'idle':dict(label='대기 · 원래 방향',seed=2026102021), 'walk':dict(label='걷기 · 오른쪽',seed=2026102022)}

def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def initialize():
 OUT.mkdir(parents=True,exist_ok=True)
 for name in CASES:(OUT/name).mkdir(exist_ok=True)
 hashes={str(p.relative_to(ROOT)):digest(p) for p in SOURCE.glob('*.png')}
 stored=OUT/'source-hashes.json'
 if stored.exists():assert read(stored)==hashes,'Accepted source changed'
 else:save(stored,hashes)
 shutil.copyfile(SOURCE/'sprite-128.png',OUT/'accepted-source.png')
 shutil.copyfile(SOURCE/'settings.json',OUT/'accepted-source-settings.json')
 source=Image.open(OUT/'accepted-source.png').convert('RGBA')
 a=np.array(source);colors=np.unique(a[:,:,:3][a[:,:,3]>0],axis=0).tolist()
 assert len(colors)<=32
 save(OUT/'palette.json',dict(colors=colors,source='accepted-source.png',maxColors=len(colors)))
 source.resize((512,512),Image.Resampling.NEAREST).save(OUT/'accepted-source-4x.png')

def prepare():
 import requests,image_pixel
 import rigging_engine as rig
 from tools import verify_pixel_minimax as job
 from tools.verify_rpg_sprite_styles import ensure_idle
 from tools.verify_pixel_female_combat import release
 from tools.sprite_matte import clean_flat_matte
 initialize();ensure_idle();release((8189,8191));rig.start_comfy()
 shutil.copyfile(OUT/'accepted-source.png',OUT/'idle/reference.png')
 folder=OUT/'walk'
 if (folder/'reference.png').exists():return
 source=Image.open(OUT/'accepted-source.png').convert('RGBA').resize((768,768),Image.Resampling.NEAREST)
 white=Image.new('RGB',source.size,'white');white.paste(source,mask=source.getchannel('A'))
 input_path=rig.INPUT_ROOT/'chibi_motion_right_reference.png';white.save(input_path)
 g=rig.qwen21_workflow(input_path.name,'chibi_motion/right_reference',768,20,2026102020)
 g['6']['inputs'].update(device='cpu',dtype='default')
 g['5']['inputs']['prompt']=(
  'Edit image 1 into a STRICT SIDE PROFILE FACING SCREEN RIGHT of the EXACT SAME SINGLE chibi pixel-art girl. '
  'Her nose, face, shoulders, waist, knees and boots all point toward the RIGHT edge together. Only ONE green eye is visible in profile. '
  'Keep her oversized chibi head and compact short body proportions, brown hair in a high ponytail, cream short military jacket with dark teal collar, '
  'brown waist belt, short teal skirt over dark trousers, brown gloves and brown boots. Preserve her original face design, hair colour and costume details. '
  'A short relaxed walking mid-step pose: the near boot is slightly forward and bent, the far boot is planted under the pelvis, small stride, NO wide legs. '
  'Hold the SAME ONE small straight silver sword in the near hand beside the hip, blade angled diagonally down toward SCREEN RIGHT, entire blade visible. '
  'Do not add a shield, scabbard, hat or any new accessory. Keep the exact same chunky square pixel clusters and simple limited-palette flat shading. '
  'Match the original sprite scale and placement: head near 12 percent height, boots near 88 percent height. Leave empty space on all sides. '
  'ONE character only, full body, pure flat WHITE background, no ground, no cast shadow, no text, no sheet, no other views. '
  'Do not make a tall adult or realistic illustration. Change only orientation and the small mid-step pose.')
 g['5']['inputs']['negative_prompt']='front view, facing viewer, facing left, looking at camera, tall body, realistic adult proportions, multiple characters, sprite sheet, multiple views, extra limbs, changed clothes, extra weapon, cropped sword, floor, shadow, text, watermark, smooth painting'
 save(folder/'reference-settings.json',dict(inputSha256=digest(OUT/'accepted-source.png'),prompt=g['5']['inputs']['prompt'],seed=2026102020,width=768,steps=20,model='installed Qwen Image 2.1 edit',changedOrientation=True,referenceConditioned=True))
 job.OUT=folder;start=time.monotonic()
 try:
  history=job.execute(g,rig.COMFY_URL,'right-reference')
  raw=Image.open(rig._saved_image(history,'9')).convert('RGBA');raw.save(folder/'reference-raw.png')
  cut,meta=clean_flat_matte(raw,tolerance=24,radius=3);cut.save(folder/'reference-cutout.png')
  small=cut.resize((128,128),Image.Resampling.NEAREST);a=np.array(small)
  palette=np.array(read(OUT/'palette.json')['colors'],np.int32)
  distances=((a[:,:,:3].astype(np.int32)[:,:,None,:]-palette[None,None,:,:])**2).sum(axis=3)
  rgb=palette[distances.argmin(axis=2)].astype(np.uint8);alpha=(a[:,:,3]>=128).astype(np.uint8)*255
  rgba=np.dstack((rgb,alpha));rgba[alpha==0,:3]=0;Image.fromarray(rgba).save(folder/'reference.png')
  Image.fromarray(rgba).resize((512,512),Image.Resampling.NEAREST).save(folder/'reference-4x.png')
  save(folder/'reference-processing.json',dict(matte=meta,seconds=round(time.monotonic()-start,2),palette='same exact colors as accepted-source.png',nearestScale=6))
 finally:release((8190,))
 print('RIGHT_REFERENCE_READY',flush=True)

def videos():
 import idle_tool as engine
 from tools import verify_pixel_minimax as job
 from tools.verify_rpg_sprite_styles import ensure_idle
 from tools.verify_pixel_female_combat import release
 initialize();ensure_idle();engine.start_comfy();release((8190,8191))
 prompts={
 'idle':('A very small relaxed game idle loop in the supplied original three-quarter orientation. Both boots remain planted at their original positions. '
  'Very subtle shoulder and chest breathing, no swelling of the body; the torso rises and falls by at most one or two low-resolution pixels. '
  'The ponytail tip trails gently with the breathing. Head remains steady, same eye shapes and facial features, no talking or exaggerated expressions. '
  'The sword hand holds the small straight silver sword in the SAME diagonal-down pose throughout, with almost no arm movement. '
  'NO walking, no stepping, no turning, no bounce, no sword swings.'),
 'walk':('A compact relaxed side-scrolling WALK cycle facing strictly SCREEN RIGHT, walking ON A TREADMILL IN PLACE. '
  'Perform two small even walking cycles, already underway at the first frame and continuing at the last. '
  'Alternate the two short legs FORWARD AND BACK along screen X in strict side profile; NEVER spread them sideways toward or away from the camera. '
  'One boot supports her on a fixed horizontal ground line. Small foot lift and natural knee bend, short steps, NO running, hopping, marching, skating or kicking. '
  'Her head, nose and ONE visible green eye keep facing RIGHT throughout. Tiny natural torso rise/fall with small opposing arm motion, ponytail tip follows gently. '
  'The near hand carries ONE rigid small silver sword down-right with a restrained swing, constant blade length and a fixed grip. '
  'Keep the hip at a fixed screen X. NO turning toward the camera, no walking away, no settling into an idle pose.')}
 try:
  for name,c in CASES.items():
   folder=OUT/name
   if (folder/'action-raw.mp4').exists():continue
   ensure_idle();reference=Image.open(folder/'reference.png').convert('RGBA').resize((512,512),Image.Resampling.NEAREST)
   matte=Image.new('RGB',reference.size,(128,128,128));matte.paste(reference,mask=reference.getchannel('A'));matte.save(folder/'video-input.png')
   upload=folder/'upload.json';sha=digest(folder/'video-input.png')
   if upload.exists():record=read(upload);assert record['sha256']==sha;uploaded=record['name']
   else:uploaded=engine.upload_image((folder/'video-input.png').read_bytes(),'chibi-motion-'+name+'.png');save(upload,dict(name=uploaded,sha256=sha))
   prompt=(prompts[name]+' Preserve the exact same single chibi girl, large head, short body, brown high ponytail, small green eyes, cream military jacket, '
    'teal skirt, dark trousers, brown gloves, brown boots and one silver sword. Same face and costume, no added detail, no body proportion changes. '
    'Fixed orthographic camera, fixed scale and framing, no pan, zoom or cut. Full body and sword remain inside the canvas. '
    'Flat pixel-art shading, chunky square clusters and stable colours, no realistic textures. '
    'Background stays the exact uniform medium grey supplied, including gaps between arms and legs. No floor, shadows, scenery, text, sparkles or effects.')
   g=engine.build_workflow(uploaded,prompt,3,512,512,c['seed'],animation_type=name,loop=True,facing='right' if name=='walk' else 'preserve',flat_background=True,motion_strength='low',blink_mode='none',sampling_mode='quality',workflow_id='standard')
   g['16']['inputs']['filename_prefix']='chibi_motion/'+name;g['15']['inputs'].pop('audio',None);g.pop('14');g.pop('5')
   save(folder/'video-settings.json',dict(seed=c['seed'],steps=20,width=512,height=512,frames=73,fps=24,firstAndLastReference=True,prompt=g['6']['inputs']['prompt'],referenceSha256=digest(folder/'reference.png'),sourceModel='MiniMax H3 native 20 steps',audio=False))
   job.OUT=folder;start=time.monotonic();history=job.execute(g,engine.COMFY_URL,'video-v1')
   shutil.copyfile(engine.find_saved_video(history),folder/'action-raw.mp4');save(folder/'video-timing.json',dict(seconds=round(time.monotonic()-start,2)));print('VIDEO_READY',name,flush=True)
 finally:release((8189,))

def process():
 import av,cv2
 from tools import export_pixel_sword_combo as export
 from tools.sprite_matte import clean_flat_matte
 cv2.setNumThreads(4);export.WIDTH=128;export.HEIGHT=128;export.SCALE=4
 palette=np.array(read(OUT/'palette.json')['colors'],np.float32)
 for name in CASES:
  folder=OUT/name;rgbs=[];covers=[];grays=[];mattes=[];thins=[]
  if not (folder/'action-raw.mp4').exists():continue
  if (folder/'postprocess.json').exists() and read(folder/'postprocess.json').get('rawVideoSha256')==digest(folder/'action-raw.mp4'):continue
  with av.open(str(folder/'action-raw.mp4')) as video:
   stream=video.streams.video[0];assert (stream.width,stream.height)==(512,512)
   for frame in video.decode(video=0):
    raw=np.array(frame.to_image().convert('RGB'));cut,meta=clean_flat_matte(Image.fromarray(raw),tolerance=26,radius=3)
    a=np.array(cut);rgb,cov=export.vote_grid(a[:,:,:3],a[:,:,3].astype(np.float32)/255,palette)
    cov,count=export.thin_coverage(a[:,:,:3],a[:,:,3].astype(np.float32)/255,cov)
    rgbs.append(rgb);covers.append(cov);grays.append(cv2.cvtColor(cv2.resize(raw,(128,128),interpolation=cv2.INTER_AREA),cv2.COLOR_RGB2GRAY));mattes.append(meta);thins.append(count)
  frames,changes=export.temporal_cleanup(rgbs,covers,grays,palette)
  allfolder=folder/'all-frames';allfolder.mkdir(exist_ok=True)
  for i,a in enumerate(frames):Image.fromarray(a).save(allfolder/f'frame-{i:03d}.png')
  contact=Image.new('RGB',(8*256,((len(frames)+7)//8)*280),'#263344');draw=ImageDraw.Draw(contact)
  for i,a in enumerate(frames):
   im=Image.fromarray(a).resize((256,256),Image.Resampling.NEAREST);x=(i%8)*256;y=(i//8)*280;contact.paste(im,(x,y+24),im);draw.text((x+6,y+5),str(i),fill='white')
  contact.save(folder/'all-contact.png')
  full=[Image.fromarray(a) for a in frames];full[0].save(folder/'full-animation.png',save_all=True,append_images=full[1:],duration=[round((i+1)*1000/24)-round(i*1000/24) for i in range(len(full))],loop=0,disposal=0,blend=0)
  save(folder/'postprocess.json',dict(frames=len(frames),width=128,height=128,sourceFPS=24,rawVideoSha256=digest(folder/'action-raw.mp4'),palette=palette.astype(np.uint8).tolist(),method='known-grey edge unmatting + 4x4 common-palette vote + thin weapon evidence + flow-gated temporal cleanup',matte=mattes,thinPixels=thins,temporal=changes,headReplaced=False))
  print('PROCESSED',name,len(frames),flush=True)
 selected()

def selected():
 import sprite_gif
 for name in CASES:
  folder=OUT/name
  if not (folder/'postprocess.json').exists():continue
  meta=read(folder/'postprocess.json');n=meta['frames']
  path=folder/'selection.json'
  if path.exists():sel=read(path)
  else:
   indices=np.linspace(0,n-2,12).round().astype(int).tolist();durations=[round((b-a)*1000/24) for a,b in zip(indices,indices[1:])]+[round((n-1-indices[-1])*1000/24)]
   sel=dict(indices=indices,durationMs=durations,notes='Uniform draft. Visual loop review pending; final duplicate reference excluded.');save(path,sel)
  indices=sel['indices'];durations=sel['durationMs'];assert indices==sorted(set(indices)) and len(indices)==len(durations)
  frames=[Image.open(folder/'all-frames'/f'frame-{i:03d}.png').convert('RGBA') for i in indices]
  target=folder/'selected';target.mkdir(exist_ok=True);grid=Image.new('RGBA',(128*4,128*((len(frames)+3)//4)));strip=Image.new('RGBA',(128*len(frames),128))
  for i,f in enumerate(frames):f.save(target/f'frame-{i:02d}.png');grid.paste(f,((i%4)*128,(i//4)*128));strip.paste(f,(i*128,0))
  grid.save(folder/'sheet-grid.png');strip.save(folder/'sheet.png')
  frames[0].save(folder/'animation.png',save_all=True,append_images=frames[1:],duration=durations,loop=0,disposal=0,blend=0)
  large=[im.resize((384,384),Image.Resampling.NEAREST) for im in frames];large[0].save(folder/'animation-3x.webp',save_all=True,append_images=large[1:],duration=durations,loop=0,lossless=True)
  data,gifmeta=sprite_gif.encode(frames,durations);(folder/'animation.gif').write_bytes(data);save(folder/'gif.json',gifmeta)
  data,_=sprite_gif.encode(large,durations);(folder/'animation-3x.gif').write_bytes(data)
  save(folder/'frames.json',dict(frameWidth=128,frameHeight=128,columns=4,rows=(len(frames)+3)//4,sourceFPS=24,sourceIndices=indices,durationMs=durations,sourceTimeMs=[round(i*1000/24) for i in indices],notes=sel['notes'],seamlessGuaranteed=False))
 build()

def build():
 cards=[];players={};review=read(OUT/'review.json') if (OUT/'review.json').exists() else {'summary':'초안 내보내기 완료 · 동작과 루프 시각 검토 전입니다.','cases':{}}
 for name,c in CASES.items():
  if not (OUT/name/'frames.json').exists():continue
  meta=read(OUT/name/'frames.json');players[name]=dict(urls=[f'{name}/selected/frame-{i:02d}.png' for i in range(len(meta['sourceIndices']))],times=meta['durationMs'],indices=meta['sourceIndices'])
  note=review.get('cases',{}).get(name,{}).get('summary','시각 검토 전입니다.')
  cards.append(f'''<article id="{name}"><h2>{c['label']}</h2><p>{html.escape(note)}</p><div class="pair"><figure><img src="{name}/reference.png" width="128" height="128"><figcaption>영상 입력 기준</figcaption></figure><figure><img class="player" src="{name}/selected/frame-00.png" width="128" height="128"><figcaption class="position"></figcaption></figure></div><div class="controls"><button class="play">정지</button><button class="prev">이전 장</button><button class="next">다음 장</button><input class="seek" type="range" min="0" max="{len(meta['sourceIndices'])-1}" value="0" aria-label="{c['label']} 프레임"><label>속도 <select class="speed"><option value="0.5">0.5배</option><option value="1" selected>1배</option><option value="2">2배</option></select></label></div><p><a href="{name}/sheet-grid.png" download>PNG 시트</a> · <a href="{name}/animation.gif" download>GIF</a> · <a href="{name}/animation-3x.gif" download>GIF 3배</a> · <a href="{name}/frames.json">프레임 시간</a></p><details><summary>전체 영상·프레임 보기</summary><p><a href="{name}/action-raw.mp4">생성 원본 MP4</a> · <a href="{name}/full-animation.png">전체 73장 APNG</a> · <a href="{name}/video-settings.json">프롬프트·설정</a></p><img class="contact" src="{name}/all-contact.png"></details></article>''')
 page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>치비 · 대기와 걷기</title><style>:root{--zoom:3}body{margin:24px;background:#151b26;color:#eee;font:15px/1.6 system-ui}a{color:#c8c4ff}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,680px),1fr));gap:20px}article{min-width:0;background:#252d3b;padding:20px;border-radius:12px}.pair{display:flex;gap:12px;overflow:auto}figure{margin:0;flex-shrink:0}.pair img{display:block;width:calc(128px * var(--zoom));height:calc(128px * var(--zoom));image-rendering:pixelated;background:#263344}body[data-bg=light] .pair img{background:#eee}body[data-bg=checker] .pair img{background:repeating-conic-gradient(#263344 0 25%,#455069 0 50%) 0/24px 24px}.controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:14px 0}button,select{padding:8px;background:#35455c;color:white;border:1px solid #687b99;border-radius:6px}.contact{max-width:100%;image-rendering:pixelated}figcaption{font-size:13px;color:#b9c6d8}</style><h1>치비 · 대기와 오른쪽 걷기</h1><p>채택한 치비 Anima 정지 이미지로 MiniMax 영상 기반 동작을 시험했습니다. 대기는 기존 원본을 그대로 입력했고, 걷기는 같은 원본을 Qwen으로 오른쪽 옆모습으로 편집한 뒤 입력했습니다. 방향 편집 자체도 외형을 바꿀 수 있습니다.</p><p>영상 생성 뒤 128×128px·기존 원본의 공통 팔레트·이진 투명도로 후처리한 도트입니다. 원본 도트 픽셀을 그대로 움직인 애니메이션은 아닙니다. 전체 영상과 프레임도 보존했습니다. 미리보기 반복이 매끄러운 게임용 루프 완성을 보장하지는 않습니다.</p>'''
 page+='<p><strong>'+html.escape(review['summary'])+'</strong></p><p><a href="chibi-motion.zip" download>대기·걷기 PNG·GIF·전체 프레임 ZIP</a></p><div class="controls"><label>배율 <select id="zoom"><option value="1">1배</option><option value="2">2배</option><option value="3" selected>3배</option><option value="4">4배</option></select></label><label>배경 <select id="background"><option value="dark">어두움</option><option value="light">밝음</option><option value="checker">체크</option></select></label></div><main>'+''.join(cards)+'</main>'
 script='''const data=DATA;const states={};document.getElementById('zoom').onchange=e=>document.documentElement.style.setProperty('--zoom',e.target.value);document.getElementById('background').onchange=e=>document.body.dataset.bg=e.target.value;for(const [name,d] of Object.entries(data)){const root=document.getElementById(name),img=root.querySelector('.player'),seek=root.querySelector('.seek'),button=root.querySelector('.play');let s={i:0,running:true,speed:1,elapsed:0};states[name]=s;const draw=()=>{img.src=d.urls[s.i];seek.value=s.i;root.querySelector('.position').textContent=`${s.i+1}/${d.urls.length}장 · 원본 ${d.indices[s.i]}번`};button.onclick=()=>{s.running=!s.running;button.textContent=s.running?'정지':'재생';s.elapsed=0};const step=delta=>{s.running=false;button.textContent='재생';s.i=(s.i+delta+d.urls.length)%d.urls.length;s.elapsed=0;draw()};root.querySelector('.prev').onclick=()=>step(-1);root.querySelector('.next').onclick=()=>step(1);seek.oninput=e=>{s.i=Number(e.target.value);s.running=false;button.textContent='재생';s.elapsed=0;draw()};root.querySelector('.speed').onchange=e=>s.speed=Number(e.target.value);for(const url of d.urls){const preload=new Image();preload.src=url}draw();s.tick=delta=>{if(!s.running)return;s.elapsed+=delta*s.speed;while(s.elapsed>=d.times[s.i]){s.elapsed-=d.times[s.i];s.i=(s.i+1)%d.urls.length;draw()}}}let previous;function tick(now){if(previous!==undefined){const delta=Math.min(now-previous,250);Object.values(states).forEach(s=>s.tick(delta))}previous=now;requestAnimationFrame(tick)}requestAnimationFrame(tick);'''.replace('DATA',json.dumps(players,ensure_ascii=False))
 page+='<script>'+script+'</script></html>'
 (OUT/'preview.html').write_text(page,encoding='utf-8');(OUT/'preview-script.js').write_text(script,encoding='utf-8')
 with zipfile.ZipFile(OUT/'chibi-motion.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in OUT.rglob('*'):
   if p.is_file() and p.suffix in ('.png','.webp','.gif','.mp4','.json','.html','.js'):z.write(p,p.relative_to(OUT))
 print('PREVIEW',OUT/'preview.html',flush=True)

def check():
 import av
 for path,sha in read(OUT/'source-hashes.json').items():assert digest(ROOT/path)==sha
 assert digest(OUT/'accepted-source.png')==digest(SOURCE/'sprite-128.png')
 assert digest(OUT/'idle/reference.png')==digest(OUT/'accepted-source.png')
 colors={tuple(c) for c in read(OUT/'palette.json')['colors']};total=0
 for name in CASES:
  folder=OUT/name;meta=read(folder/'frames.json');frames=[]
  with av.open(str(folder/'action-raw.mp4')) as video:
   s=video.streams.video[0];assert (s.width,s.height)==(512,512) and float(s.average_rate)==24
   n=sum(1 for _ in video.decode(video=0));assert n==73
  assert len(list((folder/'all-frames').glob('frame-*.png')))==n
  for p in sorted((folder/'all-frames').glob('*.png')):
   a=np.array(Image.open(p).convert('RGBA'));assert a.shape==(128,128,4) and set(np.unique(a[:,:,3]))<={0,255}
   assert {tuple(c) for c in np.unique(a[:,:,:3][a[:,:,3]>0],axis=0)}<=colors
   frames.append(a);total+=1
  sheet=Image.open(folder/'sheet-grid.png').convert('RGBA');strip=Image.open(folder/'sheet.png').convert('RGBA')
  for i,index in enumerate(meta['sourceIndices']):
   assert np.array_equal(np.array(Image.open(folder/'selected'/f'frame-{i:02d}.png').convert('RGBA')),frames[index])
   assert np.array_equal(np.array(sheet.crop(((i%4)*128,(i//4)*128,(i%4+1)*128,(i//4+1)*128))),frames[index])
   assert np.array_equal(np.array(strip.crop((i*128,0,(i+1)*128,128))),frames[index])
  with Image.open(folder/'animation.gif') as gif:
   assert gif.size==(128,128) and gif.info.get('loop')==0
   actual_ms=0
   for i in range(gif.n_frames):gif.seek(i);actual_ms+=gif.info['duration']
   assert actual_ms==read(folder/'gif.json')['totalMs']
   assert abs(sum(meta['durationMs'])-actual_ms)<=10
   with Image.open(folder/'animation-3x.gif') as big:
    assert big.size==(384,384) and big.n_frames==gif.n_frames
    for i in range(gif.n_frames):
     gif.seek(i);big.seek(i);a=np.array(gif.convert('RGBA'));b=np.array(big.convert('RGBA'))
     assert np.array_equal(b,np.repeat(np.repeat(a,3,axis=0),3,axis=1))
     assert gif.info['duration']==big.info['duration']
 import re
 for link in re.findall(r'(?:href|src)="([^"]+)"',(OUT/'preview.html').read_text(encoding='utf-8')):assert (OUT/link).exists(),link
 save(OUT/'validation.json',dict(passed=True,frames=total,originalSourceUnchanged=True,exactIdleReference=True,maxColors=len(colors),binaryAlpha=True,sourceVideos='512x512, 24FPS, 73 frames each',sheetsMatchSelected=True,actualBrowserVerified=False));build()
 with zipfile.ZipFile(OUT/'chibi-motion.zip') as z:
  assert z.testzip() is None
  assert z.read('validation.json')==(OUT/'validation.json').read_bytes()
 print('PASS source hashes, 146 pixel frames, selected/sheets, GIF timing, links and ZIP',flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','videos','process','selected','build','check']);args=p.parse_args();globals()[args.stage]()
