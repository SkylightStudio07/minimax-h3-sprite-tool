"""Static pages, status, gallery and generation entry routes."""
from itsdangerous import BadSignature
from PIL import Image
from PIL import ImageChops
from pathlib import Path
from itsdangerous import SignatureExpired
import asset_types
import base64
import idle_tool as engine
import image_engine
import io
import json
from flask import jsonify
import music_engine as music
import music_prompts
import re
from flask import redirect
from flask import request
import rigging_v2 as rig_v2
import rigging_engine as rigging
import secrets
from flask import send_file
from flask import send_from_directory
from flask import session
import sprite_prompts
import time


def register(app, *, GALLERY_PRIVATE_KEYS, ROOT, auth, database, db, link_character_job, payload, poster_lock,
             public_live2d_payload, rig_version_payload, unity_importer_archive, unity_links):
    @app.get('/')
    def home():
        return send_file(ROOT / 'web' / 'team.html')

    @app.get('/studio')
    @auth()
    def studio():
        html = (ROOT / 'web' / 'index.html').read_text(encoding='utf-8')
        shim = """<script>
        const teamBase=new URL('./',location.href).pathname;
        const nativeFetch=window.fetch.bind(window);
        window.fetch=async(input,options={})=>{
          if(typeof input==='string'&&input.startsWith('/'))input=teamBase+input.slice(1);
          options.headers={...options.headers,'X-Sprite-Request':'1'};
          const r=await nativeFetch(input,options);
          if(r.status===401)top.location.href=teamBase;
          return r;
        };
        function fixURL(v){return typeof v==='string'&&v.startsWith('/outputs/')?teamBase+v.slice(1):v}
        for(const [proto,key] of [[HTMLMediaElement.prototype,'src'],[HTMLImageElement.prototype,'src'],[HTMLAnchorElement.prototype,'href']]){
          const d=Object.getOwnPropertyDescriptor(proto,key);
          Object.defineProperty(proto,key,{...d,set(v){d.set.call(this,fixURL(v))}});
        }
        </script>"""
        return html.replace('<head>','<head>'+shim)

    @app.get('/rigging')
    @auth()
    def rigging_studio():
        response=send_file(ROOT / 'web' / 'rigging.html',conditional=False,max_age=0)
        response.headers['Cache-Control']='no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma']='no-cache'
        return response

    @app.get('/music')
    @auth()
    def music_studio():
        response=send_file(ROOT / 'web' / 'music.html',conditional=False,max_age=0)
        response.headers['Cache-Control']='no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma']='no-cache'
        return response

    @app.get('/api/sprite-prompts/status')
    @auth()
    def sprite_prompt_status():
        return jsonify(sprite_prompts.status_payload())

    @app.post('/api/sprite-prompts/analyze')
    @auth()
    def analyze_sprite_reference():
        image=image_engine.read_image(payload().get('imageData'))
        try:
            return jsonify(sprite_prompts.analyze(image,f'{database.resolve()}:{request.team_user["id"]}'))
        except sprite_prompts.PromptBusy as error:
            return jsonify(error=str(error)),429

    @app.post('/api/sprite-prompts/plan')
    @auth()
    def plan_sprite_motion():
        try:
            return jsonify(sprite_prompts.plan(payload(),f'{database.resolve()}:{request.team_user["id"]}'))
        except sprite_prompts.PromptBusy as error:
            return jsonify(error=str(error)),429

    @app.get('/unity-importer.zip')
    @auth()
    def unity_importer_download():
        return send_file(unity_importer_archive(), mimetype='application/zip', as_attachment=True,
                         download_name='sprite-lab-unity-importer.zip', conditional=False, max_age=0)

    @app.get('/rigging-editor')
    @auth()
    def rigging_editor_page():
        response=send_file(ROOT / 'web' / 'rigging-editor.html',conditional=False,max_age=0)
        response.headers['Cache-Control']='no-store, no-cache, must-revalidate, max-age=0'
        return response

    @app.get('/rigging-expressions.js')
    def rigging_expression_script():
        return send_file(ROOT/'web'/'rigging-expressions.js',conditional=False,max_age=0)

    @app.get('/rigging-bones.js')
    def rigging_bone_script():
        return send_file(ROOT/'web'/'rigging-bones.js',conditional=False,max_age=0)

    @app.get('/rigging-animation.js')
    @app.get('/rigging-animation-math.js')
    def rigging_animation_script():
        return send_file(ROOT/'web'/request.path.rsplit('/',1)[1],conditional=False,max_age=0)

    @app.get('/guide')
    def guide_page():
        return send_file(ROOT / 'web' / 'guide.html',conditional=False,max_age=0)

    @app.get('/layer-editing-guide')
    def layer_editing_guide_page():
        return redirect('guide#rig-studio',code=301)

    @app.get('/assets/<path:filename>')
    def ui_assets(filename):
        # Shared design system (ui.css/ui.js) and self-hosted fonts; public because the landing and /live2d pages use it.
        response=send_from_directory(ROOT / 'web' / 'assets',filename,conditional=True,max_age=0)
        if filename.lower().endswith('.webp'):
            response.mimetype='image/webp'
        if filename.startswith('fonts/'):
            response.headers['Cache-Control']='public, max-age=31536000, immutable'
        else:
            response.headers['Cache-Control']='no-cache'
        return response

    @app.get('/rigging-player/<path:filename>')
    @auth()
    def rigging_player(filename):
        response=send_from_directory(ROOT / 'vendor' / 'Anime2.5DRig',filename,conditional=False,max_age=0)
        response.headers['Cache-Control']='no-store, no-cache, must-revalidate, max-age=0'
        return response

    @app.post('/api/shares/<token>/revoke')
    @auth()
    def revoke_share(token):
        user=request.team_user
        with db() as con:
            row=con.execute("""SELECT s.*,j.user_id FROM rig_shares s JOIN jobs j ON j.id=s.job_id
                WHERE s.token=? AND s.revoked IS NULL""",(token,)).fetchone()
            if not row:
                return jsonify(error='공유 링크를 찾을 수 없습니다.'),404
            if user['role']!='admin' and user['id'] not in (row['user_id'],row['created_by']):
                return jsonify(error='공유 링크를 해제할 권한이 없습니다.'),403
            con.execute('UPDATE rig_shares SET revoked=? WHERE token=?',(time.time(),token))
        return jsonify(ok=True)

    @app.get('/api/status')
    @auth()
    def status():
        s = engine.status_payload()
        rs = rigging.status_payload()
        ms = music.status_payload() | {'gemini': music_prompts.status_payload()}
        return jsonify(**{k:s[k] for k in ('comfy','modelsReady','licenseConfirmed')}, spriteWorkflows=s.get('spriteWorkflows',[]), spriteBackground=engine.image_background.status(), rigging=rs, music=ms)

    def gallery_viewer_approved(con):
        viewer=con.execute("SELECT state FROM users WHERE id=?",(session.get('uid'),)).fetchone()
        return bool(viewer and viewer['state']=='approved')

    def gallery_item(row,approved,public_by_job,settings=False):
        result=json.loads(row['result'] or '{}')
        p=json.loads(row['payload'])
        item=dict(id=row['id'],created=row['created'],updated=row['updated'],animationType=p.get('animationType','idle'),jobType=p.get('jobType','video'),title=p.get('resultTitle'),
            poster=f'/gallery-media/{row["id"]}/poster' if result.get('video') else None,
            exportSheets={k:f'/gallery-media/{row["id"]}/{k}' for k in result.get('exportSheets',{})},
            loop=bool(p.get('loop',True)),loopReport=result.get('loopReport'),
            **{k:f'/gallery-media/{row["id"]}/{k}' if result.get(k) else None for k in ('video','spriteSheet','transparentSheet','loopVideo','loopSheet','loopTransparentSheet')})
        if approved:
            item['frameWorkspace']=result.get('frameWorkspace')
            item.update(owner=row['name'],userId=row['user_id'],rawVideo=result.get('rawVideo'))
            if p.get('jobType')=='rigging':
                current=int(result.get('rigRevision',0))
                item.update(composite=result.get('composite'),psd=result.get('psd'),package=result.get('package'),packageV2=result.get('packageV2'),rigRevision=current,rigV2BoneCount=result.get('rigV2BoneCount'),player=result.get('player'),
                            rigVersions=rig_version_payload(row['id'],current,f'/api/jobs/{row["id"]}/rig-edit/versions'),
                            publicLive2d=public_live2d_payload(public_by_job.get(row['id'])))
            elif p.get('jobType')=='image':
                item.update(image=result.get('image'),images=result.get('images',[]),metadata=result.get('metadata'))
            elif p.get('jobType')=='music':
                item.update(audio=result.get('audio'),score=result.get('score'),duration=result.get('duration'),
                            promptReason=p.get('promptReason'),resolvedPrompt=p.get('resolvedPrompt'),
                            vocalMode=p.get('vocalMode','instrumental'),lyrics=p.get('lyrics',''))
            if settings:
                # Inputs are stripped after a job finishes; what remains are the reusable form settings.
                item['settings']={k:v for k,v in p.items() if k not in GALLERY_PRIVATE_KEYS}
        return item

    @app.get('/api/gallery')
    def public_gallery():
        try:
            page=max(1,int(request.args.get('page','1')))
            size=min(48,max(1,int(request.args.get('size','6'))))
        except ValueError:
            raise ValueError('페이지 번호와 개수는 정수여야 합니다.')
        kind=request.args.get('type','')
        if kind not in ('','video','rigging','music','image'):
            raise ValueError('결과 종류가 올바르지 않습니다.')
        query=request.args.get('q','').strip()[:60]
        with db() as con:
            approved=gallery_viewer_approved(con)
            if not approved:
                kind='video'  # guests only see finished sprite videos
            clauses,args=["j.state='complete'", "COALESCE(json_extract(j.payload,'$.jobType'),'video') NOT IN ('rig-part','frame-edit','pose-motion')"],[]
            if kind:
                clauses.append("COALESCE(json_extract(j.payload,'$.jobType'),'video')=?");args.append(kind)
            if approved and request.args.get('owner')=='me':
                clauses.append('j.user_id=?');args.append(session.get('uid'))
            if query:
                like='%'+query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
                fields=["json_extract(j.payload,'$.animationType')","json_extract(j.payload,'$.title')","json_extract(j.payload,'$.resultTitle')"]+(['u.name'] if approved else [])
                clauses.append('('+' OR '.join(f"COALESCE({field},'') LIKE ? ESCAPE '\\'" for field in fields)+')');args+=[like]*len(fields)
            where=' AND '.join(clauses)
            total=con.execute(f"SELECT count(*) FROM jobs j JOIN users u ON u.id=j.user_id WHERE {where}",args).fetchone()[0]
            pages=max(1,(total+size-1)//size);page=min(page,pages)
            rows=con.execute(f"""SELECT j.*,u.name FROM jobs j JOIN users u ON u.id=j.user_id
                WHERE {where} ORDER BY j.updated DESC,j.id DESC LIMIT ? OFFSET ?""",(*args,size,(page-1)*size)).fetchall()
            public_by_job={item['job_id']:item for item in con.execute(
                'SELECT * FROM public_live2d WHERE revoked IS NULL').fetchall()} if approved else {}
        return jsonify(jobs=[gallery_item(row,approved,public_by_job) for row in rows],page=page,pages=pages,total=total)

    @app.get('/api/gallery/<jid>')
    def gallery_detail(jid):
        with db() as con:
            approved=gallery_viewer_approved(con)
            row=con.execute("""SELECT j.*,u.name FROM jobs j JOIN users u ON u.id=j.user_id
                WHERE j.id=? AND j.state='complete'""",(jid,)).fetchone()
            if not row or (not approved and json.loads(row['payload']).get('jobType','video')!='video'):
                return jsonify(error='결과를 찾을 수 없습니다.'),404
            public=con.execute('SELECT * FROM public_live2d WHERE revoked IS NULL AND job_id=?',(jid,)).fetchone() if approved else None
        return jsonify(job=gallery_item(row,approved,{jid:public} if public else {},settings=approved))

    @app.get('/gallery-media/<jid>/<kind>')
    def public_result(jid,kind):
        # Only presentation assets are public, never rawVideo or input images.
        if kind not in ('video','spriteSheet','transparentSheet','poster','loopVideo','loopSheet','loopTransparentSheet') and not re.fullmatch(r'sheet_[0-9]+_[0-9a-f]{16}(?:_transparent)?',kind):
            return jsonify(error='결과를 찾을 수 없습니다.'),404
        with db() as con:
            row=con.execute("SELECT result FROM jobs WHERE id=? AND state='complete'",(jid,)).fetchone()
        result=json.loads(row['result'] or '{}') if row else {}
        if kind=='poster':
            relative=result.get('video','')
            if not relative.startswith(f'/outputs/results/{jid}/'):
                return jsonify(error='영상이 없습니다.'),404
            folder=(engine.RESULT_ROOT/jid).resolve()
            video=(folder/Path(relative).name).resolve()
            cached=(folder/'gallery-poster-v1.jpg').resolve()
            if (not folder.is_relative_to(engine.RESULT_ROOT.resolve()) or
                not video.is_relative_to(folder) or not cached.is_relative_to(folder) or not video.is_file()):
                return jsonify(error='영상 파일이 없습니다.'),404
            try:
                with poster_lock:
                    if not cached.is_file():
                        content=engine.video_thumbnail(video)
                        cached.write_bytes(content)
            except Exception:
                app.logger.exception('Gallery thumbnail failed')
                return jsonify(error='썸네일을 만들 수 없습니다.'),500
            return send_file(cached,mimetype='image/jpeg',conditional=True,max_age=0)
        relative=result.get('exportSheets',{}).get(kind) if kind.startswith('sheet_') else result.get(kind)
        if not relative or not relative.startswith(f'/outputs/results/{jid}/'):
            return jsonify(error='결과를 찾을 수 없습니다.'),404
        target=(engine.RESULT_ROOT/jid/Path(relative).name).resolve()
        if not target.is_relative_to(engine.RESULT_ROOT.resolve()) or not target.is_file():
            return jsonify(error='파일을 찾을 수 없습니다.'),404
        return send_file(target,conditional=True)

    @app.post('/api/generate')
    @auth()
    def generate():
        p=payload()
        p['jobType']='video'
        if p.get('motionPromptMode','manual') not in ('manual','image-guided'):
            raise ValueError('동작 설명 방식을 확인하세요.')
        spec=asset_types.validate(p.get('assetSpec'))
        if spec:p['assetSpec']=spec
        engine.guidance_options(p)
        p.update(engine.sprite_combat.options(p))
        engine.background_options(p)
        engine.motion_timing.options(p)
        if p.get('samplingMode','quality') not in ('quality','turbo'):
            raise ValueError('잘못된 생성 모드입니다.')
        p.setdefault('samplingMode','quality')
        if type(p.get('motionPadding',10)) is not int or p.get('motionPadding',10) not in (0,10,20,30,40,50,58):
            raise ValueError('동작 여백은 0, 10, 20, 30, 40, 50, 58% 중 선택하세요.')
        if p.get('subjectType','human') not in ('human', *engine.SUBJECT_DEFAULTS):
            raise ValueError('잘못된 대상 유형입니다.')
        if p.get('motionStrength','normal') not in engine.MOTION_PROMPTS:
            raise ValueError('잘못된 움직임 강도입니다.')
        if p.get('animationType','idle') not in engine.ANIMATION_DEFAULTS:
            raise ValueError('잘못된 동작입니다.')
        w,h=int(p.get('width',640)),int(p.get('height',928))
        if min(w,h)<256 or max(w,h)>2048 or w%32 or h%32 or w*h>1100000:
            raise ValueError('해상도는 32의 배수, 256~2048, 총 1.1MP 이하여야 합니다.')
        frames=p.get('frameCount',8)
        if isinstance(frames,bool) or not isinstance(frames,(int,float)) or (isinstance(frames,float) and not frames.is_integer()):
            raise ValueError('프레임 수는 2~64 사이 정수여야 합니다.')
        if not 3<=float(p.get('duration',5))<=5 or not 2<=frames<=64 or len(p.get('prompt',''))>4000:
            raise ValueError('길이는 3~5초, 시트는 2~64프레임, 설명은 4000자 이하여야 합니다.')
        if p.get('facing','preserve') not in engine.FACING_PROMPTS:
            raise ValueError('잘못된 방향입니다.')
        if p.get('blinkMode','none') not in ('none','once'):
            raise ValueError('잘못된 눈 깜박임 설정입니다.')
        if p.get('seed') not in (None,''):
            seed=int(p['seed'])
            if not 0<=seed<2**63:
                raise ValueError('Seed는 0 이상 2^63 미만이어야 합니다.')
            p['seed']=seed
        if type(p.get('backgroundTolerance',24)) is not int or not 4 <= p.get('backgroundTolerance',24) <= 64:
            raise ValueError('배경 제거 강도는 4~64 정수여야 합니다.')
        if any(k in p and not isinstance(p[k],bool) for k in ('loop','optimizeLoop','stabilize','removeBackground')):
            raise ValueError('루프와 정규화는 체크박스로 선택하세요.')
        try:
            raw=base64.b64decode(p.get('imageData','').split(',')[-1],validate=True)
            im=Image.open(io.BytesIO(raw))
            if im.width*im.height>24000000:
                raise ValueError()
            im.verify()
        except Exception:
            raise ValueError('유효한 24MP 이하 이미지를 선택하세요.')
        p['width'],p['height'],p['filename']=w,h,'reference.png'
        p['workflowId']=engine.sprite_workflows.validate(p,engine.COMFY_ROOT)
        jid=secrets.token_hex(16)
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            active=con.execute("SELECT count(*) FROM jobs WHERE state NOT IN ('complete','error','cancelled')").fetchone()[0]
            mine=con.execute("SELECT count(*) FROM jobs WHERE user_id=? AND state NOT IN ('complete','error','cancelled')",(request.team_user['id'],)).fetchone()[0]
            if active>=20 or mine>=3:
                return jsonify(error='전체 20개 또는 개인 3개 대기 한도에 도달했습니다.'),429
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',
                        (jid,request.team_user['id'],'queued',time.time(),time.time(),json.dumps(p),json.dumps({'message':'대기 중'})))
            link_character_job(con,jid)
        return jsonify(jobId=jid),202

    @app.post('/api/music/generate')
    @auth()
    def generate_music():
        p=payload()
        resolved=music_prompts.resolve(p)
        p={**resolved,'jobType':'music','animationType':'BGM · '+resolved['title']}
        jid=secrets.token_hex(16)
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            active=con.execute("SELECT count(*) FROM jobs WHERE state NOT IN ('complete','error','cancelled')").fetchone()[0]
            mine=con.execute("SELECT count(*) FROM jobs WHERE user_id=? AND state NOT IN ('complete','error','cancelled')",(request.team_user['id'],)).fetchone()[0]
            if active>=20 or mine>=3:
                return jsonify(error='전체 20개 또는 개인 3개 대기 한도에 도달했습니다.'),429
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',
                        (jid,request.team_user['id'],'queued',time.time(),time.time(),json.dumps(p,ensure_ascii=False),
                         json.dumps({'message':'BGM 대기 중'},ensure_ascii=False)))
        return jsonify(jobId=jid,resolvedPrompt=resolved['resolvedPrompt'],promptReason=resolved['promptReason']),202

    @app.post('/api/music/refine-prompt')
    @auth()
    def refine_music_prompt():
        p=payload()
        return jsonify(prompt=music_prompts.refine_direct_prompt(
                           p.get('prompt'),p.get('vocalMode','instrumental')),
                       model=music_prompts.LITE_MODEL)

    @app.post('/api/rigging/generate')
    @auth()
    def generate_rigging():
        p=payload()
        resolution=p.get('resolution',1024)
        steps=p.get('steps',30)
        if type(resolution) is not int or resolution not in (768,1024):
            raise ValueError('리깅 해상도는 768 또는 1024여야 합니다.')
        if type(steps) is not int or steps not in (20,30):
            raise ValueError('리깅 스텝은 20 또는 30이어야 합니다.')
        if p.get('seed') not in (None,''):
            seed=int(p['seed'])
            if not 0<=seed<2**31:
                raise ValueError('Seed는 0 이상 2^31 미만이어야 합니다.')
            p['seed']=seed
        try:
            raw=base64.b64decode(p.get('imageData','').split(',')[-1],validate=True)
            im=Image.open(io.BytesIO(raw))
            source_size=im.size
            if im.width*im.height>24000000:
                raise ValueError()
            im.verify()
        except Exception:
            raise ValueError('유효한 24MP 이하 이미지를 선택하세요.')
        for key in ('eyeLeftAbsent','eyeRightAbsent'):
            if key in p and not isinstance(p[key],bool):
                raise ValueError('보이지 않는 눈 설정은 체크박스로 선택하세요.')
            p.setdefault(key,False)
        eye_input_mode=p.get('eyeInputMode','area')
        if eye_input_mode not in ('area','closed-stroke'):
            raise ValueError('지원하지 않는 눈 입력 방식입니다.')
        mouth_state=p.get('mouthState','closed')
        if mouth_state not in ('closed','slightly-open'):
            raise ValueError('원본 입 상태를 닫힌 입 또는 살짝 열린 입으로 선택하세요.')
        p['mouthState']=mouth_state
        if 'preserveOriginalEyes' in p and not isinstance(p['preserveOriginalEyes'],bool):
            raise ValueError('원본 눈 보존 설정은 체크박스로 선택하세요.')
        p.setdefault('preserveOriginalEyes',True)
        if 'preserveOriginalEyebrows' in p and not isinstance(p['preserveOriginalEyebrows'],bool):
            raise ValueError('원본 눈썹 보존 설정은 체크박스로 선택하세요.')
        p.setdefault('preserveOriginalEyebrows',True)
        rig_mode=p.get('rigMode','illustration')
        if rig_mode not in ('illustration','game-sprite'):
            raise ValueError('지원하지 않는 리깅 모드입니다.')
        p['rigMode']=rig_mode
        separation_backend=p.get('separationBackend','standard')
        if separation_backend not in ('standard','qwen21-experimental'):
            raise ValueError('지원하지 않는 레이어 분리 엔진입니다.')
        if separation_backend=='qwen21-experimental' and not rigging.status_payload().get('qwen21Ready'):
            return jsonify(error='Qwen 2.1 실험 모델이 아직 설치되지 않았습니다.'),503
        p['separationBackend']=separation_backend
        def check_mask(key,label,required=True):
            value=p.get(key,'')
            if not value:
                if required:
                    raise ValueError(label+' 마스크를 칠해 주세요.')
                return
            try:
                mask_raw=base64.b64decode(value.split(',')[-1],validate=True)
                with Image.open(io.BytesIO(mask_raw)) as opened:
                    rgba=opened.convert('RGBA')
                    if rgba.size!=source_size:
                        raise ValueError()
                    visible=ImageChops.multiply(rgba.convert('L'),rgba.getchannel('A'))
                    box=visible.getbbox()
                    if not box or sum(visible.histogram()[1:])<8:
                        raise ValueError()
            except Exception:
                raise ValueError(label+' 마스크가 비어 있거나 이미지 크기와 다릅니다.')
            return box
        eye_boxes=[]
        for mask_key,absent_key,label in (
            ('eyeLeftMask','eyeLeftAbsent','화면 왼쪽 눈'),
            ('eyeRightMask','eyeRightAbsent','화면 오른쪽 눈')):
            if p[absent_key]:
                p.pop(mask_key,None)
            else:
                eye_box=check_mask(mask_key,label)
                eye_boxes.append((label,eye_box))
        if eye_input_mode=='closed-stroke':
            for label,(x0,y0,x1,y1) in eye_boxes:
                eye_width,eye_height=x1-x0,y1-y0
                if eye_width<max(6,source_size[0]*.006):
                    raise ValueError(label+'의 감은 눈 선이 너무 짧습니다. 눈 안쪽부터 바깥쪽까지 그어 주세요.')
                if eye_width>source_size[0]*.45 or eye_height>source_size[1]*.22 or eye_height>max(6,eye_width*.9):
                    raise ValueError(label+'의 선 범위가 너무 큽니다. 눈썹과 주변 피부를 제외하고 감은 눈 선만 그어 주세요.')
        mouth_box=check_mask('mouthMask','입')
        mouth_width=mouth_box[2]-mouth_box[0]
        mouth_height=mouth_box[3]-mouth_box[1]
        if mouth_width>source_size[0]*0.25 or mouth_height>source_size[1]*0.18:
            raise ValueError('입 마스크가 너무 넓습니다. 입술과 입 안 주변만 짧게 칠해 주세요.')
        for key,label in (('eyebrowLeftMask','화면 왼쪽 눈썹'),('eyebrowRightMask','화면 오른쪽 눈썹')):
            eyebrow_box=check_mask(key,label,required=False)
            if eyebrow_box:
                eyebrow_width=eyebrow_box[2]-eyebrow_box[0]
                eyebrow_height=eyebrow_box[3]-eyebrow_box[1]
                if eyebrow_width>source_size[0]*0.35 or eyebrow_height>source_size[1]*0.14:
                    raise ValueError(label+' 마스크가 너무 넓습니다. 눈썹 선과 외곽만 작게 칠해 주세요.')
        p.update(jobType='rigging',maskVersion=2 if eye_input_mode=='closed-stroke' else 1,eyeInputMode=eye_input_mode,resolution=resolution,steps=steps,filename='character.png',animationType='2D 리깅')
        jid=secrets.token_hex(16)
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            active=con.execute("SELECT count(*) FROM jobs WHERE state NOT IN ('complete','error','cancelled')").fetchone()[0]
            mine=con.execute("SELECT count(*) FROM jobs WHERE user_id=? AND state NOT IN ('complete','error','cancelled')",(request.team_user['id'],)).fetchone()[0]
            if active>=20 or mine>=3:
                return jsonify(error='전체 20개 또는 개인 3개 대기 한도에 도달했습니다.'),429
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',
                        (jid,request.team_user['id'],'queued',time.time(),time.time(),json.dumps(p),json.dumps({'message':'리깅 대기 중'})))
            link_character_job(con,jid)
        return jsonify(jobId=jid),202

    @app.get('/unity-import/<token>')
    def unity_link_download(token):
        try:
            signed=unity_links.loads(token,max_age=300)
        except SignatureExpired:
            return jsonify(error='Unity 가져오기 링크가 만료되었습니다. 사이트에서 다시 여세요.'),410
        except BadSignature:
            return jsonify(error='올바르지 않은 Unity 가져오기 링크입니다.'),404
        if not isinstance(signed,dict) or not isinstance(signed.get('jid'),str) or type(signed.get('revision')) is not int:
            return jsonify(error='올바르지 않은 Unity 가져오기 링크입니다.'),404
        jid=signed['jid']
        with db() as con:
            row=con.execute("SELECT state,result FROM jobs WHERE id=?",(jid,)).fetchone()
        result=json.loads(row['result'] or '{}') if row and row['state']=='complete' else {}
        if result.get('packageV2SourceRevision')!=signed['revision'] or not result.get('packageV2'):
            return jsonify(error='이 패키지는 더 이상 현재 버전이 아닙니다.'),410
        folder=(rigging.RESULT_ROOT/jid).resolve()
        target=(folder/rig_v2.V2_FILENAME).resolve()
        if not folder.is_relative_to(rigging.RESULT_ROOT.resolve()) or not target.is_relative_to(folder) or not target.is_file():
            return jsonify(error='V2 스켈레톤 패키지를 찾을 수 없습니다.'),404
        return send_file(target,mimetype='application/zip',conditional=False,max_age=0,as_attachment=True,
                         download_name='sprite-lab-'+jid[:8]+'-v2.zip')

    @app.get('/outputs/results/<jid>/<filename>')
    @auth()
    def media(jid,filename):
        with db() as con:
            row=con.execute("SELECT result FROM jobs WHERE id=? AND state='complete'",(jid,)).fetchone()
        allowed=json.loads(row['result']) if row else {}
        relative=f'/outputs/results/{jid}/{filename}'
        if relative not in [allowed.get(k) for k in ('video','rawVideo','spriteSheet','transparentSheet','loopVideo','loopSheet','loopTransparentSheet')]+list(allowed.get('exportSheets',{}).values()):
            return jsonify(error='결과를 찾을 수 없습니다.'),404
        target=(engine.RESULT_ROOT/jid/filename).resolve()
        if not target.is_relative_to(engine.RESULT_ROOT.resolve()) or not target.is_file():
            return jsonify(error='파일을 찾을 수 없습니다.'),404
        return send_file(target,conditional=True)

    @app.get('/outputs/rigging/<jid>/<filename>')
    @auth()
    def rigging_media(jid,filename):
        with db() as con:
            row=con.execute("SELECT result FROM jobs WHERE id=? AND state='complete'",(jid,)).fetchone()
        result=json.loads(row['result']) if row else {}
        relative=f'/outputs/rigging/{jid}/{filename}'
        if relative not in [result.get(k) for k in ('psd','package','packageV2','composite','preview','manifest')]:
            return jsonify(error='리깅 결과를 찾을 수 없습니다.'),404
        folder=(rigging.RESULT_ROOT/jid).resolve()
        target=(folder/filename).resolve()
        if not folder.is_relative_to(rigging.RESULT_ROOT.resolve()) or not target.is_relative_to(folder) or not target.is_file():
            return jsonify(error='리깅 파일을 찾을 수 없습니다.'),404
        return send_file(target,conditional=True)

    @app.get('/outputs/music/<jid>/<filename>')
    @auth()
    def music_media(jid,filename):
        with db() as con:
            row=con.execute("SELECT result FROM jobs WHERE id=? AND state='complete'",(jid,)).fetchone()
        result=json.loads(row['result']) if row else {}
        relative=f'/outputs/music/{jid}/{filename}'
        if relative not in [result.get('audio'),result.get('score')]:
            return jsonify(error='BGM 결과를 찾을 수 없습니다.'),404
        folder=(music.RESULT_ROOT/jid).resolve()
        target=(folder/filename).resolve()
        if not folder.is_relative_to(music.RESULT_ROOT.resolve()) or not target.is_relative_to(folder) or not target.is_file():
            return jsonify(error='BGM 파일을 찾을 수 없습니다.'),404
        return send_file(target,conditional=True,as_attachment=filename.endswith('.abc'))
