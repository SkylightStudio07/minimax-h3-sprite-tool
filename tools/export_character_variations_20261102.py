"""CPU matte and handoff for selected blonde and six pistol motions; no kunai."""
import os
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
import gc
import html
import json
import shutil
import sys
import zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import av
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from pymatting import estimate_alpha_cf, estimate_foreground_ml
import image_background
from tools import verify_masked_rifleman_motion as base
from tools import export_soldier_robot_batch as effects
from tools import export_guardian_drone_batch as checks
from tools.sprite_matte import clean_flat_matte

OUT = ROOT / 'outputs/character-variations-cutout-20261102'
OLD = ROOT / 'outputs/character-variations-20261101'
BLONDE = ROOT / 'outputs/blonde-grip-retry-20261101'
CASES = [dict(id='blonde', label='금발 · 선택한 이전 버전', src=BLONDE, prefix='blonde_grip_retry_20261101', ids=['01-blonde-idle-grip','02-blonde-fire-v2'])]
for letter, number in [('a',3), ('b',5), ('c',7)]:
    CASES.append(dict(id='pistol-'+letter, label='권총 · '+letter.upper(), src=OLD, prefix='character_variations_20261101', ids=[f'{number:02d}-pistol-idle-{letter}',f'{number+1:02d}-pistol-fire-{letter}']))

def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def configure(case):
    root = OUT / case['id']
    root.mkdir(parents=True, exist_ok=True)
    for action, mid in zip(('idle','attack'),case['ids']):
        dest = root / action
        dest.mkdir(exist_ok=True)
        source = case['src'] / mid
        for name in ('settings.json','reference-prepared.png','native-v1-workflow.json'):
            if not (dest/name).exists(): shutil.copy2(source/name,dest/name)
        video = ROOT/'outputs/comfy'/case['prefix']/(mid+'_00001_.mp4')
        if not (dest/'raw.mp4').exists(): shutil.copy2(video,dest/'raw.mp4')
        assert checks.digest(video) == checks.digest(dest/'raw.mp4')
    for name in ('source-original.png','reference.png','source.json'):
        if not (root/name).exists(): shutil.copy2(case['src']/case['ids'][0]/name,root/name)
    base.OUT=root
    base.SOURCE=root/'source-original.png'
    base.ACTIONS={a:dict(title=a,loop=a=='idle',padding=30,frames=24) for a in ('idle','attack')}
    base.build=lambda: build()
    base.configure()
    return root

def matte(raw, case, action):
    rgb=np.array(raw.convert('RGB'),dtype=float)
    bg=np.median(np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1])),axis=0)
    delta=np.max(np.abs(rgb-bg),axis=2)
    chroma=np.ptp(rgb,axis=2)
    semantic=np.array(image_background.remove(raw))[:,:,3]
    protected=ndimage.distance_transform_edt(semantic>230)>2
    neutral=(delta<25)&(chroma<14)
    seeds=np.zeros(delta.shape,bool)
    seeds[0],seeds[-1],seeds[:,0],seeds[:,-1]=neutral[0],neutral[-1],neutral[:,0],neutral[:,-1]
    exterior=ndimage.binary_propagation(seeds,mask=neutral)
    protected[exterior]=False
    # Only low-confidence enclosed flat-grey holes are keyed, retaining opaque fabric.
    holes=(delta<12)&(chroma<9)&(semantic<192)&~protected
    trimap=np.full(delta.shape,.5)
    trimap[(delta>40)|protected]=1
    trimap[(exterior|holes|((delta<18)&(semantic<16)))&~protected]=0
    yy,xx=np.indices(delta.shape)
    roi=((xx<380) if case['id']=='blonde' else (xx>430))&(yy>140)&(yy<480)
    warm=roi&(rgb[:,:,0]>210)&(rgb[:,:,1]>145)&(rgb[:,:,0]-rgb[:,:,2]>55)&(semantic<200)
    flash=action=='attack' and warm.sum()>=3
    if flash:
        support=(ndimage.distance_transform_edt(~warm)<40)&roi
        outside=(ndimage.distance_transform_edt(semantic<16)>3)&~support
        trimap[(delta>40)&~protected]=.5
        trimap[(semantic>240)&(delta>20)]=1
        trimap[outside]=0
        protected[outside]=False
    alpha=np.clip(estimate_alpha_cf(rgb/255,trimap),0,1)
    foreground=np.clip(estimate_foreground_ml(rgb/255,alpha),0,1)
    recovered=0
    if flash:
        recover,emission,unmixed=effects.emission_patch(rgb,semantic,protected,warm,roi,bg)
        alpha[recover],foreground[recover]=emission[recover],unmixed[recover]
        recovered=int((recover&(emission>0)).sum())
    # Thin crimson eye trails are colored foreground even when semantic matte misses them.
    if case['id']=='blonde' and action=='attack':
        red=(rgb[:,:,0]-rgb[:,:,1]>22)&(rgb[:,:,0]-rgb[:,:,2]>18)&(yy<330)&(xx>340)&~protected
        alpha[red]=np.maximum(alpha[red],np.clip((rgb[:,:,0]-np.maximum(rgb[:,:,1],rgb[:,:,2]))[red]/85,0,1))
        fg=np.clip((rgb-bg*(1-alpha[:,:,None]))/np.maximum(alpha[:,:,None],.02),0,255)/255
        foreground[red]=fg[red]
    alpha[protected]=1
    foreground[protected]=rgb[protected]/255
    alpha[exterior]=0
    alpha[alpha<.025]=0
    alpha[alpha>.995]=1
    rgba=np.rint(np.dstack((foreground,alpha))*255).astype('uint8')
    # Use raw backdrop RGB in the unmatting estimator, then retain its recovered RGB.
    clean,info=clean_flat_matte(Image.fromarray(np.dstack((rgb.astype('uint8'),rgba[:,:,3]))),tolerance=25,radius=3)
    cleaned=np.array(clean)
    changed=cleaned[:,:,3]<rgba[:,:,3]
    rgba[changed]=cleaned[changed]
    # Blonde generation includes a white sticker-like outer ring. Remove only bright,
    # low-chroma pixels next to transparency, never the protected white shirt interior.
    if case['id']=='blonde':
        depth=ndimage.distance_transform_edt(rgba[:,:,3]>32)
        core=depth>4
        distance,indices=ndimage.distance_transform_edt(~core,return_indices=True)
        prior=rgb[indices[0],indices[1]]
        rim=(depth<=4)&(distance<7)&(rgba[:,:,3]>0)&(chroma<30)&(rgb.mean(2)>prior.mean(2)+32)&(prior.mean(2)<145)
        # Hair has warm saturation; flash/smoke may also be bright and must survive.
        if action=='attack': rim &= ~((roi)&(semantic<128)) & ~((yy<330)&(xx>450))
        rgba[rim,3]=0
        labels,count=ndimage.label(rgba[:,:,3]>0)
        sizes=np.bincount(labels.ravel())
        detached=(labels>0)&(sizes[labels]<30)&(chroma<30)&(rgb.mean(2)>140)
        if action=='attack': detached &= ~roi & ~(yy<330)
        rgba[detached,3]=0
    rgba[rgba[:,:,3]==0]=0
    return Image.fromarray(rgba),dict(background=bg.tolist(),protectedPixels=int(protected.sum()),holes=int(holes.sum()),flash=bool(flash),emissionPixels=recovered,**{'unmatting':info})

def samples():
    OUT.mkdir(exist_ok=True)
    canvas=Image.new('RGB',(4*384,len(CASES)*2*384))
    draw=ImageDraw.Draw(canvas)
    for ci,case in enumerate(CASES):
        root=configure(case)
        for ai,action in enumerate(('idle','attack')):
            with av.open(str(root/action/'raw.mp4')) as video:
                for i,frame in enumerate(video.decode(video=0)):
                    if i not in (0,20): continue
                    cut,_=matte(frame.to_image(),case,action)
                    cut.save(root/action/f'sample-{i:03d}.png')
                    for bi,color in enumerate(('#142436','#fff4dc')):
                        back=Image.new('RGBA',cut.size,color);back.alpha_composite(cut)
                        col=(0 if i==0 else 2)+bi
                        canvas.paste(back.resize((384,384)).convert('RGB'),(col*384,(ci*2+ai)*384))
                    if i==20: break
            draw.text((5,(ci*2+ai)*384+5),case['id']+' '+action,fill='red')
            print('SAMPLE',case['id'],action,flush=True)
    canvas.save(OUT/'matte-samples.jpg',quality=95)

def build():
    cards=[]
    for case in CASES:
        for action in ('idle','attack'):
            p=OUT/case['id']/action
            if not (p/'game-animation.webp').exists(): continue
            rel=f'{case["id"]}/{action}'
            cards.append(f'<article><h2>{html.escape(case["label"])} · {action}</h2><img src="{rel}/game-animation.webp"><p><a href="{rel}/game-animation.gif">GIF</a> · <a href="{rel}/native-sheet.png">전체 PNG 시트</a> · <a href="{rel}/matte-review.jpg">밝은·어두운 배경</a></p></article>')
    (OUT/'preview.html').write_text(checks.page_head('금발·권총 누끼')+'<h1>금발·권총 바리에이션 · 8개 동작</h1><p>금발은 선택한 이전 그립 버전. 쿠나이 횡베기 제외. 768×768·24FPS, 원본 좌표 유지.</p>'+checks.buttons()+'<p><a href="character-variations-handoff.zip">전체 ZIP</a> · <a href="character-variations-gifs.zip">GIF ZIP</a></p><main>'+''.join(cards)+'</main></html>',encoding='utf-8')

def process():
    OUT.mkdir(exist_ok=True)
    for ci,case in enumerate(CASES):
        root=configure(case)
        for action in ('idle','attack'):
            folder=root/action
            frames=folder/'all-frames';frames.mkdir(exist_ok=True)
            report=folder/'matte-process.json'
            old=json.loads(report.read_text(encoding='utf-8')) if report.exists() else {}
            records={r['frame']:r for r in old.get('processed',[])}
            with av.open(str(folder/'raw.mp4')) as video:
                for i,frame in enumerate(video.decode(video=0)):
                    dest=frames/f'frame-{i:03d}.png'
                    if dest.exists() and i in records: continue
                    cut,info=matte(frame.to_image(),case,action)
                    cut.save(dest)
                    records[i]=dict(frame=i,**info)
                    if i%6==0:
                        save(report,dict(revision='selected-characters-v1',processed=list(records.values())))
                        save(OUT/'progress.json',dict(phase='matting',case=case['id'],action=action,frame=i,totalFrames=73,completedPairs=ci))
                        print('MATTED',case['id'],action,i,flush=True)
            assert len(records)==73
            save(report,dict(revision='selected-characters-v1',processed=list(records.values()),geometryUnchanged=True))
            save(folder/'review.json',dict(reviewed=False,note='원본 좌표·그림 크기를 유지했습니다. 얇은 총열과 원본 영상의 장비 변화는 남을 수 있습니다.'))
        save(root/'idle/selection.json',dict(start=0,end=71,note='Duplicate closing anchor omitted.'))
        base.export()
        for action in ('idle','attack'):
            native=json.loads((root/action/'native-frames.json').read_text(encoding='utf-8'))
            assert native['frameCount']==(72 if action=='idle' else 73)
            with Image.open(root/action/'game-animation.gif') as gif: assert gif.n_frames==native['frameCount']
        save(root/'validation.json',dict(fileChecksPassed=True,geometryUnchanged=True,sourcePreserved=True,visualReview='pending'))
        build();gc.collect()
    package()
    save(OUT/'progress.json',dict(phase='complete',completedPairs=4,totalActions=8))

def package():
    build()
    with zipfile.ZipFile(OUT/'character-variations-handoff.zip','w',zipfile.ZIP_DEFLATED) as bundle,zipfile.ZipFile(OUT/'character-variations-gifs.zip','w',zipfile.ZIP_DEFLATED) as gifs:
        bundle.write(OUT/'preview.html','preview.html')
        for case in CASES:
            root=OUT/case['id']
            for name in ('source-original.png','reference.png','source.json','validation.json','game-registration.json'):
                bundle.write(root/name,case['id']+'/'+name)
            for action in ('idle','attack'):
                folder=root/action
                for name in ('game-animation.gif','game-animation.webp','native-sheet.png','native-frames.json','game-sheet.png','game-frames.json','raw.mp4','settings.json','matte-review.jpg','review.json'):
                    bundle.write(folder/name,f'{case["id"]}/{action}/{name}')
                meta=json.loads((folder/'native-frames.json').read_text(encoding='utf-8'))
                for i in meta['sourceIndices']:
                    bundle.write(folder/'all-frames'/f'frame-{i:03d}.png',f'{case["id"]}/{action}/frames/frame-{i:03d}.png')
                gifs.write(folder/'game-animation.gif',f'{case["id"]}-{action}.gif')
    for name in ('character-variations-handoff.zip','character-variations-gifs.zip'):
        with zipfile.ZipFile(OUT/name) as z: assert z.testzip() is None
    print('PACKAGED',flush=True)

if __name__=='__main__':
    globals()[sys.argv[1] if len(sys.argv)>1 else 'process']()
