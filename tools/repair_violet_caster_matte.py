"""Re-matte original caster video frames with closed-form alpha estimation.

Old exports are immutable inputs. No video regeneration, geometry changes or
synthetic effects. Interior seeds protect real neutral costume details; a
measured grey trimap removes neutral spill and enclosed background gaps.
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import av
import numpy as np
from PIL import Image,ImageDraw
from scipy import ndimage
from pymatting import estimate_alpha_cf,estimate_foreground_ml
from tools import verify_violet_caster_motion as caster

PREVIOUS=ROOT/'outputs/violet-caster-motion-20261024'
OUT=ROOT/'outputs/violet-caster-matte-v2-20261024'


def configure():
    caster.OUT=OUT;caster.configure()


def link_copy(source,dest):
    if dest.exists():return
    try:os.link(source,dest)
    except OSError:shutil.copy2(source,dest)


def rematte(raw,previous):
    rgb=np.array(raw.convert('RGB'),dtype=np.float64);image=rgb/255
    border=np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1]));bg=np.median(border,axis=0)
    delta=np.max(np.abs(rgb-bg),axis=2);chroma=np.ptp(rgb,axis=2);lum=rgb.mean(2)
    old=np.array(previous.convert('RGBA'))[:,:,3]
    protect=ndimage.distance_transform_edt(old>230)>2.5
    neutral=(chroma<16)&(lum>82)&(lum<162)&~protect
    trimap=np.full(delta.shape,.5,dtype=np.float64)
    trimap[(delta>40)|protect]=1
    trimap[((delta<9)|neutral)&~protect]=0
    alpha=np.clip(estimate_alpha_cf(image,trimap),0,1)
    foreground=np.clip(estimate_foreground_ml(image,alpha),0,1)
    # Suppress tiny isolated video-compression dots, never the large spell orb.
    labels,n=ndimage.label(alpha>.03,structure=np.ones((3,3)))
    sizes=np.bincount(labels.ravel());small=sizes[labels]<3;small[labels==0]=False
    alpha[small&~protect]=0;alpha[alpha<.02]=0;alpha[alpha>.995]=1
    alpha[protect]=1
    rgba=np.rint(np.dstack((foreground,alpha))*255).astype('uint8');rgba[alpha==0]=0
    return Image.fromarray(rgba),dict(background=bg.tolist(),protectedInteriorPixels=int(protect.sum()),
        neutralBgSeeds=int(neutral.sum()),unknownPixels=int((trimap==.5).sum()),
        oldNeutralOpaquePixels=int(((old>128)&neutral).sum()),newNeutralOpaquePixels=int(((rgba[:,:,3]>128)&neutral).sum()),
        opaqueInteriorPreserved=bool(np.all(rgba[:,:,3][protect]==255)))


def process():
    configure();OUT.mkdir(exist_ok=True)
    for name in ['source-original.png','source.json','reference.png']:
        link_copy(PREVIOUS/name,OUT/name)
    for name in caster.ACTIONS:
        src=PREVIOUS/name;dest=OUT/name;dest.mkdir(exist_ok=True);framesdir=dest/'all-frames';framesdir.mkdir(exist_ok=True)
        for filename in ['raw.mp4','settings.json','native-v1-workflow.json','reference-prepared.png','review-raw.webp','selection.json']:
            if (src/filename).exists():link_copy(src/filename,dest/filename)
        records=[]
        with av.open(str(src/'raw.mp4')) as video:
            for i,frame in enumerate(video.decode(video=0)):
                old=Image.open(src/'all-frames'/f'frame-{i:03d}.png').convert('RGBA')
                image,info=rematte(frame.to_image(),old);image.save(framesdir/f'frame-{i:03d}.png')
                records.append(dict(frame=i,**info))
                if i%18==0:print('REMATTED',name,i,flush=True)
        assert all(x['opaqueInteriorPreserved'] for x in records)
        caster.save(dest/'matte-v2.json',dict(method='Closed-form alpha with protected interior and neutral grey seeds; multilevel foreground colour estimation',
            priorExport=str(src),rawVideoUnchanged=True,geometryUnchanged=True,newEffectsDrawn=False,frames=records))
        review=json.loads((src/'review.json').read_text(encoding='utf-8'))
        review['note']+=' 원본 영상에서 경계 투명도와 전경색을 다시 계산해 회색 번짐·틈의 잔여 배경·효과 가장자리의 손상을 줄였습니다. 얇은 마법 효과에는 원본 영상의 압축 흔들림이 남을 수 있습니다.'
        review.update(matteRevision='closed-form-v2',previousExportPreserved=True,rawVideoUnchanged=True)
        caster.save(dest/'review.json',review)
        print('ACTION_REMATTED',name,len(records),flush=True)
    caster.export();comparison();caster.check()
    # Add the cleanup evidence to the final handoff without rebuilding media.
    import zipfile
    with zipfile.ZipFile(OUT/'violet-caster-idle-attack.zip','a',zipfile.ZIP_DEFLATED) as z:
        for name in caster.ACTIONS:z.write(OUT/name/'matte-v2.json',name+'/matte-v2.json')
        z.write(OUT/'matte-before-after.jpg','matte-before-after.jpg')
    with zipfile.ZipFile(OUT/'violet-caster-idle-attack.zip') as z:assert z.testzip() is None
    print('MATTE_V2_COMPLETE',flush=True)


def comparison():
    # Identical source coordinates and magnification, two backgrounds.
    cases=[('idle',18),('attack',36)]
    canvas=Image.new('RGB',(2048,1024));draw=ImageDraw.Draw(canvas)
    for row,(name,i) in enumerate(cases):
        for col,root in enumerate([PREVIOUS,OUT]):
            im=Image.open(root/name/'all-frames'/f'frame-{i:03d}.png').convert('RGBA')
            for theme,color in enumerate(['#142436','#fff4dc']):
                bg=Image.new('RGBA',im.size,color);bg.alpha_composite(im)
                panel=bg.resize((512,512)).convert('RGB')
                x=(theme*2+col)*512;y=row*512
                canvas.paste(panel,(x,y));draw.text((x+8,y+8),f'{name} {i} '+('BEFORE' if col==0 else 'AFTER'),fill='red')
    canvas.save(OUT/'matte-before-after.jpg',quality=97)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['process','comparison']);stage=parser.parse_args().stage
    globals()[stage]()
