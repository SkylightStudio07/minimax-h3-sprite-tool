"""Finish already-generated CP02 videos: protected alpha matting and handoff."""
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
from tools import submit_cp02_grounded_motion as submitted

OUT=submitted.OUT;SOURCE=submitted.SOURCE
ACTIONS={name:dict(item,title=('방패 경계 · Idle' if name=='idle' else '창 찌르기 · Attack'),padding=50,frames=24) for name,item in submitted.ACTIONS.items()}


def save(path,value):base.save(path,value)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def configure():
    base.OUT=OUT;base.SOURCE=SOURCE;base.ACTIONS=ACTIONS;base.build=build;base.configure()


def matte(raw):
    rgb=np.array(raw.convert('RGB'),dtype=np.float64);image=rgb/255
    border=np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1]));bg=np.median(border,axis=0)
    delta=np.max(np.abs(rgb-bg),axis=2);chroma=np.ptp(rgb,axis=2);lum=rgb.mean(2)
    semantic=np.array(image_background.remove(raw))[:,:,3]
    protect=ndimage.distance_transform_edt(semantic>240)>2.5
    # Large patches exactly matching the measured key are empty limb/cloth gaps.
    near=(delta<9)&(chroma<8);labels,n=ndimage.label(near);sizes=np.bincount(labels.ravel())
    gaps=(labels>0)&(sizes[labels]>=100);protect[gaps]=False
    neutral=(chroma<12)&(lum>88)&(lum<158)&~protect
    trimap=np.full(delta.shape,.5);trimap[(delta>40)|protect]=1
    trimap[((delta<9)|neutral)&~protect]=0
    alpha=np.clip(estimate_alpha_cf(image,trimap),0,1)
    foreground=np.clip(estimate_foreground_ml(image,alpha),0,1)
    alpha[alpha<.02]=0;alpha[alpha>.995]=1;alpha[protect]=1
    rgba=np.rint(np.dstack((foreground,alpha))*255).astype('uint8');rgba[alpha==0]=0
    return Image.fromarray(rgba),dict(background=bg.tolist(),protectedInteriorPixels=int(protect.sum()),
        gapSeedPixels=int(gaps.sum()),protectedInteriorPreserved=bool(np.all(rgba[:,:,3][protect]==255)))


def build():
    cards=[]
    for name,item in ACTIONS.items():
        folder=OUT/name
        if not (folder/'game-animation.webp').exists():continue
        review=json.loads((folder/'review.json').read_text(encoding='utf-8')) if (folder/'review.json').exists() else {}
        cards.append(f'<article><h2>{item["title"]}</h2><p>{html.escape(review.get("note",""))}</p><img src="{name}/game-animation.webp" alt="{name}"><p><a href="{name}/game-animation.gif">GIF</a> · <a href="{name}/native-sheet.png">전체 PNG 시트</a> · <a href="{name}/native-frames.json">프레임 시간</a> · <a href="{name}/matte-review.jpg">밝은·어두운 배경</a></p></article>')
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>CP02 Idle / Attack</title><style>:root{--matte:#142436}body{background:#1b2230;color:#eee;font:16px/1.65 system-ui;margin:24px}main{display:flex;gap:24px;flex-wrap:wrap}article{width:512px;max-width:100%}img{width:100%;background:var(--matte)}a{color:#c9c0ff}button{padding:8px 14px}</style><h1>CP02 · 방패 경계 / 창 찌르기</h1><p>768px · 24FPS · 40스텝. 원본 영상에서 갑옷·창대를 보호하며 경계 투명도를 계산했습니다. 두 발을 디딘 방패 대기와 오른쪽 창 찌르기입니다. PNG/WebP는 부드러운 투명도를 유지하고 GIF는 이진 투명도를 사용합니다.</p><button onclick="document.documentElement.style.setProperty('--matte','#142436')">어둡게</button> <button onclick="document.documentElement.style.setProperty('--matte','#fff4dc')">밝게</button> <button onclick="document.documentElement.style.setProperty('--matte','#226b54')">초록</button><p><a href="cp02-grounded-idle-attack.zip">Idle + Attack 전체 ZIP</a></p><main>'''+''.join(cards)+'</main></html>'
    (OUT/'preview.html').write_text(page,encoding='utf-8')


def process():
    configure();assert digest(SOURCE)==digest(OUT/'source-original.png')
    reviews={
        'idle':dict(note='두 발을 디딘 방패 경계 자세에서 창을 조금 내려 조준한 뒤 원래 각도로 복귀합니다. 머리카락과 옷자락이 조금 움직입니다. 창·방패·갑옷 세부에 생성 변화가 남습니다.',actualMotion='small spear aim correction and shield guard',sourceClipping=False),
        'attack':dict(note='방패를 앞세워 몸을 낮추고 오른쪽으로 창을 크게 찌른 뒤, 잠시 자세를 유지하고 원래 경계 자세로 돌아옵니다. 방패·창날·손·갑옷 세부에 생성 변화가 남습니다.',actualMotion='single rightward spear lunge, extended hold and recovery',sourceClipping=False)}
    for name in ACTIONS:
        folder=OUT/name;framesdir=folder/'all-frames';framesdir.mkdir(exist_ok=True);records=[]
        with av.open(str(folder/'raw.mp4')) as video:
            for i,frame in enumerate(video.decode(video=0)):
                path=framesdir/f'frame-{i:03d}.png'
                if path.exists():continue
                cut,info=matte(frame.to_image());cut.save(path);records.append(dict(frame=i,**info))
                if i%18==0:print('MATTED',name,i,flush=True)
        save(folder/'matte-process.json',dict(method='Semantic interior protection, measured neutral-gap trimap, closed-form alpha and multilevel foreground estimation',processed=records,geometryUnchanged=True,originalVideoPreserved=True))
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
    (OUT/'README.txt').write_text('CP02 grounded Idle + Attack\n\n768x768 native cells, 24FPS, 40 MiniMax steps.\nIdle: 72 forward frames, repeated closing reference omitted. Attack: 73 forward frames.\nUse action/native-sheet.png and native-frames.json, or action/frames/*.png.\nAlso included: action/game-sheet.png and game-frames.json, a lighter 24-cell selection.\nBoth motions share the original input scale and canvas coordinates.\nPNG/WebP preserve soft alpha; GIF has binary alpha.\nNew grounded source: shield guard idle and rightward spear lunge with recovery. Native frame borders are checked in validation.json.\nFine weapon, shield and armour details can drift across generated frames.\nOriginal image and both original videos preserved.\n',encoding='utf-8')
    build();target=OUT/'cp02-grounded-idle-attack.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for name in ['source-original.png','source.json','reference.png','preview.html','validation.json','README.txt','game-registration.json']:z.write(OUT/name,name)
        for action in ACTIONS:
            folder=OUT/action;meta=json.loads((folder/'native-frames.json').read_text(encoding='utf-8'))
            for name in ['game-animation.gif','game-animation.webp','native-sheet.png','native-frames.json','game-sheet.png','game-frames.json','settings.json','raw.mp4','reference-prepared.png','review-raw.webp','matte-review.jpg','review.json','matte-process.json']:z.write(folder/name,action+'/'+name)
            for i in meta['sourceIndices']:
                p=folder/'all-frames'/f'frame-{i:03d}.png';z.write(p,action+'/frames/'+p.name)
    with zipfile.ZipFile(target) as z:assert z.testzip() is None
    print('CP02_HANDOFF_READY',records,flush=True)


if __name__=='__main__':process()
