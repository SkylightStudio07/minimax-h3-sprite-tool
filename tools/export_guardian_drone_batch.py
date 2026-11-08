"""Protected alpha export for the eight completed guardian/drone videos."""
import argparse
import hashlib
import html
import json
import os
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import av
import cv2
import numpy as np
from PIL import Image,ImageDraw
from scipy import ndimage
from pymatting import estimate_alpha_cf,estimate_foreground_ml
import image_background
from tools import verify_masked_rifleman_motion as base
from tools.submit_guardian_drone_batch import OUT,INPUT,CASES

REVISION='guardian-drone-closed-form-v1'
NOTES={
    '01-crystal-guardian':dict(idle='부유 자세에서 장갑과 팔을 조금 조정하고 코어가 움직입니다. 분리된 조각과 발톱의 세부에는 생성 흔들림이 남습니다.',attack='왼쪽 팔을 당겼다가 앞으로 내밀어 타격하고 원래 자세로 복귀합니다. 장갑·팔 연결부·코어 세부에 생성 변화가 남습니다.'),
    '02-defensive-guardian':dict(idle='큰 장갑 팔로 코어를 지키며 부유 자세와 발톱을 조금 조정합니다. 결정·작은 조각·코어의 세부에는 생성 흔들림이 남습니다.',attack='왼쪽 발톱을 당겼다가 휘두르고 보라색 궤적을 남긴 뒤 복귀합니다. 코어와 장갑·발톱 형태가 조금씩 변합니다.'),
    '03-heavy-gun-drone':dict(idle='선체가 작게 부유하며 하부 포대의 각도를 조정합니다. 포신·안테나·선체 문자에 생성 흔들림이 남습니다.',attack='하부 두 포대에서 번갈아 연사하고 섬광·연기가 나타난 뒤 부유 자세로 복귀합니다. 일부 발사체는 원본 화면 왼쪽 또는 아래 끝에 잘립니다. 포신과 선체 문자에 생성 변화가 남습니다.'),
    '04-fast-gun-drone':dict(idle='선체가 작게 부유하며 하부 포의 조준을 유지합니다. 안테나·포신·선체 문자에 생성 흔들림이 남습니다.',attack='하부 두 포에서 연사하며 섬광·발사체·연기가 나타난 뒤 부유 자세로 복귀합니다. 일부 발사체는 원본 화면 왼쪽 끝에 잘립니다. 포신·안테나·선체 문자에 생성 변화가 남습니다.')}


def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def drone_reference(case):
    root=OUT/case['id'];ref=Image.open(root/'reference.png').convert('RGBA')
    scale=min(768/ref.width,768/ref.height)*(1-case['padding']/100)
    size=(max(1,round(ref.width*scale)),max(1,round(ref.height*scale)))
    alpha=ref.getchannel('A').resize(size,Image.Resampling.LANCZOS)
    canvas=Image.new('L',(768,768));canvas.paste(alpha,((768-size[0])//2,(768-size[1])//2))
    core=ndimage.distance_transform_edt(np.array(canvas)>230)>5
    yy,xx=np.indices(core.shape);core&=yy<(480 if case['id'].startswith('04-') else 430)
    prepared=np.array(Image.open(root/'idle/reference-prepared.png').convert('RGB'))
    grey=cv2.cvtColor(prepared,cv2.COLOR_RGB2GRAY)
    points=cv2.goodFeaturesToTrack(grey,maxCorners=240,qualityLevel=.01,minDistance=5,mask=core.astype('uint8')*255)
    return core,grey,points


def tracked_hull_core(raw,reference):
    core,grey,points=reference;current=cv2.cvtColor(np.array(raw.convert('RGB')),cv2.COLOR_RGB2GRAY)
    transform=np.array([[1.,0.,0.],[0.,1.,0.]])
    if points is not None:
        moved,status,_=cv2.calcOpticalFlowPyrLK(grey,current,points,None,winSize=(31,31),maxLevel=3)
        valid=status.ravel().astype(bool)
        if valid.sum()>=8:
            fitted,_=cv2.estimateAffinePartial2D(points[valid],moved[valid],method=cv2.RANSAC,ransacReprojThreshold=2)
            if fitted is not None and .94<np.hypot(fitted[0,0],fitted[1,0])<1.06 and max(abs(fitted[:,2]))<35:
                transform=fitted
    # Track only the foreground seed mask. Exported image geometry is untouched.
    return cv2.warpAffine(core.astype('uint8'),transform,(768,768),flags=cv2.INTER_NEAREST).astype(bool)


def matte(raw,gunfire=False,drone=False,reference=None,semantic=None):
    rgb=np.array(raw.convert('RGB'),dtype=np.float64);image=rgb/255
    border=np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1]));bg=np.median(border,axis=0)
    delta=np.max(np.abs(rgb-bg),axis=2);chroma=np.ptp(rgb,axis=2);lum=rgb.mean(2)
    if semantic is None:semantic=np.array(image_background.remove(raw))[:,:,3]
    protect=ndimage.distance_transform_edt(semantic>240)>2.5
    near=(delta<9)&(chroma<8);labels,n=ndimage.label(near);sizes=np.bincount(labels.ravel())
    gaps=(labels>0)&(sizes[labels]>=100)
    if drone:
        seeds=np.zeros(near.shape,bool)
        seeds[0]=near[0];seeds[-1]=near[-1];seeds[:,0]=near[:,0];seeds[:,-1]=near[:,-1]
        # Grey hull highlights can match the key exactly. Keep semantic hull
        # interiors; only exterior-connected key overrides them on machines.
        gaps&=ndimage.binary_propagation(seeds,mask=near)
    protect[gaps]=False
    if drone and reference is not None:protect|=tracked_hull_core(raw,reference)
    yy,xx=np.indices(lum.shape)
    # Dark smoke from the actual lower guns is allowed as uncertain foreground;
    # the measured grey key remains background in that region.
    effects=(yy>300)&(xx<650)&(semantic<200) if gunfire else np.zeros(lum.shape,bool)
    neutral=(chroma<12)&(lum>88)&(lum<158)&~protect&~effects
    trimap=np.full(delta.shape,.5);trimap[(delta>40)|protect]=1
    trimap[((delta<9)|neutral)&~protect]=0
    alpha=np.clip(estimate_alpha_cf(image,trimap),0,1)
    foreground=np.clip(estimate_foreground_ml(image,alpha),0,1)
    alpha[alpha<.02]=0;alpha[alpha>.995]=1;alpha[protect]=1
    rgba=np.rint(np.dstack((foreground,alpha))*255).astype('uint8');rgba[alpha==0]=0
    return Image.fromarray(rgba),dict(background=bg.tolist(),protectedInteriorPixels=int(protect.sum()),
        gapSeedPixels=int(gaps.sum()),protectedInteriorPreserved=bool(np.all(rgba[:,:,3][protect]==255)))


def configure(case):
    folder=OUT/case['id'];actions={}
    for name in ['idle','attack']:
        actions[name]=dict(title='대기 · Idle' if name=='idle' else '공격 · Attack',loop=name=='idle',padding=case['padding'],frames=24)
    base.OUT=folder;base.SOURCE=INPUT/case['file'];base.ACTIONS=actions
    base.build=lambda:build_case(case)
    base.configure()
    return folder


def build_case(case):
    root=OUT/case['id'];cards=[]
    for name in ['idle','attack']:
        if not (root/name/'game-animation.webp').exists():continue
        review=json.loads((root/name/'review.json').read_text(encoding='utf-8')) if (root/name/'review.json').exists() else {}
        cards.append(f'<article><h2>{"대기" if name=="idle" else "공격"}</h2><p>{html.escape(review.get("note",""))}</p><img src="{name}/game-animation.webp" alt="{name}"><p><a href="{name}/game-animation.gif">GIF</a> · <a href="{name}/native-sheet.png">전체 PNG 시트</a> · <a href="{name}/native-frames.json">프레임 시간</a> · <a href="{name}/matte-review.jpg">밝은·어두운 배경</a></p></article>')
    page=page_head(case['label'])+f'<h1>{html.escape(case["label"])}</h1><p>768px · 24FPS · 40스텝. 결정 조각·포신·안테나와 실제 생성 효과를 보존하며 회색 배경을 분리했습니다. PNG/WebP는 부드러운 투명도를 유지하고 GIF는 이진 투명도를 사용합니다.</p>'+buttons()+f'<p><a href="{case["id"]}-idle-attack.zip">Idle + Attack ZIP</a></p><main>'+''.join(cards)+'</main></html>'
    (root/'preview.html').write_text(page,encoding='utf-8')


def page_head(title):
    return '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'+html.escape(title)+'</title><style>:root{--matte:#142436}body{background:#1b2230;color:#eee;font:16px/1.65 system-ui;margin:24px}main{display:flex;gap:24px;flex-wrap:wrap}article{width:512px;max-width:100%}img{width:100%;background:var(--matte)}a{color:#c9c0ff}button{padding:8px 14px;margin-right:8px}</style>'


def buttons():
    return '''<button onclick="document.documentElement.style.setProperty('--matte','#142436')">어둡게</button><button onclick="document.documentElement.style.setProperty('--matte','#fff4dc')">밝게</button><button onclick="document.documentElement.style.setProperty('--matte','#226b54')">초록</button>'''


def process_case(case):
    # Each worker owns a separate case directory and separate exporter globals.
    root=configure(case);assert digest(INPUT/case['file'])==digest(root/'source-original.png')
    reference=drone_reference(case) if case['id'].startswith(('03-','04-')) else None
    for name in ['idle','attack']:
        folder=root/name;framesdir=folder/'all-frames';framesdir.mkdir(exist_ok=True)
        oldmeta=json.loads((folder/'matte-process.json').read_text(encoding='utf-8')) if (folder/'matte-process.json').exists() else {}
        records={x['frame']:x for x in oldmeta.get('processed',[])}
        with av.open(str(folder/'raw.mp4')) as video:
            for i,frame in enumerate(video.decode(video=0)):
                path=framesdir/f'frame-{i:03d}.png'
                if path.exists() and i in records:continue
                is_drone=case['id'].startswith(('03-','04-'))
                cut,info=matte(frame.to_image(),gunfire=is_drone and name=='attack',drone=is_drone,reference=reference)
                cut.save(path);records[i]=dict(frame=i,**info)
                if i%24==0:
                    save(folder/'matte-process.json',dict(revision=REVISION,processed=list(records.values()),geometryUnchanged=True,originalVideoPreserved=True))
                    print('MATTED',case['id'],name,i,flush=True)
        save(folder/'matte-process.json',dict(revision=REVISION,method='Semantic interior protection, measured gap trimap, closed-form alpha and multilevel foreground estimation',processed=list(records.values()),geometryUnchanged=True,originalVideoPreserved=True))
        save(folder/'review.json',dict(reviewed=False,userApproval='pending',note=NOTES[case['id']][name],
            generatedDetailDrift=True,rawProjectileClipping=case['id'].startswith(('03-','04-')) and name=='attack'))
        print('ACTION_MATTED',case['id'],name,flush=True)
    if not (root/'idle/selection.json').exists():save(root/'idle/selection.json',dict(start=0,end=71,note='Duplicate closing reference omitted; forward frames only.'))
    base.export();return validate(case)


def validate(case):
    root=configure(case);records={}
    for name in ['idle','attack']:
        folder=root/name;native=json.loads((folder/'native-frames.json').read_text(encoding='utf-8'))
        meta=json.loads((folder/'frames.json').read_text(encoding='utf-8'))
        graph=json.loads((folder/'native-v1-workflow.json').read_text(encoding='utf-8'));assert graph['10']['inputs']['steps']==40
        sheet=Image.open(folder/'native-sheet.png').convert('RGBA');assert max(sheet.size)<=8192
        for n,i in enumerate(native['sourceIndices']):
            original=np.array(Image.open(folder/'all-frames'/f'frame-{i:03d}.png').convert('RGBA'))
            cell=np.array(sheet.crop((n%8*768,n//8*768,(n%8+1)*768,(n//8+1)*768)))
            assert np.array_equal(original,cell)
        with Image.open(folder/'game-animation.gif') as gif:
            assert gif.n_frames==native['frameCount'];total=0
            for i in range(gif.n_frames):gif.seek(i);total+=gif.info['duration']
        assert abs(total-sum(native['durationMs']))<=10
        records[name]=dict(frameCount=native['frameCount'],durationMs=total,
            edgeContactFrames=[x['frame'] for x in meta['diagnostics'] if x['edgeContact']],
            review=json.loads((folder/'review.json').read_text(encoding='utf-8')))
    save(root/'validation.json',dict(fileChecksPassed=True,sourceUnchanged=digest(INPUT/case['file'])==digest(root/'source-original.png'),
        nativeCanvas=[768,768],fps=24,steps=40,matteRevision=REVISION,cases=records,userApproval='pending'))
    return dict(case=case['id'],actions=records)


def package_case(case):
    root=OUT/case['id'];build_case(case)
    (root/'README.txt').write_text(case['label']+' / Idle + Attack\n\n768x768 native cells, 24FPS, 40 MiniMax steps.\nIdle 72 frames, 3.000 seconds; duplicate closing anchor omitted. Attack 73 frames.\nUse action/native-sheet.png and native-frames.json, or action/frames/*.png.\nA lighter 24-frame option is included as game-sheet.png and game-frames.json.\nBoth actions share the same source scale and registration. GIF uses binary alpha; PNG/WebP preserve soft alpha.\nNo regenerated motion, reversed poses, interpolation or synthetic effects. Original source and videos preserved.\nThin crystals, claws, barrels, antennae, markings and smoke can drift or weaken across generated frames.\nFor the gun drones, some projectiles reach the original video border; these missing pixels were not invented.\nSee review.json, validation.json and matte-review.jpg for actual observed limits.\n',encoding='utf-8')
    target=root/(case['id']+'-idle-attack.zip')
    files=['source-original.png','source.json','reference.png','preview.html','README.txt','validation.json','game-registration.json']
    for name in ['idle','attack']:
        folder=root/name;native=json.loads((folder/'native-frames.json').read_text(encoding='utf-8'))
        for f in ['game-animation.gif','game-animation.webp','native-sheet.png','native-frames.json','game-sheet.png','game-frames.json','settings.json','raw.mp4','reference-prepared.png','review-raw.webp','matte-review.jpg','review.json','matte-process.json']:files.append(name+'/'+f)
        for f in ['effects-matte-review.jpg','hull-refinement.json']:
            if (folder/f).exists():files.append(name+'/'+f)
        for i in native['sourceIndices']:files.append(name+'/all-frames/'+f'frame-{i:03d}.png')
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for f in files:z.write(root/f,f.replace('/all-frames/','/frames/'))
    with zipfile.ZipFile(target) as z:assert z.testzip() is None
    return target


def build_all():
    cards=[]
    for case in CASES:
        root=OUT/case['id']
        if not (root/'idle/game-animation.webp').exists():continue
        cid=case['id']
        for action in ['idle','attack']:
            cards.append(f'<article><h2>{html.escape(case["label"])} · {action}</h2><img src="{cid}/{action}/game-animation.webp" alt="{cid} {action}"><p><a href="{cid}/preview.html">상세 미리보기</a> · <a href="{cid}/{cid}-idle-attack.zip">캐릭터 ZIP</a></p></article>')
    page=page_head('수호자·비행 포대 4종')+'<h1>수호자·비행 포대 · Idle / Attack</h1><p>4종, 8개 동작. 768px · 24FPS · 40스텝.</p>'+buttons()+'<p><a href="guardian-drone-all-idle-attack.zip">전체 ZIP</a></p><main>'+''.join(cards)+'</main></html>'
    (OUT/'preview.html').write_text(page,encoding='utf-8')


def package_all():
    archives=[package_case(case) for case in CASES];build_all()
    summary=[json.loads((OUT/c['id']/'validation.json').read_text(encoding='utf-8')) for c in CASES]
    save(OUT/'batch-validation.json',dict(fileChecksPassed=all(s['fileChecksPassed'] for s in summary),cases=summary,visualReview='completed' if all(s['cases'][a]['review']['reviewed'] for s in summary for a in ['idle','attack']) else 'pending'))
    target=OUT/'guardian-drone-all-idle-attack.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        preview=(OUT/'preview.html').read_text(encoding='utf-8')
        preview=preview.replace('<p><a href="guardian-drone-all-idle-attack.zip">전체 ZIP</a></p>','<p>각 캐릭터 폴더에 GIF·PNG 시트·원본 영상이 있습니다.</p>')
        for case in CASES:
            cid=case['id'];preview=preview.replace(f'<a href="{cid}/{cid}-idle-attack.zip">캐릭터 ZIP</a>',f'<a href="{cid}/preview.html">파일 보기</a>')
        z.writestr('preview.html',preview);z.write(OUT/'batch-validation.json','batch-validation.json')
        for case,archive in zip(CASES,archives):
            # Include each case's actual files so the top-level preview works immediately.
            with zipfile.ZipFile(archive) as src:
                for info in src.infolist():
                    data=src.read(info.filename)
                    if info.filename=='preview.html':
                        data=data.decode('utf-8').replace(f'<p><a href="{case["id"]}-idle-attack.zip">Idle + Attack ZIP</a></p>','<p>GIF·PNG 시트·원본 영상은 각 동작 폴더에 있습니다.</p>').encode('utf-8')
                    z.writestr(case['id']+'/'+info.filename,data)
    with zipfile.ZipFile(target) as z:assert z.testzip() is None
    print('ALL_HANDOFFS_PACKAGED',str(target),round(target.stat().st_size/1024/1024,1),'MiB',flush=True)


def process():
    # Process two independent CPU cases at once. No GPU models are allocated.
    os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
    results=[]
    with ProcessPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(process_case,c):c['id'] for c in CASES}
        for future in as_completed(futures):
            result=future.result();results.append(result);print('CASE_READY',result['case'],flush=True)
            save(OUT/'export-progress.json',dict(completed=results,expectedCases=4))
    build_all();print('ALL_CASES_READY_FOR_VISUAL_REVIEW',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['process','package','build']);stage=parser.parse_args().stage
    if stage=='process':process()
    elif stage=='package':package_all()
    else:build_all()
