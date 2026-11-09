"""Team accounts, approval, persistent FIFO GPU queue and shared gallery."""
import team_routes_account
import team_routes_images
import team_routes_jobs
import team_routes_live2d
import team_routes_share
import team_routes_site
import base64
from contextlib import contextmanager
import functools
import hashlib
import html as html_lib
import io
import ipaddress
import json
import os
import re
import secrets
import shutil
import sqlite3
import threading
import time
import zipfile
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env', override=False)

from flask import Flask, request, session, jsonify, send_file, send_from_directory, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from PIL import Image, ImageChops
import idle_tool as engine
import rigging_engine as rigging
import rigging_upscale
import rigging_regenerate
import character_studio
import frame_edit
import pose_motion
import loop_editor
import rigging_editor as rig_edit
import rigging_bones
import rigging_showcase as rig_showcase
import rigging_v2 as rig_v2
import music_engine as music
import music_prompts
import sprite_prompts
import image_engine
import image_caption
import image_face_refine
import asset_types

TERMINAL = ('complete', 'error', 'cancelled')


def unity_importer_archive():
    """Build the install-once UPM package without duplicating importer sources."""
    mappings = {
        ROOT/'unity-bridge'/'package.json': 'package.json',
        ROOT/'unity-bridge'/'README.md': 'README.md',
        ROOT/'unity-bridge'/'Runtime'/'SpriteLab.Unity.Runtime.asmdef': 'Runtime/SpriteLab.Unity.Runtime.asmdef',
        ROOT/'unity-v2'/'Runtime'/'RiggingV2Portrait.cs': 'Runtime/RiggingV2Portrait.cs',
        ROOT/'unity-bridge'/'Editor'/'SpriteLab.Unity.Editor.asmdef': 'Editor/SpriteLab.Unity.Editor.asmdef',
        ROOT/'unity-bridge'/'Editor'/'SpriteLabUnityLink.cs': 'Editor/SpriteLabUnityLink.cs',
        ROOT/'unity-bridge'/'Editor'/'SpriteLabUnityLinkHandler.txt': 'Editor/SpriteLabUnityLinkHandler.txt',
        ROOT/'unity-package'/'Runtime'/'RiggingV1Avatar.cs': 'Runtime/RiggingV1Avatar.cs',
        ROOT/'unity-v2'/'Runtime'/'RiggingV2Avatar.cs': 'Runtime/RiggingV2Avatar.cs',
        ROOT/'unity-v2'/'Runtime'/'RiggingV2ClipPlayer.cs': 'Runtime/RiggingV2ClipPlayer.cs',
        ROOT/'unity-package'/'Editor'/'RiggingV1Importer.cs': 'Editor/RiggingV1Importer.cs',
        ROOT/'unity-v2'/'Editor'/'RiggingV2Importer.cs': 'Editor/RiggingV2Importer.cs',
        ROOT/'unity-v2'/'Editor'/'RiggingV2AnimationBuilder.cs': 'Editor/RiggingV2AnimationBuilder.cs',
        ROOT/'unity-bridge'/'Editor'/'SpriteSheetImporter.cs': 'Editor/SpriteSheetImporter.cs',
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for source, target in mappings.items():
            if not source.is_file():
                raise FileNotFoundError('Unity importer source missing: '+str(source))
            archive.write(source, 'com.skylight.sprite-lab/'+target)
    output.seek(0)
    return output


def render_page(name, **values):
    page=(ROOT/'web'/'pages'/name).read_text(encoding='utf-8')
    for key,value in values.items():
        page=page.replace('{{'+key+'}}',value)
    return page


def create_app(data_dir=None, runner=None, rigging_runner=None, music_runner=None, image_runner=None):
    data = Path(data_dir or ROOT / 'data')
    data.mkdir(parents=True, exist_ok=True)
    key = data / 'session.key'
    if not key.exists():
        key.write_text(secrets.token_hex(32), encoding='utf-8')
    app = Flask(__name__, static_folder=None)
    app.config.update(SECRET_KEY=key.read_text().strip(), MAX_CONTENT_LENGTH=30*1024*1024,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      SESSION_COOKIE_SECURE=os.environ.get('SPRITE_HTTPS') == '1')
    unity_links = URLSafeTimedSerializer(app.config['SECRET_KEY'], salt='sprite-lab-unity-import-v1')
    database = data / 'team.sqlite3'
    public_live2d_root = data / 'public-live2d'
    public_live2d_root.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def db():
        con = sqlite3.connect(database, timeout=30)
        con.row_factory = sqlite3.Row
        try:
            with con:
                yield con
        finally:
            con.close()

    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, name TEXT,
          password TEXT, state TEXT, role TEXT, created REAL);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, user_id INTEGER, state TEXT,
          created REAL, updated REAL, payload TEXT, result TEXT);
        CREATE TABLE IF NOT EXISTS attempts(ip TEXT, created REAL);
        CREATE TABLE IF NOT EXISTS deleted_jobs(id TEXT PRIMARY KEY, record TEXT, deleted REAL, deleted_by INTEGER);
        CREATE TABLE IF NOT EXISTS rig_shares(token TEXT PRIMARY KEY, job_id TEXT, kind TEXT,
          created REAL, created_by INTEGER, revoked REAL);
        CREATE TABLE IF NOT EXISTS public_live2d(token TEXT PRIMARY KEY, job_id TEXT UNIQUE, title TEXT,
          created REAL, updated REAL, created_by INTEGER, revoked REAL);
        """)
        con.execute("UPDATE jobs SET state='error',result=? WHERE state NOT IN ('queued','complete','error','cancelled')",
                    (json.dumps({'message':'서버 재시작으로 중단됨. 다시 요청하세요.'}),))
    setup_file = data / 'admin-setup-code.txt'
    with db() as con:
        first = con.execute("SELECT 1 FROM users WHERE role='admin'").fetchone() is None
    if first and not setup_file.exists():
        setup_file.write_text(secrets.token_urlsafe(24), encoding='utf-8')

    @app.before_request
    def guard_request():
        if request.method == 'POST':
            if request.headers.get('X-Sprite-Request') != '1' or not request.is_json:
                return jsonify(error='잘못된 요청 출처 또는 형식입니다.'), 403

    @app.after_request
    def response_headers(response):
        if not request.path.startswith('/assets/'):
            response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        return response

    def password_fingerprint(u):
        return hashlib.sha256(('sprite-session:'+u['password']).encode()).hexdigest()[:24]

    def session_password_current(u):
        expected=password_fingerprint(u)
        if session.get('pwv') is None:
            session['pwv']=expected  # sessions created before fingerprints existed adopt the current one
            return True
        return secrets.compare_digest(str(session['pwv']),expected)

    def auth(admin=False):
        def decorate(fn):
            @functools.wraps(fn)
            def wrapped(*args, **kwargs):
                with db() as con:
                    u = con.execute('SELECT * FROM users WHERE id=?',(session.get('uid'),)).fetchone()
                if not u or u['state'] != 'approved':
                    return jsonify(error='승인된 계정으로 로그인하세요.'),401
                if not session_password_current(u):
                    session.clear()
                    return jsonify(error='비밀번호가 바뀌어 다시 로그인해야 합니다.'),401
                if admin and u['role'] != 'admin':
                    return jsonify(error='관리자만 사용할 수 있습니다.'),403
                request.team_user = u
                return fn(*args, **kwargs)
            return wrapped
        return decorate

    @app.errorhandler(ValueError)
    @app.errorhandler(TypeError)
    def bad_value(error):
        return jsonify(error=str(error) if isinstance(error,ValueError) else '입력 형식을 확인하세요.'),400

    @app.errorhandler(413)
    def too_large(error):
        return jsonify(error='업로드 크기는 30MB 이하여야 합니다.'),413

    def payload():
        p = request.get_json()
        if not isinstance(p,dict):
            raise ValueError('잘못된 요청입니다.')
        for k in ('username','name','password','setupCode','imageData','eyeLeftMask','eyeRightMask','eyebrowLeftMask','eyebrowRightMask','mouthMask','prompt','animationType','facing','title','notes','gameDocument','promptMode','preset','cot','vocalMode','lyrics'):
            if k in p and not isinstance(p[k],str):
                raise ValueError('문자열 입력이 필요합니다: '+k)
        return p

    def rig_version_payload(jid,current,prefix):
        folder=(rigging.RESULT_ROOT/jid).resolve()
        if not folder.is_relative_to(rigging.RESULT_ROOT.resolve()):return []
        versions=[]
        for item in rig_edit.list_versions(folder,current):
            base=f'{prefix}/{item["revision"]}'
            versions.append(item|{'composite':base+'/composite.png','psd':base+'/character.psd',
                                  'package':base+'/character-unity-parts.zip'})
        return versions

    def public_live2d_payload(row):
        if not row: return None
        return dict(token=row['token'],title=row['title'],url=f'/live2d/{row["token"]}',
                    preview=f'/live2d/{row["token"]}/preview.png',updated=row['updated'])

    GALLERY_PRIVATE_KEYS=('imageData','maskData','eyeLeftMask','eyeRightMask','eyebrowLeftMask','eyebrowRightMask','mouthMask','resultTitle')

    poster_lock=threading.Lock()

    extraction_lock=threading.Lock()
    rig_edit_lock=threading.Lock()
    showcase_lock=threading.Lock()
    public_live2d_lock=threading.Lock()

    def rig_editor_payload(jid, row, asset_prefix, readonly=False):
        folder=(rigging.RESULT_ROOT/jid).resolve()
        if not folder.is_relative_to(rigging.RESULT_ROOT.resolve()):
            raise FileNotFoundError('리깅 결과 경로를 확인할 수 없습니다.')
        manifest=rig_edit.read_manifest(folder)
        result=json.loads(row['result'] or '{}')
        revision=int(result.get('rigRevision',manifest.get('editRevision',0)))
        layers=[]
        records=rig_edit.layer_records(manifest)
        order=rig_edit.effective_layer_order(manifest)
        by_key=dict(records)
        for layer_key in order:
            part=by_key[layer_key];kind,layer_id=layer_key.split(':',1)
            asset=f'{asset_prefix}/{kind}/{layer_id}'
            neutral=(kind=='part' or part.get('fade')=='eyeOpen' or layer_id=='eyebrow' or
                     (manifest.get('sourceMouthState')=='closed' and layer_id=='mouth_close') or
                     (manifest.get('sourceMouthState')=='slightly-open' and layer_id=='mouth_open'))
            visibility=manifest.get('layerVisibility')
            if isinstance(visibility,dict) and layer_key in visibility and isinstance(visibility[layer_key],bool):
                neutral=visibility[layer_key]
            if part.get('variantOf'):neutral=False
            layers.append({key:part.get(key) for key in ('id','runtimeName','sourceLayerName','left','top','width','height','sourceRecovered','recoveryType','variantOf','activeVariant')}|
                          {'key':layer_key,'kind':kind,'defaultVisible':neutral,'asset':asset,'originalAsset':asset+'?original=1'})
        parts=[item for item in layers if item['kind']=='part']
        version_prefix=asset_prefix.rsplit('/layers',1)[0]+'/versions'
        versions=rig_version_payload(jid,revision,version_prefix)
        source_url=asset_prefix.rsplit('/layers',1)[0]+'/source' if (folder/rig_edit.SOURCE_REFERENCE).is_file() else None
        return dict(jobId=jid,revision=revision,versions=versions,canvas=manifest['canvas'],parts=parts,layers=layers,
                    layerOrder=order,readonly=readonly,upscale=rigging_upscale.super_resolution.status(),rig=rigging_bones.get_rig(manifest,folder),rigAnimations=manifest.get('rigAnimations'),
                    sourceReference=source_url,recoveryTypes=sorted(rig_edit.RECOVERY_TYPES),
                    composite=result.get('composite'),psd=result.get('psd'),package=result.get('package'),
                    packageV2=result.get('packageV2') if result.get('packageV2SourceRevision')==revision else None,
                    editedParts=manifest.get('editedParts',[]))

    def regenerate_rig_part(jid, row):
        p=payload()
        folder=rigging.RESULT_ROOT/jid
        manifest,record=rigging_regenerate.validate(folder,p)
        is_expression=record['id'].startswith('eye_close') or record['id'] in ('mouth_open','mouth_close')
        if is_expression and not all(path.is_file() for path in rigging.QWEN_MODEL_PATHS):
            raise ValueError('눈·입 재생성 모델이 설치되지 않았습니다.')
        task=secrets.token_hex(16)
        settings=dict(jobType='rig-part',parentJob=jid,revision=p['revision'],layerKey=p['layerKey'],hint=p.get('hint',''),animationType='눈·입·장비 재생성')
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            count=con.execute("SELECT count(*) FROM jobs WHERE state NOT IN ('complete','error','cancelled')").fetchone()[0]
            mine=con.execute("SELECT count(*) FROM jobs WHERE user_id=? AND state NOT IN ('complete','error','cancelled')",(row['user_id'],)).fetchone()[0]
            if count>=20 or mine>=3:return jsonify(error='전체 20개 또는 개인 3개 대기 한도에 도달했습니다.'),429
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(task,row['user_id'],'queued',time.time(),time.time(),json.dumps(settings),json.dumps(dict(message='파츠 재생성 대기 중'))))
        return jsonify(taskId=task),202

    def rig_candidate(jid, task):
        with db() as con:
            row=con.execute('SELECT * FROM jobs WHERE id=?',(task,)).fetchone()
        p=json.loads(row['payload']) if row else {}
        if not row or p.get('jobType')!='rig-part' or p.get('parentJob')!=jid:
            return jsonify(error='재생성 결과를 찾을 수 없습니다.'),404
        result=json.loads(row['result'] or '{}')
        answer=dict(state=row['state'],message=result.get('message',''))
        if row['state']=='complete':
            folder=rigging_regenerate.ROOT/task
            answer.update(json.loads((folder/'candidate.json').read_text(encoding='utf-8')))
            with Image.open(folder/'candidate.png') as image:
                answer['imageData']=rigging_regenerate.image_data(image)
        return jsonify(**answer)

    def save_rig_revision(jid,p,row):
        expected=p.get('revision')
        if type(expected) is not int or expected<0:
            raise ValueError('편집 버전을 확인할 수 없습니다. 페이지를 새로고침하세요.')
        result=json.loads(row['result'] or '{}')
        current=int(result.get('rigRevision',0))
        if expected!=current:
            return jsonify(error='다른 창에서 결과가 수정되었습니다. 새로고침한 뒤 다시 편집하세요.'),409
        if not rig_edit_lock.acquire(blocking=False):
            return jsonify(error='다른 리깅 결과를 저장 중입니다. 잠시 후 다시 시도하세요.'),409
        try:
            with db() as con:
                latest=con.execute("SELECT result FROM jobs WHERE id=? AND state='complete'",(jid,)).fetchone()
            if not latest:return jsonify(error='결과를 찾을 수 없습니다.'),404
            latest_result=json.loads(latest['result'] or '{}')
            if int(latest_result.get('rigRevision',0))!=expected:
                return jsonify(error='다른 창에서 결과가 수정되었습니다. 새로고침한 뒤 다시 편집하세요.'),409
            folder=(rigging.RESULT_ROOT/jid).resolve()
            saved=rig_edit.save_revision(folder,p.get('operations'),expected,ROOT/'tools'/'write_psd.js',
                                         layer_order=p.get('layerOrder'),
                                         layer_visibility=p.get('layerVisibility'))
            latest_result.update(rigRevision=saved['revision'],editedParts=saved['manifest'].get('editedParts',[]),
                                 warnings=saved['manifest'].get('warnings',[]),qualityStatus=saved['manifest'].get('status','needs_review'),
                                 message='레이어 수정본 저장 완료')
            latest_result.pop('packageV2',None)
            latest_result.pop('packageV2SourceRevision',None)
            latest_result.pop('rigV2BoneCount',None)
            with db() as con:
                con.execute('UPDATE jobs SET updated=?,result=? WHERE id=?',(time.time(),json.dumps(latest_result,ensure_ascii=False),jid))
            (folder/rig_v2.V2_FILENAME).unlink(missing_ok=True)
            (folder/rig_showcase.SHOWCASE_FILENAME).unlink(missing_ok=True)
            return jsonify(ok=True,revision=saved['revision'],editedParts=saved['manifest'].get('editedParts',[]),
                           composite=latest_result.get('composite'),psd=latest_result.get('psd'),package=latest_result.get('package'),packageV2=None)
        except ValueError:
            raise
        except Exception:
            app.logger.exception('Rig layer edit failed')
            return jsonify(error='수정본 저장에 실패했습니다. 기존 결과는 유지됩니다.'),500
        finally:
            rig_edit_lock.release()

    def export_rig_upscale(jid,p,row):
        if type(p.get('revision')) is not int or p['revision']!=int(json.loads(row['result'] or '{}').get('rigRevision',0)):
            return jsonify(error='결과 버전이 변경되었습니다. 새로고침한 뒤 다시 내보내세요.'),409
        if not rig_edit_lock.acquire(blocking=False):
            return jsonify(error='다른 레이어 작업을 처리 중입니다. 잠시 후 다시 시도하세요.'),409
        try:
            with db() as con:
                latest=con.execute("SELECT result FROM jobs WHERE id=? AND state='complete'",(jid,)).fetchone()
            if not latest or int(json.loads(latest['result'] or '{}').get('rigRevision',0))!=p['revision']:
                return jsonify(error='결과 버전이 변경되었습니다. 새로고침하세요.'),409
            if p.get('action')=='apply':
                folder=rigging.RESULT_ROOT/jid
                saved=rigging_upscale.apply_layers(folder,p.get('scale'),p['revision'],ROOT/'tools'/'write_psd.js',ROOT/'unity-v2',method=p.get('method','lanczos'))
                result=json.loads(latest['result'] or '{}')
                result.update(rigRevision=saved['revision'],message='확대본 적용 및 V2 생성 완료',
                              packageV2=f'/outputs/rigging/{jid}/{rig_v2.V2_FILENAME}',
                              packageV2SourceRevision=saved['revision'],rigV2BoneCount=saved['bones'])
                with db() as con:
                    con.execute('UPDATE jobs SET updated=?,result=? WHERE id=?',(time.time(),json.dumps(result,ensure_ascii=False),jid))
                (folder/rig_showcase.SHOWCASE_FILENAME).unlink(missing_ok=True)
                return jsonify(ok=True,revision=saved['revision'],packageV2=result['packageV2'],scale=p['scale'])
            content=rigging_upscale.export_layers(rigging.RESULT_ROOT/jid,p.get('scale'),ROOT/'tools'/'write_psd.js',method=p.get('method','lanczos'))
            return send_file(io.BytesIO(content),mimetype='application/zip',as_attachment=True,
                             download_name=f'character-layers-{p["scale"]}x.zip',max_age=0)
        except ValueError:
            raise
        except Exception:
            app.logger.exception('Rig upscale export failed')
            return jsonify(error='확대 파일 생성에 실패했습니다. 원본 작업은 유지됩니다.'),500
        finally:
            rig_edit_lock.release()

    def restore_rig_version(jid,p,row):
        expected,target=p.get('revision'),p.get('targetRevision')
        if type(expected) is not int or expected<0 or type(target) is not int or target<0:
            raise ValueError('복원할 작업 버전을 확인하세요.')
        result=json.loads(row['result'] or '{}');current=int(result.get('rigRevision',0))
        if expected!=current:
            return jsonify(error='다른 창에서 결과가 수정되었습니다. 새로고침한 뒤 다시 복원하세요.'),409
        if not rig_edit_lock.acquire(blocking=False):
            return jsonify(error='다른 리깅 결과를 저장 중입니다. 잠시 후 다시 시도하세요.'),409
        try:
            with db() as con:
                latest=con.execute("SELECT result FROM jobs WHERE id=? AND state='complete'",(jid,)).fetchone()
            if not latest:return jsonify(error='결과를 찾을 수 없습니다.'),404
            latest_result=json.loads(latest['result'] or '{}')
            if int(latest_result.get('rigRevision',0))!=expected:
                return jsonify(error='다른 창에서 결과가 수정되었습니다. 새로고침한 뒤 다시 복원하세요.'),409
            folder=(rigging.RESULT_ROOT/jid).resolve()
            restored=rig_edit.restore_version(folder,target,current);manifest=restored['manifest']
            latest_result.update(rigRevision=restored['revision'],editedParts=manifest.get('editedParts',[]),
                                 warnings=manifest.get('warnings',[]),qualityStatus=manifest.get('status','needs_review'),
                                 message=f'작업 버전 v{target+1}을 새 버전으로 복원 완료')
            for key in ('packageV2','packageV2SourceRevision','rigV2BoneCount'):latest_result.pop(key,None)
            with db() as con:
                con.execute('UPDATE jobs SET updated=?,result=? WHERE id=?',(time.time(),json.dumps(latest_result,ensure_ascii=False),jid))
            (folder/rig_v2.V2_FILENAME).unlink(missing_ok=True)
            (folder/rig_showcase.SHOWCASE_FILENAME).unlink(missing_ok=True)
            return jsonify(ok=True,revision=restored['revision'],restoredFrom=target,packageV2=None)
        except (ValueError,FileNotFoundError):
            raise
        except Exception:
            app.logger.exception('Rig version restore failed')
            return jsonify(error='이전 작업 버전 복원에 실패했습니다. 현재 결과는 유지됩니다.'),500
        finally:
            rig_edit_lock.release()

    def build_rig_v2_response(jid,row,p):
        expected=p.get('revision')
        if type(expected) is not int or expected<0:
            raise ValueError('편집 버전을 확인할 수 없습니다. 결과를 새로고침하세요.')
        result=json.loads(row['result'] or '{}')
        current=int(result.get('rigRevision',0))
        if expected!=current:
            return jsonify(error='레이어가 수정되었습니다. 결과를 새로고침한 뒤 V2를 다시 만드세요.'),409
        folder=(rigging.RESULT_ROOT/jid).resolve()
        if not folder.is_relative_to(rigging.RESULT_ROOT.resolve()):
            return jsonify(error='리깅 결과 경로를 확인할 수 없습니다.'),404
        existing=folder/rig_v2.V2_FILENAME
        pose=p.get('pose') if p.get('mode')=='game-sprite' else None
        if pose is not None:
            rig_v2.normalize_pose(pose,rig_edit.read_manifest(folder)['canvas'])
        if pose is None and result.get('packageV2SourceRevision')==current and existing.is_file() and rig_v2.has_editor_skinning(folder):
            return jsonify(ok=True,packageV2=result.get('packageV2'),boneCount=result.get('rigV2BoneCount'),sourceRevision=current,cached=True)
        if not rig_edit_lock.acquire(blocking=False):
            return jsonify(error='다른 리깅 패키지를 저장 중입니다. 잠시 후 다시 시도하세요.'),409
        try:
            built=(rig_v2.build_package(folder,ROOT/'unity-v2',current,pose=pose) if pose is not None
                   else rig_v2.build_package(folder,ROOT/'unity-v2',current))
            relative=f'/outputs/rigging/{jid}/{rig_v2.V2_FILENAME}'
            with db() as con:
                latest=con.execute("SELECT result FROM jobs WHERE id=? AND state='complete'",(jid,)).fetchone()
                if not latest:return jsonify(error='결과를 찾을 수 없습니다.'),404
                latest_result=json.loads(latest['result'] or '{}')
                if int(latest_result.get('rigRevision',0))!=current:
                    existing.unlink(missing_ok=True)
                    return jsonify(error='저장 중 레이어가 수정되었습니다. V2를 다시 만드세요.'),409
                latest_result.update(packageV2=relative,packageV2SourceRevision=current,rigV2BoneCount=built['bones'],message='V2 스켈레톤 패키지 생성 완료')
                con.execute('UPDATE jobs SET updated=?,result=? WHERE id=?',(time.time(),json.dumps(latest_result,ensure_ascii=False),jid))
            return jsonify(ok=True,packageV2=relative,boneCount=built['bones'],sourceRevision=current,cached=False,warnings=built['warnings'])
        except (ValueError,FileNotFoundError):
            raise
        except Exception:
            app.logger.exception('Rig V2 package failed')
            return jsonify(error='V2 스켈레톤 패키지 생성에 실패했습니다. V1 결과는 유지됩니다.'),500
        finally:
            rig_edit_lock.release()

    link_character_job=character_studio.register(app,db,auth,data,payload)
    team_routes_site.register(app, GALLERY_PRIVATE_KEYS=GALLERY_PRIVATE_KEYS, ROOT=ROOT, auth=auth,
        database=database, db=db, link_character_job=link_character_job, payload=payload,
        poster_lock=poster_lock, public_live2d_payload=public_live2d_payload,
        rig_version_payload=rig_version_payload, unity_importer_archive=unity_importer_archive,
        unity_links=unity_links)
    team_routes_images.register(app, ROOT=ROOT, auth=auth, db=db, image_runner=image_runner,
        link_character_job=link_character_job, payload=payload)
    team_routes_account.register(app, auth=auth, db=db, password_fingerprint=password_fingerprint,
        payload=payload, session_password_current=session_password_current, setup_file=setup_file)
    team_routes_jobs.register(app, GALLERY_PRIVATE_KEYS=GALLERY_PRIVATE_KEYS, TERMINAL=TERMINAL, auth=auth,
        build_rig_v2_response=build_rig_v2_response, db=db, export_rig_upscale=export_rig_upscale,
        extraction_lock=extraction_lock, payload=payload, regenerate_rig_part=regenerate_rig_part,
        restore_rig_version=restore_rig_version, rig_candidate=rig_candidate,
        rig_editor_payload=rig_editor_payload, save_rig_revision=save_rig_revision, unity_links=unity_links)
    team_routes_live2d.register(app, ROOT=ROOT, auth=auth, db=db, payload=payload,
        public_live2d_lock=public_live2d_lock, public_live2d_payload=public_live2d_payload,
        public_live2d_root=public_live2d_root, render_page=render_page)
    team_routes_share.register(app, ROOT=ROOT, build_rig_v2_response=build_rig_v2_response, db=db,
        export_rig_upscale=export_rig_upscale, payload=payload, regenerate_rig_part=regenerate_rig_part,
        render_page=render_page, restore_rig_version=restore_rig_version, rig_candidate=rig_candidate,
        rig_editor_payload=rig_editor_payload, save_rig_revision=save_rig_revision,
        showcase_lock=showcase_lock)
    finish_pose_motion=pose_motion.register(app,db,auth,data,payload)
    loop_editor.register(app,db,auth,data,payload,extraction_lock)

    stop=threading.Event()
    def worker():
        while not stop.wait(0.5):
            with db() as con:
                candidate=con.execute("""SELECT j.* FROM jobs j JOIN users u ON u.id=j.user_id
                    WHERE j.state='queued' AND u.state='approved' ORDER BY j.created LIMIT 1""").fetchone()
            if not candidate:
                continue
            candidate_payload=json.loads(candidate['payload'])
            job_type=candidate_payload.get('jobType','video')
            if job_type in ('rig-part','frame-edit','pose-motion'):
                try:
                    legacy_motion=job_type=='pose-motion' and candidate_payload.get('consistency','independent')=='independent'
                    target_address=image_engine.COMFY_URL if legacy_motion else rigging.COMFY_URL
                    if legacy_motion:
                        if not engine.comfy_online():engine.start_comfy()
                    elif not rigging.comfy_ready():rigging.start_comfy()
                    busy=False
                    for address in (image_engine.COMFY_URL,rigging.COMFY_URL,image_engine.image_soya.URL):
                        try:
                            q=engine.requests.get(address+'/queue',timeout=3).json()
                            busy=busy or bool(q.get('queue_running') or q.get('queue_pending'))
                        except engine.requests.RequestException:
                            if address==target_address:busy=True
                    if busy:continue
                except Exception as error:
                    with db() as con:
                        con.execute("UPDATE jobs SET state='error',result=? WHERE id=?",(json.dumps(dict(message=str(error))),candidate['id']))
                    continue
            elif job_type=='image' and image_runner is None:
                try:
                    target_address=image_engine.backend_url(candidate_payload)
                    if target_address==image_engine.image_soya.URL and not image_engine.image_soya.online():
                        image_engine.image_soya.start_server()
                    # Both Comfy processes share a physical GPU.
                    busy=False
                    for address in (image_engine.COMFY_URL,rigging.COMFY_URL,image_engine.image_soya.URL):
                        try:
                            q=engine.requests.get(address+'/queue',timeout=3).json()
                            busy=busy or bool(q.get('queue_running') or q.get('queue_pending'))
                        except engine.requests.RequestException:
                            if address in (image_engine.COMFY_URL,target_address): busy=True
                    if busy: continue
                except Exception:
                    continue
            elif job_type=='music' and music_runner is None:
                if not music.status_payload()['ready']:
                    continue
            elif job_type=='rigging' and rigging_runner is None:
                try:
                    q=rigging.requests.get(rigging.COMFY_URL+'/queue',timeout=3).json()
                    if q.get('queue_running') or q.get('queue_pending'):
                        continue
                except Exception:
                    continue
            elif job_type=='video' and runner is None:
                try:
                    q=engine.requests.get(engine.COMFY_URL+'/queue',timeout=3).json()
                    if q.get('queue_running') or q.get('queue_pending'):
                        continue
                except Exception:
                    continue
                if not engine.LICENSE_MARKER.exists():
                    continue
            with db() as con:
                con.execute('BEGIN IMMEDIATE')
                row=con.execute("SELECT j.* FROM jobs j JOIN users u ON u.id=j.user_id WHERE j.state='queued' AND u.state='approved' ORDER BY j.created LIMIT 1").fetchone()
                if not row:
                    continue
                con.execute("UPDATE jobs SET state='starting' WHERE id=?",(row['id'],))
            jid=row['id']
            job_payload=json.loads(row['payload'])
            job_type=job_payload.get('jobType','video')
            def update(job_id,**changes):
                with db() as con:
                    current=con.execute('SELECT result FROM jobs WHERE id=?',(job_id,)).fetchone()
                    result=json.loads(current[0] or '{}');result.update(changes)
                    con.execute('UPDATE jobs SET state=?,updated=?,result=? WHERE id=?',
                                (result.get('state','starting'),time.time(),json.dumps(result),job_id))
            target_engine=pose_motion if job_type=='pose-motion' else frame_edit if job_type=='frame-edit' else rigging_regenerate if job_type=='rig-part' else image_engine if job_type=='image' else music if job_type=='music' else rigging if job_type=='rigging' else engine
            target_engine.update_job=update
            try:
                target_runner=frame_edit.run_job if job_type=='frame-edit' else rigging_regenerate.run_job if job_type=='rig-part' else (image_runner or image_engine.run_job) if job_type=='image' else (music_runner or music.run_job) if job_type=='music' else (rigging_runner or rigging.run_job) if job_type=='rigging' else (runner or engine.run_job)
                if job_type=='pose-motion':
                    finish_pose_motion(jid,job_payload,pose_motion.run_job(jid,job_payload))
                else:
                    target_runner(jid,job_payload)
            except Exception as error:
                update(jid,state='error',message=str(error) or '생성 중 오류가 발생했습니다.')
            finally:
                with db() as con:
                    p=json.loads(row['payload'])
                    for key in ('imageData','maskData','eyeLeftMask','eyeRightMask','eyebrowLeftMask','eyebrowRightMask','mouthMask'):
                        p.pop(key,None)
                    con.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(p),jid))
    app.start_worker=lambda: threading.Thread(target=worker,daemon=True).start()
    app.stop_worker=stop.set
    return app


if __name__=='__main__':
    from waitress import serve
    # Keep one worker per machine; a second launcher must not interrupt persisted jobs.
    import msvcrt
    (ROOT/'data').mkdir(exist_ok=True)
    instance_lock=open(ROOT/'data'/'server.lock','a+b')
    instance_lock.seek(0)
    try:
        msvcrt.locking(instance_lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:
        raise SystemExit('Team server is already running.')
    app=create_app()
    if os.environ.get('SPRITE_SKIP_COMFY')!='1':
        def boot_engine():
            try:
                engine.start_comfy()
            except Exception as error:
                print('Generation engine not ready:',error,flush=True)
        threading.Thread(target=boot_engine,daemon=True).start()
        def boot_rigging_engine():
            try:
                rigging.start_comfy()
            except Exception as error:
                print('Rigging engine not ready:',error,flush=True)
        threading.Thread(target=boot_rigging_engine,daemon=True).start()
        def boot_soya_engine():
            try:
                image_engine.image_soya.start_server()
            except Exception as error:
                print('Soya engine not ready:',error,flush=True)
        threading.Thread(target=boot_soya_engine,daemon=True).start()
    app.start_worker()
    print('Team Sprite Lab: http://127.0.0.1:7866',flush=True)
    print('First admin setup code: data/admin-setup-code.txt (local only)',flush=True)
    serve(app,host='127.0.0.1',port=int(os.environ.get('SPRITE_PORT','7866')),threads=6)
