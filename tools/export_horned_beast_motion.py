"""Finish horned beast videos: protected fur matting, cast-shadow cleanup and handoff."""
import hashlib
import html
import json
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import av
import numpy as np
from PIL import Image
from scipy import ndimage
from pymatting import estimate_alpha_cf,estimate_foreground_ml
import image_background
from tools import verify_masked_rifleman_motion as base
from tools import submit_horned_beast_motion as submitted

OUT=submitted.OUT;SOURCE=submitted.SOURCE
ACTIONS={name:dict(item,title=('경계 대기 · Idle' if name=='idle' else '돌진 공격 · Attack'),padding=40,frames=24) for name,item in submitted.ACTIONS.items()}


def save(path,value):base.save(path,value)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def configure():
    base.OUT=OUT;base.SOURCE=SOURCE;base.ACTIONS=ACTIONS;base.build=build;base.configure()


def matte(raw,semantic=None):
    rgb=np.array(raw.convert('RGB'),dtype=np.float64);image=rgb/255
    border=np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1]));bg=np.median(border,axis=0)
    delta=np.max(np.abs(rgb-bg),axis=2);chroma=np.ptp(rgb,axis=2);lum=rgb.mean(2)
    if semantic is None:semantic=np.array(image_background.remove(raw))[:,:,3]
    protect=ndimage.distance_transform_edt(semantic>240)>2.5
    # Large patches exactly matching the measured key are empty limb/cloth gaps.
    near=(delta<9)&(chroma<8);labels,n=ndimage.label(near);sizes=np.bincount(labels.ravel())
    gaps=(labels>0)&(sizes[labels]>=100);protect[gaps]=False
    yy,xx=np.indices(lum.shape)
    # Coloured fur and ink form a connected body. Neutral cast shadow farther
    # than 2.5px from it, only in the lower paw band, is empty background.
    body_colour=(chroma>6)&(lum>25)&(lum<230)
    body_colour=ndimage.binary_fill_holes(ndimage.binary_closing(body_colour,iterations=1))
    fur_distance=ndimage.distance_transform_edt(~body_colour)
    shadow=(yy>raw.height*.70)&(chroma<np.maximum(12,lum*.12))&(lum<165)&(fur_distance>2)
    protect[shadow]=False
    neutral=(chroma<12)&(lum>88)&(lum<158)&~protect
    trimap=np.full(delta.shape,.5);trimap[(delta>40)|protect]=1
    trimap[((delta<9)|neutral|shadow)&~protect]=0
    alpha=np.clip(estimate_alpha_cf(image,trimap),0,1)
    foreground=np.clip(estimate_foreground_ml(image,alpha),0,1)
    alpha[alpha<.02]=0;alpha[alpha>.995]=1;alpha[protect]=1
    components,n=ndimage.label(alpha>.02,structure=np.ones((3,3)))
    counts=np.bincount(components.ravel());bottom_counts=np.bincount(components.ravel(),weights=(yy>raw.height*.70).ravel())
    tiny=(counts[components]<60)&(bottom_counts[components]==counts[components])&(components>0)
    alpha[tiny]=0
    rgba=np.rint(np.dstack((foreground,alpha))*255).astype('uint8');rgba[alpha==0]=0
    return Image.fromarray(rgba),dict(background=bg.tolist(),protectedInteriorPixels=int(protect.sum()),
        gapSeedPixels=int(gaps.sum()),protectedInteriorPreserved=bool(np.all(rgba[:,:,3][protect]==255)),shadowSeedPixels=int(shadow.sum()))


def build():
    cards=[]
    for name,item in ACTIONS.items():
        folder=OUT/name
        if not (folder/'game-animation.webp').exists():continue
        review=json.loads((folder/'review.json').read_text(encoding='utf-8')) if (folder/'review.json').exists() else {}
        cards.append(f'<article><h2>{item["title"]}</h2><p>{html.escape(review.get("note",""))}</p><img src="{name}/game-animation.webp" alt="{name}"><p><a href="{name}/game-animation.gif">GIF</a> · <a href="{name}/native-sheet.png">전체 PNG 시트</a> · <a href="{name}/native-frames.json">프레임 시간</a> · <a href="{name}/matte-review.jpg">밝은·어두운 배경</a></p></article>')
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>뿔짐승 Idle / Attack</title><style>:root{--matte:#142436}body{background:#1b2230;color:#eee;font:16px/1.65 system-ui;margin:24px}main{display:flex;gap:24px;flex-wrap:wrap}article{width:512px;max-width:100%}img{width:100%;background:var(--matte)}a{color:#c9c0ff}button{padding:8px 14px}</style><h1>뿔짐승 · 경계 대기 / 돌진 공격</h1><p>768px · 24FPS · 40스텝. 원본 영상에서 털·뿔·입마개를 보호하며 경계 투명도를 계산했습니다. 왼쪽 경계 대기와 짧은 돌진 공격입니다. 원본에 생성된 바닥 그림자도 발을 보호하며 정리했습니다. PNG/WebP는 부드러운 투명도를 유지하고 GIF는 이진 투명도를 사용합니다.</p><button onclick="document.documentElement.style.setProperty('--matte','#142436')">어둡게</button> <button onclick="document.documentElement.style.setProperty('--matte','#fff4dc')">밝게</button> <button onclick="document.documentElement.style.setProperty('--matte','#226b54')">초록</button><p><a href="horned-beast-idle-attack.zip">Idle + Attack 전체 ZIP</a></p><main>'''+''.join(cards)+'</main></html>'
    (OUT/'preview.html').write_text(page,encoding='utf-8')


def process():
    configure();assert digest(SOURCE)==digest(OUT/'source-original.png')
    reviews={
        'idle':dict(note='입마개를 쓴 머리를 조금 낮췄다가 복귀하며 털과 침방울이 움직입니다. 몸과 발 위치는 대체로 유지됩니다. 털·입마개·발의 세부에 생성 변화가 남습니다.',actualMotion='small head/snarl adjustment and subtle fur motion',sourceClipping=False),
        'attack':dict(note='왼쪽으로 몸을 낮춰 어깨와 앞발을 내밀고, 짧은 회복 동작으로 원래 경계 자세에 돌아옵니다. 몸통·입마개·발·털의 세부에 생성 변화가 남습니다. 발밑에 생성된 중성색 바닥 그림자를 정리했습니다.',actualMotion='short leftward shoulder lunge and forepaw landing, then recovery',sourceClipping=False)}
    for name in ACTIONS:
        folder=OUT/name;framesdir=folder/'all-frames';framesdir.mkdir(exist_ok=True);records=[]
        with av.open(str(folder/'raw.mp4')) as video:
            for i,frame in enumerate(video.decode(video=0)):
                path=framesdir/f'frame-{i:03d}.png'
                if path.exists():continue
                cut,info=matte(frame.to_image());cut.save(path);records.append(dict(frame=i,**info))
                if i%18==0:print('MATTED',name,i,flush=True)
        save(folder/'matte-process.json',dict(method='Semantic fur protection, neutral-gap and lower cast-shadow trimap, closed-form alpha and multilevel foreground estimation',processed=records,geometryUnchanged=True,originalVideoPreserved=True))
        save(folder/'review.json',dict(reviewed=True,accepted=None,userApproval='pending',**reviews[name]))
    if not (OUT/'idle/selection.json').exists():save(OUT/'idle/selection.json',dict(start=0,end=71,note='Closing duplicate anchor omitted. Forward frames only.'))
    base.export();package()


def package():
    configure();records={}
    for name in ACTIONS:
        folder=OUT/name;meta=json.loads((folder/'native-frames.json').read_text(encoding='utf-8'))
        graph=json.loads((folder/'native-v1-workflow.json').read_text(encoding='utf-8'));assert graph['10']['inputs']['steps']==40
        frame_meta=json.loads((folder/'frames.json').read_text(encoding='utf-8'))
        sheet=Image.open(folder/'native-sheet.png').convert('RGBA');assert max(sheet.size)<=8192
        for n,i in enumerate(meta['sourceIndices']):
            actual=np.array(Image.open(folder/'all-frames'/f'frame-{i:03d}.png').convert('RGBA'))
            cell=np.array(sheet.crop((n%8*768,n//8*768,(n%8+1)*768,(n//8+1)*768)))
            assert np.array_equal(actual,cell)
        with Image.open(folder/'game-animation.gif') as gif:
            assert gif.n_frames==meta['frameCount'];duration=0
            for i in range(gif.n_frames):gif.seek(i);duration+=gif.info['duration']
        assert abs(duration-sum(meta['durationMs']))<=10
        records[name]=dict(frameCount=meta['frameCount'],durationMs=duration,
            edgeContactFrames=[x['frame'] for x in frame_meta['diagnostics'] if x['edgeContact']],
            review=json.loads((folder/'review.json').read_text(encoding='utf-8')))
    save(OUT/'validation.json',dict(fileChecksPassed=True,sourceUnchanged=digest(SOURCE)==digest(OUT/'source-original.png'),
        nativeCanvas=[768,768],fps=24,steps=40,sourceClippingPreserved=True,cases=records,userApproval='pending'))
    (OUT/'README.txt').write_text('Horned beast Idle + Attack\n\n768x768 native cells, 24FPS, 40 MiniMax steps.\nIdle: 72 forward frames, repeated closing reference omitted. Attack: 73 forward frames.\nUse action/native-sheet.png and native-frames.json, or action/frames/*.png.\nAlso included: action/game-sheet.png and game-frames.json, a lighter 24-cell selection.\nBoth motions share the original input scale and canvas coordinates.\nPNG/WebP preserve soft alpha; GIF has binary alpha.\nLeft-facing restrained beast idle and shoulder lunge with recovery. Neutral ground shadow separated while preserving the paws. Native frame borders are checked in validation.json.\nFine muzzle, fur, harness, teeth and paw details can drift across generated frames.\nOriginal image and both original videos preserved.\n',encoding='utf-8')
    build();target=OUT/'horned-beast-idle-attack.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for name in ['source-original.png','source.json','reference.png','preview.html','validation.json','README.txt','game-registration.json']:z.write(OUT/name,name)
        for action in ACTIONS:
            folder=OUT/action;meta=json.loads((folder/'native-frames.json').read_text(encoding='utf-8'))
            for name in ['game-animation.gif','game-animation.webp','native-sheet.png','native-frames.json','game-sheet.png','game-frames.json','settings.json','raw.mp4','reference-prepared.png','review-raw.webp','matte-review.jpg','review.json','matte-process.json']:z.write(folder/name,action+'/'+name)
            for i in meta['sourceIndices']:
                p=folder/'all-frames'/f'frame-{i:03d}.png';z.write(p,action+'/frames/'+p.name)
    with zipfile.ZipFile(target) as z:assert z.testzip() is None
    print('BEAST_HANDOFF_READY',records,flush=True)


if __name__=='__main__':process()
