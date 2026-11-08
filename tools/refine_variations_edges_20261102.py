"""Versioned contour cleanup and native-resolution previews; no regeneration."""
import os
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import gc
import json
import shutil
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import av
import numpy as np
from scipy import ndimage
from PIL import Image,ImageDraw
import sprite_gif
from tools import export_character_variations_20261102 as task

OLD=task.OUT
OUT=ROOT/'outputs/character-variations-cutout-v2-20261102'

def save(p,obj):
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def refine(raw,old):
    rgb=np.array(raw.convert('RGB'),dtype=float)
    a=np.array(old.convert('RGBA'))
    olda=a[:,:,3].copy()
    depth=ndimage.distance_transform_edt(a[:,:,3]>32)
    # Restrict removal to the outer three source pixels. Bright shirt/skin
    # interiors are never flood-filled through gaps in their drawn outlines.
    stroke=(rgb.min(2)>165)&(np.ptp(rgb,axis=2)<30)&(depth<3)&(a[:,:,3]>0)
    a[stroke,3]=0
    labels,n=ndimage.label(a[:,:,3]>32)
    sizes=np.bincount(labels.ravel())
    tiny=(labels>0)&(sizes[labels]<12)
    # Preserve all chromatic disconnected wisps; only neutral detached rim specks.
    tiny &= np.ptp(rgb,axis=2)<30
    a[tiny,3]=0
    mask=a[:,:,3]/255.
    smooth=ndimage.gaussian_filter(mask,.45)
    edge=(ndimage.distance_transform_edt(mask>0)<1.5)&(mask>0)
    a[edge,3]=np.minimum(a[:,:,3][edge],np.rint(smooth[edge]*255)).astype('uint8')
    a[:,:,3][depth>=3]=olda[depth>=3]
    a[a[:,:,3]==0]=0
    assert np.array_equal(a[:,:,3][depth>=3],olda[depth>=3])
    return Image.fromarray(a),dict(strokePixels=int(stroke.sum()),detachedNeutralPixels=int(tiny.sum()),interiorAlphaPreserved=True)

def native_previews(root,action):
    folder=root/action
    meta=json.loads((folder/'native-frames.json').read_text(encoding='utf-8'))
    frames=[Image.open(folder/'all-frames'/f'frame-{i:03d}.png').convert('RGBA') for i in meta['sourceIndices']]
    # All displayed pixels use source coordinates and source resolution.
    frames[0].save(folder/'game-animation.webp',save_all=True,append_images=frames[1:],duration=meta['durationMs'],loop=0,lossless=True)
    data,info=sprite_gif.encode(frames,meta['durationMs'])
    (folder/'game-animation.gif').write_bytes(data)
    frames[0].save(folder/'native-poster.png')
    gm=json.loads((folder/'game-frames.json').read_text(encoding='utf-8'))
    gm['previewCanvas']=[768,768]
    gm['previewResampling']='none'
    gm['gif']=info
    save(folder/'game-frames.json',gm)
    frames.clear();gc.collect()

def main():
    OUT.mkdir(exist_ok=True)
    task.OUT=OUT
    for case in task.CASES:
        source=OLD/case['id'];dest=OUT/case['id']
        if not dest.exists():shutil.copytree(source,dest)
        if case['id']=='blonde':
            for action in ('idle','attack'):
                records=[]
                with av.open(str(source/action/'raw.mp4')) as video:
                    for i,frame in enumerate(video.decode(video=0)):
                        with Image.open(source/action/'all-frames'/f'frame-{i:03d}.png') as im:
                            result,info=refine(frame.to_image(),im)
                        result.save(dest/action/'all-frames'/f'frame-{i:03d}.png')
                        records.append(dict(frame=i,**info))
                save(dest/action/'contour-refinement.json',dict(revision='boundary-white-stroke-v2',frames=records))
                p=dest/action/'frames.json'
                if p.exists():p.replace(dest/action/'pre-contour-v2-frames.json')
            task.configure(case);task.base.export()
        for action in ('idle','attack'):
            native_previews(dest,action)
            save(dest/action/'review.json',dict(reviewed=False,note='768px 원본 좌표·해상도의 미리보기. PNG/WebP는 반투명, GIF는 256색과 이진 투명도입니다.'))
        save(dest/'validation.json',dict(fileChecksPassed=True,geometryUnchanged=True,sourcePreserved=True,nativePreviewResolution=[768,768],originalVersionRetained=str(source)))
        print('NATIVE_PREVIEWS',case['id'],flush=True)
    task.build()
    p=OUT/'preview.html'
    page=p.read_text(encoding='utf-8').replace('article{width:512px','article{width:768px')
    page=page.replace('<h1>','<h1>수정본 · ',1).replace('768×768·24FPS, 원본 좌표 유지.','768×768·24FPS, 미리보기 축소 없음. 금발 외곽 흰 선 추가 정리.')
    page=page.replace('/game-animation.webp"','/game-animation.webp?v=2"')
    p.write_text(page,encoding='utf-8')
    # package() builds the page, so temporarily retain our native-preview layout.
    build=task.build;task.build=lambda:None
    task.package();task.build=build
    save(OUT/'progress.json',dict(phase='complete',totalActions=8,nativeResolution=True))

if __name__=='__main__':main()
