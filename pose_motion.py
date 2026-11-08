"""Pose-conditioned walk/run drafts, reusing image edits and frame workspaces."""
from __future__ import annotations

import base64
import io
import json
import math
from pathlib import Path
import secrets
import shutil
import time

from flask import jsonify, request, send_file, redirect
from PIL import Image

import image_background
import image_engine
import image_pose
import rigging_engine
import motion_identity

ROOT = Path(__file__).resolve().parent
# Retired after real walk/run comparisons. Keep readers and historical outputs.
GENERATE_ENABLED = False
NEUTRAL = [[.53,.15],[.50,.25],[.46,.27],[.43,.42],[.42,.56],
           [.54,.27],[.57,.42],[.58,.56],[.47,.53],[.43,.72],[.40,.91],
           [.53,.53],[.57,.72],[.60,.91],[.54,.14],[.52,.14],[.51,.15],[.49,.15]]


def align_frame(image,size):
    """Place the visible silhouette on a common floor without cropping or stretching it."""
    image=image.convert('RGBA')
    box=image.getchannel('A').point(lambda a:255 if a>=24 else 0).getbbox()
    if not box:raise RuntimeError('생성 프레임이 비어 있습니다.')
    crop=image.crop(box)
    scale=min(size[0]*.88/crop.width,size[1]*.88/crop.height)
    target=(max(1,round(crop.width*scale)),max(1,round(crop.height*scale)))
    crop=crop.convert('RGBa').resize(target,Image.Resampling.LANCZOS).convert('RGBA')
    full=Image.new('RGBA',size)
    left=(size[0]-crop.width)//2;top=round(size[1]*.95)-crop.height
    full.paste(crop,(left,top))
    return full,dict(sourceBox=list(box),scale=scale,left=left,top=top)


ACTIONS={'walk':'걷기','run':'달리기'}


def gait(action='walk',count=4,facing='right',stride=None):
    """Full-body COCO-18 gait. Run includes flight, a forward lean and bent arms."""
    if not isinstance(action,str) or action not in ACTIONS:raise ValueError('걷기 또는 달리기를 선택하세요.')
    if type(count) is not int or count not in (4,8):raise ValueError('포즈는 4장 또는 8장을 지정하세요.')
    if facing not in ('left','right'):raise ValueError('왼쪽·오른쪽 방향을 선택하세요.')
    if stride is None:stride=.17 if action=='run' else .12
    if type(stride) not in (int,float) or not math.isfinite(stride) or not .04<=stride<=.22:raise ValueError('보폭은 0.04~0.22입니다.')
    run=action=='run'
    frames = []
    for i in range(count):
        phase = 2*math.pi*i/count
        swing = math.cos(phase)
        points = [p[:] for p in NEUTRAL]
        lift_cycle=math.sin(phase)**2
        bob=-(.045 if run else .022)*lift_cycle
        sway=.012*math.sin(phase)
        hip=[.48+sway,.54+bob]
        neck=[hip[0]+(.095 if run else .018)+.012*swing,.27+bob]
        for joint in (0,14,15,16,17):
            points[joint]=[NEUTRAL[joint][0]+neck[0]-.5,NEUTRAL[joint][1]+neck[1]-.25]
        points[1]=neck
        # Shoulder and pelvis counter-motion, rather than a rigid upper-body block.
        for joint,sign in ((2,1),(5,-1)):
            points[joint]=[neck[0]+sign*(.021+.012*swing),neck[1]+.02+sign*.009*swing]
        for joint,sign in ((8,1),(11,-1)):
            points[joint]=[hip[0]+sign*(.016-.008*swing),hip[1]-sign*.007*swing]
        for hip,knee,ankle,sign in [(8,9,10,1),(11,12,13,-1)]:
            s = swing*sign
            lift = max(0,math.sin(phase)*sign)
            # Both feet leave the ground around run passing poses. Walking always
            # retains a support foot; the trailing knee folds forward naturally.
            points[ankle]=[.48+sway+s*stride-(.07*lift if run else 0),.92-lift*(.20 if run else .13)-(.075*lift_cycle if run else 0)]
            a=points[hip];b=points[ankle]
            dx,dy=b[0]-a[0],b[1]-a[1];distance=math.hypot(dx,dy)
            half=distance/2;length=max(.215,half+.001)
            bend=math.sqrt(max(0,length*length-half*half))
            points[knee]=[(a[0]+b[0])/2+dy/distance*bend,(a[1]+b[1])/2-dx/distance*bend]
        for shoulder,elbow,wrist,sign in [(2,3,4,-1),(5,6,7,1)]:
            s=sign*swing;a=points[shoulder]
            points[elbow]=[a[0]+s*stride*.8-(.025 if run else 0),a[1]+.15+(.012*s if run else 0)]
            points[wrist]=[a[0]+s*stride*(1.15 if run else 1.05)+(.09 if run else .02),
                           a[1]+(.085-.07*s if run else .25-.035*abs(s))]
        if facing=='left':points = [[1-x,y] for x,y in points]
        frames.append(dict(points=points,strength=1.1))
    return frames


def walking(count=4,facing='right',stride=.12):return gait('walk',count,facing,stride)


def preserve_canvas(image,size):
    """Keep generated placement, including body bob and run flight; never fit each silhouette."""
    image=image.convert('RGBA')
    if not image.getchannel('A').getbbox():raise RuntimeError('생성 프레임이 비어 있습니다.')
    if image.size!=size:image=image.convert('RGBa').resize(size,Image.Resampling.LANCZOS).convert('RGBA')
    return image,dict(mode='fixed-canvas',left=0,top=0,scale=1)


def validate(p):
    if not isinstance(p,dict):raise ValueError('동작 설정을 확인하세요.')
    model=p.get('model','wai-cutscene-counter')
    if model not in image_pose.SUPPORTED:raise ValueError('지원하는 기본 그림체를 선택하세요.')
    consistency=p.get('consistency','reference-edit')
    if consistency not in ('reference-edit','independent'):raise ValueError('외형 보존 방식을 확인하세요.')
    action=p.get('action','walk')
    if not isinstance(action,str) or action not in ACTIONS:raise ValueError('걷기 또는 달리기를 선택하세요.')
    facing=p.get('facing','right')
    if facing not in ('left','right'):raise ValueError('동작 초안은 왼쪽·오른쪽 방향을 지원합니다.')
    poses=p.get('poses')
    if not isinstance(poses,list) or len(poses) not in (4,8) or any(not isinstance(pose,dict) for pose in poses):raise ValueError('동작 포즈는 4장 또는 8장을 지정하세요.')
    clean=[image_pose.validate(pose,model,'reference',require_ready=consistency=='independent') for pose in poses]
    prompt=p.get('prompt','')
    if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>3000:raise ValueError('유지할 캐릭터 외형을 1~3000자로 입력하세요.')
    size=p.get('size','512x768')
    if size not in ('512x768','768x1024'):raise ValueError('지원하는 프레임 해상도를 선택하세요.')
    fps=p.get('fps',len(clean)*3//2 if action=='run' else len(clean))
    if type(fps) is not int or not 1<=fps<=24:raise ValueError('FPS는 1~24 정수로 입력하세요.')
    denoise=p.get('denoise',.8)
    if type(denoise) not in (int,float) or not math.isfinite(denoise) or not .4<=denoise<=.95:raise ValueError('포즈 변형 강도는 0.4~0.95입니다.')
    seed=p.get('seed')
    if seed in (None,''):seed=secrets.randbelow(2**32)
    if type(seed) is not int or not 0<=seed<2**32:raise ValueError('재현 번호는 0~4294967295 정수입니다.')
    return dict(action=action,model=model,facing=facing,poses=clean,prompt=prompt.strip(),size=size,fps=fps,denoise=denoise,seed=seed,consistency=consistency)


def run_job(jid,p):
    """Each frame sees the same reference and seed; no generated-frame feedback drift."""
    root=Path(p['_motionRoot'])/jid
    reference=(root/'reference.png').read_bytes()
    image_data='data:image/png;base64,'+base64.b64encode(reference).decode()
    width,height=map(int,p['size'].split('x'))
    folder=Path(p['_frameRoot'])/p['workspaceId']
    folder.mkdir(parents=True,exist_ok=False)
    action=p.get('action','walk');label=ACTIONS[action]
    doc=dict(revision=0,width=width,height=height,columns=len(p['poses']),rows=1,
             fps=p['fps'],frames=[],clips=[dict(name=action,start=0,end=len(p['poses'])-1)],
             motion=dict(action=action,template=action+'-v2',alignment='fixed-canvas',poses=p['poses'],facing=p['facing'],seed=p['seed'],
                         model=p['model'],denoise=p['denoise'],prompt=p['prompt'],referenceJob=jid,
                         consistency=p.get('consistency','independent')))
    callback=image_engine.update_job
    completed=False
    try:
        if p.get('consistency')=='reference-edit':
            # Release other model processes on this shared GPU before loading the editor.
            for address in (image_engine.COMFY_URL,image_engine.image_soya.URL):
                try:
                    image_engine.requests.post(address+'/free',json=dict(unload_models=True,free_memory=True),timeout=30).raise_for_status()
                except image_engine.requests.ConnectionError:pass
            with Image.open(root/'reference.png') as opened:
                original=opened.convert('RGBA')
            anchor,_=align_frame(original,(width,height))
            for i,pose in enumerate(p['poses']):
                update_job(jid,state='generating',message=f'원화 보존 {label} 편집 중 · {i+1}/{len(p["poses"])}',completedFrames=i,totalFrames=len(p['poses']))
                prompt=identity_prompt(p,pose,i)
                edited=motion_identity.edit_frame(anchor,pose,(width,height),p['seed'],prompt,root,i)
                aligned,alignment=preserve_canvas(edited,(width,height))
                name=f'original-{i:03d}.png';aligned.save(folder/name)
                doc['frames'].append(dict(file=name,locked=False,alignment=alignment))
                image_pose.render(pose,(width,height)).save(root/f'pose-{i:03d}.png')
                if i==0:
                    # All subsequent edits share the first generated frame as a baseline.
                    # They never see each other's output, avoiding recursive identity drift.
                    anchor=aligned.copy();anchor.save(root/'identity-anchor.png')
            doc['motion'].update(model='qwen-image-2.1-edit',appearanceAnchorFrame=0,identityVersion='fixed-anchor-v2',alignment='fixed-canvas')
            (root/'motion.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
            completed=True
            return doc
        for i,pose in enumerate(p['poses']):
            settings=image_engine.validate(dict(model=p['model'],mode='reference',preset='sprite',
                prompt=p['prompt']+f', {"running" if action=="run" else "walking"} in place, opposite arm swing, moving shoulders and torso, single character, full body, feet visible',
                negativePrompt='worst quality, low quality, blurry, text, watermark, extra limbs, multiple characters, halo, floating ring',
                imageData=image_data,width=width,height=height,steps=24,cfg=4.5,count=1,
                seed=p['seed'],denoise=p['denoise'],background='transparent',pose=pose,
                assetSpec=dict(type='side',directionCount=1,facing=p['facing'])))
            # Generic single-image presets include a standing/battle stance. Remove that
            # conflicting instruction for a walking frame while keeping style triggers.
            verb='running' if action=='run' else 'walking'
            settings['resolvedPrompt']=settings['resolvedPrompt'].replace('standing in a battle ready stance',f'{verb} mid-stride, opposite arm swing').replace('standing,',verb+',')
            result={}
            def capture(child,**changes):
                result.update(changes)
                if changes.get('state')!='complete':
                    update_job(jid,state='generating',message=f'{label} 프레임 생성 중 · {i+1}/{len(p["poses"])}',completedFrames=i,totalFrames=len(p['poses']))
            image_engine.update_job=capture
            child=f'{jid}_{i:02d}'
            try:
                image_engine.run_job(child,settings)
                item=result.get('images',[None])[0]
                if not item or item.get('background')!='transparent':raise RuntimeError('프레임 배경 제거에 실패했습니다. 기존 결과는 유지됩니다.')
                source=image_engine.RESULT_ROOT/child/'image-1.png'
                with Image.open(source) as image:
                    if image.size!=(width,height) or not image.getchannel('A').getbbox():raise RuntimeError('생성 프레임 크기 또는 투명도를 확인할 수 없습니다.')
                    aligned,alignment=preserve_canvas(image,(width,height))
                    name=f'original-{i:03d}.png';aligned.save(folder/name)
                doc['frames'].append(dict(file=name,locked=False,alignment=alignment))
                image_pose.render(pose,(width,height)).save(root/f'pose-{i:03d}.png')
            finally:
                # Child generations are private intermediates without job rows.
                shutil.rmtree(image_engine.RESULT_ROOT/child,ignore_errors=True)
        (root/'motion.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
        completed=True
        return doc
    finally:
        image_engine.update_job=callback
        if not completed:shutil.rmtree(folder,ignore_errors=True)
        if p.get('consistency')=='reference-edit':
            try:
                image_engine.requests.post(rigging_engine.COMFY_URL+'/free',json=dict(unload_models=True,free_memory=True),timeout=30)
            except image_engine.requests.RequestException:pass


def update_job(jid,**changes):pass  # bound by the shared FIFO worker


def identity_prompt(p,pose,index):
    direction='right' if p['facing']=='right' else 'left'
    points=pose['points']
    # State a gait phase in addition to the skeleton; repeated vague "walking" prompts
    # otherwise tend to return the same pose even when the guide legs have changed.
    spread=abs(points[10][0]-points[13][0])
    phase=('passing step, legs passing close together, one knee bent and one foot lifted' if spread<.08 else
           'contact step, legs apart, right leg in front and left leg behind' if (points[10][0]>points[13][0])==(direction=='right') else
           'opposite contact step, legs apart, left leg in front and right leg behind')
    run=p.get('action','walk')=='run';verb='running' if run else 'walking'
    if run:
        phase=('flight passing step, both feet off the ground, one knee high and the other leg folded behind' if min(points[10][1],points[13][1])<.76 else
               'running contact step, one foot landing and the other reaching behind')
    arm='right arm forward and left arm back' if (points[4][0]>points[7][0])==(direction=='right') else 'left arm forward and right arm back'
    camera=(f'Create a full-body {verb} game sprite facing {direction} in a consistent side view.' if index==0 else
            f'Keep the same side view, facing {direction}, and the same character proportions as image 1, but CHANGE the entire body pose.')
    body=('Fast run, pronounced forward torso lean, elbows bent about 90 degrees, hands pumping between chest and waist, high knee lift and visible flight. ' if run else
          'Relaxed walk, upright but moving torso, mild elbow bend, hands swinging past the hips, one foot supporting the body. ')
    return ('Image 1 is the sole character appearance reference. Image 2 is a colored skeleton pose guide, not a style reference. '
            'Repose the exact character in image 1 to match ALL joints in image 2, including shoulders, elbows, wrists, neck and pelvis, not just the legs. '+camera+' '+phase+'. '+body+
            'Arm phase: '+arm+'. Arms swing opposite the legs; shoulders counter-rotate against the pelvis, torso rises and falls with the step. '
            'The coat sleeves follow the arms and the coat hem trails the movement. The upper body must NOT remain frozen in the reference pose. '
            'Preserve character design: face identity, hair length, hood, collar, every garment, seams, buttons, gloves, trousers, coat hem, boots, colors, linework and shading style. '
            'Clothing folds, arm positions, hair silhouette and torso orientation MUST change to follow the new pose. Preserve design, not the original silhouette. '
            'Do not redesign clothes, add jewelry, remove equipment or invent skin exposure. '
            f'One character, {verb} in place, entire body and both feet visible, fixed camera and character scale, plain white background. Do not draw the skeleton. '
            'Appearance notes, subordinate to the image reference: '+p['prompt'])


def register(app,db,auth,data,payload):
    motion_root=Path(data)/'pose-motions';motion_root.mkdir(exist_ok=True)
    frame_root=Path(data)/'frame-workspaces'

    def owned_character(con,cid):
        row=con.execute('SELECT * FROM characters WHERE id=?',(cid,)).fetchone()
        if not row:raise ValueError('캐릭터 묶음을 찾을 수 없습니다.')
        if row['owner']!=request.team_user['id'] and request.team_user['role']!='admin':raise PermissionError('본인 캐릭터 묶음 또는 관리자만 생성할 수 있습니다.')
        return row

    @app.get('/motion-studio')
    @auth()
    def motion_page():
        if not GENERATE_ENABLED:return redirect('/#/create/sprite')
        return send_file(ROOT/'web/motion-studio.html',max_age=0)

    def retired():return jsonify(error='포즈별 동작 생성은 종료했습니다. 영상 기반 스프라이트 도구를 사용하세요.',retired=True,editor='/#/create/sprite'),410

    @app.get('/api/motions/templates')
    @auth()
    def motion_templates():
        if not GENERATE_ENABLED:return retired()
        models=[dict(id=model,name=image_engine.MODELS[model]['name'],ready=all((image_engine.engine.COMFY_ROOT/'models'/f).is_file() for f in image_engine.MODELS[model]['files'])) for model in image_pose.SUPPORTED]
        return jsonify(walk4=walking(4),walk8=walking(8),run4=gait('run',4),run8=gait('run',8),links=image_pose.LINKS,ready=image_pose.status()['ready'] and image_background.status()['ready'],identityReady=motion_identity.ready(),models=models)

    @app.get('/api/motions/poses')
    @auth()
    def motion_poses():
        if not GENERATE_ENABLED:return retired()
        try:
            count=int(request.args.get('count','4'));stride=float(request.args.get('stride','.12'))
        except (ValueError,TypeError):raise ValueError('프레임 수와 보폭을 확인하세요.')
        action=request.args.get('action','walk')
        return jsonify(poses=gait(action,count,request.args.get('facing','right'),stride))

    @app.post('/api/motions')
    @auth()
    def create_motion():
        if not GENERATE_ENABLED:return retired()
        p=payload();settings=validate(p)
        if not image_background.status()['ready']:raise ValueError('배경 제거 모델이 필요합니다.')
        if settings['consistency']=='reference-edit':
            if not motion_identity.ready():raise ValueError('원화 보존 편집 모델이 준비되지 않았습니다.')
        elif not all((image_engine.engine.COMFY_ROOT/'models'/f).is_file() for f in image_engine.MODELS[settings['model']]['files']):raise ValueError('선택한 그림체 모델이 준비되지 않았습니다.')
        cid=p.get('characterId')
        if cid is not None and not isinstance(cid,str):raise ValueError('캐릭터 묶음을 확인하세요.')
        source=None
        with db() as con:
            if cid:
                character=owned_character(con,cid)
                if not p.get('imageData') and character['reference']:
                    with Image.open(Path(data)/'characters'/cid/character['reference']) as im:source=im.convert('RGBA')
        if source is None:source=image_engine.read_image(p.get('imageData'))
        if not source.getchannel('A').getbbox():raise ValueError('기준 원화가 비어 있습니다.')
        jid=secrets.token_hex(16);wid=secrets.token_hex(16);folder=motion_root/jid;folder.mkdir()
        try:
            source.save(folder/'reference.png')
            settings.update(jobType='pose-motion',characterId=cid,workspaceId=wid,_motionRoot=str(motion_root),_frameRoot=str(frame_root),animationType='포즈 기반 '+ACTIONS[settings['action']]+' 초안')
            with db() as con:
                con.execute('BEGIN IMMEDIATE')
                if cid:owned_character(con,cid)
                active=con.execute("SELECT count(*) FROM jobs WHERE state NOT IN ('complete','error','cancelled')").fetchone()[0]
                mine=con.execute("SELECT count(*) FROM jobs WHERE user_id=? AND state NOT IN ('complete','error','cancelled')",(request.team_user['id'],)).fetchone()[0]
                if active>=20 or mine>=3:raise ValueError('전체 20개 또는 개인 3개 대기 한도에 도달했습니다.')
                con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(jid,request.team_user['id'],'queued',time.time(),time.time(),json.dumps(settings),json.dumps(dict(message='포즈 기반 '+ACTIONS[settings['action']]+' 대기 중'))))
        except Exception:
            shutil.rmtree(folder,ignore_errors=True);raise
        return jsonify(taskId=jid),202

    @app.get('/api/motions/<jid>')
    @auth()
    def motion_status(jid):
        with db() as con:row=con.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
        if not row or json.loads(row['payload']).get('jobType')!='pose-motion':return jsonify(error='동작 작업을 찾을 수 없습니다.'),404
        if row['user_id']!=request.team_user['id'] and request.team_user['role']!='admin':raise PermissionError('본인 동작 작업만 확인할 수 있습니다.')
        result=json.loads(row['result'] or '{}')
        return jsonify(result|dict(state=row['state']))

    def finish(jid,p,doc):
        """Publish the complete workspace in one transaction, never a partial walking cycle."""
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            row=con.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
            if not row or row['state']=='cancelled':raise RuntimeError('동작 작업이 취소되거나 삭제되었습니다.')
            wid=p['workspaceId'];cid=p.get('characterId')
            con.execute('INSERT INTO frame_workspaces VALUES(?,?,?,?,?,?,?)',(wid,None,cid,row['user_id'],json.dumps(doc),time.time(),time.time()))
            con.execute('INSERT INTO frame_versions VALUES(?,?,?,?)',(wid,0,json.dumps(doc),time.time()))
            if cid:con.execute('UPDATE characters SET updated=? WHERE id=?',(time.time(),cid))
        update_job(jid,state='complete',message=ACTIONS[p.get('action','walk')]+' 초안 완료 · 프레임 편집기에서 확인하세요.',workspaceId=wid,editor='/frame-editor?set='+wid)

    return finish
