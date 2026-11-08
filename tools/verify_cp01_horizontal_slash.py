"""One new right-facing horizontal knife cut; retain accepted idle/thrust assets."""
import argparse
import html
import json
import math
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import av
import numpy as np
from PIL import Image, ImageDraw
import sprite_gif
from tools import verify_cp01_motion as cp
from tools.repair_cp01_matte import repair

OUT = ROOT / 'outputs/cp01-horizontal-slash-20261023'
ACCEPTED = ROOT / 'outputs/cp01-dagger-matte-v2-20261023'
ORIGINAL_CUT = cp.cut_with_crimson
ACTION = dict(title='단검 횡베기 · 오른쪽', seed=2026102333, padding=20,
    loop=False, strength='normal', frames=24,
    prompt=(
        'Perform exactly ONE quick HORIZONTAL DAGGER SLASH toward the space at SCREEN RIGHT. '
        'This is a sideways cutting SWEEP, with the cutting edge leading, rather than a point-first '
        'straight thrust. At first bend the knife elbow and draw the knife hand inward and backward '
        'toward the far shoulder at chest height, winding the shoulders and hips a little. '
        'Then sharply uncoil the shoulders and hips together and SWEEP the knife arm outward '
        'in ONE broad shallow HORIZONTAL ARC across the FRONT of the torso, ending toward screen RIGHT '
        'at about rib-to-chest height. The hand travels sideways along a curved path, the wrist turns '
        'with that cutting arc, and the elbow stays slightly bent. Do not poke the knife straight '
        'forward or pump the arm like a jab. The blade stays a SHORT dark triangular dagger of '
        'constant length, held tightly in the original gloved hand. '
        'Show a compact but decisive shoulder-and-waist rotation, a firm planted front boot and a '
        'small weight transfer. Head and gaze remain to screen RIGHT throughout; do not turn the '
        'face to the viewer. The empty hand counterbalances close to the ribs, keeping clear of the '
        'blade. A narrow crimson crescent briefly traces ONLY the actual lateral blade path, '
        'with the effect confined close to the hand and blade; it quickly fades. '
        'After the sweep hold the follow-through briefly, then return to the original right-facing '
        'ready stance. Timing: brief windup in the first half second, fast cut in the next half '
        'second, then follow-through and recovery. Both boots stay near their original coordinates. '
        'No vertical chop, downward stab, second attack, full spin, running, jumping, bowing '
        'at the waist, giant sword, extra knife, target, large waves or camera motion. '
        'Retain hand-drawn lineart, sharply painted 2D cel shadows and the original facial design.'))


def configure():
    cp.OUT = OUT
    cp.ACTIONS = {'attack': ACTION}
    cp.build = build
    cp.cut_with_crimson = lambda image: repair(ORIGINAL_CUT(image))[0]


def build():
    OUT.mkdir(exist_ok=True)
    cards = []
    for name, title, folder in [('idle','대기 · 기존', 'accepted-idle'),
                              ('thrust','찌르기 · 기존', 'accepted-thrust'),
                              ('slash','횡베기 · 새 시험', 'attack')]:
        target = OUT / folder
        if not (target/'game-animation.webp').exists(): continue
        review_path=target/'review.json'
        note=json.loads(review_path.read_text(encoding='utf-8')).get('note','') if review_path.exists() else ''
        cards.append(f'<article><h2>{title}</h2><p>{html.escape(note)}</p><img class="motion" src="{folder}/game-animation.webp" alt="{title}">'
            f'<p><a href="{folder}/game-animation.gif">GIF</a> · '
            f'<a href="{folder}/game-sheet.png">투명 PNG 시트</a> · '
            f'<a href="{folder}/game-frames.json">프레임 시간</a></p></article>')
    page = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>단검 횡베기 시험</title><style>:root{--matte:#142436}body{background:#1b2230;color:#eee;font:16px/1.65 system-ui;margin:24px}main{display:flex;gap:20px;flex-wrap:wrap}article{width:420px;max-width:100%}.motion{width:100%;background:var(--matte)}a{color:#c9c0ff}button{padding:8px 14px;margin-right:8px}</style><h1>대기 · 찌르기 · 횡베기</h1><p>기존 대기와 찌르기에 같은 원화로 횡베기를 추가했습니다. 세 동작은 같은 캔버스 비율과 확대 영역으로 표시합니다. 새 동작에도 회색 잔여물 정리와 윤곽 배경색 보정을 적용했습니다.</p><p>새 횡베기는 팔을 앞에서 뒤로 쓸며 붉은 궤적이 따라오는 1.63초 단발 동작입니다. 팔을 뒤로 뺀 자세에서 끝나며 원래 자세로 복귀하지 않습니다. GIF 반복은 미리보기용입니다. PNG/WebP는 반투명 경계를 유지합니다.</p><button onclick="document.documentElement.style.setProperty('--matte','#142436')">어둡게</button><button onclick="document.documentElement.style.setProperty('--matte','#fff4dc')">밝게</button><button onclick="document.documentElement.style.setProperty('--matte','#226b54')">초록</button><p><a href="cp01-horizontal-slash.zip">횡베기 GIF·PNG 시트·원본 영상 ZIP</a></p><main>'''+''.join(cards)+'''</main><p><a href="attack/raw.mp4">새 생성 원본 영상</a> · <a href="attack/review-raw.webp">원본 프레임 비교</a> · <a href="attack/matte-review.jpg">밝은·어두운 배경 비교</a> · <a href="attack/settings.json">프롬프트·설정</a></p></html>'''
    (OUT/'preview.html').write_text(page, encoding='utf-8')


def previous():
    for source, dest in [('idle','accepted-idle'), ('attack','accepted-thrust')]:
        target = OUT/dest
        target.mkdir(parents=True, exist_ok=True)
        for f in ['game-animation.gif','game-animation.webp','game-sheet.png','game-frames.json']:
            if not (target/f).exists(): shutil.copy2(ACCEPTED/source/f,target/f)


def raw_review():
    folder = OUT/'attack'
    with av.open(str(folder/'raw.mp4')) as v: frames=[f.to_image().convert('RGB') for f in v.decode(video=0)]
    indices = np.linspace(0,len(frames)-1,15).round().astype(int)
    canvas = Image.new('RGB',(1600,960))
    draw = ImageDraw.Draw(canvas)
    for n,i in enumerate(indices):
        canvas.paste(frames[i].resize((320,320)),(n%5*320,n//5*320))
        draw.text((n%5*320+8,n//5*320+8),str(i),fill='red')
    canvas.save(folder/'review-raw.webp',quality=95)


def export():
    configure()
    cp.export()
    raw_review()
    matte_review()
    align_previews()
    build()


def matte_review():
    folder=OUT/'attack'
    canvas=Image.new('RGB',(1536,1024))
    draw=ImageDraw.Draw(canvas)
    for col,index in enumerate([12,19,32]):
        im=Image.open(folder/'all-frames'/f'frame-{index:03d}.png').convert('RGBA')
        for row,color in enumerate(['#142436','#ffefd6']):
            bg=Image.new('RGBA',im.size,color)
            bg.alpha_composite(im)
            canvas.paste(bg.resize((512,512)).convert('RGB'),(col*512,row*512))
            draw.text((col*512+8,row*512+8),str(index),fill='red')
    canvas.save(folder/'matte-review.jpg',quality=96)


def align_previews():
    cases=[(ACCEPTED/'idle',OUT/'accepted-idle'),(ACCEPTED/'attack',OUT/'accepted-thrust'),(OUT/'attack',OUT/'attack')]
    boxes=[json.loads((dest/'game-frames.json').read_text(encoding='utf-8'))['commonPresentationCrop'] for _,dest in cases]
    l,t,r,b=min(x[0] for x in boxes),min(x[1] for x in boxes),max(x[2] for x in boxes),max(x[3] for x in boxes)
    side=max(r-l,b-t)
    x,y=math.floor((l+r-side)/2),math.floor((t+b-side)/2)
    crop=[x,y,x+side,y+side]
    for source,dest in cases:
        meta=json.loads((source/'frames.json').read_text(encoding='utf-8'))
        images=[Image.open(source/'all-frames'/f'frame-{i:03d}.png').convert('RGBA').crop(crop).resize((512,512),Image.Resampling.LANCZOS)
                for i in meta['previewSourceIndices']]
        times=meta['previewDurationMs']
        images[0].save(dest/'game-animation.webp',save_all=True,append_images=images[1:],duration=times,loop=0,lossless=True)
        data,gif=sprite_gif.encode(images,times)
        (dest/'game-animation.gif').write_bytes(data)
        game=json.loads((dest/'game-frames.json').read_text(encoding='utf-8'))
        game.update(commonPresentationCrop=crop,gif=gif)
        (dest/'game-frames.json').write_text(json.dumps(game,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'comparison-crop.json').write_text(json.dumps(dict(commonPresentationCrop=crop,frameScale=1)),encoding='utf-8')


def check():
    configure()
    cp.check()
    # Do not inherit the earlier thrust's artistic review for this new action.
    validation=json.loads((OUT/'validation.json').read_text(encoding='utf-8'))
    validation['visualReview'] = {'attack':'Front-to-back horizontal sweep with crimson crescent. Ends with arm behind body; no recovery. Three frames inspected on light/dark backgrounds; no edge contact. User approval pending.'}
    (OUT/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'README.txt').write_text('CP01 horizontal dagger slash\n\nNew reference-conditioned MiniMax video; same original image.\n'
        '768x768, 24FPS, 20 steps. Known-neutral-matte contour repair applied.\n'
        'Game assets: attack/game-sheet.png, game-frames.json, game-selected/*.png.\n'
        'GIF/WebP previews repeat the one-shot attack. PNG/WebP preserve soft alpha.\n'
        'Accepted idle and thrust previews are included for comparison.\n'
        'Slash is raw frames 0-38, 1.63 seconds. Ends with arm behind body; no generated recovery.\n'
        'See validation.json and attack/review.json for artistic limitations.\n',encoding='utf-8')
    files=['source-original.png','source.json','README.txt','validation.json','preview.html']
    with zipfile.ZipFile(OUT/'cp01-horizontal-slash.zip','w',zipfile.ZIP_DEFLATED) as z:
        for f in files:z.write(OUT/f,f)
        for folder in ['accepted-idle','accepted-thrust']:
            for p in (OUT/folder).iterdir():
                if p.is_file():z.write(p,folder+'/'+p.name)
        for f in ['game-animation.gif','game-animation.webp','game-sheet.png','game-frames.json','raw.mp4','settings.json','reference-prepared.png','review-raw.webp','matte-review.jpg']:
            z.write(OUT/'attack'/f,'attack/'+f)
        review=OUT/'attack/review.json'
        if review.exists(): z.write(review,'attack/review.json')
        for p in (OUT/'attack/game-selected').glob('*.png'):z.write(p,'attack/game-selected/'+p.name)
    with zipfile.ZipFile(OUT/'cp01-horizontal-slash.zip') as z:assert z.testzip() is None
    print('SLASH_EXPORT_VALIDATED',OUT,flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['all','generate','export','build','check','align_previews'])
    args=parser.parse_args()
    configure()
    if args.stage=='all':
        previous(); cp.generate(); raw_review(); export(); check()
    elif args.stage=='generate':
        previous(); cp.generate(); raw_review()
    else:globals()[args.stage]()
