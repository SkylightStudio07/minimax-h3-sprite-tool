"""Job control, rig editing and export routes."""
from PIL import Image
from pathlib import Path
import base64
import idle_tool as engine
import io
import json
from flask import jsonify
import os
from urllib.parse import quote
import re
from flask import request
import rigging_editor as rig_edit
import rigging_v2 as rig_v2
import rigging_engine as rigging
import secrets
from flask import send_file
import time
import zipfile


def register(app, *, GALLERY_PRIVATE_KEYS, TERMINAL, auth, build_rig_v2_response, db, export_rig_upscale,
             extraction_lock, payload, regenerate_rig_part, restore_rig_version, rig_candidate,
             rig_editor_payload, save_rig_revision, unity_links):
    @app.post('/api/jobs/<jid>/title')
    @auth()
    def rename_result(jid):
        title=payload().get('title','')
        if not isinstance(title,str):
            raise ValueError('문자열 입력이 필요합니다.')
        title=' '.join(title.split())
        if len(title)>60:
            raise ValueError('결과 이름은 60자 이하입니다.')
        with db() as con:
            row=con.execute("SELECT * FROM jobs WHERE id=? AND state='complete'",(jid,)).fetchone()
            if not row:
                return jsonify(error='완료된 결과를 찾을 수 없습니다.'),404
            if row['user_id']!=request.team_user['id'] and request.team_user['role']!='admin':
                return jsonify(error='이름을 바꿀 권한이 없습니다.'),403
            p=json.loads(row['payload'])
            if title:
                p['resultTitle']=title
            else:
                p.pop('resultTitle',None)
            con.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(p),jid))
        return jsonify(title=title or None)

    def job_json(row):
        result = json.loads(row['result'] or '{}')
        p = json.loads(row['payload'])
        return dict(result,id=row['id'],state=row['state'],owner=row['name'],userId=row['user_id'],
                    jobType=p.get('jobType','video'),workflowId=p.get('workflowId','standard'),rigMode=p.get('rigMode','illustration'),
                    assetSpec=p.get('assetSpec'),sheetLayout=p.get('sheetLayout'),
                    **({'settings':{k:v for k,v in p.items() if k not in GALLERY_PRIVATE_KEYS}} if p.get('jobType')=='image' else {}),
                    created=row['created'],animationType=p.get('animationType','idle'),
                    width=p.get('width'),height=p.get('height'),
                    promptReason=p.get('promptReason'),resolvedPrompt=p.get('resolvedPrompt'),
                    vocalMode=p.get('vocalMode','instrumental'),
                    referencePreview=f'/api/jobs/{row["id"]}/reference' if p.get('imageData') and row['state'] not in TERMINAL else None)

    @app.get('/api/jobs/<jid>/reference')
    @auth()
    def reference(jid):
        with db() as con:
            row=con.execute('SELECT payload,state FROM jobs WHERE id=?',(jid,)).fetchone()
        p=json.loads(row['payload']) if row else {}
        if not p.get('imageData') or row['state'] in TERMINAL:
            return jsonify(error='원본 미리보기를 찾을 수 없습니다.'),404
        raw=base64.b64decode(p['imageData'].split(',')[-1],validate=True)
        with Image.open(io.BytesIO(raw)) as im:
            im.thumbnail((256,256))
            out=io.BytesIO()
            im.convert('RGBA').save(out,format='PNG')
        out.seek(0)
        return send_file(out,mimetype='image/png')

    @app.get('/api/jobs')
    @auth()
    def jobs():
        with db() as con:
            # Always include all active jobs, then recent completed results.
            rows = con.execute("""SELECT j.*,u.name FROM jobs j JOIN users u ON u.id=j.user_id
                WHERE COALESCE(json_extract(j.payload,'$.jobType'),'video') NOT IN ('rig-part','frame-edit','pose-motion')
                ORDER BY CASE WHEN j.state NOT IN ('complete','error','cancelled') THEN 0 ELSE 1 END,
                j.created DESC""").fetchall()
        return jsonify(jobs=[job_json(r) for r in rows])

    @app.get('/api/jobs/<jid>')
    @auth()
    def job(jid):
        with db() as con:
            row=con.execute('SELECT j.*,u.name FROM jobs j JOIN users u ON u.id=j.user_id WHERE j.id=?',(jid,)).fetchone()
        return jsonify(job_json(row)) if row else (jsonify(error='작업을 찾을 수 없습니다.'),404)

    @app.post('/api/jobs/<jid>/loop')
    @auth()
    def optimize_existing_loop(jid):
        with db() as con:
            row=con.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
        if not row:return jsonify(error='결과를 찾을 수 없습니다.'),404
        if row['user_id']!=request.team_user['id'] and request.team_user['role']!='admin':
            return jsonify(error='본인 결과 또는 관리자만 루프를 보정할 수 있습니다.'),403
        p=json.loads(row['payload']);result=json.loads(row['result'] or '{}')
        if row['state']!='complete' or p.get('jobType')=='rigging' or not p.get('loop',True):
            return jsonify(error='반복 재생으로 생성한 완료 영상만 보정할 수 있습니다.'),409
        if result.get('loopReport') and result['loopReport'].get('reason')!='processing_failed':
            return jsonify(error='이미 루프 검사를 마친 영상입니다.'),409
        relative=result.get('video','')
        if not relative.startswith(f'/outputs/results/{jid}/'):
            return jsonify(error='저장된 영상이 없습니다.'),404
        folder=(engine.RESULT_ROOT/jid).resolve();source=(folder/Path(relative).name).resolve()
        if not folder.is_relative_to(engine.RESULT_ROOT.resolve()) or not source.is_relative_to(folder) or not source.is_file():
            return jsonify(error='저장된 영상이 없습니다.'),404
        if not extraction_lock.acquire(blocking=False):
            return jsonify(error='다른 영상 또는 시트를 처리 중입니다. 잠시 후 다시 시도하세요.'),409
        created=[]
        try:
            # Recheck under the lock: two clicks must not create competing results.
            with db() as con: current=con.execute('SELECT result FROM jobs WHERE id=?',(jid,)).fetchone()
            if current and json.loads(current['result'] or '{}').get('loopVideo'):
                return jsonify(error='이미 루프 보정본이 있습니다.'),409
            stem='loop_'+secrets.token_hex(8)
            video=folder/(stem+'.mp4');sheet=folder/(stem+'.png')
            transparent=folder/(stem+'_transparent.png') if p.get('removeBackground',False) else None
            created=[video,sheet]+([transparent] if transparent else [])
            report=engine.sprite_loop.optimize_video(source,video)
            sheet_mode='subtle' if p.get('combatEffect')=='subtle' and not p.get('pixelOutput') else p.get('backgroundRemoval','flat')
            engine.make_sprite_sheet(video,sheet,int(p.get('frameCount',8)),True,transparent,int(p.get('backgroundTolerance',24)),sheet_mode)
            changes=dict(loopReport=report,loopVideo=f'/outputs/results/{jid}/{video.name}',loopSheet=f'/outputs/results/{jid}/{sheet.name}',
                         loopTransparentSheet=f'/outputs/results/{jid}/{transparent.name}' if transparent else None)
            with db() as con:
                con.execute('BEGIN IMMEDIATE')
                current=con.execute("SELECT result FROM jobs WHERE id=? AND state='complete'",(jid,)).fetchone()
                if not current:return jsonify(error='보정 중 결과가 삭제되었습니다.'),409
                updated=json.loads(current['result'] or '{}');updated.update(changes)
                con.execute('UPDATE jobs SET result=?,updated=? WHERE id=?',(json.dumps(updated),time.time(),jid))
            created=[]
            return jsonify(ok=True,**changes)
        except Exception:
            app.logger.exception('Loop optimization failed')
            return jsonify(error='루프 보정에 실패했습니다. 기존 영상은 보존됩니다.'),500
        finally:
            for path in created:path.unlink(missing_ok=True)
            extraction_lock.release()

    @app.post('/api/jobs/<jid>/extract')
    @auth()
    def extract_sheet(jid):
        extraction=payload()
        count=extraction.get('frameCount')
        method=engine.background_options(extraction)
        transparent_requested=extraction.get('removeBackground',False)
        if type(count) is not int or not 2<=count<=64:
            raise ValueError('프레임 수는 2~64 정수여야 합니다.')
        with db() as con:
            row=con.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
        if not row:
            return jsonify(error='결과를 찾을 수 없습니다.'),404
        if row['user_id']!=request.team_user['id'] and request.team_user['role']!='admin':
            return jsonify(error='본인 결과 또는 관리자만 다시 추출할 수 있습니다.'),403
        if row['state']!='complete':
            return jsonify(error='완료된 영상만 다시 추출할 수 있습니다.'),409
        original_settings=json.loads(row['payload'])
        if transparent_requested and original_settings.get('combatEffect')=='subtle' and not original_settings.get('pixelOutput'):
            engine.background_options(dict(removeBackground=True,backgroundRemoval='flat',combatEffect='subtle'))
        result=json.loads(row['result'] or '{}')
        relative=result.get('loopVideo') or result.get('video','')
        if not relative.startswith(f'/outputs/results/{jid}/'):
            return jsonify(error='저장된 영상을 찾을 수 없습니다.'),404
        folder=(engine.RESULT_ROOT/jid).resolve()
        video=(folder/Path(relative).name).resolve()
        if not folder.is_relative_to(engine.RESULT_ROOT.resolve()) or not video.is_relative_to(folder) or not video.is_file():
            return jsonify(error='저장된 영상 파일이 없습니다.'),404
        if not extraction_lock.acquire(blocking=False):
            return jsonify(error='다른 시트를 추출 중입니다. 잠시 후 다시 시도하세요.'),409
        created=[]
        try:
            key=f'sheet_{count}_{secrets.token_hex(8)}'
            output=folder/(key+'.png')
            p=json.loads(row['payload'])
            transparent=folder/(key+'_transparent.png') if transparent_requested else None
            created=[output]+([transparent] if transparent else [])
            if transparent:
                sheet_mode='subtle' if p.get('combatEffect')=='subtle' and not p.get('pixelOutput') else method
                engine.make_sprite_sheet(video,output,count,bool(p.get('loop',True)),transparent,24,sheet_mode)
            else:
                engine.make_sprite_sheet(video,output,count,bool(p.get('loop',True)))
            path=f'/outputs/results/{jid}/{output.name}'
            with db() as con:
                con.execute('BEGIN IMMEDIATE')
                current=con.execute("SELECT result FROM jobs WHERE id=? AND state='complete'",(jid,)).fetchone()
                if not current:
                    return jsonify(error='추출 중 결과가 삭제되었습니다.'),409
                updated=json.loads(current['result'] or '{}')
                updated.setdefault('exportSheets',{})[key]=path
                if transparent:
                    updated['exportSheets'][key+'_transparent']=f'/outputs/results/{jid}/{transparent.name}'
                    updated.setdefault('exportSheetInfo',{})[key+'_transparent']=dict(backgroundRemoval=method,frameCount=count)
                con.execute('UPDATE jobs SET result=? WHERE id=?',(json.dumps(updated),jid))
            created=[]
            return jsonify(ok=True,spriteSheet=path,transparentSheet=f'/outputs/results/{jid}/{transparent.name}' if transparent else None,backgroundRemoval=method if transparent else None)
        except Exception:
            app.logger.exception('Sprite sheet extraction failed')
            return jsonify(error='시트 추출에 실패했습니다. 서버 로그를 확인하세요.'),500
        finally:
            for file in created:file.unlink(missing_ok=True)
            extraction_lock.release()

    @app.post('/api/jobs/<jid>/delete')
    @auth()
    def delete_result(jid):
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            row=con.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
            if not row:
                return jsonify(error='결과를 찾을 수 없습니다.'),404
            if row['user_id']!=request.team_user['id'] and request.team_user['role']!='admin':
                return jsonify(error='본인 결과 또는 관리자만 삭제할 수 있습니다.'),403
            if row['state']!='complete':
                return jsonify(error='완료된 결과만 삭제할 수 있습니다.'),409
            con.execute('INSERT INTO deleted_jobs VALUES(?,?,?,?)',
                        (jid,json.dumps(dict(row)),time.time(),request.team_user['id']))
            con.execute('UPDATE public_live2d SET revoked=?,updated=? WHERE job_id=?',(time.time(),time.time(),jid))
            con.execute('DELETE FROM jobs WHERE id=?',(jid,))
        return jsonify(ok=True)

    def editable_rig(jid):
        with db() as con:
            row=con.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
        if not row or row['state']!='complete' or json.loads(row['payload']).get('jobType')!='rigging':
            return None,(jsonify(error='완료된 리깅 결과를 찾을 수 없습니다.'),404)
        if row['user_id']!=request.team_user['id'] and request.team_user['role']!='admin':
            return None,(jsonify(error='본인 결과 또는 관리자만 편집할 수 있습니다.'),403)
        return row,None

    @app.post('/api/jobs/<jid>/rig-edit/regenerate')
    @auth()
    def rig_part_generate(jid):
        row,error=editable_rig(jid)
        if error:return error
        return regenerate_rig_part(jid,row)

    @app.get('/api/jobs/<jid>/rig-edit/regenerate/<task>')
    @auth()
    def rig_part_candidate(jid,task):
        row,error=editable_rig(jid)
        if error:return error
        return rig_candidate(jid,task)

    @app.get('/api/jobs/<jid>/rig-edit')
    @auth()
    def rig_edit_info(jid):
        row,error=editable_rig(jid)
        if error:return error
        try:
            return jsonify(**rig_editor_payload(jid,row,f'/api/jobs/{jid}/rig-edit/layers'))
        except FileNotFoundError:
            return jsonify(error='리깅 결과 경로를 확인할 수 없습니다.'),404
        except Exception:
            return jsonify(error='편집할 manifest를 읽을 수 없습니다.'),500

    @app.get('/api/jobs/<jid>/rig-edit/layers/<layer_id>')
    @auth()
    def rig_edit_layer(jid,layer_id):
        row,error=editable_rig(jid)
        if error:return error
        if not re.fullmatch(r'[a-z0-9_]{1,80}',layer_id):
            return jsonify(error='레이어를 찾을 수 없습니다.'),404
        folder=(rigging.RESULT_ROOT/jid).resolve()
        try:
            content=rig_edit.layer_bytes(folder,layer_id,original=request.args.get('original')=='1')
        except (FileNotFoundError,KeyError,zipfile.BadZipFile):
            return jsonify(error='레이어를 찾을 수 없습니다.'),404
        return send_file(io.BytesIO(content),mimetype='image/png',conditional=True,download_name=layer_id+'.png')

    @app.get('/api/jobs/<jid>/rig-edit/layers/<kind>/<layer_id>')
    @auth()
    def rig_edit_typed_layer(jid,kind,layer_id):
        row,error=editable_rig(jid)
        if error:return error
        if kind not in ('part','expression') or not re.fullmatch(r'[a-z0-9_]{1,80}',layer_id):
            return jsonify(error='레이어를 찾을 수 없습니다.'),404
        try:content=rig_edit.layer_bytes((rigging.RESULT_ROOT/jid).resolve(),layer_id,request.args.get('original')=='1',kind)
        except (FileNotFoundError,KeyError,zipfile.BadZipFile):return jsonify(error='레이어를 찾을 수 없습니다.'),404
        return send_file(io.BytesIO(content),mimetype='image/png',conditional=True,download_name=layer_id+'.png')

    @app.route('/api/jobs/<jid>/rig-edit/source',methods=['GET','POST'])
    @auth()
    def rig_edit_source(jid):
        row,error=editable_rig(jid)
        if error:return error
        folder=(rigging.RESULT_ROOT/jid).resolve()
        if request.method=='POST':
            target=rig_edit.save_source_reference(folder,payload().get('imageData'))
            return jsonify(ok=True,sourceReference=f'/api/jobs/{jid}/rig-edit/source',bytes=target.stat().st_size)
        try:target=rig_edit.source_reference_path(folder)
        except FileNotFoundError:return jsonify(error='보관된 원본 이미지가 없습니다.'),404
        return send_file(target,mimetype='image/png',conditional=True,max_age=0)

    @app.post('/api/jobs/<jid>/rig-edit/revisions')
    @auth()
    def save_rig_edit(jid):
        p=payload()
        row,error=editable_rig(jid)
        if error:return error
        return save_rig_revision(jid,p,row)

    @app.post('/api/jobs/<jid>/rig-edit/upscale')
    @auth()
    def rig_upscale_export(jid):
        p=payload()
        row,error=editable_rig(jid)
        if error:return error
        return export_rig_upscale(jid,p,row)

    @app.post('/api/jobs/<jid>/rig-edit/restore')
    @auth()
    def restore_rig_edit(jid):
        p=payload();row,error=editable_rig(jid)
        if error:return error
        return restore_rig_version(jid,p,row)

    @app.get('/api/jobs/<jid>/rig-edit/versions/<int:revision>/<filename>')
    @auth()
    def rig_version_asset(jid,revision,filename):
        with db() as con:
            row=con.execute("SELECT * FROM jobs WHERE id=? AND state='complete'",(jid,)).fetchone()
        if not row or json.loads(row['payload']).get('jobType')!='rigging':
            return jsonify(error='결과를 찾을 수 없습니다.'),404
        current=int(json.loads(row['result'] or '{}').get('rigRevision',0));folder=(rigging.RESULT_ROOT/jid).resolve()
        try:target=rig_edit.version_file(folder,revision,current,filename)
        except FileNotFoundError:return jsonify(error='작업 버전을 찾을 수 없습니다.'),404
        return send_file(target,conditional=False,max_age=0,as_attachment=filename.endswith(('.psd','.zip')),download_name=filename)

    @app.post('/api/jobs/<jid>/rig-v2')
    @auth()
    def build_rig_v2(jid):
        p=payload()
        row,error=editable_rig(jid)
        if error:return error
        return build_rig_v2_response(jid,row,p)

    @app.post('/api/jobs/<jid>/unity-link')
    @auth()
    def create_unity_link(jid):
        payload()
        row,error=editable_rig(jid)
        if error:return error
        result=json.loads(row['result'] or '{}')
        revision=int(result.get('rigRevision',0))
        relative=result.get('packageV2')
        if not relative or result.get('packageV2SourceRevision')!=revision:
            return jsonify(error='현재 레이어 버전의 V2 스켈레톤 패키지를 먼저 만드세요.'),409
        folder=(rigging.RESULT_ROOT/jid).resolve()
        target=(folder/rig_v2.V2_FILENAME).resolve()
        if not folder.is_relative_to(rigging.RESULT_ROOT.resolve()) or not target.is_relative_to(folder) or not target.is_file():
            return jsonify(error='V2 스켈레톤 패키지 파일을 찾을 수 없습니다.'),404
        token=unity_links.dumps({'jid':jid,'revision':revision})
        configured_origin=os.environ.get('SPRITE_PUBLIC_ORIGIN','').strip().rstrip('/')
        if configured_origin:
            if not re.fullmatch(r'https://[^/]+',configured_origin):
                return jsonify(error='SPRITE_PUBLIC_ORIGIN은 https://호스트 형식이어야 합니다.'),500
            origin=configured_origin
        else:
            forwarded=request.headers.get('X-Forwarded-Proto','').split(',',1)[0].strip().lower()
            scheme='https' if os.environ.get('SPRITE_HTTPS')=='1' or forwarded=='https' else request.scheme
            origin=scheme+'://'+request.host
        download=origin+'/unity-import/'+token
        name='sprite-'+jid[:8]
        deep_link='spritelab-unity://import?url='+quote(download,safe='')+'&name='+quote(name,safe='')
        return jsonify(uri=deep_link,downloadUrl=download,expiresIn=300)

    @app.post('/api/jobs/<jid>/cancel')
    @auth()
    def cancel(jid):
        with db() as con:
            row=con.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
            if not row or (row['user_id']!=request.team_user['id'] and request.team_user['role']!='admin'):
                return jsonify(error='취소 권한이 없습니다.'),403
            count=con.execute("UPDATE jobs SET state='cancelled' WHERE id=? AND state='queued'",(jid,)).rowcount
            if count:
                p=json.loads(row['payload'])
                for key in ('imageData','maskData','eyeLeftMask','eyeRightMask','eyebrowLeftMask','eyebrowRightMask','mouthMask'):
                    p.pop(key,None)
                con.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(p),jid))
        return jsonify(ok=bool(count)),200 if count else 409

    @app.post('/api/jobs/<jid>/shares')
    @auth()
    def create_rig_share(jid):
        kind=payload().get('kind')
        if kind=='external':
            return jsonify(error='외부 쇼케이스 대신 관리자가 공개 Live2D로 게시할 수 있습니다.'),410
        if kind!='internal': raise ValueError('공유 종류를 확인하세요.')
        with db() as con:
            row=con.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
            if not row or row['state']!='complete' or json.loads(row['payload']).get('jobType')!='rigging':
                return jsonify(error='완료된 리깅 결과를 찾을 수 없습니다.'),404
            if row['user_id']!=request.team_user['id'] and request.team_user['role']!='admin': return jsonify(error='공유 권한이 없습니다.'),403
            found=con.execute('SELECT token FROM rig_shares WHERE job_id=? AND kind=? AND revoked IS NULL',(jid,kind)).fetchone()
            token=found['token'] if found else secrets.token_urlsafe(24)
            if not found: con.execute('INSERT INTO rig_shares VALUES(?,?,?,?,?,NULL)',(token,jid,kind,time.time(),request.team_user['id']))
        return jsonify(kind=kind,url=f'/share/rig/{token}')
