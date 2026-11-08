"""Repair the isolated sword's matte holes/outline without changing body motion."""
import json
from pathlib import Path
import sys
import zipfile

import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.verify_pixel_weapon_layers import weapon_transform,over

SOURCE=ROOT/'outputs/pixel-weapon-layers-20261019'
OUT=ROOT/'outputs/pixel-weapon-edge-20261019'
# Reviewed original blade silhouette. Includes dark contours and white blade
# pixels that the earlier flat-white matte removed. Ranges are inclusive.
ROWS={70:(64,69),71:(65,71),72:(66,72),73:(68,73),74:(68,75),75:(69,76),
      76:(71,76),77:(71,78),78:(72,78),79:(73,80),80:(74,81),81:(77,82),
      82:(78,84),83:(79,85),84:(80,86),85:(81,87),86:(83,87),87:(84,88),88:(85,88)}


def main():
    OUT.mkdir(exist_ok=True)
    settings=json.loads((SOURCE/'editor-settings.json').read_text(encoding='utf-8'))
    results=json.loads((SOURCE/'results.json').read_text(encoding='utf-8'))
    palette=np.array(results['palette'],np.int32)
    old=np.array(Image.open(SOURCE/'weapon.png').convert('RGBA'))
    raw=Image.open(ROOT/'outputs/pixel-minimax-right-20261019/reference-right-raw.png').convert('RGB')
    raw=np.array(raw.resize((128,128),Image.Resampling.NEAREST)).astype(np.int32)
    colors=palette[((raw[:,:,None,:]-palette[None,None,:,:])**2).sum(axis=3).argmin(axis=2)].astype(np.uint8)
    restored=old.copy();mask=np.zeros((128,128),bool)
    for y,(left,right) in ROWS.items():mask[y,left:right+1]=True
    restored[mask,:3]=colors[mask];restored[mask,3]=255
    # Native-resolution pixel redrawing, not a generated higher-resolution sword.
    # A single continuous tapered silhouette and four original palette colours.
    clean=old.copy();yy,xx=np.indices((128,128));clean[(yy>=70)&(xx>=64)]=0
    base=np.array([65.,71.]);tip=np.array([88.,88.]);axis=tip-base;length=np.linalg.norm(axis);direction=axis/length
    along=(xx-base[0])*direction[0]+(yy-base[1])*direction[1]
    normal=(xx-base[0])*(-direction[1])+(yy-base[1])*direction[0]
    t=np.clip(along/length,0,1);half=2.15-1.4*t
    blade=(along>=-1)&(along<=length+.3)&(np.abs(normal)<=half)
    border=(np.abs(normal)>half-.85)|(along>length-.9)
    clean[blade]=[181,177,179,255]
    clean[blade&(normal<-.15)]=[252,251,249,255]
    clean[blade&(normal>.6)]=[103,113,155,255]
    clean[blade&border]=[26,33,57,255]
    variants={'before':(old,False),'restored':(restored,False),'crisp':(clean,True)}
    for name,(weapon,fixed) in variants.items():
        folder=OUT/name;folder.mkdir(exist_ok=True);Image.fromarray(weapon).save(folder/'weapon.png')
        frames=[];sheet=Image.new('RGBA',(1024,128))
        for i,f in enumerate(settings['frames']):
            body=np.array(Image.open(SOURCE/'body'/f'frame-{i:02d}.png').convert('RGBA'))
            hand=np.array(Image.open(SOURCE/'hand'/f'frame-{i:02d}.png').convert('RGBA'))
            moved,_=weapon_transform(weapon,f['grip'],0 if fixed else f['angle'])
            a=over(over(body,moved),hand)
            assert set(np.unique(a[:,:,3]))<={0,255}
            assert {tuple(c) for c in np.unique(a[:,:,:3][a[:,:,3]>0],axis=0)}<={tuple(c) for c in palette}
            assert np.array_equal(a[(moved[:,:,3]==0)&(hand[:,:,3]==0)],body[(moved[:,:,3]==0)&(hand[:,:,3]==0)])
            image=Image.fromarray(a);frames.append(image);image.save(folder/f'frame-{i:02d}.png');sheet.paste(image,(i*128,0))
        sheet.save(folder/'sheet.png')
        frames[0].save(folder/'animation.png',save_all=True,append_images=frames[1:],duration=settings['frameDurationMs'],loop=0,disposal=0,blend=0)
        large=[f.resize((512,512),Image.Resampling.NEAREST) for f in frames]
        large[0].save(folder/'animation.webp',save_all=True,append_images=large[1:],duration=settings['frameDurationMs'],loop=0,lossless=True)
    comparison=Image.new('RGB',(8*240,3*270),'#ddd');d=ImageDraw.Draw(comparison)
    for row,name in enumerate(variants):
        for i in range(8):
            image=Image.open(OUT/name/f'frame-{i:02d}.png').convert('RGBA').resize((240,240),Image.Resampling.NEAREST)
            comparison.paste(image,(i*240,row*270+25),image);d.text((i*240+5,row*270+5),f'{name} / {i+1}',fill='black')
    comparison.save(OUT/'comparison.png')
    doc=dict(palette=results['palette'],bodyMotionUnchanged=True,newInference=False,manualRestorationRows=ROWS,
             missingOriginalBladePixels=int(np.sum(mask&(old[:,:,3]==0))),
             addedDarkOriginalPixels=int(np.sum(mask&(old[:,:,3]==0)&(colors[:,:,0]<70))),
             variants={'before':'previous isolated sword','restored':'original RGB/contour restored; same rotation',
                       'crisp':'manually redrawn 128px 4-color blade; original handle; translation only'},
             limitation='The fixed-angle version trades weapon sway for stable pixel contours. Manual masks/redrawing apply only to this reference.')
    (OUT/'results.json').write_text(json.dumps(doc,indent=2),encoding='utf-8')
    cards=''.join(f'<article><h2>{label}</h2><div class="checker"><img src="{name}/animation.webp"></div><p>{detail}</p><a href="{name}/sheet.png">PNG 시트</a> · <a href="{name}/animation.png">APNG</a></article>' for name,label,detail in [
        ('before','이전 검','외곽선과 밝은 검날 일부가 빠진 추출본'),('restored','원본 윤곽 복원','원본 RGB에서 빠진 검날 픽셀·어두운 외곽선 복원. 기존 각도 움직임 유지.'),('crisp','검날 도트 정리 + 각도 고정','검날을 실제 128px에서 4색으로 다시 정리. 손 위치만 따라가며 각도는 고정해 회전 계단 변화 억제.')])
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>검 윤곽 보정 비교</title><style>body{background:#171923;color:#eee;font:15px/1.65 system-ui;margin:24px}main{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}article{background:#282c39;padding:16px;border-radius:12px}h2{font-size:18px}.checker{background:repeating-conic-gradient(#ddd 0 25%,#f8f8f8 0 50%) 0/20px 20px}img{width:100%;image-rendering:pixelated}a{color:#bacaff}@media(max-width:850px){main{grid-template-columns:1fr}}</style><h1>캐릭터는 그대로 · 검 윤곽만 비교</h1><p>새 영상·모델 생성 없이 같은 몸/손/얼굴/8프레임에 검만 바꿨습니다. 원본 32색과 이진 알파를 유지합니다. 세 번째는 수동 도트 정리한 검날이며 원본 RGB를 그대로 복사한 버전과 구분합니다.</p><main>'''+cards+'''</main><p><a href="weapon-edge-comparison.zip">PNG·검 파츠·시트 ZIP</a> · <a href="../pixel-weapon-layers-20261019/preview.html">이전 위치 편집 화면</a></p><h2>프레임 비교</h2><img src="comparison.png"><p>각도 고정은 윤곽 흔들림을 줄이는 대신 검의 각도 변화가 없어집니다. 검이 휘둘러지는 공격에는 각 포즈별 도트 재정리가 필요합니다.</p></html>'''
    (OUT/'preview.html').write_text(page,encoding='utf-8')
    with zipfile.ZipFile(OUT/'weapon-edge-comparison.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for name in variants:
            for p in (OUT/name).iterdir():archive.write(p,p.relative_to(OUT).as_posix())
        for name in ('preview.html','comparison.png','results.json'):archive.write(OUT/name,name)
    print('RESTORED missing blade pixels:',doc['missingOriginalBladePixels'],'including dark:',doc['addedDarkOriginalPixels'])
    print('PREVIEW',OUT/'preview.html')


if __name__=='__main__':main()
