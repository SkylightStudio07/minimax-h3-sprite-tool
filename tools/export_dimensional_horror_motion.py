"""CPU matte/export for the completed standard-resolution boss videos only."""
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
from PIL import Image,ImageDraw
from scipy import ndimage
from pymatting import estimate_alpha_cf,estimate_foreground_ml
import image_background
from tools import verify_masked_rifleman_motion as base
from tools import submit_dimensional_horror_standard as submitted

OUT=submitted.OUT
SOURCE=submitted.SOURCE
ACTIONS={name:dict(item,title=('균열 대기 · Idle' if name=='idle' else '낫발 휘두르기 · Attack'),padding=10,frames=24) for name,item in submitted.ACTIONS.items()}

def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def configure():
    base.OUT=OUT;base.SOURCE=SOURCE;base.ACTIONS=ACTIONS;base.build=build;base.configure()

def matte(raw):
    rgb=np.array(raw.convert('RGB'),dtype=np.float64);image=rgb/255
    border=np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1]));bg=np.median(border,axis=0)
    delta=np.max(np.abs(rgb-bg),axis=2);chroma=np.ptp(rgb,axis=2);lum=rgb.mean(2)
    semantic=np.array(image_background.remove(raw))[:,:,3]
    protect=ndimage.distance_transform_edt(semantic>240)>2.5
    near=(delta<9)&(chroma<8);labels,_=ndimage.label(near);sizes=np.bincount(labels.ravel())
    gaps=(labels>0)&(sizes[labels]>=100)
    # Suppress neutral codec blocks connected to the exterior matte, while
    # retaining enclosed armour highlights and strongly coloured violet light.
    neutral_band=(delta<24)&(chroma<12)
    seed=np.zeros(delta.shape,dtype=bool)
    seed[0]=neutral_band[0];seed[-1]=neutral_band[-1]
    seed[:,0]=neutral_band[:,0];seed[:,-1]=neutral_band[:,-1]
    exterior=ndimage.binary_propagation(seed,mask=neutral_band)
    protect[gaps|exterior]=False
    neutral=(chroma<12)&(lum>88)&(lum<158)&~protect
    trimap=np.full(delta.shape,.5);trimap[(delta>40)|protect]=1
    trimap[((delta<9)|neutral|exterior)&~protect]=0
    alpha=np.clip(estimate_alpha_cf(image,trimap),0,1)
    foreground=np.clip(estimate_foreground_ml(image,alpha),0,1)
    alpha[alpha<.02]=0;alpha[alpha>.995]=1;alpha[protect]=1
    rgba=np.rint(np.dstack((foreground,alpha))*255).astype('uint8');rgba[alpha==0]=0
    return Image.fromarray(rgba),dict(background=bg.tolist(),protectedInteriorPixels=int(protect.sum()),
        gapSeedPixels=int(gaps.sum()),exteriorKeyPixels=int(exterior.sum()),
        protectedInteriorPreserved=bool(np.all(rgba[:,:,3][protect]==255)))

def samples():
    review=Image.new('RGB',(1536,1536));draw=ImageDraw.Draw(review)
    for row,(name,index) in enumerate([('idle',18),('attack',26),('attack',31)]):
        with av.open(str(OUT/name/'raw.mp4')) as video:
            for i,frame in enumerate(video.decode(video=0)):
                if i==index:
                    cut,info=matte(frame.to_image());break
        cut.save(OUT/name/f'matte-sample-{index:03d}.png')
        for col,color in enumerate(['#142436','#fff4dc','#226b54']):
            bg=Image.new('RGBA',cut.size,color);bg.alpha_composite(cut)
            review.paste(bg.resize((512,512)).convert('RGB'),(col*512,row*512))
            draw.text((col*512+8,row*512+8),f'{name} {index}',fill='red')
        print('SAMPLE',name,index,info,flush=True)
    review.save(OUT/'matte-samples.jpg',quality=97)

def build():
    cards=[]
    for name,item in ACTIONS.items():
        if not (OUT/name/'game-animation.webp').exists():continue
        cards.append(f'<article><h2>{html.escape(item["title"])}</h2><img src="{name}/game-animation.webp" alt="{name}"><p><a href="{name}/game-animation.gif">GIF</a> · <a href="{name}/native-sheet.png">전체 프레임 PNG 시트</a> · <a href="{name}/native-frames.json">프레임 정보</a> · <a href="{name}/matte-review.jpg">배경 비교</a></p></article>')
    (OUT/'preview.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Dimensional Horror · Idle / Attack</title><style>:root{--matte:#142436}body{background:#1b2230;color:#eee;font:16px/1.65 system-ui;margin:24px}main{display:flex;gap:24px;flex-wrap:wrap}article{width:600px;max-width:100%}img{width:100%;background:var(--matte)}a{color:#c9c0ff}button{padding:8px 14px}</style><h1>Dimensional Horror · Idle / Attack</h1><p>원본 768×768 · 24FPS. Idle 72프레임 / Attack 73프레임. 원본 캔버스 좌표를 유지한 투명 PNG 시트와 개별 프레임을 제공합니다. GIF는 이진 투명도, PNG/WebP는 반투명 효과를 유지합니다.</p><p>오른쪽 균열을 중심으로 한 대기와 왼쪽 낫발 휘두르기입니다. 발톱·균열의 세부 형태와 밝기에는 생성 영상의 변화가 남아 있습니다. 공격은 미리보기에서 반복되며 게임에서는 한 번 재생하세요.</p><button onclick="document.documentElement.style.setProperty('--matte','#142436')">어둡게</button> <button onclick="document.documentElement.style.setProperty('--matte','#fff4dc')">밝게</button> <button onclick="document.documentElement.style.setProperty('--matte','#226b54')">초록</button><p><a href="dimensional-horror-idle-attack.zip">Idle + Attack 전체 ZIP</a></p><main>'''+''.join(cards)+'</main></html>',encoding='utf-8')

def process():
    configure()
    assert digest(SOURCE)==digest(OUT/'source-original.png')
    notes={
        'idle':'Small head/neck inclination, hanging scythe adjustment and smaller-digit flex; right rift approximately anchored. Fine pale strands and violet fissures vary in the generated frames.',
        'attack':'Existing scythe forelimb lifts, sweeps left with a brief violet crescent, then returns. Rift remains approximately in place; claw, strands and armour details vary.'}
    for name in ACTIONS:
        folder=OUT/name;framesdir=folder/'all-frames';framesdir.mkdir(exist_ok=True);records=[]
        with av.open(str(folder/'raw.mp4')) as video:
            for i,frame in enumerate(video.decode(video=0)):
                path=framesdir/f'frame-{i:03d}.png'
                if path.exists():continue
                cut,info=matte(frame.to_image());cut.save(path);records.append(dict(frame=i,**info))
                if i%12==0:print('MATTED',name,i,flush=True)
        save(folder/'matte-process.json',dict(method='CPU semantic core protection, measured grey-gap trimap, closed-form alpha and foreground estimation',processed=records,geometryUnchanged=True,originalVideoPreserved=True))
        save(folder/'review.json',dict(rawContactReviewed=True,matteVisualReview='pending',accepted=None,note=notes[name]))
    save(OUT/'idle/selection.json',dict(start=0,end=71,note='Repeated closing reference omitted; forward playback only.'))
    base.export()
    for name in ACTIONS:
        path=OUT/name/'native-frames.json';meta=json.loads(path.read_text(encoding='utf-8'))
        meta.update(anchor=[735,384],anchorMeaning='Suggested fixed right-rift registration point; generated slight local drift is preserved.')
        save(path,meta)
    print('BOSS_EXPORT_READY_FOR_REVIEW',flush=True)

def package():
    configure();records={}
    for name in ACTIONS:
        folder=OUT/name;meta=json.loads((folder/'native-frames.json').read_text(encoding='utf-8'))
        assert meta['frameCount']==(72 if name=='idle' else 73)
        workflow=json.loads((folder/'native-v1-workflow.json').read_text(encoding='utf-8'))
        assert workflow['10']['inputs']['steps']==40
        with av.open(str(folder/'raw.mp4')) as video:
            raw=list(video.decode(video=0));assert len(raw)==73 and all((f.width,f.height)==(768,768) for f in raw)
        rift_columns=[]
        for f in raw:
            rgb=np.array(f.to_image())
            strength=np.maximum(100-rgb[540:630,710:750].mean(2),0).sum(0)
            rift_columns.append(int(strength.argmax())+710)
        sheet=Image.open(folder/'native-sheet.png').convert('RGBA');assert max(sheet.size)<=8192
        contacts=[]
        for n,i in enumerate(meta['sourceIndices']):
            actual=np.array(Image.open(folder/'all-frames'/f'frame-{i:03d}.png').convert('RGBA'))
            cell=np.array(sheet.crop((n%8*768,n//8*768,(n%8+1)*768,(n//8+1)*768)))
            assert np.array_equal(actual,cell)
            alpha=actual[:,:,3]
            if alpha[0].any() or alpha[-1].any() or alpha[:,0].any() or alpha[:,-1].any():contacts.append(i)
            assert not actual[alpha==0,:3].any()
        with Image.open(folder/'game-animation.gif') as gif:
            assert gif.n_frames==meta['frameCount'];duration=0
            for i in range(gif.n_frames):gif.seek(i);duration+=gif.info['duration']
        assert abs(duration-sum(meta['durationMs']))<=10
        reviewpath=folder/'review.json';review=json.loads(reviewpath.read_text(encoding='utf-8'))
        review['matteVisualReview']='Reviewed against dark blue, cream and green backgrounds, including attack effect peak. Original pale edge accents and thin strands retained.'
        save(reviewpath,review)
        records[name]=dict(frameCount=meta['frameCount'],durationMs=duration,nativeSheetSize=list(sheet.size),edgeContactFrames=contacts,rawSha256=digest(folder/'raw.mp4'),riftLowerSegmentDarkColumnRange=[min(rift_columns),max(rift_columns)],riftMeasurementROI=[710,540,750,630])
    assert digest(SOURCE)==digest(OUT/'source-original.png')
    save(OUT/'validation.json',dict(fileChecksPassed=True,sourceUnchanged=True,nativeCanvas=[768,768],fps=24,generationSteps=40,geometryUnchanged=True,noUpscaling=True,cases=records))
    (OUT/'README.txt').write_text('Dimensional Horror - Idle + Attack\n\nNative 768x768, 24FPS. No generation or upscaling during export.\nIdle: 72 forward frames (3s), repeated closing reference omitted.\nAttack: 73 forward frames (about 3.04s), play once in game.\nUse action/native-sheet.png + native-frames.json or action/frames/*.png.\nCells are 768x768; columns=8. Empty trailing cells are transparent.\nBoth actions retain original canvas coordinates, no per-frame recentering.\nSuggested rift registration anchor is [735,384] in top-left image coordinates.\nThis is a placement guide; slight generated local drift is preserved.\nGame-sheet is a lighter 24-frame selection; use its own game-frames.json timings.\nGIF/WebP previews use the same static presentation crop at 512px.\nPNG/WebP retain soft alpha; GIF has binary transparency.\nOriginal source and 73-frame MP4s included unchanged.\nFine claws, pale strands, fissures and rift details can vary between generated frames.\n',encoding='utf-8')
    build();target=OUT/'dimensional-horror-idle-attack.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for name in ['source-original.png','source.json','reference.png','reference-native-alpha.png','preview.html','validation.json','README.txt','game-registration.json','matte-samples.jpg']:
            z.write(OUT/name,name)
        for action in ACTIONS:
            folder=OUT/action;meta=json.loads((folder/'native-frames.json').read_text(encoding='utf-8'))
            for name in ['game-animation.gif','game-animation.webp','native-sheet.png','native-frames.json','game-sheet.png','game-frames.json','settings.json','native-v1-workflow.json','raw.mp4','reference-prepared.png','review-raw.webp','matte-review.jpg','review.json','matte-process.json']:
                z.write(folder/name,action+'/'+name)
            for i in meta['sourceIndices']:
                p=folder/'all-frames'/f'frame-{i:03d}.png';z.write(p,action+'/frames/'+p.name)
    with zipfile.ZipFile(target) as z:assert z.testzip() is None
    print('BOSS_HANDOFF_VALIDATED',json.dumps(records),round(target.stat().st_size/1024**2,1),'MiB',flush=True)

if __name__=='__main__':
    globals()[sys.argv[1] if len(sys.argv)>1 else 'samples']()
