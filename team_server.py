"""Team accounts, approval, persistent FIFO GPU queue and shared gallery."""
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

    def user_json(u):
        return {k:u[k] for k in ('id','username','name','state','role')}

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

    def client_address():
        remote=request.remote_addr or ''
        if os.environ.get('SPRITE_TRUST_PROXY')=='1' and remote in ('127.0.0.1','::1'):
            # Only the last hop is written by our own proxy; earlier entries are client-supplied.
            forwarded=request.headers.get('X-Forwarded-For','').rsplit(',',1)[-1].strip()
            try:
                return str(ipaddress.ip_address(forwarded))
            except ValueError:
                pass
        return remote

    def attempts_over(key,limit):
        with db() as con:
            con.execute('DELETE FROM attempts WHERE created < ?',(time.time()-600,))
            return con.execute('SELECT count(*) FROM attempts WHERE ip=?',(key,)).fetchone()[0]>=limit

    def record_attempt(*keys):
        with db() as con:
            con.executemany('INSERT INTO attempts VALUES(?,?)',[(key,time.time()) for key in keys])

    def rate_limit(scope):
        key=f'{scope}|{client_address()}'
        if attempts_over(key,30):
            return False
        record_attempt(key)
        return True

    def login_keys(username):
        client=client_address()
        keys=[f'login|{client}|{username}']
        if client not in ('127.0.0.1','::1',''):
            keys.append(f'login-client|{client}')  # behind an untrusted proxy every user shares loopback
        return keys

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

    @app.get('/image-studio')
    @auth()
    def image_studio():
        return send_file(ROOT/'web'/'image-studio.html', conditional=False, max_age=0)

    @app.get('/api/images/models')
    @auth()
    def image_models():
        return jsonify(image_engine.status_payload() | {'caption':image_caption.status_payload()})

    @app.post('/api/images/describe')
    @auth()
    def describe_image():
        image=image_engine.read_image(payload().get('imageData'))
        try:
            return jsonify(image_caption.analyze(image))
        except image_caption.CaptionBusy as error:
            return jsonify(error=str(error)),429

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

    @app.post('/api/images/generate')
    @auth()
    def generate_image():
        p=image_engine.validate(payload())
        model=image_engine.MODELS[p['model']]
        if image_runner is None and not all((engine.COMFY_ROOT/'models'/f).is_file() for f in model['files']):
            return jsonify(error='선택한 모델을 설치 중이거나 파일이 없습니다.'),409
        jid=secrets.token_hex(16)
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            active=con.execute("SELECT count(*) FROM jobs WHERE state NOT IN ('complete','error','cancelled')").fetchone()[0]
            mine=con.execute("SELECT count(*) FROM jobs WHERE user_id=? AND state NOT IN ('complete','error','cancelled')",(request.team_user['id'],)).fetchone()[0]
            if active>=20 or mine>=3:
                return jsonify(error='전체 20개 또는 개인 3개 대기 한도에 도달했습니다.'),429
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(jid,request.team_user['id'],'queued',time.time(),time.time(),json.dumps(p),json.dumps({'message':'원화 생성 대기 중'})))
            link_character_job(con,jid)
        return jsonify(jobId=jid,seed=p['seed']),202

    @app.get('/api/images/<jid>/<filename>')
    @auth()
    def image_media(jid,filename):
        with db() as con:
            row=con.execute("SELECT result FROM jobs WHERE id=? AND state='complete'",(jid,)).fetchone()
        result=json.loads(row['result']) if row else {}
        relative=f'/api/images/{jid}/{filename}'
        if relative not in [item.get(key) for item in result.get('images',[]) for key in ('url','originalUrl','beforeFaceUrl','beforeHiresUrl','beforePixelUrl','pixelPreviewUrl')]+[result.get('metadata')]:
            return jsonify(error='이미지를 찾을 수 없습니다.'),404
        target=(image_engine.RESULT_ROOT/jid/filename).resolve()
        if not target.is_relative_to(image_engine.RESULT_ROOT.resolve()) or not target.is_file():
            return jsonify(error='이미지를 찾을 수 없습니다.'),404
        return send_file(target,conditional=True)

    @app.post('/api/images/<jid>/face-refine')
    @auth()
    def refine_saved_face(jid):
        body=payload();index=body.get('image',0)
        if type(index) is not int or not 0<=index<4:raise ValueError('보정할 후보 이미지를 선택하세요.')
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            row=con.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
            original_settings=json.loads(row['payload']) if row else {}
            original_result=json.loads(row['result'] or '{}') if row else {}
            if not row or row['state']!='complete' or original_settings.get('jobType')!='image':
                return jsonify(error='완료된 원화 결과에서 얼굴 보정을 선택하세요.'),404
            if original_settings.get('sheetLayout') or original_settings.get('preset')=='rpg-sheet':
                raise ValueError('4방향 시트는 부분 수정으로 얼굴을 직접 지정해 주세요.')
            if original_settings.get('model')==image_engine.image_pixel.MODEL_ID:
                raise ValueError('도트 결과는 픽셀 크기를 유지해 Aseprite 등에서 수정하세요. 일러스트 얼굴 보정은 적용하지 않습니다.')
            images=original_result.get('images',[])
            if index>=len(images):raise ValueError('보정할 후보 이미지를 찾을 수 없습니다.')
            expected=f'/api/images/{jid}/image-{index+1}.png'
            source=(image_engine.RESULT_ROOT/jid/f'image-{index+1}.png').resolve()
            if images[index].get('url')!=expected or not source.is_relative_to(image_engine.RESULT_ROOT.resolve()) or not source.is_file():
                return jsonify(error='원본 결과 이미지가 없습니다.'),404
            with Image.open(source) as im:
                if im.width*im.height>24000000:raise ValueError('얼굴 보정은 24MP 이하 이미지를 지원합니다.')
                p=image_face_refine.settings(original_settings,body,jid,index,im.size)
            if image_runner is None and (not image_engine.image_face_detail.ready() or not all((engine.COMFY_ROOT/'models'/f).is_file() for f in image_engine.MODELS[p['model']]['files'])):
                return jsonify(error='얼굴 보정 모델·검출 도구가 준비되지 않았습니다.'),409
            active=con.execute("SELECT count(*) FROM jobs WHERE state NOT IN ('complete','error','cancelled')").fetchone()[0]
            mine=con.execute("SELECT count(*) FROM jobs WHERE user_id=? AND state NOT IN ('complete','error','cancelled')",(request.team_user['id'],)).fetchone()[0]
            if active>=20 or mine>=3:return jsonify(error='전체 20개 또는 개인 3개 대기 한도에 도달했습니다.'),429
            task=secrets.token_hex(16);folder=(image_engine.RESULT_ROOT/task).resolve()
            if not folder.is_relative_to(image_engine.RESULT_ROOT.resolve()):raise ValueError('결과 경로를 확인하세요.')
            folder.mkdir(parents=True,exist_ok=False)
            try:
                shutil.copyfile(source,folder/'image-1-before-face.png')
                con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(task,request.team_user['id'],'queued',time.time(),time.time(),json.dumps(p),json.dumps(dict(message='얼굴 보정 대기 중 · 원본은 유지됩니다.'))))
            except Exception:
                shutil.rmtree(folder)
                raise
        return jsonify(jobId=task,model=p['model'],strength=p['faceRefineStrength']),202

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

    @app.get('/api/me')
    def me():
        with db() as con:
            u = con.execute('SELECT * FROM users WHERE id=?',(session.get('uid'),)).fetchone()
            setup = con.execute("SELECT 1 FROM users WHERE role='admin'").fetchone() is None
        if u and not session_password_current(u):
            session.clear();u=None
        return jsonify(user=user_json(u) if u else None, setupRequired=setup)

    @app.post('/api/register')
    def register():
        if not rate_limit('register'):
            return jsonify(error='요청이 많습니다. 10분 뒤 다시 시도하세요.'),429
        p = payload()
        username,name,password = p.get('username','').strip().lower(),p.get('name','').strip(),p.get('password','')
        if not re.fullmatch(r'[a-z0-9_.-]{3,40}',username) or not 1<=len(name)<=40 or not 10<=len(password)<=200:
            raise ValueError('아이디는 영문·숫자 3~40자, 이름은 1~40자, 비밀번호는 10~200자입니다.')
        password_hash = generate_password_hash(password)
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            first = con.execute("SELECT 1 FROM users WHERE role='admin'").fetchone() is None
            if first and (not setup_file.exists() or not secrets.compare_digest(p.get('setupCode',''),setup_file.read_text().strip())):
                return jsonify(error='이 PC에 저장된 관리자 설정 코드가 필요합니다.'),403
            try:
                con.execute('INSERT INTO users(username,name,password,state,role,created) VALUES(?,?,?,?,?,?)',
                            (username,name,password_hash,'approved' if first else 'pending','admin' if first else 'member',time.time()))
            except sqlite3.IntegrityError:
                return jsonify(error='이미 사용 중인 아이디입니다.'),409
        if first:
            setup_file.unlink(missing_ok=True)
        return jsonify(message='관리자 생성 완료. 로그인하세요.' if first else '가입 요청 완료. 관리자 승인을 기다려 주세요.')

    @app.post('/api/login')
    def login():
        p = payload()
        username=p.get('username','').lower().strip()
        keys=login_keys(username)
        if attempts_over(keys[0],10) or (len(keys)>1 and attempts_over(keys[1],30)):
            return jsonify(error='로그인 시도가 많습니다. 10분 뒤 다시 시도하세요.'),429
        with db() as con:
            u = con.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
        if not u or not check_password_hash(u['password'],p.get('password','')):
            record_attempt(*keys)
            return jsonify(error='아이디 또는 비밀번호가 맞지 않습니다.'),401
        if u['state'] != 'approved':
            return jsonify(error='관리자 승인 대기 중이거나 이용이 제한된 계정입니다.'),403
        session.clear()
        session['uid'] = u['id']
        session['pwv'] = password_fingerprint(u)
        return jsonify(user=user_json(u))

    @app.post('/api/logout')
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.post('/api/me/profile')
    @auth()
    def update_profile():
        name=payload().get('name','').strip()
        if not 1<=len(name)<=40:
            raise ValueError('이름은 1~40자입니다.')
        with db() as con:
            con.execute('UPDATE users SET name=? WHERE id=?',(name,request.team_user['id']))
            u=con.execute('SELECT * FROM users WHERE id=?',(request.team_user['id'],)).fetchone()
        return jsonify(user=user_json(u))

    @app.post('/api/me/password')
    @auth()
    def change_password():
        if not rate_limit(f'password|{request.team_user["id"]}'):
            return jsonify(error='요청이 많습니다. 10분 뒤 다시 시도하세요.'),429
        p=payload()
        current,new=p.get('currentPassword',''),p.get('newPassword','')
        if not isinstance(current,str) or not isinstance(new,str):
            raise ValueError('문자열 입력이 필요합니다.')
        if not check_password_hash(request.team_user['password'],current):
            return jsonify(error='현재 비밀번호가 맞지 않습니다.'),403
        if not 10<=len(new)<=200:
            raise ValueError('새 비밀번호는 10~200자입니다.')
        if new==current:
            raise ValueError('새 비밀번호가 현재 비밀번호와 같습니다.')
        with db() as con:
            con.execute('UPDATE users SET password=? WHERE id=?',(generate_password_hash(new),request.team_user['id']))
            u=con.execute('SELECT * FROM users WHERE id=?',(request.team_user['id'],)).fetchone()
        session['pwv']=password_fingerprint(u)  # this browser stays signed in; other sessions end
        return jsonify(ok=True)

    @app.get('/api/me/summary')
    @auth()
    def my_summary():
        uid=request.team_user['id']
        with db() as con:
            counts={row[0]:row[1] for row in con.execute("""SELECT COALESCE(json_extract(payload,'$.jobType'),'video'),count(*)
                FROM jobs WHERE user_id=? AND state='complete' GROUP BY 1""",(uid,))}
            active=con.execute("SELECT count(*) FROM jobs WHERE user_id=? AND state NOT IN ('complete','error','cancelled')",(uid,)).fetchone()[0]
            shares=con.execute("""SELECT s.token,s.job_id,s.created,j.payload,j.result FROM rig_shares s JOIN jobs j ON j.id=s.job_id
                WHERE s.kind='internal' AND s.revoked IS NULL AND j.state='complete' AND (j.user_id=? OR s.created_by=?)
                ORDER BY s.created DESC""",(uid,uid)).fetchall()
            published=con.execute("""SELECT p.token,p.job_id,p.title,p.updated FROM public_live2d p JOIN jobs j ON j.id=p.job_id
                WHERE p.revoked IS NULL AND j.user_id=? ORDER BY p.updated DESC""",(uid,)).fetchall()
        def share_item(row):
            p,result=json.loads(row['payload']),json.loads(row['result'] or '{}')
            return dict(token=row['token'],jobId=row['job_id'],created=row['created'],url=f'/share/rig/{row["token"]}',
                        title=p.get('resultTitle'),composite=result.get('composite'),rigRevision=int(result.get('rigRevision',0)))
        return jsonify(counts={kind:counts.get(kind,0) for kind in ('video','rigging','music','image')},active=active,activeLimit=3,
                       shares=[share_item(row) for row in shares],
                       publicLive2d=[dict(token=row['token'],jobId=row['job_id'],title=row['title'],updated=row['updated'],url=f'/live2d/{row["token"]}') for row in published])

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

    @app.get('/api/users')
    @auth(True)
    def users():
        with db() as con:
            return jsonify(users=[user_json(u) for u in con.execute('SELECT * FROM users ORDER BY created')])

    @app.post('/api/users/<int:uid>')
    @auth(True)
    def approve(uid):
        state = payload().get('state')
        if state not in ('approved','rejected'):
            raise ValueError('잘못된 승인 상태입니다.')
        with db() as con:
            con.execute("UPDATE users SET state=? WHERE id=? AND role!='admin'",(state,uid))
            if state=='rejected':
                con.execute("UPDATE jobs SET state='cancelled' WHERE user_id=? AND state='queued'",(uid,))
        return jsonify(ok=True)

    @app.get('/api/status')
    @auth()
    def status():
        s = engine.status_payload()
        rs = rigging.status_payload()
        ms = music.status_payload() | {'gemini': music_prompts.status_payload()}
        return jsonify(**{k:s[k] for k in ('comfy','modelsReady','licenseConfirmed')}, spriteWorkflows=s.get('spriteWorkflows',[]), spriteBackground=engine.image_background.status(), rigging=rs, music=ms)

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

    poster_lock=threading.Lock()

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

    extraction_lock=threading.Lock()
    rig_edit_lock=threading.Lock()
    showcase_lock=threading.Lock()
    public_live2d_lock=threading.Lock()

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

    @app.post('/api/jobs/<jid>/rig-edit/revisions')
    @auth()
    def save_rig_edit(jid):
        p=payload()
        row,error=editable_rig(jid)
        if error:return error
        return save_rig_revision(jid,p,row)

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

    @app.post('/api/jobs/<jid>/rig-edit/upscale')
    @auth()
    def rig_upscale_export(jid):
        p=payload()
        row,error=editable_rig(jid)
        if error:return error
        return export_rig_upscale(jid,p,row)

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

    def get_public_live2d(token):
        with db() as con:
            return con.execute('SELECT * FROM public_live2d WHERE token=? AND revoked IS NULL',(token,)).fetchone()

    @app.post('/api/jobs/<jid>/public-live2d')
    @auth(admin=True)
    def manage_public_live2d(jid):
        data_in=payload();action=data_in.get('action');title=data_in.get('title','공개 Live2D')
        if action not in ('publish','unpublish'): raise ValueError('공개 작업을 확인하세요.')
        if not isinstance(title,str) or not title.strip() or len(title.strip())>60:
            raise ValueError('공개 제목은 1~60자로 입력하세요.')
        with db() as con:
            job=con.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
            existing=con.execute('SELECT * FROM public_live2d WHERE job_id=?',(jid,)).fetchone()
        if not job or job['state']!='complete' or json.loads(job['payload']).get('jobType')!='rigging':
            return jsonify(error='완료된 리깅 결과를 찾을 수 없습니다.'),404
        if action=='unpublish':
            if not existing or existing['revoked'] is not None:
                return jsonify(error='공개 중인 Live2D가 없습니다.'),409
            with db() as con: con.execute('UPDATE public_live2d SET revoked=?,updated=? WHERE job_id=?',(time.time(),time.time(),jid))
            return jsonify(ok=True,publicLive2d=None)
        source=(rigging.RESULT_ROOT/jid).resolve()
        psd=(source/'character.psd').resolve();preview=(source/'composite.png').resolve()
        valid_header=b''
        if psd.is_file():
            with psd.open('rb') as stream: valid_header=stream.read(4)
        if (not source.is_relative_to(rigging.RESULT_ROOT.resolve()) or not psd.is_file() or not preview.is_file() or
            psd.stat().st_size>128*1024*1024 or valid_header!=b'8BPS'):
            return jsonify(error='공개할 PSD 또는 미리보기를 찾을 수 없습니다.'),404
        token=existing['token'] if existing else secrets.token_urlsafe(24)
        target=(public_live2d_root/token).resolve()
        if not target.is_relative_to(public_live2d_root.resolve()):
            return jsonify(error='공개 저장 경로를 만들 수 없습니다.'),500
        with public_live2d_lock:
            target.mkdir(parents=True,exist_ok=True)
            for source_file,name in ((psd,'character.psd'),(preview,'preview.png')):
                staged=target/(f'.{name}.{secrets.token_hex(6)}.tmp')
                try:
                    shutil.copyfile(source_file,staged);os.replace(staged,target/name)
                finally: staged.unlink(missing_ok=True)
        now=time.time();clean_title=title.strip()
        with db() as con:
            if existing:
                con.execute('UPDATE public_live2d SET title=?,updated=?,created_by=?,revoked=NULL WHERE job_id=?',
                            (clean_title,now,request.team_user['id'],jid))
            else:
                con.execute('INSERT INTO public_live2d VALUES(?,?,?,?,?,?,NULL)',
                            (token,jid,clean_title,now,now,request.team_user['id']))
            published=con.execute('SELECT * FROM public_live2d WHERE job_id=?',(jid,)).fetchone()
        return jsonify(ok=True,publicLive2d=public_live2d_payload(published))

    @app.get('/api/admin/public-live2d')
    @auth(admin=True)
    def admin_public_live2d():
        with db() as con:
            rows=con.execute('''SELECT p.*,u.name AS owner FROM public_live2d p JOIN jobs j ON j.id=p.job_id
                                LEFT JOIN users u ON u.id=j.user_id WHERE p.revoked IS NULL ORDER BY p.updated DESC''').fetchall()
        def same(a,b):
            if not a.is_file() or not b.is_file() or a.stat().st_size!=b.stat().st_size: return False
            return hashlib.sha256(a.read_bytes()).digest()==hashlib.sha256(b.read_bytes()).digest()
        return jsonify(items=[dict(public_live2d_payload(row),jobId=row['job_id'],owner=row['owner'],
                                   stale=not same(rigging.RESULT_ROOT/row['job_id']/'character.psd',public_live2d_root/row['token']/'character.psd'))
                              for row in rows])

    @app.get('/api/public-live2d')
    def public_live2d_list_api():
        with db() as con:
            rows=con.execute('SELECT * FROM public_live2d WHERE revoked IS NULL ORDER BY updated DESC').fetchall()
        return jsonify(items=[public_live2d_payload(row) for row in rows])

    @app.get('/live2d')
    def public_live2d_list_page():
        with db() as con:
            rows=con.execute('SELECT * FROM public_live2d WHERE revoked IS NULL ORDER BY updated DESC').fetchall()
        cards=''.join(f'<a class="pub-card" href="/live2d/{row["token"]}"><img src="/live2d/{row["token"]}/preview.png" alt=""><b>{html_lib.escape(row["title"])}</b><span>공개 워크스페이스 열기</span></a>' for row in rows)
        if not cards: cards='<p class="pub-empty">현재 공개된 Live2D가 없습니다.</p>'
        return render_page('live2d-list.html',cards=cards)

    @app.get('/live2d/<token>')
    def public_live2d_workspace(token):
        row=get_public_live2d(token)
        if not row:return '공개가 종료되었거나 존재하지 않는 Live2D입니다.',404
        title=html_lib.escape(row['title'])
        return render_page('live2d-workspace.html',title=title,token=token)

    @app.get('/live2d/<token>/player')
    def public_live2d_player(token):
        if not get_public_live2d(token):return '공개가 종료되었거나 존재하지 않는 Live2D입니다.',404
        html=(ROOT/'vendor'/'Anime2.5DRig'/'index.html').read_text(encoding='utf-8')
        html=html.replace('<head>','<head><base href="/shared-rig-player/">',1)
        model_url=f'/live2d/{token}/character.psd'
        return html.replace('<script src="lib/app.js"></script>',f'<script>window.SHARED_MODEL_URL={json.dumps(model_url)}</script><script src="lib/app.js"></script>',1)

    @app.get('/live2d/<token>/<filename>')
    def public_live2d_asset(token,filename):
        if filename not in ('character.psd','preview.png') or not get_public_live2d(token):
            return jsonify(error='공개 파일을 찾을 수 없습니다.'),404
        target=(public_live2d_root/token/filename).resolve()
        if not target.is_relative_to(public_live2d_root.resolve()) or not target.is_file():
            return jsonify(error='공개 파일을 찾을 수 없습니다.'),404
        return send_file(target,conditional=True,as_attachment=False,
                         mimetype='image/vnd.adobe.photoshop' if filename.endswith('.psd') else 'image/png')

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

    def get_share(token):
        with db() as con: return con.execute("SELECT s.*,j.result FROM rig_shares s JOIN jobs j ON j.id=s.job_id WHERE s.token=? AND s.revoked IS NULL AND j.state='complete'",(token,)).fetchone()

    @app.get('/share/rig/<token>')
    def share_page(token):
        row=get_share(token)
        if not row:return '공유 링크가 없거나 만료되었습니다.',404
        if row['kind']=='internal':
            return render_page('share-rig.html',token=token)
        with db() as con: published=con.execute('SELECT token FROM public_live2d WHERE job_id=? AND revoked IS NULL',(row['job_id'],)).fetchone()
        if not published:return '이 쇼케이스는 종료되었습니다. 공개 Live2D는 관리자가 지정한 결과만 제공됩니다.',410
        return redirect(f'/live2d/{published["token"]}',code=302)

    @app.get('/share/rig/<token>/asset/<filename>')
    def share_asset(token,filename):
        row=get_share(token); allowed=('character.psd','character-unity-parts.zip','character-unity-skeleton.zip') if row and row['kind']=='internal' else ('composite.png','showcase.webp')
        if not row or filename not in allowed:return jsonify(error='공유할 수 없는 파일입니다.'),404
        if row['kind']=='external':return jsonify(error='외부 쇼케이스는 공개 Live2D로 전환되었습니다.'),410
        folder=(rigging.RESULT_ROOT/row['job_id']).resolve();target=(folder/filename).resolve()
        if row['kind']=='external' and filename=='showcase.webp' and not rig_showcase.showcase_is_current(folder):
            with showcase_lock:
                if not rig_showcase.showcase_is_current(folder):
                    try:
                        rig_showcase.build_showcase(folder,target)
                    except Exception:
                        app.logger.exception('Rig showcase rendering failed')
                        target=folder/'composite.png'
        if not target.is_relative_to(folder) or not target.is_file():return jsonify(error='파일을 찾을 수 없습니다.'),404
        mimetype='image/webp' if filename=='showcase.webp' and target.name=='showcase.webp' else None
        return send_file(target,conditional=True,as_attachment=filename.endswith('.psd'),download_name=filename,mimetype=mimetype)

    @app.get('/share/rig/<token>/inspector')
    def shared_rig_inspector(token):
        row=get_share(token)
        if not row or row['kind']!='internal':return '공유 링크가 없거나 만료되었습니다.',404
        response=send_file(ROOT/'web'/'rigging-editor.html',conditional=False,max_age=0)
        response.headers['Cache-Control']='no-store, no-cache, must-revalidate, max-age=0'
        return response

    @app.get('/share/rig/<token>/rig-edit')
    def shared_rig_edit_info(token):
        row=get_share(token)
        if not row or row['kind']!='internal':return jsonify(error='공유 링크가 없거나 만료되었습니다.'),404
        try:
            data=rig_editor_payload(row['job_id'],row,f'/share/rig/{token}/layers',readonly=False)
            data.update(psd=f'/share/rig/{token}/asset/character.psd',
                        package=f'/share/rig/{token}/asset/character-unity-parts.zip',
                        packageV2=f'/share/rig/{token}/asset/character-unity-skeleton.zip' if data.get('packageV2') else None,composite=None)
            return jsonify(**data)
        except FileNotFoundError:
            return jsonify(error='리깅 결과를 찾을 수 없습니다.'),404
        except Exception:
            app.logger.exception('Shared rig inspector failed')
            return jsonify(error='레이어 정보를 읽을 수 없습니다.'),500

    @app.get('/share/rig/<token>/layers/<layer_id>')
    def shared_rig_layer(token,layer_id):
        row=get_share(token)
        if not row or row['kind']!='internal' or not re.fullmatch(r'[a-z0-9_]{1,80}',layer_id):
            return jsonify(error='레이어를 찾을 수 없습니다.'),404
        folder=(rigging.RESULT_ROOT/row['job_id']).resolve()
        try:
            content=rig_edit.layer_bytes(folder,layer_id,original=request.args.get('original')=='1')
        except (FileNotFoundError,KeyError,zipfile.BadZipFile):
            return jsonify(error='레이어를 찾을 수 없습니다.'),404
        return send_file(io.BytesIO(content),mimetype='image/png',conditional=True,download_name=layer_id+'.png')

    @app.get('/share/rig/<token>/layers/<kind>/<layer_id>')
    def shared_rig_typed_layer(token,kind,layer_id):
        row=get_share(token)
        if not row or row['kind']!='internal' or kind not in ('part','expression') or not re.fullmatch(r'[a-z0-9_]{1,80}',layer_id):
            return jsonify(error='레이어를 찾을 수 없습니다.'),404
        try:content=rig_edit.layer_bytes((rigging.RESULT_ROOT/row['job_id']).resolve(),layer_id,request.args.get('original')=='1',kind)
        except (FileNotFoundError,KeyError,zipfile.BadZipFile):return jsonify(error='레이어를 찾을 수 없습니다.'),404
        return send_file(io.BytesIO(content),mimetype='image/png',conditional=True,download_name=layer_id+'.png')

    @app.route('/share/rig/<token>/source',methods=['GET','POST'])
    def shared_rig_source(token):
        row=get_share(token)
        if not row or row['kind']!='internal':return jsonify(error='공유 링크가 없거나 만료되었습니다.'),404
        folder=(rigging.RESULT_ROOT/row['job_id']).resolve()
        if request.method=='POST':
            target=rig_edit.save_source_reference(folder,payload().get('imageData'))
            return jsonify(ok=True,sourceReference=f'/share/rig/{token}/source',bytes=target.stat().st_size)
        try:target=rig_edit.source_reference_path(folder)
        except FileNotFoundError:return jsonify(error='보관된 원본 이미지가 없습니다.'),404
        return send_file(target,mimetype='image/png',conditional=True,max_age=0)

    @app.route('/share/rig/<token>/rig-edit/regenerate',methods=['POST'])
    def shared_part_generate(token):
        row=get_share(token)
        if not row or row['kind']!='internal':return jsonify(error='내부 공유 링크가 필요합니다.'),404
        with db() as con:
            job=con.execute('SELECT * FROM jobs WHERE id=?',(row['job_id'],)).fetchone()
        return regenerate_rig_part(row['job_id'],job)

    @app.get('/share/rig/<token>/rig-edit/regenerate/<task>')
    def shared_part_candidate(token,task):
        row=get_share(token)
        if not row or row['kind']!='internal':return jsonify(error='내부 공유 링크가 필요합니다.'),404
        return rig_candidate(row['job_id'],task)

    @app.post('/share/rig/<token>/rig-edit/revisions')
    def shared_save_rig_edit(token):
        row=get_share(token)
        if not row or row['kind']!='internal':return jsonify(error='공유 링크가 없거나 만료되었습니다.'),404
        return save_rig_revision(row['job_id'],payload(),row)

    @app.post('/share/rig/<token>/rig-edit/upscale')
    def shared_rig_upscale_export(token):
        row=get_share(token)
        if not row or row['kind']!='internal':return jsonify(error='공유 링크가 없거나 만료되었습니다.'),404
        return export_rig_upscale(row['job_id'],payload(),row)

    @app.post('/share/rig/<token>/rig-edit/restore')
    def shared_restore_rig_edit(token):
        row=get_share(token)
        if not row or row['kind']!='internal':return jsonify(error='공유 링크가 없거나 만료되었습니다.'),404
        return restore_rig_version(row['job_id'],payload(),row)

    @app.post('/share/rig/<token>/rig-v2')
    def shared_build_rig_v2(token):
        row=get_share(token)
        if not row or row['kind']!='internal':return jsonify(error='공유 링크가 없거나 만료되었습니다.'),404
        response=build_rig_v2_response(row['job_id'],row,payload())
        if hasattr(response,'get_json') and response.status_code==200:
            data=response.get_json();data['packageV2']=f'/share/rig/{token}/asset/{rig_v2.V2_FILENAME}'
            return jsonify(data)
        return response

    @app.get('/share/rig/<token>/versions/<int:revision>/<filename>')
    def shared_rig_version_asset(token,revision,filename):
        row=get_share(token)
        if not row or row['kind']!='internal':return jsonify(error='공유 링크가 없거나 만료되었습니다.'),404
        current=int(json.loads(row['result'] or '{}').get('rigRevision',0));folder=(rigging.RESULT_ROOT/row['job_id']).resolve()
        try:target=rig_edit.version_file(folder,revision,current,filename)
        except FileNotFoundError:return jsonify(error='작업 버전을 찾을 수 없습니다.'),404
        return send_file(target,conditional=False,max_age=0,as_attachment=filename.endswith(('.psd','.zip')),download_name=filename)

    @app.get('/share/rig/<token>/player')
    def shared_internal_player(token):
        row=get_share(token)
        if not row or row['kind']!='internal':return '공유 링크가 없거나 만료되었습니다.',404
        html=(ROOT/'vendor'/'Anime2.5DRig'/'index.html').read_text(encoding='utf-8')
        model_url=f'/share/rig/{token}/asset/character.psd'
        html=html.replace('<head>','<head><base href="/shared-rig-player/">',1)
        return html.replace('<script src="lib/app.js"></script>',f'<script>window.SHARED_MODEL_URL={json.dumps(model_url)}</script><script src="lib/app.js"></script>',1)

    @app.get('/shared-rig-player/<path:filename>')
    def shared_player_asset(filename):
        allowed={'lib/app.css','lib/ag-psd.min.js','lib/rigger.js','lib/genericparts.js','lib/runtime.js','lib/app.js','lib/ko.js','lib/psd-worker.js','README_KO.md','eye_close.psd','mouth_close.psd'}
        normalized=filename.replace('\\','/')
        if normalized not in allowed:return jsonify(error='파일을 찾을 수 없습니다.'),404
        return send_from_directory(ROOT/'vendor'/'Anime2.5DRig',normalized,conditional=True)

    link_character_job=character_studio.register(app,db,auth,data,payload)
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
