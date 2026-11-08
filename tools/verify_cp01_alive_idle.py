"""40-step articulated idle after the restrained 20-step clip was rejected."""
import argparse
import html
import json
import math
import shutil
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
from PIL import Image
import idle_tool as engine
import sprite_gif
from tools import verify_cp01_ready_idle as base
from tools import verify_pixel_minimax as executor
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release

OUT=ROOT/'outputs/cp01-alive-idle40-20261023'
PREVIOUS=ROOT/'outputs/cp01-ready-idle-20261023'
STEPS=40
SEED=2026102336
PROMPT=(
    'A fluid WHOLE-BODY combat-ready idle loop, like a relaxed martial artist balancing while '
    'waiting for an opponent. The SAME hand-drawn 2D anime character from the reference: white '
    'bob with red hair accent, red eye, white blouse and black tie, grey flared trousers, red '
    'gloves, black platform boots and ONE short black dagger held in a bent arm near the waist. '
    'Animate ONE complete continuous weight-transfer and breathing cycle in three seconds. '
    'The pelvis travels visibly back and forth between the two supporting legs. As the weight '
    'moves onto one leg, that knee bends and the opposite leg softens; the pelvis gently lowers '
    'then rises. Let the shoulder line counter-rotate naturally against the hips instead of '
    'locking the torso into a flat panel. The head follows the moving spine with a small relaxed '
    'tilt. The guard hands, bent elbows and dagger follow the moving shoulders with a slight '
    'delay, making soft rounded paths instead of jerky independent wrist twitches. '
    'Use clearly VISIBLE rhythmic movement: about 15-25 pixels of combined hip travel and body '
    'rise/fall on this 768-pixel canvas, not an almost motionless still with fluttering hair. '
    'Keep natural anatomy and stable cloth volume while moving the joints; no torso inflation. '
    'Hair tips, tie and trouser hems swing after the body changes direction and settle smoothly. '
    'The soles keep contact with the same two ground spots; allow subtle heel rolls and ankle '
    'flexion to carry the shifting weight. No foot sliding, walking, jumping, deep crouching '
    'or attack. The nose and gaze stay RIGHT while shoulders and pelvis may twist naturally. '
    'One brief natural blink near the middle is fine, with the same facial identity throughout. '
    'Keep the action in motion from first to last frame, without freezing at either end. '
    'Smoothly complete the cycle at the original stance, with matching velocity for the loop. '
    'Original drawn ink contours, flat cel-shadow shapes and stable colours; no 3D relighting. '
    'Full body and dagger visible at constant scale with a fixed side-view camera. Featureless '
    'uniform medium-grey matte in every empty gap. No floor shadow, blood marks, red ribbons, '
    'particles, aura or weapon effects; only the real gloves and hair accent are red.')


def configure():
    base.OUT=OUT
    base.ACTION=dict(base.ACTION,seed=SEED,strength='high',frames=24,title='전신 리듬 대기 · 40스텝')
    base.PROMPT=PROMPT
    base.build=build
    base.compare=compare
    base.configure()
    # The existing checker permits an optional attack comparison directory.
    (OUT/'attack').mkdir(parents=True,exist_ok=True)


def generate():
    configure();folder=OUT/'idle';folder.mkdir(exist_ok=True)
    for name in ['source-original.png','reference.png','reference-edit-prompt.txt']:
        if not (OUT/name).exists():shutil.copy2(PREVIOUS/name,OUT/name)
    assert base.cp.digest(OUT/'source-original.png')==base.cp.digest(base.cp.SOURCE)
    assert base.cp.digest(OUT/'reference.png')==base.cp.digest(PREVIOUS/'reference.png')
    base.cp.save(OUT/'source.json',dict(sourcePath=str(base.cp.SOURCE),sha256=base.cp.digest(base.cp.SOURCE),
        sourceUnchanged=True,referenceSha256=base.cp.digest(OUT/'reference.png'),published=False,motionPadding=30,
        preparation='Same VFX-free ready-stance reference pixels as the rejected 20-step trial. No new image edit.'))
    if (folder/'raw.mp4').exists():return
    if (folder/'native-v1-pending.json').exists():
        graph=json.loads((folder/'native-v1-workflow.json').read_text(encoding='utf-8'))
    else:
        ensure_idle();engine.start_comfy();release((8190,8191))
        prepared=(PREVIOUS/'idle/reference-prepared.png').read_bytes()
        (folder/'reference-prepared.png').write_bytes(prepared)
        uploaded=engine.upload_image(prepared,'cp01-alive-idle40.png')
        graph=engine.build_workflow(uploaded,PROMPT,3,768,768,SEED,animation_type='idle',loop=True,
            facing='preserve',flat_background=True,blink_mode='single',motion_strength='high',
            sampling_mode='quality',workflow_id='standard')
        graph['10']['inputs']['steps']=STEPS
        text=graph['6']['inputs']['prompt']
        text=text.replace(engine.FACING_PROMPTS['preserve'],
            'The nose and gaze stay directed screen RIGHT with the same side-view camera. Allow natural shoulder and pelvis counterrotation, spinal movement, head tilt and ankle flexion. Do not freeze the torso or hips into their opening orientation.')
        text=text.replace('The opening character size, screen placement, head-to-body proportions, costume, equipment, linework and painted shading are retained.',
            'Retain character scale, head-to-body proportions, costume, equipment and the original ink-and-cel shading. The pelvis, chest, head and guard hands may translate and rotate naturally within the fixed camera during the weight shifts.')
        graph['6']['inputs']['prompt']=text
        graph['15']['inputs'].pop('audio',None);graph.pop('14',None);graph.pop('5',None)
        graph['16']['inputs']['filename_prefix']='cp01_alive_idle40_20261023/idle'
        base.cp.save(folder/'settings.json',dict(animationType='idle',seed=SEED,width=768,height=768,
            duration=3,fps=24,steps=STEPS,loop=True,facing='right, articulated',motionPadding=30,
            motionStrength='high',referenceOffsetX=0,workflowId='standard',samplingMode='quality',
            blinkMode='single',prompt=PROMPT,actualPrompt=text,sourceSha256=base.cp.digest(base.cp.SOURCE),
            referenceSha256=base.cp.digest(OUT/'reference.png'),published=False,
            changesFromPrevious=['20 to 40 steps','visible whole-body rhythm','torso/view locks relaxed','single blink allowed'],
            controlledStepComparison=False))
    executor.OUT=folder
    history=executor.execute(graph,engine.COMFY_URL,'native-v1')
    shutil.copyfile(engine.find_saved_video(history),folder/'raw.mp4')
    ensure_idle();release((8189,));base.raw_review()
    print('ALIVE_IDLE40_VIDEO_SAVED',flush=True)


def compare():
    previous=OUT/'previous';previous.mkdir(exist_ok=True)
    for name in ['game-sheet.png','game-frames.json']:
        if not (previous/name).exists():shutil.copy2(PREVIOUS/'idle'/name,previous/name)
    cases=[(PREVIOUS/'idle',previous),(OUT/'idle',OUT/'idle')]
    metas=[json.loads((s/'frames.json').read_text(encoding='utf-8')) for s,_ in cases]
    sets=[[Image.open(s/'all-frames'/f'frame-{i:03d}.png').convert('RGBA') for i in m['previewSourceIndices']] for (s,_),m in zip(cases,metas)]
    boxes=[im.getchannel('A').getbbox() for frames in sets for im in frames]
    l,t,r,b=min(q[0] for q in boxes),min(q[1] for q in boxes),max(q[2] for q in boxes),max(q[3] for q in boxes)
    size=math.ceil(max(r-l,b-t)*1.08);x,y=math.floor((l+r-size)/2),math.floor((t+b-size)/2);crop=[x,y,x+size,y+size]
    for (_,dest),meta,frames in zip(cases,metas,sets):
        images=[im.crop(crop).resize((512,512),Image.Resampling.LANCZOS) for im in frames]
        times=meta['previewDurationMs']
        images[0].save(dest/'game-animation.webp',save_all=True,append_images=images[1:],duration=times,loop=0,lossless=True)
        data,gif=sprite_gif.encode(images,times);(dest/'game-animation.gif').write_bytes(data)
        game=json.loads((dest/'game-frames.json').read_text(encoding='utf-8'));game.update(commonPresentationCrop=crop,gif=gif)
        base.cp.save(dest/'game-frames.json',game)
    base.cp.save(OUT/'comparison.json',dict(commonCrop=crop,sharedCanvas=[768,768],inputPadding=30,
        referencePixelsIdentical=True,seedIdentical=True,steps=[20,40],promptAndMotionAlsoChanged=True,
        perFrameStabilisation=False))


def build():
    OUT.mkdir(exist_ok=True);cards=[]
    for name,title in [('previous','이전 · 20스텝 / 움직임 약함'),('idle','새 시험 · 40스텝 / 전신 리듬')]:
        if not (OUT/name/'game-animation.webp').exists():continue
        note=''
        p=OUT/name/'review.json'
        if p.exists():note=json.loads(p.read_text(encoding='utf-8')).get('note','')
        downloads=(f'<a href="{name}/native-loop-sheet.png">전체 72프레임 PNG 시트</a> · <a href="{name}/native-loop.json">전체 프레임 시간</a> · <a href="{name}/game-sheet.png">24프레임 간편 시트</a>'
                   if name=='idle' else f'<a href="{name}/game-sheet.png">PNG 시트</a> · <a href="{name}/game-frames.json">프레임 시간</a>')
        cards.append(f'<article><h2>{title}</h2><p>{html.escape(note)}</p><img src="{name}/game-animation.webp" alt="{title}"><p><a href="{name}/game-animation.gif">GIF</a> · {downloads}</p></article>')
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>전신 리듬 idle · 40스텝</title><style>:root{--matte:#142436}body{background:#1b2230;color:#eee;font:16px/1.65 system-ui;margin:24px}main{display:flex;gap:20px;flex-wrap:wrap}article{width:512px;max-width:100%}img{width:100%;background:var(--matte)}a{color:#c9c0ff}button{padding:8px 14px;margin-right:8px}</style><h1>전신 리듬 idle · 40스텝 시험</h1><p>같은 입력 이미지·시드에서 스텝을 20→40으로 높이고, 몸통 고정을 풀고 무릎·골반·어깨의 연결된 움직임을 요청했습니다. 프롬프트와 움직임 조건도 달라졌으므로 차이를 스텝 수만의 효과로 해석하지 않습니다.</p><button onclick="document.documentElement.style.setProperty('--matte','#142436')">어둡게</button><button onclick="document.documentElement.style.setProperty('--matte','#fff4dc')">밝게</button><button onclick="document.documentElement.style.setProperty('--matte','#226b54')">초록</button><p><a href="cp01-alive-idle40.zip">새 대기 GIF·PNG 시트·원본 영상 ZIP</a></p><main>'''+''.join(cards)+'''</main><p><a href="idle/raw.mp4">새 원본 영상</a> · <a href="idle/matte-review.jpg">밝은·어두운 배경 비교</a> · <a href="idle/settings.json">실제 설정·프롬프트</a></p></html>'''
    (OUT/'preview.html').write_text(page,encoding='utf-8')


def export():
    configure();base.export()
    full_sheet();build()


def full_sheet():
    folder=OUT/'idle'
    meta=json.loads((folder/'frames.json').read_text(encoding='utf-8'))
    indices=meta['previewSourceIndices'];assert len(indices)==72
    columns=8;rows=9;size=768
    sheet=Image.new('RGBA',(columns*size,rows*size))
    for n,index in enumerate(indices):
        im=Image.open(folder/'all-frames'/f'frame-{index:03d}.png').convert('RGBA')
        sheet.paste(im,(n%columns*size,n//columns*size))
    sheet.save(folder/'native-loop-sheet.png')
    base.cp.save(folder/'native-loop.json',dict(frameWidth=size,frameHeight=size,columns=columns,rows=rows,
        sourceIndices=indices,durationMs=meta['previewDurationMs'],fps=24,loop=True,
        totalMs=sum(meta['previewDurationMs']),frameCount=len(indices),anchor=[384,384],
        framesFolder='full-frames',nativeVideoFrames=meta['sourceFrames'],
        note='All forward generated frames except repeated closing anchor. No resampling or per-frame pose stabilisation.'))
    print('FULL_72_FRAME_SHEET_READY',flush=True)


def check():
    configure();base.check()
    graph=json.loads((OUT/'idle/native-v1-workflow.json').read_text(encoding='utf-8'))
    assert graph['10']['inputs']['steps']==40
    assert graph['6']['inputs']['first_frame']==graph['6']['inputs']['last_frame']
    assert base.cp.digest(OUT/'idle/reference-prepared.png')==base.cp.digest(PREVIOUS/'idle/reference-prepared.png')
    native=json.loads((OUT/'idle/native-loop.json').read_text(encoding='utf-8'))
    sheet=Image.open(OUT/'idle/native-loop-sheet.png').convert('RGBA')
    assert sheet.size==(6144,6912) and native['frameCount']==72 and sum(native['durationMs'])==3000
    for n,index in enumerate(native['sourceIndices']):
        im=Image.open(OUT/'idle/all-frames'/f'frame-{index:03d}.png').convert('RGBA')
        cell=sheet.crop((n%8*768,n//8*768,(n%8+1)*768,(n//8+1)*768))
        assert np.array_equal(np.asarray(im),np.asarray(cell))
    p=OUT/'validation.json';validation=json.loads(p.read_text(encoding='utf-8'))
    validation.update(actualSteps=40,sameReferencePixels=True,sameSeed=True,otherMotionConstraintsAlsoChanged=True,
        fullNativeSheetFrames=72,fullSheetCellsPixelEqual=True)
    base.cp.save(p,validation)
    (OUT/'README.txt').write_text('CP01 40-step articulated idle\n\nSame VFX-free reference, 768px input pixels and seed as the earlier 20-step idle.\n'
        '40 native MiniMax steps; high motion, relaxed torso orientation, single blink allowed.\n'
        'Prompt and constraints also changed: this is not a controlled step-only comparison.\n'
        '3-second native loop; repeated final anchor omitted. No reverse playback or frame interpolation.\n'
        'Full-quality game files: idle/native-loop-sheet.png (8x9 cells, 768px each), native-loop.json, full-frames/*.png.\n'
        'All 72 frames at native 24FPS, 3-second loop; no frame interpolation. Texture size 6144x6912.\n'
        'Lighter 24-frame option: idle/game-sheet.png, game-frames.json, game-selected/*.png.\n'
        'PNG/WebP preserve soft alpha; GIF is limited to binary alpha.\n'
        'See idle/review.json and validation.json for actual observed limits.\n',encoding='utf-8')
    with zipfile.ZipFile(OUT/'cp01-ready-idle.zip') as source,zipfile.ZipFile(OUT/'cp01-alive-idle40.zip','w',zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            path=OUT/info.filename
            target.writestr(info.filename,path.read_bytes() if info.filename in ['README.txt','validation.json','preview.html'] else source.read(info.filename))
        for p in (OUT/'previous').iterdir():
            if p.is_file():target.write(p,'previous/'+p.name)
        for name in ['native-loop-sheet.png','native-loop.json']:
            target.write(OUT/'idle'/name,'idle/'+name)
        for index in native['sourceIndices']:
            path=OUT/'idle/all-frames'/f'frame-{index:03d}.png'
            target.write(path,'idle/full-frames/'+path.name)
    with zipfile.ZipFile(OUT/'cp01-alive-idle40.zip') as z:assert z.testzip() is None
    print('ALIVE_IDLE40_VALIDATED',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['generate','export','build','check','full_sheet','all'])
    stage=parser.parse_args().stage
    if stage=='all':generate();export();check()
    else:globals()[stage]()
