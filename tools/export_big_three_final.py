"""Finish selected v1/v3 takes without touching rejected generations."""
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
from tools import export_big_three_motion as batch

OUT=ROOT/'outputs/big-three-final-20261024'
REVISION='big-three-final-alpha-v2'
ORIGINAL_MATTE=batch.matte
batch.OUT=OUT
batch.NOTES['02-desmond-kilroy']['idle']='소총을 낮게 든 자세에서 어깨에 올려 잠시 왼쪽을 조준하고 다시 내립니다. 마스크·총기·위장 무늬에 생성 변화가 남습니다.'
batch.NOTES['03-van-rieden']['idle']='지팡이를 짚은 채 시가 연기가 위로 말려 올라가고, 망토와 고개가 작게 움직입니다. 옷·시가·연기 세부에 생성 변화가 남습니다.'
batch.NOTES['03-van-rieden']['attack']='등의 소총을 꺼내 왼쪽으로 조준·발사하고 다시 멥니다. 꺼내는 도중 오른쪽·위쪽 총끝과 발사 섬광 일부가 원본 영상 가장자리에서 잘립니다. 지팡이·손·총 형태에도 생성 변화가 남습니다.'

def save(path,obj):batch.save(path,obj)

def matte(raw,case,action):
    cut,info=ORIGINAL_MATTE(raw,case,action)
    if case['id']=='03-van-rieden' and action=='idle':
        rgb=np.asarray(raw.convert('RGB'),dtype=float);rgba=np.array(cut)
        border=np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1]));bg=np.median(border,axis=0)
        yy,xx=np.indices(rgb.shape[:2]);lum=rgb.mean(2)
        # Recover the observed bright neutral cigar smoke. The grey key is
        # unmixed once, retaining its soft coverage on light and dark backgrounds.
        region=(xx>245)&(xx<450)&(yy>30)&(yy<245)&(rgba[:,:,3]<220)
        neutral=np.ptp(rgb,axis=2)<28;signal=lum-bg.mean()
        smoke=ndimage.binary_propagation(region&neutral&(signal>18),mask=region&neutral&(signal>6))
        alpha=np.clip(np.max((rgb-bg)/np.maximum(255-bg,1),axis=2),0,1)
        foreground=np.clip((rgb-bg*(1-alpha[:,:,None]))/np.maximum(alpha[:,:,None],.01),0,255)
        recover=smoke&(alpha>.04)
        rgba[recover,:3]=np.rint(foreground[recover]).astype('uint8')
        rgba[recover,3]=np.rint(alpha[recover]*255).astype('uint8')
        rgba[rgba[:,:,3]==0,:3]=0;cut=Image.fromarray(rgba)
        info['cigarSmokePixelsRecovered']=int(recover.sum())
    return cut,info

def review_samples():
    for case in batch.CASES:
        root=OUT/case['id'];contact=Image.new('RGB',(1536,1024));draw=ImageDraw.Draw(contact)
        samples=[('idle',31),('attack',46 if case['id'].startswith(('01','03')) else 31)]
        for row,(action,index) in enumerate(samples):
            existing=root/action/'all-frames'/f'frame-{index:03d}.png'
            if existing.exists() and (root/action/'frames.json').exists():cut=Image.open(existing).convert('RGBA')
            else:
                with av.open(str(root/action/'raw.mp4')) as video:
                    for i,f in enumerate(video.decode(video=0)):
                        if i==index:cut,_=matte(f.to_image(),case,action);break
            cut.save(root/action/f'matte-test-{index:03d}.png')
            for col,color in enumerate(['#142436','#fff4dc','#226b54']):
                bg=Image.new('RGBA',cut.size,color);bg.alpha_composite(cut)
                contact.paste(bg.resize((512,512)).convert('RGB'),(col*512,row*512));draw.text((col*512+8,row*512+8),f'{action} {index}',fill='red')
        contact.save(root/'matte-tests.jpg',quality=97);print('REVIEW_SAMPLES',case['id'],flush=True)

def process():
    for case in batch.CASES:
        root=batch.configure(case)
        assert batch.digest(batch.base.SOURCE)==batch.digest(root/'source-original.png')
        for action in ['idle','attack']:
            folder=root/action
            if (folder/'frames.json').exists():continue
            frames=folder/'all-frames';frames.mkdir(exist_ok=True)
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
                        print('MATTED_FINAL',case['id'],action,i,flush=True)
            assert len(records)==73
            save(folder/'matte-process.json',dict(revision=REVISION,processed=list(records.values()),geometryUnchanged=True,originalVideoPreserved=True))
            save(folder/'review.json',dict(reviewed=False,userApproval='pending',note=batch.NOTES[case['id']][action],generatedDetailDrift=True))
        save(root/'idle/selection.json',dict(start=0,end=71,note='Closing duplicate omitted; all other forward frames retained.'))
        batch.base.export();batch.checks.REVISION=REVISION;batch.validate(case);batch.build_all()
        print('FINAL_CASE_READY',case['id'],flush=True)

def inspect():
    report={}
    for case in batch.CASES:
        report[case['id']]={}
        for action in ['idle','attack']:
            folder=OUT/case['id']/action;records=[]
            for p in sorted((folder/'all-frames').glob('frame-*.png')):
                rgba=np.array(Image.open(p).convert('RGBA'));alpha=rgba[:,:,3]
                assert not rgba[alpha==0,:3].any()
                records.append(dict(frame=int(p.stem.split('-')[-1]),coverage=int((alpha>16).sum()),opaque=int((alpha>240).sum())))
            assert len(records)==73
            report[case['id']][action]=records
    save(OUT/'alpha-coverage.json',report)
    print('ALPHA_INTEGRITY_OK',flush=True)

def package():
    inspect();batch.checks.REVISION=REVISION;batch.package()
    # Include selection provenance, including the exact original v3 graphs.
    for case in batch.CASES:
        root=OUT/case['id'];archive=root/(case['id']+'-idle-attack.zip')
        with zipfile.ZipFile(archive,'a',zipfile.ZIP_DEFLATED) as z:
            for action in ['idle','attack']:
                for name in ['selected-take.json','native-v3-workflow.json','native-v4-workflow.json']:
                    p=root/action/name
                    if p.exists():z.write(p,action+'/'+name)
        with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    archive=OUT/'big-three-all-idle-attack.zip'
    with zipfile.ZipFile(archive,'a',zipfile.ZIP_DEFLATED) as z:
        z.write(OUT/'alpha-coverage.json','alpha-coverage.json')
        z.write(OUT/'take-selection.json','take-selection.json')
        for case in batch.CASES:
            for action in ['idle','attack']:
                for name in ['selected-take.json','native-v3-workflow.json','native-v4-workflow.json']:
                    p=OUT/case['id']/action/name
                    if p.exists():z.write(p,case['id']+'/'+action+'/'+name)
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    gifs=OUT/'big-three-gifs.zip'
    with zipfile.ZipFile(gifs,'w',zipfile.ZIP_DEFLATED) as z:
        for case in batch.CASES:
            for action in ['idle','attack']:
                z.write(OUT/case['id']/action/'game-animation.gif',case['label']+'_'+action+'.gif')
        z.writestr('README.txt','Six transparent 512px GIF previews at the original 24FPS timing (10ms GIF time-grid rounding).\nFor native 768x768 cells and soft alpha, use the full PNG/WebP package.\nVan Rieden back-rifle draw and muzzle flash are partly clipped in the original video.\n')
    with zipfile.ZipFile(gifs) as z:assert z.testzip() is None
    print('SELECTED_TAKES_FINAL_HANDOFF_READY',archive,flush=True)

if __name__=='__main__':globals()[sys.argv[1] if len(sys.argv)>1 else 'review_samples']()
