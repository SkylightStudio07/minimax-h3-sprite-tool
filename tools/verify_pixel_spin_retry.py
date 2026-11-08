"""Low travelling one-shot turning cut, separate from rejected skating spin."""
import argparse,hashlib,json,shutil,sys,time,zipfile
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import verify_pixel_attack_actions as base
import pixel_attack_prompts as prompts
OUT=ROOT/'outputs/pixel-spin-retry-20261019'
KEY='spin_slash'
MOTION=(
 'ONE low travelling turning sword cut toward SCREEN RIGHT. This is a single decisive grounded combat move. '
 'Start in the supplied right-facing guard. Bend BOTH knees deeply and lower the hips, with feet shoulder-width apart. '
 'During 0.25-0.95 seconds, push off the rear boot and step a short distance RIGHT while turning the shoulders and hips together once. '
 'The torso leans forward over bent knees, the sword stays drawn close across the waist until the final strike. '
 'Show the back briefly in the middle of the turn. The feet STEP through the turn on two alternating bent legs; never balance upright on a single straight supporting leg. '
 'By 0.95 seconds complete the turn facing RIGHT. Plant the front boot well ahead, rear heel raised, knees bent, shoulders driving forward. '
 'At 0.95-1.20 seconds release ONE fast low diagonal-to-horizontal sword cut toward the RIGHT at waist height, ending with the blade extending to the right. '
 'The front boot brakes the body firmly: a wide low lunge, front knee deeply bent, rear leg stretched back, chest leaning forward, head looking right. '
 'Keep this powerful finishing lunge visible during 1.20-1.65 seconds, with all turning COMPLETELY STOPPED. '
 'Then slowly stand back into a stable right-facing guard at the NEW position, approximately 20 source pixels RIGHT of the initial guard, and stay still until the final frame. '
 'No step or slide back to the initial horizontal position. No repeated turns, no pirouettes, no upright skating, no dancing, no jump, no orbiting camera. '
 'Use only ONE tiny thin pale-cyan blade trail just in FRONT and to the RIGHT of the hands during the final cut. '
 'No full circle, no overhead arc, no glowing ring around the body. Keep the sword hand, bent legs and foot placement readable. '
 'Ponytail and skirt follow the short turn then settle as the front boot brakes. '
)
ITEM=dict(label='낮게 전진하는 돌려베기 · 재시험',seed=2026101971,allowFacingChange=True,
 requestedPhases=['낮게 준비','짧게 전진하며 한 번 회전','앞발 제동·오른쪽 베기','낮은 마무리 유지','이동한 위치에서 대기'],motion=MOTION)
TURN_MOTION=(
 'She performs a LOW SPINNING ADVANCE into ONE sword slash, like a grounded martial-arts turning attack. '
 'First crouch and pull the sword CLOSE against her waist. '
 'Then make ONE COMPLETE BODY TURN while taking two short bent-knee steps toward screen right. '
 'Her face must turn away: show her LEFT-FACING profile, then the BACK of her head, the BACK of her cream jacket and both shoulder blades, '
 'then the other side of her body, and finally her RIGHT-FACING profile again. Her whole hips and torso follow the face through this ONE turn. '
 'This visible sequence of views is the main action, not just swinging the sword while looking right. '
 'Stay low on flexed knees and move right through the turn, carrying the sword folded close to her belt. '
 'Only AFTER her back has been shown and she turns right again, plant the front boot and extend the sword in ONE fast rightward horizontal cut. '
 'Stop rotating completely in a wide low right-facing lunge with the front knee bent and the rear leg stretched back. '
 'Hold that planted finishing pose briefly, then recover to the final guard at the new position. '
 'Timing: preparation first 0.3 seconds; the single stepped full-body turn during 0.3-1.3 seconds; final slash and braking during 1.3-1.6 seconds; stable recovery afterward. '
 'The sword is held close during the body turn, not extended like a spinning skater. No repeated rotation. '
 'Only a very short pale-cyan horizontal blade trail on the final rightward cut; no effects during the turn and no circular ring. '
)

def configure():
 base.OUT=OUT;prompts.TEMPLATES={KEY:ITEM}

def prepare():
 configure();base.prepare();folder=OUT/KEY
 source=Image.open(base.SOURCE).convert('RGBA')
 end=Image.new('RGBA',(192,192));end.paste(source,(52,56));end.save(folder/'end-reference.png')
 large=end.resize((576,576),Image.Resampling.NEAREST);matte=Image.new('RGB',large.size,(128,128,128));matte.paste(large,mask=large.getchannel('A'));matte.save(folder/'video-end-input.png')

def video():
 import idle_tool as engine
 from tools.verify_rpg_sprite_styles import ensure_idle
 from tools.verify_pixel_female_combat import release
 from tools import verify_pixel_minimax as exp
 folder=OUT/KEY
 if (folder/'action-raw.mp4').exists():return
 ensure_idle();engine.start_comfy();release((8190,8191));exp.OUT=folder
 names=[]
 for filename,record in [('video-input.png','upload.json'),('video-end-input.png','end-upload.json')]:
  sig=hashlib.sha256((folder/filename).read_bytes()).hexdigest();path=folder/record
  if path.exists():
   old=json.loads(path.read_text());assert old['sha256']==sig;name=old['name']
  else:
   name=engine.upload_image((folder/filename).read_bytes(),'pixel-spin-retry-'+filename);base.save(folder,record,dict(name=name,sha256=sig))
  names.append(name)
 graph=engine.build_workflow(names[0],ITEM['motion'],3,576,576,ITEM['seed'],animation_type='custom',loop=False,facing='preserve',flat_background=True,motion_strength='high',sampling_mode='quality',workflow_id='standard')
 frames=engine.frame_length(3);duration=frames/24
 common=prompts.COMMON.replace('Perform the action once with readable anticipation, execution, follow-through and recovery, then return to the opening ready pose. ','')
 prompt=f'<Picture 1> is the opening guard at 0.00 seconds. <Picture 2> is the final guard at {duration:.2f} seconds, shifted a small distance screen right at identical scale.\n\nintegrated_multimodal_description: [Shot 1] '+common+ITEM['motion']+'\n\noverall_soundscape: N/A\n\nnon_diegetic_music: N/A'
 graph['17']=dict(class_type='LoadImage',inputs=dict(image=names[1]));graph['6']['inputs'].update(prompt=prompt,last_frame=['17',0])
 graph['16']['inputs']['filename_prefix']='pixel_spin_retry/low_travelling_cut';graph['15']['inputs'].pop('audio',None);graph.pop('14');graph.pop('5')
 base.save(folder,'video-settings.json',dict(steps=20,seed=ITEM['seed'],width=576,height=576,frames=frames,fps=24,loopKeyframe=False,endReferenceShift=[20,0],prompt=prompt))
 start=time.monotonic();history=exp.execute(graph,engine.COMFY_URL,'action-video');shutil.copyfile(engine.find_saved_video(history),folder/'action-raw.mp4');base.save(folder,'video-timing.json',dict(seconds=round(time.monotonic()-start,2)));release((8189,));print('VIDEO READY',flush=True)

def bundle():
 with zipfile.ZipFile(OUT/'pixel-spin-retry.zip','w',zipfile.ZIP_DEFLATED) as z:
  for path in OUT.rglob('*'):
   if path.is_file() and path.suffix in ('.png','.webp','.mp4','.json','.html'):z.write(path,path.relative_to(OUT))

def build():
 from tools import build_pixel_attack_actions_review as review
 review.OUT=OUT;review.TEMPLATES={KEY:ITEM};review.build()
 page=(OUT/'preview.html').read_text(encoding='utf-8').replace('픽셀 공격 테스트 · 돌려베기 / 점프 내려찍기','낮게 전진하는 돌려베기 · 재시험').replace('두 동작 시트·전체 프레임·영상·프롬프트 ZIP','돌려베기 시트·영상·프롬프트 ZIP').replace('pixel-attack-actions.zip','pixel-spin-retry.zip').replace('같은 보정 정지 여검사로 행동을 각각 따로 생성했습니다.','같은 보정 정지 여검사로 돌려베기를 다시 생성했습니다. 종료 기준은 시작보다 오른쪽으로 20픽셀 이동했습니다. 원샷 반복 표시이며 처음 위치로 되돌아갈 때는 미리보기 재시작입니다.')
 shutil.copyfile(ROOT/'outputs/pixel-attack-actions-20261019/spin_slash/animation.webp',OUT/'previous-spin.webp')
 page=page.replace('<script id="configs"','<details><summary>이전 연속 회전 결과 비교</summary><img class="sprite" src="previous-spin.webp"></details><script id="configs"')
 first=ROOT/'outputs/pixel-spin-retry-20261019/spin_slash/animation.webp'
 if first.exists() and first.parent.parent!=OUT:
  shutil.copyfile(first,OUT/'first-retry.webp')
  page=page.replace('<script id="configs"','<details open><summary>첫 재시험 · 회전이 빠진 전진 베기</summary><img class="sprite" src="first-retry.webp"></details><script id="configs"')
 (OUT/'preview.html').write_text(page,encoding='utf-8');(OUT/'pixel-attack-actions.zip').unlink();bundle()

def check():
 from tools import check_pixel_attack_actions as checks
 checks.OUT=OUT;checks.TEMPLATES={KEY:ITEM};checks.main()
 folder=OUT/KEY;source=Image.open(base.SOURCE).convert('RGBA');expected=Image.new('RGBA',(192,192));expected.paste(source,(52,56))
 assert np.array_equal(np.array(expected),np.array(Image.open(folder/'end-reference.png')))
 large=expected.resize((576,576),Image.Resampling.NEAREST);matte=Image.new('RGB',large.size,(128,128,128));matte.paste(large,mask=large.getchannel('A'))
 assert np.array_equal(np.array(matte),np.array(Image.open(folder/'video-end-input.png')))
 assert hashlib.sha256((folder/'video-end-input.png').read_bytes()).hexdigest()==json.loads((folder/'end-upload.json').read_text())['sha256']
 report=json.loads((OUT/'validation.json').read_text());report['shiftedEndReferenceVerified']=True;base.save(OUT,'validation.json',report);bundle()
 with zipfile.ZipFile(OUT/'pixel-spin-retry.zip') as z:assert z.testzip() is None

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','video','process','selected','build','check','bundle']);p.add_argument('--variant',choices=['brake','step-turn'],default='brake');a=p.parse_args()
 if a.variant=='step-turn':
  OUT=ROOT/'outputs/pixel-spin-step-turn-20261019';ITEM.update(label='낮은 한 바퀴 돌려베기 · 두 번째 재시험',seed=2026101972,motion=TURN_MOTION)
 configure()
 if a.stage in ('process','selected'):getattr(base,a.stage)(KEY)
 else:globals()[a.stage]()
