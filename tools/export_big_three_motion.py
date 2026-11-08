"""CPU cutout and handoff for the six completed Big Three motions."""
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
from tools import export_guardian_drone_batch as checks
from tools.submit_big_three_motion import OUT,INPUT,CASES as SUBMITTED

CASES=[dict(c,file=c['label']+'.png') for c in SUBMITTED]
REVISION='big-three-protected-alpha-v1'
NOTES={
 '01-etienne-vasseur':dict(idle='권총 조준 각도와 머리를 조금 조정하며 가방이 작게 흔들립니다.',attack='권총 팔을 들어 왼쪽으로 사격하고 원래 자세로 복귀합니다. 두 발 요청보다 여러 번의 섬광이 생성되었습니다.'),
 '02-desmond-kilroy':dict(idle='소총을 낮게 든 채 상체와 조준을 조금 조정합니다.',attack='소총을 어깨에 올려 왼쪽으로 점사한 뒤 원래의 낮은 준비 자세로 복귀합니다. 발사체 일부가 원본 영상의 왼쪽 끝에 닿습니다.'),
 '03-van-rieden':dict(idle='지팡이를 짚고 자세를 조금 조정하며 망토가 움직입니다.',attack='지팡이는 짚은 채 리볼버를 뽑아 왼쪽으로 한 발 발사하고 다시 수납합니다. 발사 때 의상이 밝아지는 원본 영상의 조명 변화는 남아 있습니다.')}

def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def matte(raw,case,action):
    rgb=np.array(raw.convert('RGB'),dtype=np.float64);image=rgb/255
    border=np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1]));bg=np.median(border,axis=0)
    delta=np.max(np.abs(rgb-bg),axis=2);chroma=np.ptp(rgb,axis=2);lum=rgb.mean(2)
    semantic=np.array(image_background.remove(raw))[:,:,3]
    protect=ndimage.distance_transform_edt(semantic>240)>2.5
    near=(delta<9)&(chroma<8);labels,_=ndimage.label(near);sizes=np.bincount(labels.ravel())
    gaps=(labels>0)&(sizes[labels]>=100)
    neutral_band=(delta<24)&(chroma<12);seed=np.zeros(delta.shape,bool)
    seed[0]=neutral_band[0];seed[-1]=neutral_band[-1];seed[:,0]=neutral_band[:,0];seed[:,-1]=neutral_band[:,-1]
    exterior=ndimage.binary_propagation(seed,mask=neutral_band)
    protect[gaps|exterior]=False
    neutral=(chroma<12)&(lum>88)&(lum<158)&~protect
    trimap=np.full(delta.shape,.5);trimap[(delta>40)|protect]=1
    trimap[((delta<9)|neutral|exterior)&~protect]=0
    yy,xx=np.indices(delta.shape)
    roi=(xx<310)&(yy>110)&(yy<400)
    warm=roi&(rgb[:,:,0]>215)&(rgb[:,:,1]>160)&(rgb[:,:,0]-rgb[:,:,2]>60)
    flash=bool(action=='attack' and warm.sum()>=3)
    support=(ndimage.distance_transform_edt(~warm)<42)&roi if flash else np.zeros(delta.shape,bool)
    if flash and case['id']=='03-van-rieden':
        # This generated shot relights a large area of the flat backdrop.
        # Keep the semantic actor and actual muzzle light, not that backdrop wash.
        outside=(ndimage.distance_transform_edt(semantic<16)>3)&~support
        # Bright background wash is not a reliable foreground colour seed.
        trimap[(delta>40)&~protect]=.5
        trimap[(semantic>240)&(delta>20)]=1
        trimap[outside]=0;protect[outside]=False
    alpha=np.clip(estimate_alpha_cf(image,trimap),0,1)
    foreground=np.clip(estimate_foreground_ml(image,alpha),0,1)
    recovered=0
    if flash:
        # Estimate the slowly changing local background field outside the actor
        # and bright flash. Unmix only observed muzzle emission, avoiding grey
        # codec/bloom rings when composited onto a pale background.
        weight=((semantic<8)&(ndimage.distance_transform_edt(~warm)>18)).astype(float)
        denominator=ndimage.gaussian_filter(weight,35)
        local=np.stack([ndimage.gaussian_filter(rgb[:,:,c]*weight,35)/np.maximum(denominator,1e-5) for c in range(3)],axis=2)
        local[denominator<.02]=bg
        emission=np.clip(np.max((rgb-local)/np.maximum(255-local,1),axis=2),0,1)
        recover=support&(semantic<32)
        emission[emission<.035]=0
        unmixed=np.clip((rgb-local*(1-emission[:,:,None]))/np.maximum(emission[:,:,None],.01),0,255)/255
        alpha[recover]=emission[recover];foreground[recover]=unmixed[recover]
        recovered=int((recover&(emission>0)).sum())
    alpha[alpha<.02]=0;alpha[alpha>.995]=1;alpha[protect]=1
    rgba=np.rint(np.dstack((foreground,alpha))*255).astype('uint8');rgba[alpha==0]=0
    return Image.fromarray(rgba),dict(background=bg.tolist(),protectedInteriorPixels=int(protect.sum()),
        protectedInteriorPreserved=bool(np.all(rgba[:,:,3][protect]==255)),flashDetected=flash,recoveredEmissionPixels=recovered)

def configure(case):
    folder=OUT/case['id']
    base.OUT=folder;base.SOURCE=INPUT/case['file']
    base.ACTIONS={a:dict(title=a,loop=a=='idle',padding=case['padding'],frames=24) for a in ['idle','attack']}
    base.build=lambda:build_case(case);base.configure();return folder

def page_head(title):return checks.page_head(title)
def buttons():return checks.buttons()

def build_case(case):
    root=OUT/case['id'];cards=[]
    for a in ['idle','attack']:
        if not (root/a/'game-animation.webp').exists():continue
        cards.append(f'<article><h2>{a}</h2><p>{NOTES[case["id"]][a]}</p><img src="{a}/game-animation.webp" alt="{a}"><p><a href="{a}/game-animation.gif">GIF</a> · <a href="{a}/native-sheet.png">전체 PNG 시트</a> · <a href="{a}/native-frames.json">프레임 시간</a> · <a href="{a}/matte-review.jpg">배경 비교</a></p></article>')
    (root/'preview.html').write_text(page_head(case['label'])+f'<h1>{html.escape(case["label"])} · Idle / Attack</h1><p>768×768 · 24FPS. 원본 좌표를 유지한 투명 PNG 시트·개별 프레임. PNG/WebP는 반투명, GIF는 이진 투명도입니다. 장비·의상 세부에는 생성 변화가 남습니다.</p>'+buttons()+f'<p><a href="{case["id"]}-idle-attack.zip">캐릭터 ZIP</a></p><main>'+''.join(cards)+'</main></html>',encoding='utf-8')

def samples():
    for case in CASES:
        contact=Image.new('RGB',(1536,1024));draw=ImageDraw.Draw(contact)
        for row,(action,index) in enumerate([('idle',0),('attack',46 if case['id'].startswith('01') else 31)]):
            with av.open(str(OUT/case['id']/action/'raw.mp4')) as v:
                for i,f in enumerate(v.decode(video=0)):
                    if i==index:cut,info=matte(f.to_image(),case,action);break
            cut.save(OUT/case['id']/action/f'matte-test-{index:03d}.png')
            for col,color in enumerate(['#142436','#fff4dc','#226b54']):
                bg=Image.new('RGBA',cut.size,color);bg.alpha_composite(cut)
                contact.paste(bg.resize((512,512)).convert('RGB'),(col*512,row*512));draw.text((col*512+8,row*512+8),f'{action} {index}',fill='red')
        contact.save(OUT/case['id']/'matte-tests.jpg',quality=97);print('SAMPLES',case['id'],flush=True)

def process():
    for case in CASES:
        root=configure(case);assert digest(base.SOURCE)==digest(root/'source-original.png')
        for action in ['idle','attack']:
            folder=root/action;frames=folder/'all-frames';frames.mkdir(exist_ok=True)
            old=json.loads((folder/'matte-process.json').read_text(encoding='utf-8')) if (folder/'matte-process.json').exists() else {}
            assert old.get('revision',REVISION)==REVISION
            records={r['frame']:r for r in old.get('processed',[])}
            with av.open(str(folder/'raw.mp4')) as video:
                for i,f in enumerate(video.decode(video=0)):
                    target=frames/f'frame-{i:03d}.png'
                    if target.exists() and i in records:continue
                    cut,info=matte(f.to_image(),case,action);cut.save(target);records[i]=dict(frame=i,**info)
                    if i%24==0:
                        save(folder/'matte-process.json',dict(revision=REVISION,processed=list(records.values()),geometryUnchanged=True))
                        print('MATTED',case['id'],action,i,flush=True)
            assert len(records)==73
            save(folder/'matte-process.json',dict(revision=REVISION,processed=list(records.values()),geometryUnchanged=True,originalVideoPreserved=True))
            save(folder/'review.json',dict(reviewed=False,userApproval='pending',note=NOTES[case['id']][action],generatedDetailDrift=True))
        save(root/'idle/selection.json',dict(start=0,end=71,note='Closing reference duplicate omitted. Forward playback only.'))
        base.export();validate(case);build_all();print('CASE_READY_FOR_REVIEW',case['id'],flush=True)

def validate(case):
    checks.OUT=OUT;checks.INPUT=INPUT;checks.configure=configure
    return checks.validate(case)

def build_all():
    cards=[]
    for c in CASES:
        for a in ['idle','attack']:
            if not (OUT/c['id']/a/'game-animation.webp').exists():continue
            cards.append(f'<article><h2>{c["label"]} · {a}</h2><img src="{c["id"]}/{a}/game-animation.webp" alt="{a}"><p><a href="{c["id"]}/preview.html">상세</a> · <a href="{c["id"]}/{c["id"]}-idle-attack.zip">캐릭터 ZIP</a></p></article>')
    (OUT/'preview.html').write_text(page_head('3인방 · Idle / Attack')+'<h1>3인방 · Idle / Attack</h1><p>3명, 6개 동작 · 768×768 · 24FPS. 공격은 미리보기에서 반복되며 게임에서는 한 번 재생하세요.</p>'+buttons()+'<p><a href="big-three-all-idle-attack.zip">전체 ZIP</a></p><main>'+''.join(cards)+'</main></html>',encoding='utf-8')

def package():
    archives=[]
    for c in CASES:
        root=configure(c)
        for action in ['idle','attack']:
            path=root/action/'review.json';review=json.loads(path.read_text(encoding='utf-8'))
            review['reviewed']=True;review['matteVisualReview']='Dark, cream and green backgrounds inspected, including muzzle flashes and narrow equipment gaps.';save(path,review)
        validate(c);build_case(c)
        (root/'README.txt').write_text(c['label']+' - Idle + Attack\n\n768x768 native cells, 24FPS, 40 generation steps.\nIdle 72 forward frames, 3 seconds; repeated closing reference omitted.\nAttack 73 forward frames, about 3.04 seconds. Play once in game.\nUse action/native-sheet.png + native-frames.json, or action/frames/*.png.\nNative sheets: 8 columns, 768px cells. Blank trailing cells are transparent.\nBoth motions preserve the same canvas coordinates and source scale.\n24-frame alternative: game-sheet.png + game-frames.json.\nGIF/WebP previews are 512px with one shared static presentation crop.\nPNG/WebP retain soft alpha; GIF uses binary transparency.\nOriginal source and MP4s retained; no new generation, interpolation or reverse playback.\nExisting clothing/weapon detail drift and shot-time costume lighting are preserved.\nBroad background flash wash was removed while observed local muzzle emission was retained.\nSee review.json and matte-review.jpg for actual motion limitations.\n',encoding='utf-8')
        target=root/(c['id']+'-idle-attack.zip')
        with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
            for name in ['source-original.png','source.json','reference.png','preview.html','README.txt','validation.json','game-registration.json','matte-tests.jpg']:z.write(root/name,name)
            for a in ['idle','attack']:
                folder=root/a;native=json.loads((folder/'native-frames.json').read_text(encoding='utf-8'))
                for name in ['game-animation.gif','game-animation.webp','native-sheet.png','native-frames.json','game-sheet.png','game-frames.json','settings.json','native-v1-workflow.json','raw.mp4','reference-prepared.png','review-raw.webp','matte-review.jpg','review.json','matte-process.json']:z.write(folder/name,a+'/'+name)
                for i in native['sourceIndices']:
                    p=folder/'all-frames'/f'frame-{i:03d}.png';z.write(p,a+'/frames/'+p.name)
        with zipfile.ZipFile(target) as z:assert z.testzip() is None
        archives.append((c,target))
    build_all()
    summary=[json.loads((OUT/c['id']/'validation.json').read_text(encoding='utf-8')) for c in CASES]
    save(OUT/'batch-validation.json',dict(fileChecksPassed=all(s['fileChecksPassed'] for s in summary),visualReview='completed',cases=summary))
    target=OUT/'big-three-all-idle-attack.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        preview=(OUT/'preview.html').read_text(encoding='utf-8').replace('<p><a href="big-three-all-idle-attack.zip">전체 ZIP</a></p>','')
        for c,_ in archives:preview=preview.replace(f'<a href="{c["id"]}/{c["id"]}-idle-attack.zip">캐릭터 ZIP</a>',f'<a href="{c["id"]}/preview.html">파일 보기</a>')
        z.writestr('preview.html',preview);z.write(OUT/'batch-validation.json','batch-validation.json')
        for c,archive in archives:
            with zipfile.ZipFile(archive) as src:
                for info in src.infolist():
                    data=src.read(info.filename)
                    if info.filename=='preview.html':data=data.decode('utf-8').replace(f'<p><a href="{c["id"]}-idle-attack.zip">캐릭터 ZIP</a></p>','').encode('utf-8')
                    z.writestr(c['id']+'/'+info.filename,data)
    with zipfile.ZipFile(target) as z:assert z.testzip() is None
    print('BIG_THREE_HANDOFF_READY',target,round(target.stat().st_size/1024**2,1),'MiB',flush=True)

if __name__=='__main__':globals()[sys.argv[1] if len(sys.argv)>1 else 'samples']()
