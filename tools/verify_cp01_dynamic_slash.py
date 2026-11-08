"""Whole-body CP01 slash: allow root travel, hip rotation and an actual step."""
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
import av
import numpy as np
from PIL import Image,ImageDraw
import idle_tool as engine
import sprite_gif
from tools import verify_cp01_motion as cp
from tools import verify_cp01_horizontal_slash as old
from tools import verify_pixel_minimax as executor
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release
from tools.repair_cp01_matte import repair

OUT=ROOT/'outputs/cp01-dynamic-slash-20261023'
PREVIOUS=ROOT/'outputs/cp01-horizontal-slash-20261023'
ORIGINAL_CUT=cp.cut_with_crimson
ACTION=dict(title='전신 체중 이동 · 단검 횡베기',seed=2026102334,padding=30,
    loop=False,strength='high',frames=24)
PROMPT=(
    'A dynamic hand-drawn 2D anime game attack by the EXACT SAME character in the input: '
    'short white bob with crimson streak, red eyes, white collared blouse, black tie, grey flared '
    'trousers, red gloves, black platform ankle boots, and the same ONE SHORT black triangular dagger. '
    'Preserve her original face, ink linework, cel-painted shadows, costume colours and adult proportions. '
    'Perform ONE explosive forward-stepping HORIZONTAL DAGGER CUT toward SCREEN RIGHT, using the '
    'WHOLE BODY, with strong anticipation, acceleration and a grounded follow-through. '
    'ANTICIPATION: pull the knife elbow back to the ribs, bend BOTH knees visibly, lower the pelvis '
    'and load the weight onto the rear leg. Draw the shoulder and hip back together into a coiled '
    'athletic pose. The head moves down and back with the torso. '
    'STRIKE: push hard off the rear boot, lift its heel, and take ONE clear forward step with the '
    'front boot toward screen RIGHT, about a quarter body-width. The pelvis travels forward, '
    'hips lead and shoulders snap around after them, driving the knife arm through a fast broad '
    'horizontal cutting arc across the front of the chest. The knife cuts SIDEWAYS in a curved '
    'sweep rather than poking straight forward. The torso leans into the step without folding at '
    'the waist. The empty hand swings back as a counterbalance. '
    'FOLLOW-THROUGH: the front knee bends deeply to catch the moving body, rear leg stretches '
    'behind with its heel raised, shoulders and knife arm continue past the impact. Hair tips, '
    'tie and trouser hems whip with a delayed response. Then pull the knife back to a compact '
    'combat guard and regain a balanced ready stance with soft knees. '
    'The HEAD, CHEST and HIPS visibly travel through these different poses; the front foot moves '
    'and lands. A stationary paper-doll torso with only a moving arm is incorrect. '
    'Keep her nose and gaze directed RIGHT while allowing natural shoulder and pelvis rotation, '
    'foot pivots and a small 3/4 torso view. Fixed side-view camera, no full spin or back view. '
    'One brief narrow crimson crescent follows the blade near impact and fades, leaving the '
    'body action readable. Same short knife stays in the same hand. One cut, no repeated combo. '
    'Retain the DRAWN 2D style and constant painted lighting; no 3D rendering or new materials. '
    'Keep the entire body, both boots and the weapon inside the canvas. Uniform flat medium-grey '
    'background including every limb gap, with no floor, shadow, scenery, target or text.')


def configure():
    cp.OUT=OUT
    cp.ACTIONS={'attack':ACTION}
    cp.build=build
    cp.cut_with_crimson=lambda im:repair(ORIGINAL_CUT(im))[0]


def generate():
    configure();cp.prepare()
    source_info=json.loads((OUT/'source.json').read_text(encoding='utf-8'))
    source_info.update(motionPadding=30,preparation='Exact original RGBA; fit on neutral matte with 30 percent motion padding.')
    cp.save(OUT/'source.json',source_info)
    folder=OUT/'attack'
    if (folder/'raw.mp4').exists():return
    if (folder/'native-v1-pending.json').exists():
        graph=json.loads((folder/'native-v1-workflow.json').read_text(encoding='utf-8'))
    else:
        ensure_idle();engine.start_comfy();release((8190,8191))
        prepared=engine.prepare_reference_image((OUT/'reference.png').read_bytes(),768,768,30)
        (folder/'reference-prepared.png').write_bytes(prepared)
        uploaded=engine.upload_image(prepared,'cp01-dynamic-slash.png')
        graph=engine.build_workflow(uploaded,PROMPT,3,768,768,ACTION['seed'],
            animation_type='attack',loop=False,facing='right',flat_background=True,
            blink_mode='none',motion_strength='high',sampling_mode='quality',workflow_id='standard')
        # The old generic placement constraint opposes an actual lunge. Permit
        # deliberate root translation while preserving camera and drawing scale.
        text=graph['6']['inputs']['prompt']
        text=text.replace('The opening character size, screen placement, head-to-body proportions, costume, equipment, linework and painted shading are retained.',
            'Retain the opening drawing scale, head-to-body proportions, costume, equipment, linework and painted shading. The character is allowed to translate forward and downward during the step and knee bend; do not pin the body or feet to their opening screen positions.')
        graph['6']['inputs']['prompt']=text
        graph['15']['inputs'].pop('audio',None);graph.pop('14',None);graph.pop('5',None)
        graph['16']['inputs']['filename_prefix']='cp01_dynamic_slash_20261023/attack'
        cp.save(folder/'settings.json',dict(animationType='attack',seed=ACTION['seed'],width=768,height=768,
            duration=3,fps=24,steps=20,loop=False,facing='right',motionPadding=30,motionStrength='high',
            referenceOffsetX=0,workflowId='standard',samplingMode='quality',prompt=PROMPT,
            actualPrompt=text,sourceSha256=cp.digest(cp.SOURCE),rootMotionAllowed=True,published=False))
    executor.OUT=folder
    history=executor.execute(graph,engine.COMFY_URL,'native-v1')
    shutil.copyfile(engine.find_saved_video(history),folder/'raw.mp4')
    ensure_idle();release((8189,))
    print('DYNAMIC_VIDEO_READY',flush=True)
    raw_review()


def raw_review():
    with av.open(str(OUT/'attack/raw.mp4')) as v:frames=[f.to_image().convert('RGB') for f in v.decode(video=0)]
    contact=Image.new('RGB',(1600,960));draw=ImageDraw.Draw(contact)
    for n,i in enumerate(np.linspace(0,len(frames)-1,15).round().astype(int)):
        contact.paste(frames[i].resize((320,320)),(n%5*320,n//5*320))
        draw.text((n%5*320+8,n//5*320+8),str(i),fill='red')
    contact.save(OUT/'attack/review-raw.webp',quality=95)


def export():
    configure();cp.export();raw_review()
    old.OUT=OUT;old.matte_review()
    compare()
    build()


def compare():
    previous_folder=OUT/'previous';previous_folder.mkdir(exist_ok=True)
    previous_meta=json.loads((PREVIOUS/'attack/frames.json').read_text(encoding='utf-8'))
    current_meta=json.loads((OUT/'attack/frames.json').read_text(encoding='utf-8'))
    previous_padding=json.loads((PREVIOUS/'attack/settings.json').read_text(encoding='utf-8')).get('motionPadding',20)
    current_padding=json.loads((OUT/'attack/settings.json').read_text(encoding='utf-8')).get('motionPadding',30)
    previous_scale=(1-current_padding/100)/(1-previous_padding/100)
    previous_size=round(768*previous_scale);previous_offset=(768-previous_size)//2
    previous_frames=[]
    for index in previous_meta['previewSourceIndices']:
        source=Image.open(PREVIOUS/'attack/all-frames'/f'frame-{index:03d}.png').convert('RGBA')
        im=Image.new('RGBA',(768,768));im.paste(source.resize((previous_size,previous_size),Image.Resampling.LANCZOS),(previous_offset,previous_offset))
        previous_frames.append(im)
    current_frames=[Image.open(OUT/'attack/all-frames'/f'frame-{i:03d}.png').convert('RGBA')
                    for i in current_meta['previewSourceIndices']]
    boxes=[f.getchannel('A').getbbox() for f in previous_frames+current_frames]
    l,t,r,b=min(x[0] for x in boxes),min(x[1] for x in boxes),max(x[2] for x in boxes),max(x[3] for x in boxes)
    side=math.ceil(max(r-l,b-t)*1.08);x,y=math.floor((l+r-side)/2),math.floor((t+b-side)/2)
    crop=[x,y,x+side,y+side]
    for folder,frames,meta in [(previous_folder,previous_frames,previous_meta),(OUT/'attack',current_frames,current_meta)]:
        images=[im.crop(crop).resize((512,512),Image.Resampling.LANCZOS) for im in frames]
        times=meta['previewDurationMs']
        images[0].save(folder/'game-animation.webp',save_all=True,append_images=images[1:],duration=times,loop=0,lossless=True)
        data,gif=sprite_gif.encode(images,times);(folder/'game-animation.gif').write_bytes(data)
        source_meta=PREVIOUS/'attack/game-frames.json' if folder==previous_folder else folder/'game-frames.json'
        game=json.loads(source_meta.read_text(encoding='utf-8'));game.update(commonPresentationCrop=crop,gif=gif)
        if folder==previous_folder:
            game['scaleAboutCanvasCenter']=previous_scale
            sheet=Image.new('RGBA',(768*game['columns'],768*game['rows']))
            for n,index in enumerate(meta['sourceIndices']):
                im=frames[meta['previewSourceIndices'].index(index)]
                sheet.paste(im,(n%4*768,n//4*768))
            sheet.save(folder/'game-sheet.png')
        (folder/'game-frames.json').write_text(json.dumps(game,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'comparison.json').write_text(json.dumps(dict(previousSource=str(PREVIOUS),
        previousScale=previous_scale,currentScale=1,commonCrop=crop,rootMotionStabilised=False),indent=2),encoding='utf-8')


def build():
    OUT.mkdir(exist_ok=True)
    cards=[]
    timing_note=''
    frame_meta=OUT/'attack/frames.json'
    if frame_meta.exists():
        phase=json.loads(frame_meta.read_text(encoding='utf-8')).get('phaseTiming')
        if phase:timing_note=f'<p>공격 부분 {phase["totalMs"]/1000:.2f}초를 추렸고 베는 구간의 재생 속도를 높였습니다. 새 자세를 보간하거나 역재생한 프레임은 없습니다.</p>'
    for folder,title in [('previous','이전 · 팔 위주'),('attack','새 시험 · 전신 동작')]:
        if not (OUT/folder/'game-animation.webp').exists():continue
        note=''
        if (OUT/folder/'review.json').exists():note=json.loads((OUT/folder/'review.json').read_text(encoding='utf-8')).get('note','')
        cards.append(f'<article><h2>{title}</h2><p>{html.escape(note)}</p><img src="{folder}/game-animation.webp" alt="{title}">'
            f'<p><a href="{folder}/game-animation.gif">GIF</a> · <a href="{folder}/game-sheet.png">PNG 시트</a> · '
            f'<a href="{folder}/game-frames.json">프레임 시간</a></p></article>')
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>전신 횡베기 시험</title><style>:root{--matte:#142436}body{background:#1b2230;color:#eee;font:16px/1.65 system-ui;margin:24px}main{display:flex;gap:20px;flex-wrap:wrap}article{width:512px;max-width:100%}img{width:100%;background:var(--matte)}a{color:#c9c0ff}button{padding:8px 14px;margin-right:8px}</style><h1>전신 횡베기 시험</h1><p>무릎 굽힘, 전진 스텝, 골반과 어깨 회전을 허용한 새 영상입니다. 표시 크기는 입력의 동작 여백 비율을 보정해 비교합니다. 세부 형태와 동작 품질은 별도 검토가 필요합니다.</p><button onclick="document.documentElement.style.setProperty('--matte','#142436')">어둡게</button><button onclick="document.documentElement.style.setProperty('--matte','#fff4dc')">밝게</button><button onclick="document.documentElement.style.setProperty('--matte','#226b54')">초록</button><p><a href="cp01-dynamic-slash.zip">새 동작 파일 ZIP</a></p><main>'''+''.join(cards)+'''</main><p><a href="attack/review-raw.webp">생성 원본 프레임</a> · <a href="attack/matte-review.jpg">밝은·어두운 배경 비교</a></p></html>'''
    page=page.replace('<main>',timing_note+'<main>',1)
    (OUT/'preview.html').write_text(page,encoding='utf-8')


def check():
    configure();cp.check()
    validation=json.loads((OUT/'validation.json').read_text(encoding='utf-8'))
    validation['visualReview']={'attack':json.loads((OUT/'attack/review.json').read_text(encoding='utf-8')) if (OUT/'attack/review.json').exists() else 'pending visual review'}
    (OUT/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'README.txt').write_text('CP01 whole-body horizontal dagger attack experiment\n\n768px 24FPS 20-step reference-conditioned MiniMax video.\n'
        'High motion; right-facing action permits shoulder/hip rotation, foot articulation and root travel.\n'
        '30 percent motion padding; source scale is 0.7 versus 0.8 in the earlier tests.\n'
        'Game sheets retain native motion; no per-frame root stabilisation or reverse playback.\n'
        'If phaseTiming exists in game-frames.json, use its per-cell durationMs for the retimed attack.\n'
        'Neutral matte repair applied; PNG/WebP retain soft alpha.\n'
        'See attack/review.json for observed limits.\n',encoding='utf-8')
    with zipfile.ZipFile(OUT/'cp01-dynamic-slash.zip','w',zipfile.ZIP_DEFLATED) as z:
        for f in ['source-original.png','source.json','preview.html','README.txt','validation.json']:
            z.write(OUT/f,f)
        for f in ['game-animation.gif','game-animation.webp','game-sheet.png','game-frames.json','settings.json','raw.mp4','review-raw.webp','matte-review.jpg','reference-prepared.png','review.json']:
            p=OUT/'attack'/f
            if p.exists():z.write(p,'attack/'+f)
        for p in (OUT/'attack/game-selected').glob('*.png'):z.write(p,'attack/game-selected/'+p.name)
        for p in (OUT/'previous').iterdir():
            if p.is_file():z.write(p,'previous/'+p.name)
        z.write(OUT/'comparison.json','comparison.json')
    with zipfile.ZipFile(OUT/'cp01-dynamic-slash.zip') as z:assert z.testzip() is None
    print('DYNAMIC_EXPORT_VALIDATED',OUT,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['all','generate','export','build','check','compare'])
    stage=parser.parse_args().stage
    if stage=='all':generate();export();check()
    else:globals()[stage]()
