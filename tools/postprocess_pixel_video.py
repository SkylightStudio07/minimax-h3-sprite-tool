"""CPU-only temporal pixel cleanup of the existing MiniMax clip.

Original implementation; no external pipeline code/model is installed. Manual
reference ROIs are exported and are specific to this reviewed knight.
Run with G:/111/runtime/.venv/Scripts/python.exe (OpenCV is already installed).
"""
import hashlib
import json
from pathlib import Path
import time
import zipfile

import av
import cv2
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'outputs/pixel-minimax-right-20261019'
OUT=ROOT/'outputs/pixel-minimax-postprocess-20261019'
VERSION='motion-aware-pixel-postprocess-v1'
HEAD=(54,18,73,39)
BLADE=[(63,69),(67,69),(90,84),(90,89),(86,89),(63,74)]
NAMES={'baseline':'기존 · 한 점 샘플링','spatial':'격자 대표 색','temporal':'시간축 보정 · 우선 후보','head':'시간축 + 얼굴 추적','parts':'얼굴·검 합성 · 실험'}


def write_json(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def mask_polygon(points):
    im=Image.new('L',(128,128));ImageDraw.Draw(im).polygon(points,fill=255)
    return np.asarray(im)>0


def cutout(rgb):
    border=np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1]))
    bg=np.median(border,axis=0)
    distance=np.max(np.abs(rgb.astype(np.float32)-bg),axis=2)
    candidate=distance<=26
    seed=np.zeros(candidate.shape,bool)
    seed[0]=candidate[0];seed[-1]=candidate[-1];seed[:,0]=candidate[:,0];seed[:,-1]=candidate[:,-1]
    background=ndimage.binary_propagation(seed,mask=candidate)
    return ~background


def quantize(rgb,palette):
    distances=((rgb.astype(np.float32)[:,:,None,:]-palette[None,None,:,:])**2).sum(axis=3)
    return distances.argmin(axis=2).astype(np.uint8),distances


def robust_grid(rgb,alpha):
    """Nine current-cell samples, actual visible Lab medoid, exact 4px grid."""
    samples=[];visible=[]
    for dy in (0,2,3):
        for dx in (0,2,3):
            samples.append(rgb[dy::4,dx::4]);visible.append(alpha[dy::4,dx::4])
    samples=np.stack(samples,axis=2);visible=np.stack(visible,axis=2)
    lab=cv2.cvtColor(samples.reshape(128,128*9,3).astype(np.float32)/255,cv2.COLOR_RGB2LAB).reshape(128,128,9,3)
    weights=np.outer([1,2,1],[1,2,1]).reshape(9).astype(np.float32)
    weights=weights[None,None,:]*visible
    costs=np.zeros((128,128,9),np.float32)
    for i in range(9):
        costs[:,:,i]=np.sum(np.sqrt(((lab-lab[:,:,i:i+1,:])**2).sum(axis=3))*weights,axis=2)
    costs[~visible]=1e9
    # Prefer the centre on ties; the output is a real source colour, never an RGB average.
    costs+=np.array([.008,.005,.008,.005,0,.005,.008,.005,.008])[None,None,:]
    choice=costs.argmin(axis=2)
    chosen=np.take_along_axis(samples,choice[:,:,None,None],axis=2)[:,:,0,:]
    coverage=alpha.reshape(128,4,128,4).mean(axis=(1,3))
    return chosen,coverage


def flow_pair(previous,current):
    dis=cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    f=dis.calc(previous,current,None)
    b=dis.calc(current,previous,None)
    yy,xx=np.indices(previous.shape,dtype=np.float32)
    mx=xx+b[:,:,0];my=yy+b[:,:,1]
    opposite=cv2.remap(f,mx,my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
    error=np.sqrt(((b+opposite)**2).sum(axis=2))
    valid=(mx>=1)&(my>=1)&(mx<126)&(my<126)&(error<.65)
    return mx,my,valid,error


def temporal_cleanup(rgbs,coverages,grays,palette):
    outputs=[];records=[];previous_labels=None;previous_alpha=None
    for i,(rgb,coverage) in enumerate(zip(rgbs,coverages)):
        labels,distances=quantize(rgb,palette)
        alpha=coverage>=.5;changed_colors=0;changed_alpha=0;reliable=0
        if i:
            mx,my,valid,error=flow_pair(grays[i-1],grays[i])
            warped_labels=cv2.remap(previous_labels,mx,my,cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT)
            warped_alpha=cv2.remap(previous_alpha.astype(np.uint8),mx,my,cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT)>0
            warped_gray=cv2.remap(grays[i-1],mx,my,cv2.INTER_LINEAR)
            photo=np.abs(grays[i].astype(np.float32)-warped_gray.astype(np.float32))
            valid &= photo<18
            reliable=int(valid.sum())
            previous_cost=np.take_along_axis(distances,warped_labels[:,:,None],axis=2)[:,:,0]
            best_cost=np.min(distances,axis=2)
            # Keep a prior colour only when it explains this CURRENT pixel almost
            # as well. Motion/occlusion confidence gates prevent stale smearing.
            keep=valid&warped_alpha&alpha&(labels!=warped_labels)&(previous_cost-best_cost<260)&(previous_cost<1500)
            changed_colors=int(keep.sum());labels[keep]=warped_labels[keep]
            uncertain=(coverage>.30)&(coverage<.70)
            keep_alpha=valid&uncertain&(alpha!=warped_alpha)
            # Alpha evidence must be uncertain; a clearly revealed/covered cell
            # always wins. No dilation/erosion of all contours is performed.
            changed_alpha=int(keep_alpha.sum());alpha[keep_alpha]=warped_alpha[keep_alpha]
        image=np.dstack((palette[labels].astype(np.uint8),alpha.astype(np.uint8)*255))
        image[~alpha,:3]=0
        outputs.append(image)
        # Evidence is from the unfiltered predecessor, avoiding recursive colour
        # drift and a long trail of alpha history.
        previous_labels=quantize(rgb,palette)[0];previous_alpha=coverage>=.5
        records.append(dict(frame=i,changedColorPixels=changed_colors,changedAlphaPixels=changed_alpha,reliableFlowPixels=reliable))
    return outputs,records


def track_reference(grays,mask,name):
    reference=grays[0]
    mask256=cv2.resize(mask.astype(np.uint8)*255,(256,256),interpolation=cv2.INTER_NEAREST)
    ref256=cv2.resize(reference,(256,256),interpolation=cv2.INTER_LINEAR)
    points=cv2.goodFeaturesToTrack(ref256,maxCorners=80,qualityLevel=.01,minDistance=3,mask=mask256,blockSize=3)
    if points is None or len(points)<4:raise RuntimeError('Not enough reference features: '+name)
    tracks=[]
    for i,gray in enumerate(grays):
        if i==0:
            tracks.append(dict(frame=0,accepted=True,points=len(points),dx=0.,dy=0.,angle=0.,residual=0.));continue
        current=cv2.resize(gray,(256,256),interpolation=cv2.INTER_LINEAR)
        target,status,error=cv2.calcOpticalFlowPyrLK(ref256,current,points,None,winSize=(21,21),maxLevel=3,
                criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,40,.01))
        back,back_status,_=cv2.calcOpticalFlowPyrLK(current,ref256,target,None,winSize=(21,21),maxLevel=3)
        valid=(status[:,0]>0)&(back_status[:,0]>0)&(np.linalg.norm(points[:,0]-back[:,0],axis=1)<1.8)
        source=points[valid,0]/2;dest=target[valid,0]/2
        matrix,inliers=(None,None)
        if len(source)>=4:
            matrix,inliers=cv2.estimateAffinePartial2D(source,dest,method=cv2.RANSAC,ransacReprojThreshold=1.2,maxIters=1000)
        if matrix is None:
            tracks.append(dict(frame=i,accepted=False,points=int(valid.sum()),reason='insufficient reliable reference tracks'));continue
        selected=inliers[:,0]>0
        # Fit ONLY rigid rotation+translation on accepted tracks. Scale from the
        # generated clip is discarded, so sword length cannot stretch.
        a=source[selected];b=dest[selected];ca=a.mean(axis=0);cb=b.mean(axis=0)
        u,_,vt=np.linalg.svd((a-ca).T@(b-cb));rotation=vt.T@u.T
        if np.linalg.det(rotation)<0:vt[-1]*=-1;rotation=vt.T@u.T
        angle=float(np.degrees(np.arctan2(rotation[1,0],rotation[0,0])))
        translation=cb-rotation@ca
        if name=='head':
            rotation=np.eye(2);translation=np.median(b-a,axis=0);angle=0.
        residual=float(np.median(np.linalg.norm(a@rotation.T+translation-b,axis=1)))
        limit=12 if name=='head' else 24
        accepted=bool(len(a)>=4 and residual<1.1 and abs(angle)<limit and np.linalg.norm(cb-ca)<14)
        tracks.append(dict(frame=i,accepted=accepted,points=len(a),dx=float(translation[0]),dy=float(translation[1]),angle=angle,residual=residual,
                           matrix=np.column_stack((rotation,translation)).tolist()))
    return tracks


def track_weapon_from_hand(rgbs):
    """Track the skin-colour hand and blade angle; do not track blade length."""
    observations=[];yy,xx=np.indices((128,128))
    for i,rgb in enumerate(rgbs):
        r,g,b=rgb.astype(np.float32).transpose(2,0,1)
        hand=(r>135)&(g>80)&(r>b*1.2)&(r>g*1.07)&(xx>=49)&(xx<=67)&(yy>=57)&(yy<=73)
        labels,n=ndimage.label(hand)
        candidates=[]
        for label in range(1,n+1):
            y,x=np.where(labels==label)
            if len(x)>=2:candidates.append((len(x)-.3*((x.mean()-60)**2+(y.mean()-65)**2),float(x.mean()),float(y.mean()),len(x)))
        if not candidates:
            observations.append(dict(frame=i,accepted=False,reason='hand colour not found'));continue
        _,hx,hy,count=max(candidates)
        bright=(r>125)&(g>125)&(b>125)&(xx>hx+3)&(xx<hx+34)&(yy>hy+2)&(yy<hy+28)
        y,x=np.where(bright)
        if len(x)<5:
            observations.append(dict(frame=i,accepted=False,reason='blade angle not found'));continue
        points=np.column_stack((x,y)).astype(np.float32)
        vx,vy,line_x,line_y=cv2.fitLine(points,cv2.DIST_WELSCH,0,.01,.01).ravel()
        if vx<0:vx=-vx;vy=-vy
        angle=float(np.degrees(np.arctan2(vy,vx)))
        projected=(points-np.array([line_x,line_y]))@np.array([vx,vy])
        observations.append(dict(frame=i,accepted=bool(10<angle<70),hand=[hx,hy],angle=angle,points=len(x),handPixels=count,
                     observedLine=[float(line_x),float(line_y),float(vx),float(vy),float(projected.min()),float(projected.max())],
                     method='skin hand centroid + robust bright-blade direction, fixed original blade length'))
    reference=observations[0]
    if not reference['accepted']:raise RuntimeError('Cannot locate reference hand and blade')
    origin=np.array(reference['hand'])
    for i,track in enumerate(observations):
        if not track['accepted']:continue
        # Symmetric three-frame median suppresses isolated detector jitter;
        # never fill an unobserved hand or bridge an occlusion.
        neighbors=[t for t in observations[max(0,i-1):min(len(observations),i+2)] if t['accepted']]
        hand=np.median([t['hand'] for t in neighbors],axis=0)
        absolute_angle=float(np.median([t['angle'] for t in neighbors]))
        angle=absolute_angle-reference['angle'];rad=np.radians(angle)
        rot=np.array([[np.cos(rad),-np.sin(rad)],[np.sin(rad),np.cos(rad)]])
        translation=hand-rot@origin
        track.update(matrix=np.column_stack((rot,translation)).tolist(),dx=float(translation[0]),dy=float(translation[1]),relativeAngle=angle,hand=hand.tolist())
    return observations


def apply_parts(frames,reference,head_tracks,weapon_tracks,blade_mask):
    source=np.asarray(reference).copy();head_mask=np.zeros((128,128),bool)
    head_mask[HEAD[1]:HEAD[3],HEAD[0]:HEAD[2]]=True
    blade=np.zeros_like(source);blade[blade_mask]=source[blade_mask]
    outputs=[];records=[]
    for i,frame in enumerate(frames):
        a=frame.copy();ht=head_tracks[i];wt=weapon_tracks[i]
        if ht['accepted']:
            dx=round(ht['dx']);dy=round(ht['dy'])
            transform=np.array([[1,0,dx],[0,1,dy]],dtype=np.float32)
            # Clear only a head-region ROI and copy the fixed reference RGBA.
            # No body pixels, scarf, or swinging arms are frozen by this mask.
            x0,y0,x1,y1=HEAD
            clear=np.zeros((128,128),np.uint8);clear[max(0,y0+dy-1):y1+dy,max(0,x0+dx-1):x1+dx+1]=255
            a[clear>0]=0
            src=np.zeros_like(source);src[head_mask]=source[head_mask]
            moved=cv2.warpAffine(src,transform,(128,128),flags=cv2.INTER_NEAREST)
            use=moved[:,:,3]>0;a[use]=moved[use]
        if wt['accepted']:
            matrix=np.array(wt.get('matrix',[[1,0,0],[0,1,0]]),np.float32)
            moved=cv2.warpAffine(blade,matrix,(128,128),flags=cv2.INTER_NEAREST)
            region=cv2.warpAffine(blade_mask.astype(np.uint8),matrix,(128,128),flags=cv2.INTER_NEAREST)>0
            band=ndimage.binary_dilation(region,iterations=2)
            yy,xx=np.indices(band.shape)
            # Preserve dark clothing/skin/boots when the blade passes in front.
            # A hand-authored lower-right blade corridor bounds this cleanup.
            rgb=a[:,:,:3].astype(np.float32)
            brown=(rgb[:,:,0]>rgb[:,:,2]*1.15)&(rgb[:,:,0]>65)
            navy=(rgb[:,:,2]>rgb[:,:,0]*1.25)&(rgb[:,:,0]<75)
            hx,hy=wt.get('hand',[60,65])
            line_x,line_y,vx,vy,begin,end=wt['observedLine']
            along=(xx-line_x)*vx+(yy-line_y)*vy
            perpendicular=np.abs((xx-line_x)*vy-(yy-line_y)*vx)
            observed=(perpendicular<=2.4)&(along>=begin-2)&(along<=end+2)
            # Remove the observed generated blade, including its dark outline,
            # rather than only the new original-blade footprint (double swords).
            remove=(band|observed)&~brown&(yy>hy+3)&(xx>hx+5)
            a[remove]=0
            use=moved[:,:,3]>0;a[use]=moved[use]
        outputs.append(a);records.append(dict(frame=i,headApplied=ht['accepted'],swordApplied=wt['accepted']))
    return outputs,records


def export_variant(name,frames,indices,duration):
    folder=OUT/name;folder.mkdir(exist_ok=True)
    for i,a in enumerate(frames):Image.fromarray(a).save(folder/f'all-{i:03d}.png')
    selected=[Image.fromarray(frames[i]) for i in indices]
    sheet=Image.new('RGBA',(128*len(selected),128))
    for i,frame in enumerate(selected):
        frame.save(folder/f'frame-{i:02d}.png');sheet.paste(frame,(128*i,0))
    sheet.save(folder/'sheet.png')
    selected[0].save(folder/'animation.png',save_all=True,append_images=selected[1:],duration=duration,loop=0,disposal=0,blend=0)
    big=[im.resize((512,512),Image.Resampling.NEAREST) for im in selected]
    big[0].save(folder/'animation.webp',save_all=True,append_images=big[1:],duration=duration,loop=0,lossless=True)
    small=[im.resize((64,64),Image.Resampling.NEAREST) for im in selected]
    s=Image.new('RGBA',(64*len(small),64))
    for i,im in enumerate(small):s.paste(im,(64*i,0));im.save(folder/f'frame64-{i:02d}.png')
    s.save(folder/'sheet64.png')


def quality_report(variants,gray,reference_alpha,palette):
    report={};allowed={tuple(c) for c in palette.astype(np.uint8)}
    pairs=[flow_pair(gray[i-1],gray[i]) for i in range(1,len(gray))]
    for name,frames in variants.items():
        color_flips=[];edge_flips=[];motion=[];ious=[]
        for i,a in enumerate(frames):
            visible=a[:,:,3]>0
            assert a.shape==(128,128,4) and set(np.unique(a[:,:,3]))<={0,255}
            assert {tuple(c) for c in np.unique(a[:,:,:3][visible],axis=0)}<=allowed
            base=reference_alpha[i];intersection=(visible&base).sum();union=(visible|base).sum()
            ious.append(float(intersection/max(1,union)))
            if i:
                mx,my,valid,_=pairs[i-1];prev=frames[i-1]
                warped=cv2.remap(prev,mx,my,cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT)
                common=valid&visible&(warped[:,:,3]>0)
                color_flips.append(float(np.any(a[:,:,:3]!=warped[:,:,:3],axis=2)[common].mean()) if common.any() else 0)
                edge_flips.append(float(np.mean((visible!=(warped[:,:,3]>0))[valid])))
                motion.append(int(np.any(a!=prev,axis=2).sum()))
        report[name]=dict(meanMotionCompensatedColorChange=round(float(np.mean(color_flips)),5),
                          meanMotionCompensatedAlphaChange=round(float(np.mean(edge_flips)),5),
                          meanRawSilhouetteIoU=round(float(np.mean(ious)),5),
                          meanChangedPixels=round(float(np.mean(motion)),2),
                          warning='Lower changes can also mean over-freezing. These are diagnostics, not visual quality scores.')
    return report


def main():
    started=time.monotonic();OUT.mkdir(exist_ok=True)
    cv2.setNumThreads(4)
    palette=np.asarray(json.loads((SOURCE/'direction.json').read_text(encoding='utf-8'))['palette'],np.float32)
    loop=json.loads((SOURCE/'loop.json').read_text(encoding='utf-8'));indices=loop['selectedIndices'];duration=loop['frameDurationMs']
    reference=Image.open(SOURCE/'reference-right.png').convert('RGBA');reference.save(OUT/'reference.png')
    with av.open(str(SOURCE/'walk-raw.mp4')) as c:raw=[np.asarray(f.to_image().convert('RGB')) for f in c.decode(video=0)]
    rgbs=[];coverage=[];gray=[];original_alpha=[]
    for i,rgb in enumerate(raw):
        alpha=cutout(rgb);color,cov=robust_grid(rgb,alpha);rgbs.append(color);coverage.append(cov)
        gray.append(cv2.cvtColor(cv2.resize(rgb,(128,128),interpolation=cv2.INTER_AREA),cv2.COLOR_RGB2GRAY))
        original_alpha.append(np.asarray(Image.fromarray(alpha.astype(np.uint8)*255).resize((128,128),Image.Resampling.NEAREST))>0)
    baseline=[np.asarray(Image.open(SOURCE/'128/all-frames'/f'frame-{i:03d}.png').convert('RGBA')) for i in range(len(raw))]
    spatial=[]
    for rgb,cov in zip(rgbs,coverage):
        labels,_=quantize(rgb,palette);a=np.dstack((palette[labels].astype(np.uint8),(cov>=.5).astype(np.uint8)*255));a[a[:,:,3]==0,:3]=0;spatial.append(a)
    print('Grid samples ready',len(raw),'frames',flush=True)
    temporal,temporal_records=temporal_cleanup(rgbs,coverage,gray,palette)
    head_mask=np.zeros((128,128),bool);head_mask[HEAD[1]:HEAD[3],HEAD[0]:HEAD[2]]=True
    blade_mask=mask_polygon(BLADE)
    source_rgb=np.asarray(reference)[:,:,:3].astype(np.float32)
    # The broad geometric ROI overlaps navy coat pixels near the grip. They are
    # not part of the blade; retain only the reviewed pale/steel blade colours.
    blade_mask &= (source_rgb[:,:,0]>=70)&(source_rgb[:,:,0]<=source_rgb[:,:,2]*1.2)
    head_tracks=track_reference(gray,head_mask,'head')
    klt_weapon_tracks=track_reference(gray,blade_mask,'sword')
    # Blade deformation defeats direct reference KLT on several frames. Measure
    # hand motion + blade direction instead, while keeping the original scale.
    weapon_tracks=track_weapon_from_hand(rgbs)
    heads,_=apply_parts(temporal,reference,head_tracks,[dict(accepted=False) for _ in raw],blade_mask)
    parts,part_records=apply_parts(temporal,reference,head_tracks,weapon_tracks,blade_mask)
    for name,mask in [('head',head_mask),('blade',blade_mask)]:Image.fromarray(mask.astype(np.uint8)*255).save(OUT/f'mask-{name}.png')
    write_json('tracking.json',dict(head=head_tracks,sword=weapon_tracks,rejectedKLTExperiment=klt_weapon_tracks,applied=part_records,manualHeadBox=HEAD,manualBladePolygon=BLADE))
    variants=dict(baseline=baseline,spatial=spatial,temporal=temporal,head=heads,parts=parts)
    report=quality_report(variants,gray,original_alpha,palette)
    for name,frames in variants.items():export_variant(name,frames,indices,duration)
    montage=Image.new('RGB',(8*256,len(variants)*286),'#e1e2e9');d=ImageDraw.Draw(montage)
    for row,(name,frames) in enumerate(variants.items()):
        for col,index in enumerate(indices):
            im=Image.fromarray(frames[index]).resize((256,256),Image.Resampling.NEAREST)
            montage.paste(im,(col*256,row*286+30),im);d.text((col*256+8,row*286+8),f'{name} / {index}',fill='black')
    montage.save(OUT/'comparison.png')
    # Crop face and sword for inspecting actual pixel clusters, at integer scale.
    details=Image.new('RGB',(8*256,len(variants)*350),'#ddd');d=ImageDraw.Draw(details)
    for row,(name,frames) in enumerate(variants.items()):
        for col,index in enumerate(indices):
            im=Image.fromarray(frames[index]);face=im.crop((52,18,76,38)).resize((192,160),Image.Resampling.NEAREST);blade=im.crop((52,60,96,92)).resize((220,160),Image.Resampling.NEAREST)
            details.paste(face,(col*256,row*350+20),face);details.paste(blade,(col*256,row*350+184),blade)
            d.text((col*256+4,row*350+2),f'{name} / {index}',fill='black')
    details.save(OUT/'details.png')
    write_json('results.json',dict(version=VERSION,sourceSHA256=hashlib.sha256((SOURCE/'walk-raw.mp4').read_bytes()).hexdigest(),
             frames=len(raw),selectedIndices=indices,frameDurationMs=duration,palette=palette.astype(int).tolist(),
             diagnostics=report,temporalChanges=temporal_records,seconds=round(time.monotonic()-started,2),
             headAccepted=sum(t['accepted'] for t in head_tracks),swordAccepted=sum(t['accepted'] for t in weapon_tracks),
             recommendation='temporal: modest cleanup while retaining generated motion. head is optional. parts is a failed-quality prototype, not a recommended export.',
             limitations=['Manual head/blade masks for this single sprite','Head KLT and skin/blade tracking can drift; shape is not restored behind occlusions','Weapon composite still has harsh edges and remnants; not accepted as improved quality','Part rotation uses nearest sampling; pixel stair shapes can still change','Flow diagnostics do not establish natural gait or identity','No RGB temporal averaging, video regeneration or LoRA training']))
    with zipfile.ZipFile(OUT/'pixel-postprocess.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for name in variants:
            for p in (OUT/name).glob('*.png'):archive.write(p,p.relative_to(OUT).as_posix())
        for file in ('results.json','tracking.json','mask-head.png','mask-blade.png','reference.png'):archive.write(OUT/file,file)
    cards=''.join(f'<article><h2>{NAMES[name]}</h2><div class="checker"><canvas id="{name}" width="128" height="128"></canvas></div><p><a href="{name}/animation.webp">재생 파일</a> · <a href="{name}/sheet.png">128px 시트</a> · <a href="{name}/sheet64.png">64px 시트</a></p></article>' for name in variants)
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>도트 후처리 · 시간축과 파츠 추적 비교</title><style>body{background:#171923;color:#eee;font:15px/1.65 system-ui;margin:24px}h1{font-size:25px}main{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}article{padding:14px;background:#272b39;border:1px solid #525b74;border-radius:10px;min-width:0}h2{font-size:17px}.checker{background:repeating-conic-gradient(#ddd 0 25%,#f8f8f8 0 50%) 0/20px 20px}canvas{width:100%;image-rendering:pixelated}a{color:#bfccff}.controls{display:flex;gap:16px;flex-wrap:wrap;align-items:center;margin:18px 0}button,input{font:inherit}.wide{width:100%;image-rendering:pixelated}button{padding:6px 14px}@media(max-width:1000px){main{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:550px){main{grid-template-columns:1fr}}</style><h1>같은 MiniMax 영상 · 네 가지 도트 후처리</h1><p>새 영상·모델·학습 없이 기존 73프레임에 적용했습니다. 모든 비교는 같은 8개 원본 프레임과 같은 32색 팔레트입니다. 격자 대표 색, 전후 이동이 일치하는 영역의 색·알파 보정, 원본 얼굴·검의 위치 추적을 순서대로 비교합니다.</p><div class="controls"><button id="play">일시 정지</button><label>속도 <input type="range" id="speed" min="2" max="12" value="8"> <span id="fps">8</span> FPS</label><label>프레임 <input type="range" id="frame" min="0" max="7" value="0"> <span id="current">1 / 8</span></label></div><main>'''+cards+'''</main><p><a href="pixel-postprocess.zip" download>전후 PNG·시트·마스크·추적 기록 ZIP</a> · <a href="results.json">수치·처리 기록</a> · <a href="tracking.json">추적 신뢰도 기록</a> · <a href="../pixel-minimax-right-20261019/preview.html">원본 영상과 이전 결과</a></p><p>팔레트는 네 방식 모두 고정입니다. 얼굴과 검은 이 캐릭터에 수동 지정한 영역을 사용합니다. 검은 확대·축소 없이 회전/이동하며, 추적 불확실 시 덮어쓰지 않습니다. 파츠 합성 경계와 남은 검 픽셀도 검수 대상입니다. 변화량이 작아도 동작이 굳은 결과일 수 있어 수치만으로 품질을 판정하지 않습니다.</p><h2>네 방식 프레임 비교</h2><img class="wide" src="comparison.png"><details><summary>얼굴·검 확대</summary><img class="wide" src="details.png"></details><script>
const names=['baseline','spatial','temporal','parts'],images={};let index=0,playing=true,last=0;const slider=document.querySelector('#frame'),speed=document.querySelector('#speed');
function show(){for(const name of names){const c=document.getElementById(name).getContext('2d');c.imageSmoothingEnabled=false;c.clearRect(0,0,128,128);const image=images[name]?.[index];if(image?.complete&&image.naturalWidth)c.drawImage(image,0,0)}slider.value=index;document.querySelector('#current').textContent=`${index+1} / 8`}
for(const name of names){images[name]=[];for(let i=0;i<8;i++){const image=new Image();image.onload=show;image.src=`${name}/frame-${String(i).padStart(2,'0')}.png`;images[name].push(image)}}
document.querySelector('#play').onclick=()=>{playing=!playing;document.querySelector('#play').textContent=playing?'일시 정지':'재생';last=0};slider.oninput=()=>{playing=false;index=Number(slider.value);document.querySelector('#play').textContent='재생';show()};speed.oninput=()=>document.querySelector('#fps').textContent=speed.value;
function tick(now){if(playing&&now-last>=1000/Number(speed.value)){index=(index+1)%8;last=now;show()}requestAnimationFrame(tick)}requestAnimationFrame(tick);
</script></html>'''
    page=page.replace('네 가지 도트 후처리','다섯 가지 도트 후처리').replace('네 방식','다섯 방식').replace("['baseline','spatial','temporal','parts']","['baseline','spatial','temporal','head','parts']")
    page=page.replace('<div class="controls">','<p><strong>우선 후보는 세 번째 시간축 보정본입니다.</strong> 얼굴 잠금은 취향에 따라 비교하세요. 마지막 검 합성은 경계가 거칠고 잔여 픽셀이 있어 개선 완료로 판정하지 않은 실험본입니다.</p><div class="controls">')
    (OUT/'preview.html').write_text(page,encoding='utf-8')
    print(json.dumps(report,indent=2));print('TRACKS',sum(t['accepted'] for t in head_tracks),sum(t['accepted'] for t in weapon_tracks),'of',len(raw));print('SECONDS',round(time.monotonic()-started,2));print('PREVIEW',OUT/'preview.html')


if __name__=='__main__':main()
