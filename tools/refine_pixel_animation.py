"""Refine the reviewed pixel experiment with explicit original-pixel part locks.

No trained adapter, GPU inference, automatic segmentation or frame interpolation.
Hand-authored masks are intentionally exported so this is not mistaken for an
automatic general-purpose character rig.
"""
import hashlib
import html
import json
from pathlib import Path
import sys
import zipfile

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.verify_pixel_animation import checker

INPUT=ROOT/'outputs/pixel-animation-test-20261019'
OUTPUT=ROOT/'outputs/pixel-animation-refine-20261019'
VERSION='pixel-parts-floor-lock-v2'
SWORD=[(73,64),(78,64),(78,67),(81,67),(82,73),(91,96),(91,101),(85,101),(75,76),(72,72),(71,68)]
LEFT_ARM=[(52,38),(57,39),(57,46),(55,53),(55,58),(55,65),(55,70),(49,70),(49,58),(50,49),(51,43)]
RIGHT_ARM=[(71,38),(75,40),(75,51),(77,56),(79,59),(79,65),(77,68),(74,68),(73,59),(71,53),(71,47),(70,43)]


def polygon(points):
    result=Image.new('L',(128,128));ImageDraw.Draw(result).polygon(points,fill=255)
    return np.asarray(result)>0


def part(source,mask):
    a=np.asarray(source).copy();a[~mask]=0
    return Image.fromarray(a)


def split_source(source):
    a=np.asarray(source);fg=a[:,:,3]>0
    yy,xx=np.indices(fg.shape)
    # Remove the generated floor shadow; it is not a character part.
    floor=(yy>=101)&(a[:,:,0]==181)&(a[:,:,1]==177)&(a[:,:,2]==179)
    sword=polygon(SWORD)&fg&~floor
    right=polygon(RIGHT_ARM)&fg&~sword
    left=polygon(LEFT_ARM)&fg&~sword&~right
    torso=fg&(yy<79)&~sword&~right&~left
    masks=dict(torso=torso,left_arm=left,right_arm=right,sword=sword)
    parts={name:part(source,mask) for name,mask in masks.items()}
    return parts,masks


def warp_rows(image,phase,begin,end):
    """Integer row shifts; pivot stays fixed and source RGB is copied exactly."""
    a=np.asarray(image);result=np.zeros_like(a)
    for y in range(128):
        shift=round(phase*min(1,max(0,(y-begin)/max(1,end-begin))))
        if shift>=0: result[y,shift:]=a[y,:128-shift]
        else: result[y,:128+shift]=a[y,-shift:]
    return Image.fromarray(result)


def leg_component(frame):
    a=np.asarray(frame).copy();yy,xx=np.indices(a.shape[:2])
    # Closed white matte holes are not boots. This palette has no white clothing
    # in the lower-leg region, so this rule is specific to the reviewed knight.
    white=np.min(a[:,:,:3],axis=2)>220
    candidate=(a[:,:,3]>0)&~white&(yy>=76)&(yy<=111)&(xx>=35)&(xx<78)
    # At the upper-right corner a few blade pixels can touch the generated coat.
    # This manually reviewed ROI belongs to the weapon, never the thigh.
    candidate &= ~((xx>=74)&(yy<88))
    labels,count=ndimage.label(candidate,structure=np.ones((3,3)))
    seeds=labels[76:82,54:73]
    keep=np.unique(seeds[seeds>0])
    selected=np.isin(labels,keep)&candidate
    if not selected.any():raise RuntimeError('No connected leg pixels found')
    # A sword component must not be used as a leg or to measure the ground.
    rows,cols=np.where(selected)
    box=(int(cols.min()),76,int(cols.max())+1,int(rows.max())+1)
    a[~selected]=0
    return Image.fromarray(a),box


def fit_legs(frame,bob):
    layer,box=leg_component(frame)
    a=np.asarray(layer);visible=a[:,:,3]>0
    # Align the existing pelvis rather than centering the moving feet/sword.
    pelvis_y,pelvis_x=np.where(visible[78:82])
    center=float(np.median(pelvis_x)) if len(pelvis_x) else (box[0]+box[2])/2
    dx=round(63-center)
    crop=layer.crop(box)
    top=76+bob;ground=107
    resized=crop.resize((crop.width,ground+1-top),Image.Resampling.NEAREST)
    full=Image.new('RGBA',(128,128));full.paste(resized,(box[0]+dx,top))
    # Some source columns stop higher than their bounding rectangle. Measure real
    # alpha and correct with integer translation, never scale a whole character.
    bounds=full.getbbox()
    floor_delta=ground-(bounds[3]-1)
    if floor_delta:
        shifted=Image.new('RGBA',full.size);shifted.paste(full,(0,floor_delta));full=shifted
    return full,dict(sourceBox=list(box),pelvisCenter=center,translateX=dx,targetTop=top,groundY=107)


def shifted(image,dx,dy):
    out=Image.new('RGBA',image.size);out.paste(image,(dx,dy));return out


def render(source,parts,frame,index):
    # Contact/down, passing/up, opposite contact/down, opposite passing/up.
    bob=[1,0,1,0][index]
    swing=[-1,0,1,0][index]
    legs,alignment=fit_legs(frame,bob)
    body=parts['torso']
    # Move only coat hem clusters horizontally, never stretch the face/torso.
    body=warp_rows(body,-swing,57,78)
    left=warp_rows(parts['left_arm'],-swing,41,64)
    right=warp_rows(parts['right_arm'],swing,42,64)
    sword=shifted(parts['sword'],swing,bob)
    result=Image.new('RGBA',(128,128))
    for layer in (legs,shifted(left,0,bob),shifted(body,0,bob),shifted(right,0,bob),sword):
        result.alpha_composite(layer)
    # Clean masks should create no translucent pixels. RGB blending is not used.
    allowed={tuple(c) for c in np.unique(np.asarray(source)[:,:,:3][np.asarray(source)[:,:,3]>0],axis=0)}
    a=np.asarray(result);colors={tuple(c) for c in np.unique(a[:,:,:3][a[:,:,3]>0],axis=0)}
    assert colors<=allowed
    assert set(np.unique(a[:,:,3]))<={0,255}
    # Exact head and object pixel identity is checked relative to their translated
    # positions. Their placement can change, but colors and shape cannot morph.
    head_box=(54,17,73,34)
    expected=np.asarray(source.crop(head_box)).copy()
    expected[expected[:,:,3]==0]=0
    assert np.array_equal(np.asarray(result.crop((54,17+bob,73,34+bob))),expected)
    sa=np.asarray(sword);sv=sa[:,:,3]>0
    assert np.array_equal(a[sv],sa[sv])
    assert result.getbbox()[3]-1==107
    return result,dict(index=index,bob=bob,armSwing=swing,legAlignment=alignment,
                       swordOffset=[swing,bob],headRGBAExact=True,swordRGBAExact=True,
                       visibleColors=len(colors),groundY=result.getbbox()[3]-1)


def animation(out,name,frames):
    sheet=Image.new('RGBA',(128*len(frames),128))
    for i,frame in enumerate(frames):
        frame.save(out/f'{name}-{i:02d}.png');sheet.paste(frame,(i*128,0))
    sheet.save(out/f'{name}-sheet.png')
    frames[0].save(out/f'{name}.png',save_all=True,append_images=frames[1:],duration=170,loop=0,disposal=0,blend=0)
    large=[frame.resize((512,512),Image.Resampling.NEAREST) for frame in frames]
    large[0].save(out/f'{name}.webp',save_all=True,append_images=large[1:],duration=170,loop=0,lossless=True)


def main():
    sys.stdout.reconfigure(encoding='utf-8');out=OUTPUT;out.mkdir(exist_ok=True)
    source=Image.open(INPUT/'reference.png').convert('RGBA')
    source_array=np.asarray(source)
    palette=np.unique(source_array[:,:,:3][source_array[:,:,3]>0],axis=0).tolist()
    source.save(out/'reference.png')
    original=[Image.open(INPUT/f'frame-{i:02d}.png').convert('RGBA') for i in range(4)]
    parts,masks=split_source(source)
    for name,image in parts.items():
        image.save(out/f'part-{name}.png')
        Image.fromarray(masks[name].astype(np.uint8)*255).save(out/f'mask-{name}.png')
    final=[];records=[]
    for i,frame in enumerate(original):
        result,record=render(source,parts,frame,i);final.append(result);records.append(record)
    animation(out,'before',original);animation(out,'corrected',final)
    comparison=checker((320*5,710));draw=ImageDraw.Draw(comparison)
    for row,frames in enumerate((original,final)):
        for column,frame in enumerate([source]+frames):
            up=frame.resize((320,320),Image.Resampling.NEAREST)
            x=column*320;y=row*355+30;comparison.paste(up,(x,y),up)
            draw.text((x+12,row*355+10),'REFERENCE' if column==0 else f'{"V1" if row==0 else "V2"} FRAME {column}',fill='black')
    comparison.save(out/'comparison.png')
    part_view=checker((320*4,350));d=ImageDraw.Draw(part_view)
    for i,(name,image) in enumerate(parts.items()):
        up=image.resize((320,320),Image.Resampling.NEAREST);part_view.paste(up,(i*320,30),up);d.text((i*320+12,8),name,fill='black')
    part_view.save(out/'parts.png')
    doc=dict(version=VERSION,referenceSHA256=hashlib.sha256((INPUT/'reference.png').read_bytes()).hexdigest(),
             method='Original-pixel torso/head, integer arm/coat shifts and rigid original sword; existing Qwen-generated legs aligned to pelvis/floor with nearest resizing.',
             automaticSegmentation=False,newInference=False,training=False,frameDurationMs=170,palette=palette,
             masks=dict(leftArm=LEFT_ARM,rightArm=RIGHT_ARM,sword=SWORD),frames=records,
             limitations=['Manual masks for this character only','Leg shape and four-keyframe gait are still generated; no guarantee of natural motion','Nearest leg resize can change pixel clusters','Hidden body areas are not reconstructed'])
    (out/'results.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
    with zipfile.ZipFile(out/'pixel-animation-v2.zip','w',zipfile.ZIP_DEFLATED) as archive:
        files=['reference.png','corrected.png','corrected-sheet.png']
        files += [f'corrected-{i:02d}.png' for i in range(4)]
        files += [f'{kind}-{name}.png' for kind in ('part','mask') for name in parts]
        for filename in files:archive.write(out/filename,filename)
        archive.write(out/'results.json','results.json')
    (out/'preview.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>도트 애니메이션 V2 · 원본 파츠 보존</title><style>body{background:#171923;color:#eef0fa;font:15px/1.65 system-ui;margin:24px}h1{font-size:25px}main{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}article{background:#242735;border:1px solid #474d65;border-radius:12px;padding:16px;min-width:0}.checker{background:repeating-conic-gradient(#ddd 0 25%,#f7f7f7 0 50%) 0/24px 24px}.pixel{image-rendering:pixelated;width:100%;max-width:512px}.wide{width:100%;image-rendering:pixelated}a{color:#bdcaff}pre{white-space:pre-wrap}.controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:16px 0}button,input{font:inherit}button{padding:8px 16px}canvas{image-rendering:pixelated;width:100%}@media(max-width:800px){main{grid-template-columns:1fr}}</style><h1>도트 애니메이션 V2 · 원본 파츠 보존</h1><p>학습 없이 보정했습니다. 머리·몸통은 원본, 팔·코트는 정수 픽셀 이동, 검은 원본 모양 그대로 손과 함께 이동합니다. 다리는 앞선 Qwen 생성본의 골반·바닥 위치를 맞춘 결과입니다. 수동 마스크를 사용했고 자동 파츠 인식은 아닙니다.</p><div class="controls"><button id="play">일시 정지</button><label>재생 속도 <input id="speed" type="range" min="2" max="10" value="6"> <span id="fps">6</span> FPS</label><label>프레임 <input id="frame" type="range" min="0" max="3" value="0"> <span id="current">1 / 4</span></label></div><main><article><h2>기준 캐릭터</h2><div class="checker"><img class="pixel" src="reference.png"></div></article><article><h2>V1 · 전체 생성</h2><div class="checker"><canvas id="before" width="128" height="128"></canvas></div></article><article><h2>V2 · 원본 파츠 유지</h2><div class="checker"><canvas id="corrected" width="128" height="128"></canvas></div></article></main><p>원본 32색 팔레트 유지 · 알파 0/255 · 접지 최하단 y=107 고정 · 머리/검 원본 RGBA 보존 검사.</p><p><a href="pixel-animation-v2.zip" download>V2 PNG 프레임·파츠·마스크·시트 ZIP</a> · <a href="corrected-sheet.png">V2 PNG 시트</a> · <a href="corrected.png">V2 APNG</a> · <a href="corrected.webp">V2 확대 재생</a> · <a href="results.json">처리 기록</a> · <a href="../pixel-animation-test-20261019/preview.html">이전 시험</a></p><h2>프레임 비교 · 위 V1 / 아래 V2</h2><img class="wide" src="comparison.png"><details><summary>원본에서 분리한 파츠와 한계</summary><img class="wide" src="parts.png"><p>이 캐릭터에 직접 지정한 마스크입니다. 머리·검의 일관성을 유지해도 걷기 동작 전체가 자연스러워지는 것은 아닙니다. 생성된 다리 모양과 네 키포즈의 연결, 가려진 부분과 관절 경계는 더 수정해야 합니다. 다리 크기 조정은 최근접 방식이며 원본 도트를 그대로 보존하는 영역과 구분합니다.</p></details><script>
const images={before:[],corrected:[]};let playing=true,index=0,last=0;
const frame=document.querySelector('#frame'),speed=document.querySelector('#speed');
function show(){for(const name of Object.keys(images)){const ctx=document.getElementById(name).getContext('2d');ctx.imageSmoothingEnabled=false;ctx.clearRect(0,0,128,128);if(images[name][index]?.complete)ctx.drawImage(images[name][index],0,0)}frame.value=index;document.querySelector('#current').textContent=`${index+1} / 4`}
for(const name of Object.keys(images))for(let i=0;i<4;i++){const image=new Image();image.onload=show;image.src=`${name}-${String(i).padStart(2,'0')}.png`;images[name].push(image)}
document.querySelector('#play').onclick=()=>{playing=!playing;document.querySelector('#play').textContent=playing?'일시 정지':'재생';last=0};
frame.oninput=()=>{playing=false;document.querySelector('#play').textContent='재생';index=Number(frame.value);show()};
speed.oninput=()=>{document.querySelector('#fps').textContent=speed.value};
function tick(now){if(playing&&now-last>=1000/Number(speed.value)){index=(index+1)%4;last=now;show()}requestAnimationFrame(tick)}requestAnimationFrame(tick);
</script></html>''',encoding='utf-8')
    print('PASS',len(records),'frames; palette',len(palette),'colors; original head/sword; floor 107')
    print('PREVIEW',out/'preview.html')


if __name__=='__main__':main()
