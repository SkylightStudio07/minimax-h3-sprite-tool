"""One reference-conditioned chibi sword slash; preserves accepted idle/walk assets."""
import argparse,hashlib,html,json,re,shutil,sys,time,zipfile
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'outputs/chibi-attack-20261020'
SOURCE=ROOT/'outputs/chibi-motion-20261020'
WIDTH,HEIGHT,SCALE=192,160,4
OFFSET=(8,16)
SEED=2026102031
PROMPT=(
 'Perform exactly ONE clear side-scrolling sword attack toward SCREEN RIGHT, then recover. '
 'At 0.0-0.4 seconds, brace both boots, bend the knees slightly and draw the sword hand back and up beside the rear shoulder, winding the torso. '
 'At 0.4-0.95 seconds, deliver ONE fast decisive diagonal DOWNWARD sword cut from above and behind the shoulder through the space IN FRONT of her toward SCREEN RIGHT. '
 'The sword arm visibly extends, shoulders and hips rotate a little toward the attack and the front knee bends. One small grounded weight shift only. '
 'At 0.95-1.35 seconds, follow through with the sword low and forward-right, then brake; ponytail and skirt lag briefly. '
 'At 1.35-2.2 seconds, recover her original compact ready stance and original sword-down pose at the SAME screen location. Hold that stance until 3.0 seconds. '
 'Preparation, the actual cut, follow-through and recovery must be visually distinct. Move the arms AND torso, not only the blade. '
 'ONE short rigid straight silver sword stays attached to the same gloved hand, same length, no bending, no duplicate, no sword in the empty hand. '
 'NO second attack, no stabbing, no walking cycle, no jumping, no full body spin, no turning around, no skating. '
 'Head and nose remain facing RIGHT, one visible green eye. Preserve the EXACT same single chibi girl, her large head and short compact body, '
 'brown high ponytail, cream military jacket, dark teal collar, brown waist belt, teal skirt, dark trousers, brown gloves and brown boots. '
 'Preserve the small pixel face and eye design. No changing facial expression, clothes, head size, anatomy or body proportions. '
 'Keep the input character at the SAME PIXEL SIZE; use the generous empty upper and right canvas for the sword motion. '
 'The entire head, boots, both arms and sword remain INSIDE the frame throughout. Fixed orthographic camera, no pan, zoom, cuts or shake. '
 'Flat pixel-art shading, square pixel clusters, stable colours. No smooth illustration, realistic textures or new detail. '
 'A clean physical sword cut with NO magical effects, no slash trail, sparkles, smoke, glow, ground shadow or motion blur hiding the blade. '
 'The background remains exactly the supplied flat medium grey everywhere, also in gaps between the limbs. No scenery, floor or text.')

def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def prepare():
 OUT.mkdir(parents=True,exist_ok=True)
 files=['accepted-source.png','palette.json','walk/reference.png','idle/animation.gif','walk/animation.gif','walk/action-raw.mp4','idle/action-raw.mp4']
 hashes={str((SOURCE/p).relative_to(ROOT)):digest(SOURCE/p) for p in files}
 old=OUT/'source-hashes.json'
 if old.exists():assert read(old)==hashes,'Accepted inputs changed'
 else:save(old,hashes)
 source=Image.open(SOURCE/'walk/reference.png').convert('RGBA');assert source.size==(128,128)
 canvas=Image.new('RGBA',(WIDTH,HEIGHT));canvas.paste(source,OFFSET);canvas.save(OUT/'reference.png')
 canvas.resize((WIDTH*3,HEIGHT*3),Image.Resampling.NEAREST).save(OUT/'reference-3x.png')
 save(OUT/'source-settings.json',dict(width=WIDTH,height=HEIGHT,sourceFrameSize=[128,128],offset=list(OFFSET),referenceSha256=digest(SOURCE/'walk/reference.png'),palette=read(SOURCE/'palette.json')['colors'],characterRescaled=False,source='same right-facing reference used for the accepted chibi walking test'))

def video():
 import idle_tool as engine
 from tools import verify_pixel_minimax as job
 from tools.verify_rpg_sprite_styles import ensure_idle
 from tools.verify_pixel_female_combat import release
 prepare();ensure_idle();engine.start_comfy();release((8190,8191))
 if (OUT/'attack-raw.mp4').exists():return
 ref=Image.open(OUT/'reference.png').convert('RGBA').resize((WIDTH*SCALE,HEIGHT*SCALE),Image.Resampling.NEAREST)
 matte=Image.new('RGB',ref.size,(128,128,128));matte.paste(ref,mask=ref.getchannel('A'));matte.save(OUT/'video-input.png')
 sha=digest(OUT/'video-input.png');record=OUT/'upload.json'
 if record.exists():stored=read(record);assert stored['sha256']==sha;name=stored['name']
 else:name=engine.upload_image((OUT/'video-input.png').read_bytes(),'chibi-single-slash.png');save(record,dict(name=name,sha256=sha))
 g=engine.build_workflow(name,PROMPT,3,WIDTH*SCALE,HEIGHT*SCALE,SEED,animation_type='custom',loop=True,facing='right',flat_background=True,motion_strength='normal',blink_mode='none',sampling_mode='quality',workflow_id='standard')
 g['16']['inputs']['filename_prefix']='chibi_attack/single_slash';g['15']['inputs'].pop('audio',None);g.pop('14');g.pop('5')
 save(OUT/'video-settings.json',dict(seed=SEED,steps=20,width=WIDTH*SCALE,height=HEIGHT*SCALE,frames=73,fps=24,firstAndLastReference=True,action='one attack and recovery; repeating preview is not repeated attacks in the source',prompt=g['6']['inputs']['prompt'],model='MiniMax H3 native 20 steps',audio=False))
 job.OUT=OUT;start=time.monotonic()
 try:
  history=job.execute(g,engine.COMFY_URL,'single-slash-v1');shutil.copyfile(engine.find_saved_video(history),OUT/'attack-raw.mp4');save(OUT/'video-timing.json',dict(seconds=round(time.monotonic()-start,2)));print('ATTACK_VIDEO_READY',flush=True)
 finally:release((8189,))

def configure():
 from tools import export_pixel_sword_combo as export
 export.OUT=OUT;export.WIDTH=WIDTH;export.HEIGHT=HEIGHT;export.SCALE=SCALE;export.RAW_VIDEO='attack-raw.mp4';export.ENCLOSED_MATTE_MIN_AREA=0
 return export

def process():configure().process();selected()

def selected():
 import sprite_gif
 export=configure()
 if not (OUT/'selection.json').exists():
  n=read(OUT/'postprocess.json')['frames'];indices=np.linspace(0,n-2,24).round().astype(int).tolist()
  durations=[round((b-a)*1000/24) for a,b in zip(indices,indices[1:])]+[round((n-1-indices[-1])*1000/24)]
  save(OUT/'selection.json',dict(indices=indices,durationMs=durations,notes='Uniform initial draft; visual attack review pending.'))
 export.selected();meta=read(OUT/'frames.json');meta.update(notes=read(OUT/'selection.json')['notes'],sourceFrameSize=[128,128],sourceFrameOffset=list(OFFSET),characterRescaled=False);save(OUT/'frames.json',meta)
 # Only remove this exporter’s excess root-level draft selections; all 73 source frames remain.
 for p in OUT.glob('frame-[0-9][0-9].png'):
  if int(p.stem.split('-')[-1])>=len(meta['sourceIndices']):p.unlink()
 frames=[Image.open(OUT/f'frame-{i:02d}.png').convert('RGBA') for i in range(len(meta['sourceIndices']))]
 data,_=sprite_gif.encode(frames,meta['durationMs'],scale=3);(OUT/'animation-3x.gif').write_bytes(data)
 build()

def build():
 meta=read(OUT/'frames.json');review=read(OUT/'review.json') if (OUT/'review.json').exists() else dict(summary='내보내기 완료 · 동작 시각 검토 전입니다.')
 data={'attack':dict(urls=[f'frame-{i:02d}.png' for i in range(len(meta['sourceIndices']))],times=meta['durationMs'],indices=meta['sourceIndices'])}
 script=(SOURCE/'preview-script.js').read_text(encoding='utf-8')
 script=re.sub(r'^const data=.*?;const states=',lambda _: 'const data='+json.dumps(data,ensure_ascii=False)+';const states=',script,count=1,flags=re.S)
 page=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>치비 · 검 공격</title><style>:root{{--zoom:3}}body{{margin:24px;background:#151b26;color:#eee;font:15px/1.6 system-ui}}a{{color:#c8c4ff}}article{{background:#252d3b;padding:20px;border-radius:12px}}.pair{{display:flex;gap:16px;overflow:auto}}figure{{margin:0;flex-shrink:0}}.pair img{{display:block;width:calc({WIDTH}px * var(--zoom));height:calc({HEIGHT}px * var(--zoom));image-rendering:pixelated;background:#263344}}body[data-bg=light] .pair img{{background:#eee}}body[data-bg=checker] .pair img{{background:repeating-conic-gradient(#263344 0 25%,#455069 0 50%) 0/24px 24px}}.controls{{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:14px 0}}button,select{{padding:8px;background:#35455c;color:white;border:1px solid #687b99;border-radius:6px}}.contact{{max-width:100%;image-rendering:pixelated}}figcaption{{font-size:13px;color:#b9c6d8}}</style><h1>치비 · 오른쪽 검 공격</h1><p>같은 오른쪽 치비 기준 이미지로 한 번 베기와 복귀를 시험했습니다. 캐릭터 픽셀 크기를 유지하고 칼이 지나갈 여백만 {WIDTH}×{HEIGHT}px로 넓혔습니다. 걷기/대기 원본은 그대로입니다.</p><p><strong>{html.escape(review['summary'])}</strong></p><p>영상 생성 → 기존 팔레트/윤곽/시간축 후처리 도트입니다. 원본 픽셀을 그대로 움직인 애니메이션은 아닙니다. 공격은 한 번 실행하는 동작이며 미리보기와 GIF는 확인용으로 반복합니다.</p><p><a href="chibi-attack.zip" download>PNG·GIF·전체 프레임 ZIP</a></p><div class="controls"><label>배율 <select id="zoom"><option value="1">1배</option><option value="2">2배</option><option value="3" selected>3배</option></select></label><label>배경 <select id="background"><option value="dark">어두움</option><option value="light">밝음</option><option value="checker">체크</option></select></label></div><article id="attack"><h2>준비 → 베기 → 복귀</h2><div class="pair"><figure><img src="reference.png" width="{WIDTH}" height="{HEIGHT}"><figcaption>기준 · 캐릭터 크기 유지</figcaption></figure><figure><img class="player" src="frame-00.png" width="{WIDTH}" height="{HEIGHT}"><figcaption class="position"></figcaption></figure></div><div class="controls"><button class="play">정지</button><button class="prev">이전 장</button><button class="next">다음 장</button><input class="seek" type="range" min="0" max="{len(meta['sourceIndices'])-1}" value="0" aria-label="공격 프레임"><label>속도 <select class="speed"><option value="0.5">0.5배</option><option value="1" selected>1배</option><option value="2">2배</option></select></label></div><p><a href="sheet-grid.png" download>PNG 시트</a> · <a href="animation.gif" download>GIF</a> · <a href="animation-3x.gif" download>GIF 3배</a> · <a href="frames.json">프레임 시간</a> · <a href="video-settings.json">프롬프트</a></p><details><summary>선택 프레임 시트</summary><img class="contact" src="sheet-grid.png"></details><details><summary>전체 영상·검수 프레임</summary><p><a href="attack-raw.mp4">생성 원본 MP4</a> · <a href="full-animation.webp">전체 프레임 애니메이션</a></p>'''
 for p in sorted(OUT.glob('contact-*.png')):page+=f'<img class="contact" src="{p.name}">'
 page+='</details></article><script>'+script+'</script></html>'
 (OUT/'preview.html').write_text(page,encoding='utf-8');(OUT/'preview-script.js').write_text(script,encoding='utf-8')
 with zipfile.ZipFile(OUT/'chibi-attack.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in OUT.rglob('*'):
   if p.is_file() and p.suffix in ('.png','.webp','.gif','.mp4','.json','.html','.js'):z.write(p,p.relative_to(OUT))
 print('PREVIEW',OUT/'preview.html',flush=True)

def check():
 import av
 for p,h in read(OUT/'source-hashes.json').items():assert digest(ROOT/p)==h
 ref=np.array(Image.open(SOURCE/'walk/reference.png').convert('RGBA'));canvas=np.array(Image.open(OUT/'reference.png').convert('RGBA'))
 assert np.array_equal(canvas[OFFSET[1]:OFFSET[1]+128,OFFSET[0]:OFFSET[0]+128],ref)
 assert np.count_nonzero(canvas[:,:,3])==np.count_nonzero(ref[:,:,3])
 palette={tuple(c) for c in read(OUT/'source-settings.json')['palette']};allframes=[]
 with av.open(str(OUT/'attack-raw.mp4')) as video:
  s=video.streams.video[0];assert (s.width,s.height)==(WIDTH*SCALE,HEIGHT*SCALE) and float(s.average_rate)==24;assert sum(1 for _ in video.decode(video=0))==73
 for p in sorted((OUT/'all-frames').glob('frame-*.png')):
  a=np.array(Image.open(p).convert('RGBA'));assert a.shape==(HEIGHT,WIDTH,4) and set(np.unique(a[:,:,3]))<={0,255}
  assert {tuple(c) for c in np.unique(a[:,:,:3][a[:,:,3]>0],axis=0)}<=palette;allframes.append(a)
 assert len(allframes)==73
 meta=read(OUT/'frames.json');grid=Image.open(OUT/'sheet-grid.png').convert('RGBA');strip=Image.open(OUT/'sheet.png').convert('RGBA')
 assert len(list(OUT.glob('frame-[0-9][0-9].png')))==len(meta['sourceIndices'])
 for i,index in enumerate(meta['sourceIndices']):
  expected=allframes[index];assert np.array_equal(np.array(Image.open(OUT/f'frame-{i:02d}.png').convert('RGBA')),expected)
  assert np.array_equal(np.array(grid.crop(((i%6)*WIDTH,(i//6)*HEIGHT,(i%6+1)*WIDTH,(i//6+1)*HEIGHT))),expected)
  assert np.array_equal(np.array(strip.crop((i*WIDTH,0,(i+1)*WIDTH,HEIGHT))),expected)
 with Image.open(OUT/'animation.gif') as small,Image.open(OUT/'animation-3x.gif') as big:
  assert small.size==(WIDTH,HEIGHT) and big.size==(WIDTH*3,HEIGHT*3) and small.n_frames==big.n_frames;ms=0
  for i in range(small.n_frames):
   small.seek(i);big.seek(i);a=np.array(small.convert('RGBA'));b=np.array(big.convert('RGBA'));assert np.array_equal(b,np.repeat(np.repeat(a,3,axis=0),3,axis=1));ms+=small.info['duration'];assert small.info['duration']==big.info['duration']
  assert abs(ms-sum(meta['durationMs']))<=10
 for link in re.findall(r'(?:href|src)="([^"]+)"',(OUT/'preview.html').read_text(encoding='utf-8')):assert (OUT/link).exists(),link
 save(OUT/'validation.json',dict(passed=True,frames=73,paletteColors=len(palette),binaryAlpha=True,sourceHashesUnchanged=True,referenceNotRescaled=True,sheetsMatch=True,gif3xExact=True,actualBrowserVerified=False));build()
 with zipfile.ZipFile(OUT/'chibi-attack.zip') as z:assert z.testzip() is None and z.read('validation.json')==(OUT/'validation.json').read_bytes()
 print('PASS 73 frames, palette/alpha, exact reference and source hashes, selected/sheets, GIF and ZIP',flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','video','process','selected','build','check']);a=p.parse_args();globals()[a.stage]()
