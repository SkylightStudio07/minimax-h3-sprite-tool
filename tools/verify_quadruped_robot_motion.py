"""Private 40-step quadruped robot idle and generated roof-gun burst."""
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
from scipy import ndimage
import idle_tool as engine
import image_background
from tools import verify_masked_raider_motion as exporter
from tools import verify_pixel_minimax as executor
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release
from tools.sprite_matte import clean_flat_matte

SOURCE=Path('Z:/Vertex/적/견마로봇1.png')
OUT=ROOT/'outputs/quadruped-robot-motion-20261024'
ORIGINAL_REMOVE=image_background.remove_sprite
IDENTITY=(
    'The EXACT SAME left-facing four-legged armored robot in the input illustration, original '
    'three-quarter view, olive and tan angular armor, dark mechanical joints, four original '
    'articulated legs and claw-like feet, same white/yellow unit markings and hazard labels. '
    'Preserve every rigid plate shape and the original 2D ink contours and painted cel shadows; '
    'articulate existing joints without bending or inflating the armor. Keep the boxy roof SENSOR '
    'with its red lenses and two raised antenna-like features. That red box is a sensor, NOT a '
    'weapon. The actual weapon is the ONE long thin horizontal barrel immediately BELOW the '
    'sensor on its roof mount: its muzzle is the LEFTMOST TIP of that barrel. Keep that barrel '
    'straight, constant length and attached to the same mount, pointing screen LEFT. '
    'Same existing parts, no new turret, limbs, mouth, tail or weapons. Keep the drawn hard-surface '
    'illustration style, not a new 3D render, camera orbit or photoreal relighting. ')
ACTIONS={
    'idle':dict(title='기계식 자세 조정 · idle',seed=2026102401,padding=30,loop=True,strength='normal',frames=24,
        prompt=(
            'A continuous mechanical combat-ready IDLE LOOP. Show one readable load-balancing '
            'cycle through the existing leg joints: the foreleg knees compress a little as the '
            'rear joints extend, lowering and pitching the rigid chassis slightly forward; '
            'then the opposite joint correction brings the chassis back smoothly. About 8-15 '
            'pixels of controlled ride-height change on the 768-pixel canvas, with clear small '
            'rotation at knees and ankles. The feet keep grounded support without skating. '
            'The near front foot may unload and gently re-seat in the same spot while the other '
            'three legs support the chassis. The roof sensor makes a very small purposeful '
            'gimbal scan and returns; the gun mount compensates to keep the barrel aimed left. '
            'Red lenses remain recognizable electronic lights, no organic blinking. '
            'Movement feels like a heavy robot actively stabilizing, not human breathing or '
            'an expanding hull. No walking, stepping away, jumping, shooting, muzzle flash, smoke '
            'or red ribbons. Continuous measured joint movement through the loop boundary, '
            'ending in the same stance and motion phase as the reference.')),
    'attack':dict(title='상부 포 점사 · 왼쪽',seed=2026102402,padding=30,loop=False,strength='high',frames=24,
        prompt=(
            'Exactly ONE powerful SHOT toward SCREEN LEFT from the LEFTMOST muzzle of the '
            'existing thin horizontal roof barrel, NOT from the red sensor lenses. First the '
            'four legs brace and bend at their existing joints, lowering the chassis into a '
            'firm firing stance while the barrel stays aimed horizontally left. Then a single '
            'brief compact yellow-white muzzle flash blooms at that left barrel tip and '
            'disappears immediately. The barrel and its mount kick BACK toward screen RIGHT '
            'as one straight rigid assembly; the heavy chassis rocks a little backward and '
            'the leg joints absorb the impulse. Strong readable mechanical recoil, no barrel '
            'bending. A small pale smoke puff follows the muzzle then disperses completely. '
            'The mount slides smoothly back into battery, joints extend and the robot recovers '
            'its original ready height. Red sensor box stays a sensor and never shoots a beam. '
            'One shot only, not a burst, sweeping laser, missile, flamethrower or repeated gunfire. '
            'No new cannon, extra barrel, victim, explosion cloud, camera shake or walking. '
            'All four feet retain support; recoil is transmitted through real leg articulation, '
            'not a gelatinous body wobble. Finish recovered with no lingering flash or smoke.'))}


def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')


def generate():
    OUT.mkdir(exist_ok=True)
    assert exporter.digest(SOURCE)==exporter.digest(OUT/'source-original.png')
    save(OUT/'source.json',dict(sourcePath=str(SOURCE),sourceSha256=exporter.digest(SOURCE),
        sourceUnchanged=True,published=False,referenceSha256=exporter.digest(OUT/'reference.png'),
        preparation='Built-in edit removed white sticker rim and painted red swoosh; semantic cutout cropped with 32px border. Original file preserved.'))
    for name,item in ACTIONS.items():
        folder=OUT/name;folder.mkdir(exist_ok=True)
        if (folder/'raw.mp4').exists():continue
        if (folder/'native-v1-pending.json').exists():graph=json.loads((folder/'native-v1-workflow.json').read_text(encoding='utf-8'))
        else:
            ensure_idle();engine.start_comfy();release((8190,8191))
            prepared=engine.prepare_reference_image((OUT/'reference.png').read_bytes(),768,768,item['padding'])
            (folder/'reference-prepared.png').write_bytes(prepared)
            uploaded=engine.upload_image(prepared,'quadruped-robot-'+name+'.png')
            prompt=IDENTITY+item['prompt']+' Fixed camera, constant scale and lighting. Whole robot, feet, barrel and compact muzzle flash stay inside the canvas. Flat uniform neutral-grey matte in every leg gap; no floor, ground shadow, scenery, text outside the existing decals or floating decoration.'
            graph=engine.build_workflow(uploaded,prompt,3,768,768,item['seed'],animation_type=name,
                loop=item['loop'],facing='left',flat_background=True,blink_mode='none',motion_strength=item['strength'],
                sampling_mode='quality',workflow_id='standard',subject_type='ground_machine')
            graph['10']['inputs']['steps']=40
            graph['6']['inputs']['prompt']=graph['6']['inputs']['prompt'].replace(
                'The original subject scale, composition, silhouette, component proportions, linework and painted shading are retained.',
                'Retain the original component designs, solid proportions, linework, painted shading and camera scale. The articulated silhouette and ride height may change naturally as the existing mechanical joints move.')
            graph['15']['inputs'].pop('audio',None);graph.pop('14',None);graph.pop('5',None)
            graph['16']['inputs']['filename_prefix']='quadruped_robot_20261024/'+name
            save(folder/'settings.json',dict(animationType=name,subjectType='ground_machine',seed=item['seed'],width=768,height=768,
                duration=3,fps=24,steps=40,loop=item['loop'],motionPadding=item['padding'],motionStrength=item['strength'],
                referenceOffsetX=0,facing='left',workflowId='standard',prompt=prompt,actualPrompt=graph['6']['inputs']['prompt'],
                sourceSha256=exporter.digest(SOURCE),referenceSha256=exporter.digest(OUT/'reference.png'),published=False))
        executor.OUT=folder;history=executor.execute(graph,engine.COMFY_URL,'native-v1')
        shutil.copyfile(engine.find_saved_video(history),folder/'raw.mp4')
        raw_review(name);print('ROBOT_VIDEO_READY',name,flush=True)
    ensure_idle();release((8189,))


def raw_review(name):
    with av.open(str(OUT/name/'raw.mp4')) as v:frames=[f.to_image().convert('RGB') for f in v.decode(video=0)]
    contact=Image.new('RGB',(1600,960));draw=ImageDraw.Draw(contact)
    for n,i in enumerate(np.linspace(0,len(frames)-1,15).round().astype(int)):
        contact.paste(frames[i].resize((320,320)),(n%5*320,n//5*320));draw.text((n%5*320+8,n//5*320+8),str(i),fill='red')
    contact.save(OUT/name/'review-raw.webp',quality=95)


def cut_robot(image):
    cut=ORIGINAL_REMOVE(image)
    rgb=np.asarray(image.convert('RGB'),dtype=float);rgba=np.array(cut)
    r,g,b=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2];yy,xx=np.indices(r.shape)
    # Preserve an actually generated muzzle flash near the known leftward gun
    # axis; no synthetic VFX is drawn. Sensor reds are outside this warm test.
    roi=(xx<320)&(yy>80)&(yy<320)
    warm=(r>160)&(g>85)&(r-b>35)&(g-b>12)
    white=(rgb.min(2)>190)&(np.ptp(rgb,axis=2)<55)
    support=ndimage.binary_propagation(warm&roi,mask=(warm|white)&roi)
    border=np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1]));bg=np.median(border,axis=0)
    alpha=np.clip(np.maximum(((rgb-bg)/np.maximum(255-bg,1)).max(2),((bg-rgb)/np.maximum(bg,1)).max(2)),0,1)
    recover=support&(rgba[:,:,3]<220)
    unmix=np.clip((rgb-bg*(1-alpha[:,:,None]))/np.maximum(alpha[:,:,None],.02),0,255)
    rgba[recover,:3]=np.rint(unmix[recover]).astype('uint8')
    rgba[recover,3]=np.maximum(rgba[recover,3],np.rint(alpha[recover]*255).astype('uint8'))
    cleaned,_=clean_flat_matte(Image.fromarray(rgba),tolerance=10,radius=2)
    return remove_edge_smoke(cleaned)


def remove_edge_smoke(image):
    a=np.array(image.convert('RGBA'))
    if not a[:,0,3].any():return image
    rgb=a[:,:,:3].astype(float);r,g,b=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2]
    yy,xx=np.indices(r.shape)
    warm=(r>160)&(g>85)&(r-g>5)&(g-b>12)
    protect=ndimage.binary_dilation(warm,iterations=10)
    # Known muzzle-left empty region: remove only neutral smoke connected to
    # the clipped left edge, stopping before the protected warm flash.
    allowed=(a[:,:,3]>0)&(xx<150)&(yy>90)&(yy<320)&(np.ptp(rgb,axis=2)<35)&~protect
    seed=np.zeros(allowed.shape,bool);seed[:,0]=allowed[:,0]
    removed=ndimage.binary_propagation(seed,mask=allowed)
    a[removed]=0
    return Image.fromarray(a)


def configure():
    exporter.OUT=OUT;exporter.SOURCE=SOURCE;exporter.ACTIONS=ACTIONS;exporter.build=build


def export(only=None):
    configure()
    if (OUT/'idle/raw.mp4').exists() and not (OUT/'idle/selection.json').exists():save(OUT/'idle/selection.json',dict(start=0,end=71,note='Repeated last reference omitted.'))
    image_background.remove_sprite=cut_robot
    try:exporter.export(only)
    finally:image_background.remove_sprite=ORIGINAL_REMOVE
    if all((OUT/name/'frames.json').exists() for name in ACTIONS):
        exporter.game();full_sheets();matte_review();build()


def full_sheets():
    for name in ACTIONS:
        folder=OUT/name;meta=json.loads((folder/'frames.json').read_text(encoding='utf-8'))
        indices=meta['previewSourceIndices'];cols=8;rows=math.ceil(len(indices)/cols)
        sheet=Image.new('RGBA',(cols*768,rows*768))
        for n,i in enumerate(indices):sheet.paste(Image.open(folder/'all-frames'/f'frame-{i:03d}.png').convert('RGBA'),(n%cols*768,n//cols*768))
        sheet.save(folder/'native-sheet.png')
        save(folder/'native-frames.json',dict(frameWidth=768,frameHeight=768,columns=cols,rows=rows,
            frameCount=len(indices),sourceIndices=indices,durationMs=meta['previewDurationMs'],sourceFPS=24,
            loop=ACTIONS[name]['loop'],anchor=[384,384],note='All forward displayed native frames. No pose stabilisation, reverse playback or frame interpolation.'))


def matte_review():
    for name in ACTIONS:
        meta=json.loads((OUT/name/'frames.json').read_text(encoding='utf-8'));indices=meta['previewSourceIndices']
        samples=[9,30,indices[-1]] if name=='attack' else [indices[0],indices[len(indices)//2],indices[-1]]
        canvas=Image.new('RGB',(1536,1024));draw=ImageDraw.Draw(canvas)
        for col,i in enumerate(samples):
            im=Image.open(OUT/name/'all-frames'/f'frame-{i:03d}.png').convert('RGBA')
            for row,color in enumerate(['#142436','#fff4dc']):
                bg=Image.new('RGBA',im.size,color);bg.alpha_composite(im)
                canvas.paste(bg.resize((512,512)).convert('RGB'),(col*512,row*512));draw.text((col*512+8,row*512+8),str(i),fill='red')
        canvas.save(OUT/name/'matte-review.jpg',quality=96)


def build():
    OUT.mkdir(exist_ok=True);cards=[]
    for name,item in ACTIONS.items():
        folder=OUT/name
        prefix='game-' if (folder/'game-animation.webp').exists() else ''
        if not (folder/(prefix+'animation.webp')).exists():continue
        review=json.loads((folder/'review.json').read_text(encoding='utf-8')) if (folder/'review.json').exists() else {}
        cards.append(f'<article><h2>{item["title"]}</h2><p>{html.escape(review.get("note","시각 검토 전입니다."))}</p><img src="{name}/{prefix}animation.webp" alt="{item["title"]}"><p><a href="{name}/{prefix}animation.gif">GIF</a> · <a href="{name}/native-sheet.png">전체 프레임 PNG 시트</a> · <a href="{name}/native-frames.json">프레임 시간</a> · <a href="{name}/settings.json">프롬프트·설정</a></p></article>')
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>견마 로봇 · idle / 사격</title><style>:root{--matte:#142436}body{background:#1b2230;color:#eee;font:16px/1.65 system-ui;margin:24px}main{display:flex;gap:20px;flex-wrap:wrap}article{width:512px;max-width:100%}img{width:100%;background:var(--matte)}a{color:#c9c0ff}button{padding:8px 14px;margin-right:8px}</style><h1>견마 로봇 · 기계식 대기와 점사</h1><p>원화의 흰 테두리와 붉은 장식 잔상을 입력용 사본에서 제거한 뒤 MiniMax 영상으로 생성했습니다. 실제 센서의 붉은 빛은 유지했습니다. 두 동작 모두 768px·24FPS·40스텝입니다.</p><p>공격은 단발 지시와 달리 짧은 점사로 생성됐습니다. 판금·관절·포신·문자 표시는 일부 변합니다. 원본 이미지는 그대로 보관했습니다. PNG/WebP는 반투명 경계를 유지하며 GIF는 이진 투명도만 지원합니다.</p><button onclick="document.documentElement.style.setProperty('--matte','#142436')">어둡게</button><button onclick="document.documentElement.style.setProperty('--matte','#fff4dc')">밝게</button><button onclick="document.documentElement.style.setProperty('--matte','#226b54')">초록</button><p><a href="quadruped-robot-handoff.zip">GIF·전체 PNG 시트·원본 영상 ZIP</a></p><main>'''+''.join(cards)+'''</main><p><a href="reference.png">정리한 입력</a> · <a href="reference-edit-prompt.txt">입력 편집 프롬프트</a> · <a href="idle/matte-review.jpg">idle 배경 비교</a> · <a href="attack/matte-review.jpg">공격 배경 비교</a></p></html>'''
    (OUT/'preview.html').write_text(page,encoding='utf-8')


def check():
    assert exporter.digest(SOURCE)==exporter.digest(OUT/'source-original.png');records={}
    for name in ACTIONS:
        folder=OUT/name;meta=json.loads((folder/'frames.json').read_text(encoding='utf-8'))
        graph=json.loads((folder/'native-v1-workflow.json').read_text(encoding='utf-8'));assert graph['10']['inputs']['steps']==40
        native=json.loads((folder/'native-frames.json').read_text(encoding='utf-8'))
        sheet=Image.open(folder/'native-sheet.png').convert('RGBA');assert max(sheet.size)<=8192
        for n,i in enumerate(native['sourceIndices']):
            original=np.asarray(Image.open(folder/'all-frames'/f'frame-{i:03d}.png').convert('RGBA'))
            cell=np.asarray(sheet.crop((n%8*768,n//8*768,(n%8+1)*768,(n//8+1)*768)))
            assert np.array_equal(original,cell)
        with Image.open(folder/'game-animation.gif') as gif:
            assert gif.n_frames==len(meta['previewSourceIndices']);total=0
            for i in range(gif.n_frames):gif.seek(i);total+=gif.info['duration']
            assert abs(total-sum(meta['previewDurationMs']))<=10
        records[name]=dict(sourceFrames=meta['sourceFrames'],exportedFrames=native['frameCount'],durationMs=total,
            edgeContactFrames=[x['frame'] for x in meta['diagnostics'] if x['edgeContact']],
            review=json.loads((folder/'review.json').read_text(encoding='utf-8')) if (folder/'review.json').exists() else 'pending')
    save(OUT/'validation.json',dict(fileChecksPassed=True,actualSteps=40,sourceUnchanged=True,websiteUnchanged=True,userApproval='pending',cases=records))
    (OUT/'README.txt').write_text('Quadruped robot idle and roof-gun burst attack\n\nNative MiniMax 40 steps, 768px, 24FPS, original videos preserved.\nIdle closing duplicate is omitted. Attack GIF repeats for preview only.\nThe attack generated several shots despite a single-shot prompt. It is delivered as a short burst.\nUse native-sheet.png (8 columns, 768px cells) and native-frames.json for all displayed native frames.\nIndividual PNGs: frames/*.png in each action folder.\nSame drawing scale and common presentation crop for both motions.\nNo frame interpolation or reversed poses.\nInput white rim and decorative red swoosh removed with built-in image edit, prompt included.\nThin barrel, mechanical joints and decals can change across generated frames; see review.json.\n',encoding='utf-8')
    with zipfile.ZipFile(OUT/'quadruped-robot-handoff.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ['source-original.png','source.json','reference.png','reference-edited.png','reference-edit-prompt.txt','preview.html','validation.json','README.txt','game-registration.json']:z.write(OUT/name,name)
        for action in ACTIONS:
            folder=OUT/action;native=json.loads((folder/'native-frames.json').read_text(encoding='utf-8'))
            for name in ['game-animation.gif','game-animation.webp','native-sheet.png','native-frames.json','settings.json','raw.mp4','reference-prepared.png','review-raw.webp','matte-review.jpg','review.json','shot-diagnostics.json','edge-smoke-cleanup.json']:
                if (folder/name).exists():z.write(folder/name,action+'/'+name)
            for index in native['sourceIndices']:
                p=folder/'all-frames'/f'frame-{index:03d}.png';z.write(p,action+'/frames/'+p.name)
    with zipfile.ZipFile(OUT/'quadruped-robot-handoff.zip') as z:assert z.testzip() is None
    build();print('ROBOT_HANDOFF_VALIDATED',records,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['generate','export','idle-export','build','check','all']);stage=parser.parse_args().stage
    if stage=='all':generate();export();check()
    elif stage=='idle-export':export('idle')
    else:globals()[stage]()
