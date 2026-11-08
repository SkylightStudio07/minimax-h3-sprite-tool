"""New VFX-free ready-stance idle; source reference edited before I2V."""
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
from tools import verify_pixel_minimax as executor
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release
from tools.repair_cp01_matte import repair

OUT=ROOT/'outputs/cp01-ready-idle-20261023'
EDITED=Path('C:/Users/SKYLIGHT/.codex/generated_images/01a0943f-e4b7-7e11-af05-20d776c93f13/exec-faa643b1-6248-4f4f-874a-16416b33cacc.png')
ATTACK=ROOT/'outputs/cp01-clean-sweep-20261023'
ACTION=dict(title='준비 자세 대기 · 이펙트 없음',seed=2026102336,padding=30,loop=True,strength='normal',frames=20)
ORIGINAL_CUT=cp.cut_with_crimson
PROMPT=(
    'A living, relaxed combat-ready IDLE LOOP of the EXACT SAME hand-drawn 2D anime character '
    'in the supplied ready stance, facing SCREEN RIGHT. Short white bob with crimson hair accent, '
    'same red eye and face, white collared blouse, thin black tie, grey flared trousers, red gloves '
    'and black platform boots. Keep ONE short black triangular ring-pommel dagger in the same hand '
    'in front of the waist, elbow comfortably bent, blade angled diagonally up-right. The empty '
    'hand stays loosely raised in front of the chest. Preserve the original ink lines, flat '
    'cel-painted shading, body proportions, constant cloth volume and original colours. '
    'The whole body participates in one gentle even idle cycle: soften the knees a little, '
    'shift the pelvis a small distance from the rear supporting leg toward the front and back, '
    'and let the head and shoulders rise and fall together with natural shallow breathing. '
    'The forearms and knife move gently with the shoulder rhythm, not frozen separately in space. '
    'The bob hair tips and loose black tie follow with a small delay. Keep the chest and abdomen '
    'the same volume; breathing is coherent movement of the torso, not inflating the breasts '
    'or rubber cloth deformation. Small movement but visibly alive at game-sprite size. '
    'Both boots stay planted with the soles stable and no sliding; knees can flex softly. '
    'Continuous calm motion from the first frame through the last, without pausing to pose. '
    'Return naturally to the identical starting ready stance and motion phase. Nose and gaze '
    'stay to the right; no camera turn, speaking, arm extension, weapon attack, step, walk or crouch. '
    'Absolutely NO red effect ribbons, particles, blood marks, floor circle, aura, glow or slash '
    'trails. The only red objects are the original gloves and hair accent. Empty space beneath '
    'the boots remains featureless grey. Fixed camera and drawing scale, no zoom or pan. '
    'Entire character, hair curl, boots and knife stay inside the canvas. Uniform flat neutral '
    'medium grey field in all exposed gaps; no scenery, floor, cast shadow or text. '
    'Every frame remains a 2D ink-and-cel illustration without 3D rendering or relighting.')


def configure():
    cp.OUT=OUT;cp.ACTIONS={'idle':ACTION};cp.build=build
    cp.cut_with_crimson=lambda im:repair(ORIGINAL_CUT(im))[0]


def generate():
    configure();folder=OUT/'idle';folder.mkdir(parents=True,exist_ok=True)
    if not (OUT/'source-original.png').exists():shutil.copy2(cp.SOURCE,OUT/'source-original.png')
    assert cp.digest(cp.SOURCE)==cp.digest(OUT/'source-original.png')
    if not (OUT/'reference.png').exists():shutil.copy2(EDITED,OUT/'reference.png')
    cp.save(OUT/'source.json',dict(sourcePath=str(cp.SOURCE),sha256=cp.digest(cp.SOURCE),
        sourceUnchanged=True,referenceSha256=cp.digest(OUT/'reference.png'),published=False,motionPadding=30,
        preparation='Built-in image edit: VFX-free compact dagger-ready stance from the previously cleaned reference. Not pixel-identical to original.'))
    if (folder/'raw.mp4').exists():return
    if (folder/'native-v1-pending.json').exists():graph=json.loads((folder/'native-v1-workflow.json').read_text(encoding='utf-8'))
    else:
        ensure_idle();engine.start_comfy();release((8190,8191))
        prepared=engine.prepare_reference_image((OUT/'reference.png').read_bytes(),768,768,30)
        (folder/'reference-prepared.png').write_bytes(prepared)
        uploaded=engine.upload_image(prepared,'cp01-ready-idle.png')
        graph=engine.build_workflow(uploaded,PROMPT,3,768,768,ACTION['seed'],animation_type='idle',
            loop=True,facing='preserve',flat_background=True,blink_mode='none',motion_strength='normal',
            sampling_mode='quality',workflow_id='standard')
        graph['15']['inputs'].pop('audio',None);graph.pop('14',None);graph.pop('5',None)
        graph['16']['inputs']['filename_prefix']='cp01_ready_idle_20261023/idle'
        cp.save(folder/'settings.json',dict(animationType='idle',seed=ACTION['seed'],width=768,height=768,
            duration=3,fps=24,steps=20,loop=True,facing='preserve',motionPadding=30,motionStrength='normal',
            referenceOffsetX=0,workflowId='standard',samplingMode='quality',prompt=PROMPT,
            actualPrompt=graph['6']['inputs']['prompt'],sourceSha256=cp.digest(cp.SOURCE),
            referenceSha256=cp.digest(OUT/'reference.png'),sourceVFXRemoved=True,published=False))
    executor.OUT=folder;history=executor.execute(graph,engine.COMFY_URL,'native-v1')
    shutil.copyfile(engine.find_saved_video(history),folder/'raw.mp4')
    ensure_idle();release((8189,));raw_review()
    print('READY_IDLE_VIDEO_SAVED',flush=True)


def raw_review():
    with av.open(str(OUT/'idle/raw.mp4')) as v:frames=[f.to_image().convert('RGB') for f in v.decode(video=0)]
    contact=Image.new('RGB',(1280,640));draw=ImageDraw.Draw(contact)
    for n,i in enumerate(np.linspace(0,len(frames)-1,8).round().astype(int)):
        contact.paste(frames[i].resize((320,320)),(n%4*320,n//4*320));draw.text((n%4*320+8,n//4*320+8),str(i),fill='red')
    contact.save(OUT/'idle/review-raw.webp',quality=95)


def export():
    configure();folder=OUT/'idle'
    if not (folder/'selection.json').exists():cp.save(folder/'selection.json',dict(start=0,end=71,note='Omit repeated closing reference frame, forward generated frames only.'))
    cp.export();raw_review();compare();matte_review();build()


def compare():
    folder=OUT/'idle';other=OUT/'attack';other.mkdir(exist_ok=True)
    for name in ['game-sheet.png','game-frames.json']:
        if not (other/name).exists():shutil.copy2(ATTACK/'attack'/name,other/name)
    cases=[(folder,folder),(ATTACK/'attack',other)]
    metas=[json.loads((s/'frames.json').read_text(encoding='utf-8')) for s,_ in cases]
    sets=[[Image.open(s/'all-frames'/f'frame-{i:03d}.png').convert('RGBA') for i in m['previewSourceIndices']] for (s,_),m in zip(cases,metas)]
    boxes=[im.getchannel('A').getbbox() for frames in sets for im in frames]
    l,t,r,b=min(q[0] for q in boxes),min(q[1] for q in boxes),max(q[2] for q in boxes),max(q[3] for q in boxes)
    size=math.ceil(max(r-l,b-t)*1.08);x,y=math.floor((l+r-size)/2),math.floor((t+b-size)/2);crop=[x,y,x+size,y+size]
    for (_,dest),meta,frames in zip(cases,metas,sets):
        previews=[im.crop(crop).resize((512,512),Image.Resampling.LANCZOS) for im in frames]
        times=meta['previewDurationMs']
        previews[0].save(dest/'game-animation.webp',save_all=True,append_images=previews[1:],duration=times,loop=0,lossless=True)
        data,gif=sprite_gif.encode(previews,times);(dest/'game-animation.gif').write_bytes(data)
        game=json.loads((dest/'game-frames.json').read_text(encoding='utf-8'));game.update(commonPresentationCrop=crop,gif=gif)
        cp.save(dest/'game-frames.json',game)
    cp.save(OUT/'comparison.json',dict(commonCrop=crop,sharedCanvas=[768,768],inputPadding=30,perFrameStabilisation=False))


def matte_review():
    canvas=Image.new('RGB',(1536,1024));draw=ImageDraw.Draw(canvas)
    for col,i in enumerate([0,24,48]):
        im=Image.open(OUT/'idle/all-frames'/f'frame-{i:03d}.png').convert('RGBA')
        for row,color in enumerate(['#142436','#fff4dc']):
            bg=Image.new('RGBA',im.size,color);bg.alpha_composite(im)
            canvas.paste(bg.resize((512,512)).convert('RGB'),(col*512,row*512));draw.text((col*512+8,row*512+8),str(i),fill='red')
    canvas.save(OUT/'idle/matte-review.jpg',quality=96)


def build():
    OUT.mkdir(exist_ok=True);cards=[]
    for name,title in [('idle','새 대기 · 단검 준비 자세'),('attack','최근 횡베기 · 비교용')]:
        if not (OUT/name/'game-animation.webp').exists():continue
        note=''
        review=OUT/name/'review.json'
        if review.exists():note=json.loads(review.read_text(encoding='utf-8')).get('note','')
        cards.append(f'<article><h2>{title}</h2><p>{html.escape(note)}</p><img src="{name}/game-animation.webp" alt="{title}"><p><a href="{name}/game-animation.gif">GIF</a> · <a href="{name}/game-sheet.png">투명 PNG 시트</a> · <a href="{name}/game-frames.json">프레임 시간</a></p></article>')
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>새 준비 자세 idle</title><style>:root{--matte:#142436}body{background:#1b2230;color:#eee;font:16px/1.65 system-ui;margin:24px}main{display:flex;gap:20px;flex-wrap:wrap}article{width:512px;max-width:100%}img{width:100%;background:var(--matte)}a{color:#c9c0ff}button{padding:8px 14px;margin-right:8px}</style><h1>단검 준비 자세 · 새 idle</h1><p>원화에서 이펙트를 빼고 팔을 몸 가까이 든 준비 자세로 편집한 뒤 대기 영상을 새로 생성했습니다. 기존 공격은 비교용입니다. 두 동작은 같은 캔버스 크기와 확대 영역으로 표시합니다.</p><button onclick="document.documentElement.style.setProperty('--matte','#142436')">어둡게</button><button onclick="document.documentElement.style.setProperty('--matte','#fff4dc')">밝게</button><button onclick="document.documentElement.style.setProperty('--matte','#226b54')">초록</button><p><a href="cp01-ready-idle.zip">새 대기 GIF·PNG 시트·원본 영상 ZIP</a></p><main>'''+''.join(cards)+'''</main><p><a href="reference.png">편집한 입력 자세</a> · <a href="reference-edit-prompt.txt">자세 편집 프롬프트</a> · <a href="idle/settings.json">영상 프롬프트·설정</a> · <a href="idle/matte-review.jpg">밝은·어두운 배경 비교</a> · <a href="idle/raw.mp4">새 원본 영상</a></p></html>'''
    (OUT/'preview.html').write_text(page,encoding='utf-8')


def check():
    configure();cp.check()
    p=OUT/'validation.json';validation=json.loads(p.read_text(encoding='utf-8'))
    validation['visualReview']={'idle':json.loads((OUT/'idle/review.json').read_text(encoding='utf-8')) if (OUT/'idle/review.json').exists() else 'pending visual review'}
    meta=json.loads((OUT/'idle/frames.json').read_text(encoding='utf-8'))
    frames=[np.asarray(Image.open(OUT/'idle/all-frames'/f'frame-{i:03d}.png').convert('RGBA')) for i in meta['previewSourceIndices']]
    floor_red=[]
    motion=[]
    for a in frames:
        r,g,b=a[:,:,:3].astype(float).transpose(2,0,1)
        floor_red.append(int(((r-g>35)&(r-b>20)&(r>75)&(a[:,:,3]>64))[600:].sum()))
    small=[np.asarray(Image.fromarray(a).resize((192,192),Image.Resampling.BILINEAR)).astype(float)/255 for a in frames]
    premult=[np.concatenate((a[:,:,:3]*a[:,:,3:],a[:,:,3:]),axis=2) for a in small]
    for a,b in zip(premult,premult[1:]):motion.append(float(np.abs(b-a).mean()))
    seam=float(np.abs(premult[-1]-premult[0]).mean())
    validation['motionDiagnostics']=dict(displayedFrames=len(frames),maxFloorRedPixels=max(floor_red),
        meanAdjacentDifference=float(np.mean(motion)),loopBoundaryDifference=seam,
        loopBoundaryToMedianStep=seam/max(float(np.median(motion)),1e-8),
        note='Premultiplied RGBA difference at 192px; diagnostic only, not an artistic smoothness guarantee.')
    assert max(floor_red)==0, 'Unexpected crimson ground artefact'
    assert not any(x['edgeContact'] for x in meta['diagnostics']), 'Visible pixels touch frame boundary'
    cp.save(p,validation)
    (OUT/'README.txt').write_text('CP01 new ready-stance idle\n\nOriginal user artwork preserved.\nReference edited with built-in image generation: effects removed, dagger arm bent into guard.\nMiniMax native 20-step 768px 24FPS 3-second loop; last duplicate reference frame omitted.\nSemantic background extraction plus known-neutral-matte edge repair.\nGame files: idle/game-sheet.png, game-frames.json, game-selected/*.png.\nGIF has binary alpha; PNG/WebP retain soft alpha.\nattack/ contains earlier attack previews for comparison only.\nSee idle/review.json for observed motion limits.\n',encoding='utf-8')
    with zipfile.ZipFile(OUT/'cp01-ready-idle.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ['source-original.png','source.json','reference.png','reference-edit-prompt.txt','preview.html','validation.json','comparison.json','README.txt']:
            z.write(OUT/name,name)
        for name in ['game-animation.gif','game-animation.webp','game-sheet.png','game-frames.json','settings.json','raw.mp4','review-raw.webp','matte-review.jpg','reference-prepared.png','review.json']:
            path=OUT/'idle'/name
            if path.exists():z.write(path,'idle/'+name)
        for path in (OUT/'idle/game-selected').glob('*.png'):z.write(path,'idle/game-selected/'+path.name)
        for path in (OUT/'attack').iterdir():
            if path.is_file():z.write(path,'attack/'+path.name)
    with zipfile.ZipFile(OUT/'cp01-ready-idle.zip') as z:assert z.testzip() is None
    print('READY_IDLE_VALIDATED',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['generate','export','build','check','all'])
    stage=parser.parse_args().stage
    if stage=='all':generate();export();check()
    else:globals()[stage]()
