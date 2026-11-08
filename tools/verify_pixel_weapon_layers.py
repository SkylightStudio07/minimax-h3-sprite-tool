"""Isolated weapon-free body animation + rigid weapon + foreground grip layers.

prepare/video: web .venv; export: existing G:/111/runtime/.venv (OpenCV).
Manual source masks are specific to the reviewed knight, not automatic splitting.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys
import time
import zipfile

import av
import numpy as np
from PIL import Image,ImageDraw
from scipy import ndimage

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
OUT=ROOT/'outputs/pixel-weapon-layers-20261019'
SOURCE=ROOT/'outputs/pixel-minimax-right-20261019'
VERSION='weapon-free-body-layered-v1'
# Independent ROIs for reconstruction and actual original weapon pixels.
REPAIR=[(49,60),(56,60),(59,63),(65,63),(69,68),(93,84),(93,92),(84,92),(59,75),(56,69),(49,67)]
HANDLE=[(50,61),(55,61),(62,66),(65,65),(67,66),(64,70),(62,73),(59,72),(57,68),(51,65),(50,64)]
BLADE=[(64,68),(68,69),(91,85),(90,90),(85,89),(63,74)]
GRIP=(60.,66.)


def save(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def polygon(points):
    im=Image.new('L',(128,128));ImageDraw.Draw(im).polygon(points,fill=255)
    return np.array(im)>0


def source_parts():
    source=np.array(Image.open(SOURCE/'reference-right.png').convert('RGBA'))
    yy,xx=np.indices((128,128));rgb=source[:,:,:3].astype(float)
    # Original skin pixels crossing the grip are a foreground occluder.
    hand=(xx>=58)&(xx<=63)&(yy>=64)&(yy<=68)&(source[:,:,3]>0)
    hand &= (rgb[:,:,0]>120)&(rgb[:,:,0]>rgb[:,:,2]*1.15)
    blade=polygon(BLADE)&(source[:,:,3]>0)
    # Exclude coat colours from a broad reconstruction ROI, while retaining the
    # actual dark steel outline and the brown hilt within its tighter polygon.
    blade &= (rgb[:,:,0]>=70)&(rgb[:,:,0]<=rgb[:,:,2]*1.2)
    handle=polygon(HANDLE)&(source[:,:,3]>0)&~hand
    handle &= ((rgb[:,:,0]>rgb[:,:,2]*1.1)&(rgb[:,:,0]>50))|((rgb[:,:,0]>65)&(rgb[:,:,2]>75))
    weapon=blade|handle
    repair=polygon(REPAIR)
    layer=np.zeros_like(source);layer[weapon]=source[weapon]
    foreground=np.zeros_like(source);foreground[hand]=source[hand]
    for name,mask in [('repair',repair),('weapon',weapon),('foreground-hand',hand)]:
        Image.fromarray(mask.astype('uint8')*255).save(OUT/f'mask-{name}.png')
    Image.fromarray(layer).save(OUT/'weapon.png');Image.fromarray(foreground).save(OUT/'reference-hand.png')
    return source,repair,weapon,hand


def prepare():
    from tools import verify_pixel_minimax as experiment
    from tools.verify_pixel_animation import palette_from,pixel_export
    from tools.verify_rpg_sprite_styles import ensure_idle
    import rigging_engine as rig
    experiment.OUT=OUT
    ensure_idle();experiment.release((8189,8191))
    source,repair,weapon,hand=source_parts();reference=Image.fromarray(source)
    enlarged=reference.resize((768,768),Image.Resampling.NEAREST)
    matte=Image.new('RGB',enlarged.size,'white');matte.paste(enlarged,mask=enlarged.getchannel('A'))
    path=rig.INPUT_ROOT/'pixel_weapon_layers_reference.png';matte.save(path)
    graph=rig.qwen21_workflow(path.name,'pixel_weapon_layers/no_weapon',768,20,2026101903)
    graph['6']['inputs'].update(device='cpu',dtype='default')
    graph['5']['inputs']['prompt']=(
        'Edit image 1 by removing the ENTIRE sword, blade, brown handle, crossguard and every weapon fragment. '
        'The exact same blue-haired woman is now UNARMED with BOTH HANDS EMPTY. '
        'Reconstruct the navy coat, trousers, legs and plain white background that were hidden behind the sword. '
        'Keep the near hand at the EXACT same location beside the hip, fingers softly curled into a small EMPTY fist, holding nothing. '
        'Preserve the exact same RIGHT-FACING side-profile mid-walk pose, face, short blue bob, white scarf, navy coat with thin gold trim, brown belt, brown boots, '
        'same canvas framing, same scale, exact same small pixel-art style and colours. '
        'Change NOTHING except remove the sword and restore what it covered. Do not move or crop the character, do not add objects. '
        'One single full-body pixel sprite, flat pure white background, no shadow, no text.')
    graph['5']['inputs']['negative_prompt']='sword, weapon, knife, hilt, handle, scabbard, holding object, different pose, different clothes, extra fingers, shadow, text'
    started=time.monotonic();history=experiment.execute(graph,rig.COMFY_URL,'no-weapon-reference')
    raw=Image.open(rig._saved_image(history,'9')).convert('RGBA');raw.save(OUT/'body-repair-raw.png')
    pal,colors=palette_from(reference);edited=np.array(pixel_export(raw,pal))
    result=source.copy();result[repair]=edited[repair]
    # Keep the original fingers so the eventual weapon can be held at its original
    # grip. The video model sees these fingers without the actual weapon.
    result[hand]=source[hand]
    result[repair&(result[:,:,3]==0),:3]=0
    assert np.array_equal(result[~repair],source[~repair])
    Image.fromarray(result).save(OUT/'body-reference.png')
    Image.fromarray(result).resize((768,768),Image.Resampling.NEAREST).save(OUT/'body-reference-preview.png')
    save('prepare.json',dict(version=VERSION,seconds=round(time.monotonic()-started,2),palette=colors,
         manualRepairPolygon=REPAIR,manualHandlePolygon=HANDLE,manualBladePolygon=BLADE,referenceGrip=GRIP,
         outsideRepairRGBAUnchanged=True,originalHandRestored=True))
    experiment.release((8190,));print('PREPARED',OUT/'body-reference-preview.png',flush=True)


def video():
    from tools import verify_pixel_minimax as experiment
    from tools.verify_rpg_sprite_styles import ensure_idle
    import idle_tool as engine
    import shutil
    experiment.OUT=OUT
    ensure_idle();experiment.release((8190,8191))
    source=Image.open(OUT/'body-reference.png').convert('RGBA').resize((512,512),Image.Resampling.NEAREST)
    matte=Image.new('RGB',source.size,(128,128,128));matte.paste(source,mask=source.getchannel('A'));matte.save(OUT/'minimax-input.png')
    digest=hashlib.sha256((OUT/'minimax-input.png').read_bytes()).hexdigest();upload=OUT/'upload.json'
    if upload.is_file():
        stored=json.loads(upload.read_text());assert stored['sha256']==digest;name=stored['name']
    else:
        name=engine.upload_image((OUT/'minimax-input.png').read_bytes(),'pixel-unarmed-walk.png');save('upload.json',dict(name=name,sha256=digest))
    prompt=(
        'The UNARMED blue-haired woman continuously walks ON A TREADMILL IN PLACE, facing strictly SCREEN RIGHT. '
        'She has NO weapon or held object in either hand at any time. Both small hands remain EMPTY and loosely curled. '
        'The near wrist stays close to the hip and swings only slightly; the far arm counter-swings naturally. '
        'Two relaxed short-stride walking cycles already underway at the first frame and continuing at the last. '
        'Alternate both legs along the front-back screen X axis in a strict side view. Never spread the legs toward the camera. '
        'One boot always supports her on a fixed horizontal ground line, minimal foot lift, small natural knee bend, no running, hopping, sliding or kicking. '
        'A tiny whole-torso rise/fall and a delayed flutter at the coat hem, not swelling or deforming the chest. '
        'Head and nose keep looking RIGHT, same face and short blue bob, white scarf, navy gold-trimmed coat, brown belt and boots. '
        'Keep near hand readable and unoccluded, no hand passing behind the body. '
        'Same body size and screen placement, constant costume and anatomy, static orthographic camera, no pan, no zoom. '
        'Flat pixel-art shading and stable colours. No object appears or disappears, no sword, no sword-shaped streak or afterimage. '
        'The background between the legs and around the body is the same flat grey matte. No shadow or scenery.')
    graph=engine.build_workflow(name,prompt,3,512,512,2026101904,animation_type='walk',loop=True,
           facing='right',flat_background=True,motion_strength='low',sampling_mode='quality',workflow_id='standard')
    graph['16']['inputs']['filename_prefix']='pixel_weapon_layers/body_walk'
    graph['15']['inputs'].pop('audio',None);graph.pop('14');graph.pop('5')
    save('video-settings.json',dict(version=VERSION,model=engine.MODEL_FILES['diffusion'].name,steps=20,seed=2026101904,
                width=512,height=512,frames=73,fps=24,prompt=graph['6']['inputs']['prompt'],source='body-reference.png'))
    started=time.monotonic();history=experiment.execute(graph,engine.COMFY_URL,'body-video')
    shutil.copyfile(engine.find_saved_video(history),OUT/'body-walk.mp4')
    save('video-timing.json',dict(seconds=round(time.monotonic()-started,2)))
    experiment.release((8189,));print('VIDEO',OUT/'body-walk.mp4',flush=True)


def grip_tracks(rgbs):
    """Small manual hand search ROI and skin component; no weapon is needed."""
    records=[];yy,xx=np.indices((128,128));last=np.array(GRIP)
    for i,rgb in enumerate(rgbs):
        r,g,b=rgb.astype(float).transpose(2,0,1)
        mask=(xx>=46)&(xx<=67)&(yy>=56)&(yy<=74)&(r>145)&(g>85)&(r>b*1.2)&(r>g*1.08)
        labels,n=ndimage.label(mask);candidates=[]
        for label in range(1,n+1):
            y,x=np.where(labels==label)
            if len(x)>=3:
                center=np.array([x.mean(),y.mean()]);score=len(x)-.45*np.sum((center-last)**2)
                candidates.append((score,center,len(x)))
        if candidates:
            _,center,count=max(candidates,key=lambda item:item[0]);accepted=bool(np.linalg.norm(center-last)<7)
        else:center=last.copy();count=0;accepted=False
        if accepted:last=center
        records.append(dict(frame=i,observed=accepted,grip=center.tolist(),skinPixels=count))
    # Keep a small gap explicitly labelled, rather than pretending an inferred
    # position is a successful observation. Every position remains editable.
    observed=[i for i,r in enumerate(records) if r['observed']]
    if len(observed)<len(records)*.8:raise RuntimeError('Too many missing hand detections; inspect before compositing')
    for axis in range(2):
        coords=np.interp(np.arange(len(records)),observed,[records[i]['grip'][axis] for i in observed])
        coords=ndimage.median_filter(coords,size=3,mode='nearest')
        for i,value in enumerate(coords):records[i]['grip'][axis]=round(float(value),3)
    return records


def choose_cycle(frames):
    arr=np.array(frames,dtype=np.float32)/255;rgb=arr[:,:,:,:3]*arr[:,:,:,3:4]
    weights=np.ones((128,128,1),np.float32)*.1;weights[75:]*=20
    def diff(a,b):return float((np.abs(a-b)*weights).mean())
    best=None
    for start in range(5,29):
        for length in range(22,35):
            end=start+length
            if end+1>=len(frames):continue
            score=diff(rgb[start],rgb[end])+.4*diff(rgb[start+1]-rgb[start],rgb[end+1]-rgb[end])
            if best is None or score<best['score']:best=dict(start=start,endExclusive=end,length=length,score=score)
    return best


def weapon_transform(weapon,grip,angle):
    rad=np.radians(angle);c,s=np.cos(rad),np.sin(rad);rotation=np.array([[c,-s],[s,c]])
    translation=np.array(grip)-rotation@np.array(GRIP)
    matrix=np.column_stack((rotation,translation)).astype(np.float32)
    # Same inverse mapping and tie rounding as the editable browser renderer.
    # Explicit copies avoid Canvas rotation antialias and preserve palette/alpha.
    yy,xx=np.indices((128,128));dx=xx-grip[0];dy=yy-grip[1]
    sx=np.floor(GRIP[0]+c*dx+s*dy+.5).astype(int)
    sy=np.floor(GRIP[1]-s*dx+c*dy+.5).astype(int)
    valid=(sx>=0)&(sy>=0)&(sx<128)&(sy<128)
    result=np.zeros_like(weapon);result[valid]=weapon[sy[valid],sx[valid]]
    return result,matrix


def hand_layer(frame,grip):
    a=frame.copy();yy,xx=np.indices((128,128));rgb=a[:,:,:3].astype(float)
    skin=(rgb[:,:,0]>140)&(rgb[:,:,1]>80)&(rgb[:,:,0]>rgb[:,:,2]*1.2)
    nearby=(np.abs(xx-grip[0])<=4)&(np.abs(yy-grip[1])<=5)
    mask=ndimage.binary_dilation(skin&nearby,iterations=1)&nearby&(a[:,:,3]>0)
    hand=np.zeros_like(a);hand[mask]=a[mask];body=a.copy();body[mask]=0
    return body,hand


def over(base,layer):
    result=base.copy();mask=layer[:,:,3]>0;result[mask]=layer[mask];return result


def export():
    import cv2
    from tools import postprocess_pixel_video as pp
    started=time.monotonic();cv2.setNumThreads(4)
    reference=Image.open(OUT/'body-reference.png').convert('RGBA');palette=np.array(json.loads((OUT/'prepare.json').read_text(encoding='utf-8'))['palette'],np.float32)
    with av.open(str(OUT/'body-walk.mp4')) as container:raw=[np.array(f.to_image().convert('RGB')) for f in container.decode(video=0)]
    rgbs=[];coverages=[];grays=[]
    for rgb in raw:
        color,coverage=pp.robust_grid(rgb,pp.cutout(rgb));rgbs.append(color);coverages.append(coverage)
        grays.append(cv2.cvtColor(cv2.resize(rgb,(128,128),interpolation=cv2.INTER_AREA),cv2.COLOR_RGB2GRAY))
    temporal,changes=pp.temporal_cleanup(rgbs,coverages,grays,palette)
    hmask=np.zeros((128,128),bool);x0,y0,x1,y1=pp.HEAD;hmask[y0:y1,x0:x1]=True
    head=pp.track_reference(grays,hmask,'head')
    stable,_=pp.apply_parts(temporal,reference,head,[dict(accepted=False) for _ in raw],np.zeros((128,128),bool))
    tracks=grip_tracks(rgbs);weapon=np.array(Image.open(OUT/'weapon.png').convert('RGBA'))
    cycle=choose_cycle(stable);indices=[cycle['start']+round(i*cycle['length']/8) for i in range(8)];duration=round(cycle['length']/24/8*1000)
    folders={name:OUT/name for name in ('body','weapon-layer','hand','composite')}
    for folder in folders.values():folder.mkdir(exist_ok=True)
    combined=[];bodies=[];settings=[]
    allowed={tuple(c) for c in palette.astype(np.uint8)}
    for i,frame in enumerate(stable):
        grip=tracks[i]['grip']
        # A restrained sway follows forearm/hand travel; no scale/deformation.
        angle=round(float(np.clip((grip[0]-tracks[0]['grip'][0])*1.3,-9,9)),3)
        weapon_layer,matrix=weapon_transform(weapon,grip,angle)
        body,hand=hand_layer(frame,grip);result=over(over(body,weapon_layer),hand)
        for name,a in [('body',body),('weapon-layer',weapon_layer),('hand',hand),('composite',result)]:
            Image.fromarray(a).save(folders[name]/f'all-{i:03d}.png')
        colors={tuple(c) for c in np.unique(result[:,:,:3][result[:,:,3]>0],axis=0)}
        assert colors<=allowed and set(np.unique(result[:,:,3]))<={0,255}
        assert np.array_equal(result[hand[:,:,3]>0],hand[hand[:,:,3]>0])
        combined.append(result);bodies.append(frame)
        settings.append(dict(sourceFrame=i,grip=grip,angle=round(angle,3),observed=tracks[i]['observed'],matrix=matrix.tolist()))
    for name,frames in [('body-preview',bodies),('composite-preview',combined)]:
        pp.OUT=OUT;pp.export_variant(name,frames,indices,duration)
    selection=[]
    for i,index in enumerate(indices):
        for name,folder in folders.items():
            with Image.open(folder/f'all-{index:03d}.png') as image:image.save(folder/f'frame-{i:02d}.png')
        selection.append(dict(index=i,sourceFrame=index,grip=settings[index]['grip'],angle=settings[index]['angle'],observed=settings[index]['observed']))
    save('editor-settings.json',dict(version=VERSION,width=128,height=128,frameDurationMs=duration,referenceGrip=GRIP,frames=selection))
    save('tracks.json',dict(head=head,hand=tracks,weapon=settings))
    save('results.json',dict(version=VERSION,sourceVideoSHA256=hashlib.sha256((OUT/'body-walk.mp4').read_bytes()).hexdigest(),
        frames=len(raw),selectedIndices=indices,frameDurationMs=duration,palette=palette.astype(int).tolist(),cycle=cycle,
        observedHands=sum(t['observed'] for t in tracks),headAccepted=sum(t['accepted'] for t in head),temporalChanges=changes,seconds=round(time.monotonic()-started,2),
        sourceMasksManual=True,weaponScale=1,compositeOrder=['body','rigid original weapon','foreground hand'],
        limitations=['Single-character manual masks and skin-colour search','Rotation uses nearest grid; diagonal stair pattern may change','No automatic weapon depth switching','Browser corrections export sheet/settings; server files are not overwritten']))
    montage=Image.new('RGB',(8*256,2*286),'#e3e4eb');d=ImageDraw.Draw(montage)
    for row,frames in enumerate((bodies,combined)):
        for col,index in enumerate(indices):
            im=Image.fromarray(frames[index]).resize((256,256),Image.Resampling.NEAREST);montage.paste(im,(col*256,row*286+30),im);d.text((col*256+8,row*286+8),f'{"body" if row==0 else "layers"} / {index}',fill='black')
    montage.save(OUT/'comparison.png')
    preview(selection,duration)
    with zipfile.ZipFile(OUT/'pixel-layered-walk.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for name,folder in folders.items():
            for file in folder.glob('*.png'):archive.write(file,file.relative_to(OUT).as_posix())
        for folder in ('body-preview','composite-preview'):
            for file in (OUT/folder).glob('*.png'):
                if not file.name.startswith('all-'):archive.write(file,file.relative_to(OUT).as_posix())
            archive.write(OUT/folder/'animation.webp',folder+'/animation.webp')
        for file in ('weapon.png','body-reference.png','editor-settings.json','tracks.json','results.json','mask-repair.png','mask-weapon.png','mask-foreground-hand.png','prepare.json','preview.html','comparison.png','body-walk.mp4'):
            archive.write(OUT/file,file)
    print('EXPORTED',len(raw),'frames; hand observations',sum(t['observed'] for t in tracks),'/',len(raw));print('PREVIEW',OUT/'preview.html',flush=True)


def preview(selection,duration):
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>무기 분리 · 몸 + 검 + 앞쪽 손</title><style>body{background:#171923;color:#eef0fa;font:15px/1.65 system-ui;margin:24px}h1{font-size:25px}main{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}article{background:#272b39;border:1px solid #4b546d;border-radius:12px;padding:16px;min-width:0}h2{font-size:18px}.checker{background:repeating-conic-gradient(#ddd 0 25%,#f8f8f8 0 50%) 0/22px 22px}canvas,img.pixel{width:100%;image-rendering:pixelated;touch-action:none}a{color:#bdcbff}.controls{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin:16px 0}button,input,select{font:inherit}button{padding:6px 12px}input[type=number]{width:70px}.wide{width:100%;image-rendering:pixelated}video{width:100%}.status{min-height:28px}details{margin:16px 0}@media(max-width:850px){main{grid-template-columns:1fr}}</style><h1>검을 뺀 몸 동작 → 원본 검 → 앞쪽 손</h1><p>원본 검 뒤의 옷·다리를 먼저 복원한 기준 이미지로 MiniMax 걷기를 새로 만들었습니다. 시간축 보정과 얼굴 추적을 적용한 몸 위에 원본 검을 회전·이동하고, 손가락 레이어가 마지막에 덮입니다. 검은 확대·축소하거나 다시 생성하지 않습니다.</p><div class="controls"><button id="play">일시 정지</button><label>프레임 <input id="frame" type="range" min="0" max="7" value="0"> <span id="current">1 / 8</span></label><label>속도 <input id="speed" type="range" min="2" max="12" value="8"> <span id="fps">8</span>FPS</label></div><main><article><h2>무기 없는 몸</h2><div class="checker"><canvas id="body" width="128" height="128"></canvas></div><p>동작과 얼굴 보정 완료 · 검 합성 전</p></article><article><h2>레이어 합성 · 직접 보정 가능</h2><div class="checker"><canvas id="result" width="128" height="128"></canvas></div><p>일시 정지 후 이 화면을 드래그하면 검 손잡이를 옮깁니다.</p></article><article><h2>파츠 확인</h2><select id="layer"><option value="weapon">원본 검</option><option value="hand">앞쪽 손</option><option value="back">몸 레이어</option></select><div class="checker"><canvas id="part" width="128" height="128"></canvas></div><label><input id="markers" type="checkbox" checked>손잡이 위치 표시</label></article></main><div class="controls"><label>손잡이 X <input id="x" type="number" min="0" max="127" step="1"></label><label>Y <input id="y" type="number" min="0" max="127" step="1"></label><label>각도 <input id="angle" type="range" min="-40" max="40" step="1"> <span id="degrees"></span>°</label><button id="reset">현재 프레임 초기화</button><button id="undo">실행 취소</button></div><div class="controls"><button id="sheet">수정 PNG 시트 저장</button><button id="settings">수정 위치 JSON 저장</button><label>위치 JSON 불러오기 <input id="load" type="file" accept="application/json,.json"></label></div><p id="status" class="status" aria-live="polite">수정은 이 페이지 메모리에만 적용됩니다. 시트와 위치 JSON을 저장하면 다음 작업에 가져올 수 있습니다.</p><p><a href="pixel-layered-walk.zip" download>기본 합성본·몸/검/손 레이어·전체 프레임 ZIP</a> · <a href="composite-preview/animation.webp">기본 합성 재생</a> · <a href="composite-preview/sheet.png">기본 PNG 시트</a> · <a href="editor-settings.json">기본 위치 JSON</a> · <a href="../pixel-minimax-postprocess-20261019/preview.html">이전 영상에서 검 교체 실험</a></p><h2>위 · 무기 없는 몸 / 아래 · 검+손 합성</h2><img class="wide" src="comparison.png"><details><summary>무기 없는 기준 이미지와 생성 원본</summary><img class="pixel" src="body-reference.png"><video controls loop muted src="body-walk.mp4"></video><p>원본 복원 범위는 이 캐릭터에 직접 지정했습니다. 자동 레이어 분절 도구가 아닙니다. 검의 앞뒤 순서는 현재 몸→검→손으로 고정이며, 몸 뒤로 검이 넘어가는 동작에는 추가 가림 처리가 필요합니다.</p></details><script>
const defaults=__DEFAULTS__,embedded=__ASSETS__,cfg=structuredClone(defaults),images={back:[],hand:[],body:[]},weapon=new Image();let index=0,playing=true,last=0,drag=null,history=[],weaponPixels=null;
const $=id=>document.getElementById(id),status=text=>$('status').textContent=text;
function clear(c){const ctx=c.getContext('2d');ctx.imageSmoothingEnabled=false;ctx.clearRect(0,0,c.width,c.height);return ctx}
function ready(im){return im?.complete&&im.naturalWidth>0}
function drawComposite(canvas,i){const ctx=clear(canvas),f=cfg.frames[i];if(ready(images.back[i]))ctx.drawImage(images.back[i],0,0);if(weaponPixels){const image=ctx.getImageData(0,0,128,128),r=f.angle*Math.PI/180,c=Math.cos(r),s=Math.sin(r);for(let y=0;y<128;y++)for(let x=0;x<128;x++){const dx=x-f.grip[0],dy=y-f.grip[1],sx=Math.round(cfg.referenceGrip[0]+c*dx+s*dy),sy=Math.round(cfg.referenceGrip[1]-s*dx+c*dy);if(sx<0||sy<0||sx>=128||sy>=128)continue;const from=(sy*128+sx)*4,to=(y*128+x)*4;if(weaponPixels[from+3]>=128){image.data[to]=weaponPixels[from];image.data[to+1]=weaponPixels[from+1];image.data[to+2]=weaponPixels[from+2];image.data[to+3]=255}}ctx.putImageData(image,0,0)}if(ready(images.hand[i]))ctx.drawImage(images.hand[i],0,0)}
function show(){let ctx=clear($('body'));if(ready(images.body[index]))ctx.drawImage(images.body[index],0,0);drawComposite($('result'),index);ctx=clear($('part'));const kind=$('layer').value;if(kind==='weapon'&&ready(weapon))ctx.drawImage(weapon,0,0);else{const im=images[kind==='hand'?'hand':'back'][index];if(ready(im))ctx.drawImage(im,0,0)}if($('markers').checked){const f=cfg.frames[index];ctx=$('result').getContext('2d');ctx.strokeStyle='#ff4967';ctx.lineWidth=.5;ctx.beginPath();ctx.moveTo(f.grip[0]-3,f.grip[1]);ctx.lineTo(f.grip[0]+3,f.grip[1]);ctx.moveTo(f.grip[0],f.grip[1]-3);ctx.lineTo(f.grip[0],f.grip[1]+3);ctx.stroke()}const f=cfg.frames[index];$('frame').value=index;$('current').textContent=`${index+1} / 8`;$('x').value=f.grip[0];$('y').value=f.grip[1];$('angle').value=f.angle;$('degrees').textContent=Math.round(f.angle)}
function pause(){playing=false;$('play').textContent='재생'}function remember(){history.push(structuredClone(cfg.frames));if(history.length>100)history.shift()}
for(const kind of ['back','hand','body'])for(let i=0;i<8;i++){const im=new Image();images[kind].push(im);im.onload=show;im.src=embedded[kind][i]}weapon.onload=()=>{const c=document.createElement('canvas');c.width=c.height=128;const ctx=c.getContext('2d');ctx.imageSmoothingEnabled=false;ctx.drawImage(weapon,0,0);weaponPixels=ctx.getImageData(0,0,128,128).data;show()};weapon.src=embedded.weapon;
$('play').onclick=()=>{playing=!playing;$('play').textContent=playing?'일시 정지':'재생';last=0};$('frame').oninput=()=>{pause();index=Number($('frame').value);show()};$('speed').oninput=()=>$('fps').textContent=$('speed').value;$('markers').onchange=show;$('layer').onchange=show;
for(const id of ['x','y','angle'])$(id).onchange=()=>{pause();remember();const f=cfg.frames[index];if(id==='angle')f.angle=Math.max(-40,Math.min(40,Number($(id).value)||0));else f.grip[id==='x'?0:1]=Math.max(0,Math.min(127,Number($(id).value)||0));show()};
$('reset').onclick=()=>{pause();remember();cfg.frames[index]=structuredClone(defaults.frames[index]);show()};$('undo').onclick=()=>{if(history.length){pause();cfg.frames=history.pop();show()}};
function point(e){const r=$('result').getBoundingClientRect();return[(e.clientX-r.left)*128/r.width,(e.clientY-r.top)*128/r.height]}
$('result').onpointerdown=e=>{pause();remember();const p=point(e),f=cfg.frames[index];drag={pointer:e.pointerId,start:p,grip:f.grip.slice()};$('result').setPointerCapture(e.pointerId);e.preventDefault()};$('result').onpointermove=e=>{if(!drag||drag.pointer!==e.pointerId)return;const p=point(e);cfg.frames[index].grip=drag.grip.map((v,i)=>Math.max(0,Math.min(127,Math.round(v+p[i]-drag.start[i]))));show()};$('result').onpointerup=$('result').onpointercancel=()=>drag=null;
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
$('settings').onclick=()=>{download(new Blob([JSON.stringify(cfg,null,2)],{type:'application/json'}),'weapon-positions.json');status('현재 8프레임의 손잡이 위치와 각도를 JSON으로 저장했습니다.')};
$('sheet').onclick=()=>{if(!ready(weapon)||Object.values(images).some(items=>items.some(im=>!ready(im)))){status('이미지가 모두 로드된 뒤 다시 저장해 주세요.');return}const sheet=document.createElement('canvas');sheet.width=1024;sheet.height=128;const ctx=sheet.getContext('2d');ctx.imageSmoothingEnabled=false;const cell=document.createElement('canvas');cell.width=cell.height=128;for(let i=0;i<8;i++){drawComposite(cell,i);ctx.drawImage(cell,i*128,0)}sheet.toBlob(blob=>{if(blob){download(blob,'layered-walk-edited.png');status('표시 마커를 제외한 수정 PNG 시트를 저장했습니다. 위치 JSON도 함께 저장하세요.')}})};
$('load').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;const data=JSON.parse(await file.text());if(data.version!==defaults.version||data.frames?.length!==8||data.width!==128||data.height!==128||JSON.stringify(data.referenceGrip)!==JSON.stringify(defaults.referenceGrip)||data.frames.some((f,i)=>f.sourceFrame!==defaults.frames[i].sourceFrame||!Array.isArray(f.grip)||f.grip.length!==2||f.grip.some(v=>!Number.isFinite(v)||v<0||v>127)||!Number.isFinite(f.angle)||Math.abs(f.angle)>40))throw Error('이 작업의 유효한 8프레임 위치 JSON이 아닙니다.');pause();remember();cfg.frames=structuredClone(data.frames);show();status('위치 JSON을 불러왔습니다.')}catch(error){status('불러오기 실패: '+error.message)}finally{e.target.value=''}};
document.addEventListener('keydown',e=>{if(/INPUT|SELECT/.test(e.target.tagName))return;if(e.code==='Space'){e.preventDefault();$('play').click()}if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();pause();index=(index+(e.key==='ArrowRight'?1:7))%8;show()}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){e.preventDefault();$('undo').click()}});
function tick(now){if(playing&&now-last>=1000/Number($('speed').value)){index=(index+1)%8;last=now;show()}requestAnimationFrame(tick)}requestAnimationFrame(tick);
</script></html>'''
    data=dict(version=VERSION,width=128,height=128,frameDurationMs=duration,referenceGrip=list(GRIP),frames=selection)
    def data_url(path):return 'data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode('ascii')
    # Embedded canvas assets keep local-file image loading from tainting editable
    # exports. No file permission/browser setting or server workaround is needed.
    assets={kind:[data_url(OUT/folder/f'frame-{i:02d}.png') for i in range(8)] for kind,folder in [('back','body'),('hand','hand'),('body','body-preview')]}
    assets['weapon']=data_url(OUT/'weapon.png')
    (OUT/'preview.html').write_text(page.replace('__DEFAULTS__',json.dumps(data,ensure_ascii=False)).replace('__ASSETS__',json.dumps(assets)),encoding='utf-8')


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');OUT.mkdir(exist_ok=True)
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','video','export']);args=parser.parse_args()
    dict(prepare=prepare,video=video,export=export)[args.stage]()
