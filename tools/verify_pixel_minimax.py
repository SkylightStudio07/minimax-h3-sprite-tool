"""Private right-facing MiniMax-to-pixel walk experiment; no service mutations."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import zipfile

import av
import numpy as np
from PIL import Image, ImageDraw
import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import idle_tool as engine
import rigging_engine as rig
import motion_identity
from tools.verify_pixel_animation import palette_from,pixel_export,checker
from tools.verify_rpg_sprite_styles import ensure_idle

OUT=ROOT/'outputs/pixel-minimax-right-20261019'
SOURCE=ROOT/'outputs/pixel-art-test-20261019/knight-128/image-1.png'
VERSION='minimax-right-pixel-v1'


def save_json(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def release(ports):
    for port in ports:
        requests.post(f'http://127.0.0.1:{port}/free',json=dict(unload_models=True,free_memory=True),timeout=30).raise_for_status()


def execute(graph,url,name):
    signature=hashlib.sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest()
    pending=OUT/f'{name}-pending.json';completed=OUT/f'{name}-history.json'
    save_json(f'{name}-workflow.json',graph)
    if completed.is_file() and pending.is_file() and json.loads(pending.read_text())['signature']==signature:
        return json.loads(completed.read_text(encoding='utf-8'))
    if pending.is_file():
        previous=json.loads(pending.read_text())
        if previous['signature']!=signature:raise RuntimeError('Use another output for changed settings; do not replace a pending graph')
        pid=previous['promptId'];print('RESUME',name,pid,flush=True)
    else:
        ensure_idle()
        response=requests.post(url+'/prompt',json=dict(prompt=graph),timeout=60)
        if not response.ok:raise RuntimeError(response.text[:2000])
        pid=response.json()['prompt_id'];save_json(f'{name}-pending.json',dict(signature=signature,promptId=pid))
        print('SUBMITTED',name,pid,flush=True)
    start=time.monotonic()
    while time.monotonic()-start<3600:
        try:
            response=requests.get(url+'/history/'+pid,timeout=15);response.raise_for_status()
            history=response.json().get(pid)
        except (requests.Timeout,requests.ConnectionError):
            time.sleep(4);continue
        if history:
            save_json(f'{name}-history.json',history)
            if history.get('status',{}).get('status_str')!='success':raise RuntimeError(str(history.get('status'))[-2500:])
            return history
        time.sleep(4)
    raise TimeoutError('Generation still pending; resume using saved prompt id, never duplicate')


def direction():
    ensure_idle();release((8189,8191))
    reference=Image.open(SOURCE).convert('RGBA');reference.save(OUT/'reference-front.png')
    enlarged=reference.resize((768,768),Image.Resampling.NEAREST)
    canvas=Image.new('RGB',enlarged.size,'white');canvas.paste(enlarged,mask=enlarged.getchannel('A'))
    input_path=rig.INPUT_ROOT/'pixel_minimax_right_reference.png';canvas.save(input_path)
    graph=rig.qwen21_workflow(input_path.name,'pixel_minimax_right/source',768,20,2026101901)
    graph['6']['inputs'].update(device='cpu',dtype='default')
    graph['5']['inputs']['prompt']=(
        'Create ONE full-body pixel-art game sprite of the EXACT same character in image 1, now viewed in a STRICT SIDE PROFILE FACING SCREEN RIGHT. '
        'Her NOSE points to the RIGHT edge of the image. Only the side of the face is visible; one visible eye looks RIGHT. '
        'Head, shoulders, torso, pelvis and boots are all turned right together. NOT a front view, NOT walking toward the viewer, NOT a character sheet. '
        'Preserve her short blue bob haircut, white scarf, navy knee-length coat with thin gold trim, brown waist belt, tall brown boots, '
        'and the same single silver straight sword with brown crossguard held in the near hand, blade angled diagonally down toward screen right. '
        'Small compact adult game-sprite proportions, same head size, simple flat navy and brown pixel clusters, exact same outfit and colors. '
        'Pose her already mid-walk with ONE boot planted under the pelvis and the OTHER boot slightly forward and bent, short stride. '
        'Keep a natural side-on silhouette, arms with a slight bend, shoulders relaxed, both feet and the whole sword fully visible. '
        'Keep the character at the same size and center as image 1, leave generous empty space on every side. '
        'Keep chunky square pixel-art blocks and a limited palette, no smooth painting or gradients. Pure flat WHITE background, no floor, no cast shadow, no text.')
    graph['5']['inputs']['negative_prompt']='front view, facing viewer, facing left, looking at camera, multiple views, sprite sheet, collage, multiple swords, altered outfit, missing weapon, giant breasts, high heels, smooth painting, gradient, shadow'
    start=time.monotonic();history=execute(graph,rig.COMFY_URL,'right-reference')
    raw=Image.open(rig._saved_image(history,'9')).convert('RGBA');raw.save(OUT/'reference-right-raw.png')
    palette,colors=palette_from(reference);right=pixel_export(raw,palette);right.save(OUT/'reference-right.png')
    right.resize((768,768),Image.Resampling.NEAREST).save(OUT/'reference-right-preview.png')
    save_json('direction.json',dict(seconds=round(time.monotonic()-start,2),palette=colors,model='Qwen Image 2.1 edit',version=VERSION))
    release((8190,));print('RIGHT REFERENCE',OUT/'reference-right-preview.png',flush=True)


def video():
    ensure_idle();release((8190,8191))
    reference=Image.open(OUT/'reference-right.png').convert('RGBA')
    # Exact integer enlargement avoids softening the initial pixel clusters.
    enlarged=reference.resize((512,512),Image.Resampling.NEAREST)
    matte=Image.new('RGB',(512,512),(128,128,128));matte.paste(enlarged,mask=enlarged.getchannel('A'))
    matte.save(OUT/'minimax-input.png')
    upload_record=OUT/'video-input-upload.json'
    digest=hashlib.sha256((OUT/'minimax-input.png').read_bytes()).hexdigest()
    if upload_record.is_file():
        previous=json.loads(upload_record.read_text(encoding='utf-8'))
        if previous['sha256']!=digest:raise RuntimeError('Reference changed; use a new experiment output')
        name=previous['name']
    else:
        name=engine.upload_image((OUT/'minimax-input.png').read_bytes(),'pixel-minimax-right.png')
        save_json('video-input-upload.json',dict(sha256=digest,name=name))
    description=(
        'A restrained side-scrolling walk cycle, facing SCREEN RIGHT, walking ON A TREADMILL IN PLACE. '
        'Two complete small relaxed walking cycles at an even cadence. The motion is already underway in the first frame. '
        'Both feet travel only horizontally forward/backward along screen X, in the sagittal plane; '
        'the legs stay on two nearly overlapping tracks in the side profile and NEVER spread sideways toward or away from the viewer. '
        'Lift each boot only slightly, bend the knee, bring it forward, plant it, then let that planted foot sweep backward as the opposite leg advances. '
        'One boot always supports the weight on a fixed horizontal ground line. Short steps, ankles stay close, no skating, hopping, kicking or running. '
        'The hip stays at the same screen X; torso has a subtle one-to-two-pixel rhythmic vertical rise and fall, without changing shape. '
        'Head and nose remain facing RIGHT; no turning toward camera. Small natural opposite arm swing. '
        'The near hand carries ONE rigid silver sword angled downward-right, moving as a single unbending object with the hand. '
        'Keep the exact same small pixel face, blue bob, white scarf, navy coat, brown belt and brown boots. '
        'Chest and abdomen keep constant volume; coat seams and belt stay fixed on the body; only coat hem and scarf tip trail slightly. '
        'Orthographic side view, fixed camera, fixed scale, no pan or zoom. Flat pixel-art shading, no new detail, no light changes. '
        'Keep the entire body, both feet and sword inside the canvas. No settling into idle at the end.')
    graph=engine.build_workflow(name,description,3,512,512,2026101902,animation_type='walk',loop=True,
            facing='right',flat_background=True,motion_strength='low',sampling_mode='quality',workflow_id='standard')
    graph['16']['inputs']['filename_prefix']='pixel_minimax_right/quality_walk'
    # This is a silent asset comparison. Decode/save video only; omit the unused
    # generated audio stream and its VAE decode from the output branch.
    graph['15']['inputs'].pop('audio',None);graph.pop('14');graph.pop('5')
    save_json('video-settings.json',dict(version=VERSION,model=engine.MODEL_FILES['diffusion'].name,steps=20,
              cfg=1,seed=2026101902,width=512,height=512,length=engine.frame_length(3),fps=24,
              loopKeyframes=True,motion='low',source='reference-right.png',prompt=graph['6']['inputs']['prompt'],
              note='Native 20-step H3, no FastH3/turbo, no audio output; a mid-step right-facing anchor is also the final keyframe.'))
    started=time.monotonic();history=execute(graph,engine.COMFY_URL,'minimax-quality')
    shutil.copyfile(engine.find_saved_video(history),OUT/'walk-raw.mp4')
    save_json('video-timing.json',dict(seconds=round(time.monotonic()-started,2)))
    release((8189,));print('VIDEO',OUT/'walk-raw.mp4',flush=True)


def remap(image,palette,size):
    small=image.convert('RGBA').resize((size,size),Image.Resampling.NEAREST)
    a=np.asarray(small);rgb=a[:,:,:3].astype(np.int32);colors=np.asarray(palette,dtype=np.int32)
    distance=((rgb[:,:,None,:]-colors[None,None,:,:])**2).sum(axis=3)
    result=colors[distance.argmin(axis=2)].astype(np.uint8)
    alpha=np.where(a[:,:,3]>=128,255,0).astype(np.uint8)
    return Image.fromarray(np.dstack((result,alpha)))


def choose_cycle(frames):
    # Compare pose AND motion direction within the actual sequence. No reversed
    # playback, blended frames, duplicated endpoints or generated in-betweens.
    arrays=np.asarray([np.asarray(f.resize((96,96),Image.Resampling.NEAREST)) for f in frames],dtype=np.float32)/255
    rgb=arrays[:,:,:,:3]*arrays[:,:,:,3:4];mask=arrays[:,:,:,3]
    # Legs carry gait phase. Head/torso appearance must not dominate selection.
    yy=np.arange(96)[:,None];weight=0.1+(yy>=52)*1.8
    def diff(a,b):return float(np.mean(np.abs(a-b)*weight[:,:,None]))
    best=None
    for start in range(4,min(30,len(frames)-20)):
        for length in range(20,min(39,len(frames)-start-1)):
            end=start+length
            pose=diff(rgb[start],rgb[end])
            velocity=diff(rgb[start+1]-rgb[start],rgb[end+1]-rgb[end])
            motion=float(np.mean(np.abs(rgb[start+1:end]-rgb[start:end-1])))
            score=pose+.4*velocity
            if motion<.0001:continue
            if best is None or score<best['score']:
                best=dict(startFrame=start,endFrameExclusive=end,length=length,score=score,poseError=pose,velocityError=velocity)
    if best is None:raise RuntimeError('No moving cycle candidate')
    best.update(method='leg-weighted pose and velocity search; actual forward frames only',quality='needs_visual_review')
    return best


def export():
    raw=[]
    with av.open(str(OUT/'walk-raw.mp4')) as container:
        fps=float(container.streams.video[0].average_rate)
        raw=[f.to_image().convert('RGB') for f in container.decode(video=0)]
    masks=[]
    for frame in raw:
        # Matte distance works on source video without anime segmentation. A fixed
        # palette and hard alpha are applied only after downsampling.
        cut=engine.remove_flat_background(frame,tolerance=26)
        masks.append(cut)
    palette=json.loads((OUT/'direction.json').read_text(encoding='utf-8'))['palette']
    coarse=[remap(f,palette,128) for f in masks]
    interval=choose_cycle(coarse)
    indices=[interval['startFrame']+round(i*interval['length']/8) for i in range(8)]
    duration=round(interval['length']/fps/8*1000)
    save_json('loop.json',dict(**interval,inputFrames=len(raw),inputFPS=fps,selectedIndices=indices,frameDurationMs=duration))
    sheets={};records={}
    for size in (64,128):
        folder=OUT/str(size);folder.mkdir(exist_ok=True)
        all_folder=folder/'all-frames';all_folder.mkdir(exist_ok=True)
        frames=[remap(masks[index],palette,size) for index in indices]
        full=[remap(f,palette,size) for f in masks]
        for i,frame in enumerate(full):frame.save(all_folder/f'frame-{i:03d}.png')
        for i,frame in enumerate(frames):frame.save(folder/f'frame-{i:02d}.png')
        sheet=Image.new('RGBA',(size*8,size))
        for i,frame in enumerate(frames):sheet.paste(frame,(i*size,0))
        sheet.save(folder/'sheet.png')
        frames[0].save(folder/'animation.png',save_all=True,append_images=frames[1:],duration=duration,loop=0,disposal=0,blend=0)
        big=[f.resize((512,512),Image.Resampling.NEAREST) for f in frames]
        big[0].save(folder/'animation.webp',save_all=True,append_images=big[1:],duration=duration,loop=0,lossless=True)
        all_big=[f.resize((512,512),Image.Resampling.NEAREST) for f in full]
        all_big[0].save(folder/'full-video.webp',save_all=True,append_images=all_big[1:],duration=round(1000/fps),loop=0,lossless=True)
        records[str(size)]=[]
        allowed={tuple(c) for c in palette}
        for index,frame in zip(indices,frames):
            a=np.asarray(frame);visible=a[:,:,3]>0;colors={tuple(c) for c in np.unique(a[:,:,:3][visible],axis=0)}
            assert colors<=allowed and set(np.unique(a[:,:,3]))<={0,255} and visible.any()
            records[str(size)].append(dict(sourceFrame=index,bounds=list(frame.getbbox()),colors=len(colors),size=[size,size]))
    comparison=checker((8*256,2*286));draw=ImageDraw.Draw(comparison)
    for row,size in enumerate((64,128)):
        for i in range(8):
            image=Image.open(OUT/str(size)/f'frame-{i:02d}.png').convert('RGBA').resize((256,256),Image.Resampling.NEAREST)
            comparison.paste(image,(i*256,row*286+30),image)
            draw.text((i*256+8,row*286+8),f'{size}px / frame {indices[i]}',fill='black')
    comparison.save(OUT/'comparison.png')
    raw_review=Image.new('RGB',(4*384,2*384))
    for i in range(8):raw_review.paste(raw[round(i*(len(raw)-1)/7)].resize((384,384)),(i%4*384,i//4*384))
    raw_review.save(OUT/'raw-review.jpg')
    save_json('results.json',dict(version=VERSION,palette=palette,loop=interval,frames=records,
              sourceDirection='right',pipeline='Qwen direction edit -> original MiniMax H3 20 steps -> flat matte -> nearest grid -> exact original palette',
              limitations=['Pixel postprocessing, not native pixel sequence generation','No character-part lock','Loop selection metric does not prove anatomical quality or correct foot contact']))
    with zipfile.ZipFile(OUT/'pixel-minimax-walk.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for size in (64,128):
            for p in (OUT/str(size)).rglob('*.png'):archive.write(p,p.relative_to(OUT).as_posix())
        for name in ('reference-right.png','results.json','loop.json','video-settings.json'):archive.write(OUT/name,name)
    cards=''.join(f'<article><h2>{size}×{size} · 32색</h2><div class="checker"><img class="pixel" src="{size}/animation.webp"></div><p>실제 영상에서 고른 8프레임 · {duration}ms/프레임</p><p><a href="{size}/sheet.png">PNG 시트</a> · <a href="{size}/animation.png">APNG</a></p><details><summary>전체 영상 도트 변환 · 구간 선택 전</summary><img class="pixel" src="{size}/full-video.webp"></details></article>' for size in (64,128))
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>우측 보행 · MiniMax → 도트 비교</title><style>body{background:#171923;color:#eef0fa;font:15px/1.6 system-ui;margin:24px}h1{font-size:26px}main{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}article{background:#252936;border:1px solid #4b5268;border-radius:12px;padding:16px;min-width:0}.checker{background:repeating-conic-gradient(#ddd 0 25%,#f7f7f7 0 50%) 0/24px 24px}.pixel{image-rendering:pixelated;width:100%}a{color:#c2cdff}video{width:100%}.wide{width:100%;image-rendering:pixelated}@media(max-width:900px){main{grid-template-columns:1fr}}</style><h1>우측 걷기 · MiniMax 영상 → 도트 후처리</h1><p>같은 캐릭터를 우측 옆모습·동작 중 포즈로 변경 → 기본 MiniMax H3 20스텝 → 실제 보행 구간 8장 → 공통 원본 팔레트·격자 정리. 새 LoRA·파츠 고정·보간·역재생은 사용하지 않았습니다.</p><main><article><h2>우측 기준 스프라이트</h2><div class="checker"><img class="pixel" src="reference-right.png"></div><details><summary>원본 정면 도트</summary><img class="pixel" src="reference-front.png"></details><h2>MiniMax 원본 영상</h2><video controls loop muted playsinline src="walk-raw.mp4"></video></article>'''+cards+'''</main><p><a href="pixel-minimax-walk.zip" download>64·128px PNG 프레임·시트·APNG 다운로드</a> · <a href="results.json">설정·결과 기록</a> · <a href="../pixel-animation-refine-20261019/preview.html">이전 4포즈 방식</a></p><h2>프레임 비교</h2><img class="wide" src="comparison.png"><details><summary>후처리 전 영상의 시간별 프레임</summary><img class="wide" src="raw-review.jpg"></details><p>루프는 다리 영역의 자세·속도 차이로 실제 구간을 선택한 초안입니다. 접지·장비 변형·경계 깜빡임·루프 연결은 직접 검수해야 합니다. 최종 파일은 픽셀 격자 PNG지만 영상 모델이 처음부터 픽셀 단위로 설계한 결과는 아닙니다.</p></html>'''
    (OUT/'preview.html').write_text(page,encoding='utf-8');print('PREVIEW',OUT/'preview.html',flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');OUT.mkdir(exist_ok=True)
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['direction','video','export']);args=parser.parse_args()
    dict(direction=direction,video=video,export=export)[args.stage]()
