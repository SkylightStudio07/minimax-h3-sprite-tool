"""Team accounts, approval, persistent FIFO GPU queue and shared gallery."""
import base64
from contextlib import contextmanager
import functools
import io
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from pathlib import Path

from flask import Flask, request, session, jsonify, send_file, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image, ImageChops
import idle_tool as engine
import rigging_engine as rigging

ROOT = Path(__file__).resolve().parent
TERMINAL = ('complete', 'error', 'cancelled')


def create_app(data_dir=None, runner=None, rigging_runner=None):
    data = Path(data_dir or ROOT / 'data')
    data.mkdir(parents=True, exist_ok=True)
    key = data / 'session.key'
    if not key.exists():
        key.write_text(secrets.token_hex(32), encoding='utf-8')
    app = Flask(__name__, static_folder=None)
    app.config.update(SECRET_KEY=key.read_text().strip(), MAX_CONTENT_LENGTH=30*1024*1024,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      SESSION_COOKIE_SECURE=os.environ.get('SPRITE_HTTPS') == '1')
    database = data / 'team.sqlite3'

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
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        return response

    def auth(admin=False):
        def decorate(fn):
            @functools.wraps(fn)
            def wrapped(*args, **kwargs):
                with db() as con:
                    u = con.execute('SELECT * FROM users WHERE id=?',(session.get('uid'),)).fetchone()
                if not u or u['state'] != 'approved':
                    return jsonify(error='승인된 계정으로 로그인하세요.'),401
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
        for k in ('username','name','password','setupCode','imageData','eyeLeftMask','eyeRightMask','mouthMask','prompt','animationType','facing'):
            if k in p and not isinstance(p[k],str):
                raise ValueError('문자열 입력이 필요합니다: '+k)
        return p

    def rate_limit():
        with db() as con:
            con.execute('DELETE FROM attempts WHERE created < ?',(time.time()-600,))
            n = con.execute('SELECT count(*) FROM attempts WHERE ip=?',(request.remote_addr,)).fetchone()[0]
            if n >= 30:
                return False
            con.execute('INSERT INTO attempts VALUES(?,?)',(request.remote_addr,time.time()))
        return True

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
        return jsonify(user=user_json(u) if u else None, setupRequired=setup)

    @app.post('/api/register')
    def register():
        if not rate_limit():
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
        if not rate_limit():
            return jsonify(error='로그인 시도가 많습니다. 10분 뒤 다시 시도하세요.'),429
        p = payload()
        with db() as con:
            u = con.execute('SELECT * FROM users WHERE username=?',(p.get('username','').lower().strip(),)).fetchone()
        if not u or not check_password_hash(u['password'],p.get('password','')):
            return jsonify(error='아이디 또는 비밀번호가 맞지 않습니다.'),401
        if u['state'] != 'approved':
            return jsonify(error='관리자 승인 대기 중이거나 이용이 제한된 계정입니다.'),403
        session.clear()
        session['uid'] = u['id']
        return jsonify(user=user_json(u))

    @app.post('/api/logout')
    def logout():
        session.clear()
        return jsonify(ok=True)

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
        return jsonify(**{k:s[k] for k in ('comfy','modelsReady','licenseConfirmed')}, rigging=rs)

    def job_json(row):
        result = json.loads(row['result'] or '{}')
        p = json.loads(row['payload'])
        return dict(result,id=row['id'],state=row['state'],owner=row['name'],userId=row['user_id'],
                    jobType=p.get('jobType','video'),
                    created=row['created'],animationType=p.get('animationType','idle'),
                    width=p.get('width'),height=p.get('height'),
                    referencePreview=f'/api/jobs/{row["id"]}/reference' if p.get('imageData') and row['state'] not in TERMINAL else None)

    @app.get('/api/gallery')
    def public_gallery():
        try:
            page=max(1,int(request.args.get('page','1')))
        except ValueError:
            raise ValueError('페이지 번호는 정수여야 합니다.')
        with db() as con:
            viewer=con.execute("SELECT state FROM users WHERE id=?",(session.get('uid'),)).fetchone()
            approved=viewer and viewer['state']=='approved'
            condition="state='complete'" if approved else "state='complete' AND COALESCE(json_extract(payload,'$.jobType'),'video')='video'"
            total=con.execute(f"SELECT count(*) FROM jobs WHERE {condition}").fetchone()[0]
            pages=max(1,(total+5)//6);page=min(page,pages)
            rows=con.execute(f"""SELECT j.*,u.name FROM jobs j JOIN users u ON u.id=j.user_id
                WHERE j.{condition} ORDER BY j.created DESC,j.id DESC LIMIT 6 OFFSET ?""",((page-1)*6,)).fetchall()
        items=[]
        for row in rows:
            result=json.loads(row['result'] or '{}')
            p=json.loads(row['payload'])
            items.append(dict(id=row['id'],created=row['created'],animationType=p.get('animationType','idle'),jobType=p.get('jobType','video'),
                poster=f'/gallery-media/{row["id"]}/poster' if result.get('video') else None,
                exportSheets={k:f'/gallery-media/{row["id"]}/{k}' for k in result.get('exportSheets',{})},
                **{k:f'/gallery-media/{row["id"]}/{k}' if result.get(k) else None for k in ('video','spriteSheet','transparentSheet')}))
            if approved:
                items[-1].update(owner=row['name'],userId=row['user_id'],rawVideo=result.get('rawVideo'))
                if p.get('jobType')=='rigging': items[-1].update(composite=result.get('composite'),psd=result.get('psd'),package=result.get('package'),player=result.get('player'))
        return jsonify(jobs=items,page=page,pages=pages,total=total)

    poster_lock=threading.Lock()

    @app.get('/gallery-media/<jid>/<kind>')
    def public_result(jid,kind):
        # Only presentation assets are public, never rawVideo or input images.
        if kind not in ('video','spriteSheet','transparentSheet','poster') and not re.fullmatch(r'sheet_[0-9]+_[0-9a-f]{16}',kind):
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
        engine.guidance_options(p)
        if p.get('samplingMode','quality') not in ('quality','turbo'):
            raise ValueError('잘못된 생성 모드입니다.')
        p.setdefault('samplingMode','quality')
        if type(p.get('motionPadding',10)) is not int or p.get('motionPadding',10) not in (0,10,20,30):
            raise ValueError('동작 여백은 0, 10, 20, 30% 중 선택하세요.')
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
        if any(k in p and not isinstance(p[k],bool) for k in ('loop','stabilize','removeBackground')):
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
        jid=secrets.token_hex(16)
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            active=con.execute("SELECT count(*) FROM jobs WHERE state NOT IN ('complete','error','cancelled')").fetchone()[0]
            mine=con.execute("SELECT count(*) FROM jobs WHERE user_id=? AND state NOT IN ('complete','error','cancelled')",(request.team_user['id'],)).fetchone()[0]
            if active>=20 or mine>=3:
                return jsonify(error='전체 20개 또는 개인 3개 대기 한도에 도달했습니다.'),429
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',
                        (jid,request.team_user['id'],'queued',time.time(),time.time(),json.dumps(p),json.dumps({'message':'대기 중'})))
        return jsonify(jobId=jid),202

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
                    if not visible.getbbox() or sum(visible.histogram()[1:])<8:
                        raise ValueError()
            except Exception:
                raise ValueError(label+' 마스크가 비어 있거나 이미지 크기와 다릅니다.')
        for mask_key,absent_key,label in (
            ('eyeLeftMask','eyeLeftAbsent','화면 왼쪽 눈'),
            ('eyeRightMask','eyeRightAbsent','화면 오른쪽 눈')):
            if p[absent_key]:
                p.pop(mask_key,None)
            else:
                check_mask(mask_key,label)
        check_mask('mouthMask','입')
        p.update(jobType='rigging',maskVersion=1,resolution=resolution,steps=steps,filename='character.png',animationType='2D 리깅')
        jid=secrets.token_hex(16)
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            active=con.execute("SELECT count(*) FROM jobs WHERE state NOT IN ('complete','error','cancelled')").fetchone()[0]
            mine=con.execute("SELECT count(*) FROM jobs WHERE user_id=? AND state NOT IN ('complete','error','cancelled')",(request.team_user['id'],)).fetchone()[0]
            if active>=20 or mine>=3:
                return jsonify(error='전체 20개 또는 개인 3개 대기 한도에 도달했습니다.'),429
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',
                        (jid,request.team_user['id'],'queued',time.time(),time.time(),json.dumps(p),json.dumps({'message':'리깅 대기 중'})))
        return jsonify(jobId=jid),202

    extraction_lock=threading.Lock()

    @app.post('/api/jobs/<jid>/extract')
    @auth()
    def extract_sheet(jid):
        count=payload().get('frameCount')
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
        result=json.loads(row['result'] or '{}')
        relative=result.get('video','')
        if not relative.startswith(f'/outputs/results/{jid}/'):
            return jsonify(error='저장된 영상을 찾을 수 없습니다.'),404
        folder=(engine.RESULT_ROOT/jid).resolve()
        video=(folder/Path(relative).name).resolve()
        if not folder.is_relative_to(engine.RESULT_ROOT.resolve()) or not video.is_relative_to(folder) or not video.is_file():
            return jsonify(error='저장된 영상 파일이 없습니다.'),404
        if not extraction_lock.acquire(blocking=False):
            return jsonify(error='다른 시트를 추출 중입니다. 잠시 후 다시 시도하세요.'),409
        try:
            key=f'sheet_{count}_{secrets.token_hex(8)}'
            output=folder/(key+'.png')
            p=json.loads(row['payload'])
            engine.make_sprite_sheet(video,output,count,bool(p.get('loop',True)))
            path=f'/outputs/results/{jid}/{output.name}'
            with db() as con:
                con.execute('BEGIN IMMEDIATE')
                current=con.execute("SELECT result FROM jobs WHERE id=? AND state='complete'",(jid,)).fetchone()
                if not current:
                    return jsonify(error='추출 중 결과가 삭제되었습니다.'),409
                updated=json.loads(current['result'] or '{}')
                updated.setdefault('exportSheets',{})[key]=path
                con.execute('UPDATE jobs SET result=? WHERE id=?',(json.dumps(updated),jid))
            return jsonify(ok=True,spriteSheet=path)
        except Exception:
            app.logger.exception('Sprite sheet extraction failed')
            return jsonify(error='시트 추출에 실패했습니다. 서버 로그를 확인하세요.'),500
        finally:
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
            con.execute('DELETE FROM jobs WHERE id=?',(jid,))
        return jsonify(ok=True)

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
                for key in ('imageData','eyeLeftMask','eyeRightMask','mouthMask'):
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
        if relative not in [allowed.get(k) for k in ('video','rawVideo','spriteSheet','transparentSheet')]+list(allowed.get('exportSheets',{}).values()):
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
        if relative not in [result.get(k) for k in ('psd','package','composite','preview','manifest')]:
            return jsonify(error='리깅 결과를 찾을 수 없습니다.'),404
        folder=(rigging.RESULT_ROOT/jid).resolve()
        target=(folder/filename).resolve()
        if not folder.is_relative_to(rigging.RESULT_ROOT.resolve()) or not target.is_relative_to(folder) or not target.is_file():
            return jsonify(error='리깅 파일을 찾을 수 없습니다.'),404
        return send_file(target,conditional=True)

    @app.post('/api/jobs/<jid>/shares')
    @auth()
    def create_rig_share(jid):
        kind=payload().get('kind')
        if kind not in ('internal','external'): raise ValueError('공유 종류를 확인하세요.')
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
            return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>내부 2D 리깅 결과</title><style>body{{margin:0;font:15px system-ui;background:#0c0f16;color:#eee}}header{{display:flex;align-items:center;gap:16px;padding:14px 20px;background:#171d29;border-bottom:1px solid #30384b}}h1{{font-size:18px;margin:0}}p{{margin:0;color:#aeb8cb}}a{{margin-left:auto;padding:9px 15px;background:#7661e3;color:white;border-radius:9px;text-decoration:none}}iframe{{display:block;width:100%;height:calc(100vh - 70px);border:0;background:#101014}}</style></head><body><header><div><h1>2D 리깅 내부 결과</h1><p>PSD를 자동으로 불러왔습니다. 다운로드 파일도 함께 제공됩니다.</p></div><a id="download" href="/share/rig/{token}/asset/character.psd" download>PSD 다운로드</a></header><iframe src="/share/rig/{token}/player" allow="fullscreen" title="2D 리깅 미리보기"></iframe><script>setTimeout(()=>document.getElementById('download').click(),700)</script></body></html>'''
        return f'''<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width"><title>2D 리깅 쇼케이스</title><style>body{{margin:0;background:radial-gradient(circle,#292044,#090b11);color:white;font:16px system-ui;text-align:center}}main{{min-height:100vh;display:grid;place-items:center}}img{{max-width:82vw;max-height:76vh;filter:drop-shadow(0 25px 30px #0008);animation:f 3s ease-in-out infinite}}@keyframes f{{50%{{transform:translateY(-12px) rotate(.6deg)}}}}a{{color:#c9beff}}</style><main><div><img src="/share/rig/{token}/asset/composite.png"><h1>AI 2D 리깅 쇼케이스</h1><p>한 장의 그림을 움직이는 캐릭터로 만들었습니다.</p><a href="/">나도 만들어 보기</a></div></main>'''

    @app.get('/share/rig/<token>/asset/<filename>')
    def share_asset(token,filename):
        row=get_share(token); allowed=('character.psd',) if row and row['kind']=='internal' else ('composite.png',)
        if not row or filename not in allowed:return jsonify(error='공유할 수 없는 파일입니다.'),404
        folder=(rigging.RESULT_ROOT/row['job_id']).resolve();target=(folder/filename).resolve()
        if not target.is_relative_to(folder) or not target.is_file():return jsonify(error='파일을 찾을 수 없습니다.'),404
        return send_file(target,conditional=True,as_attachment=filename.endswith('.psd'),download_name=filename)

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
            if job_type=='rigging' and rigging_runner is None:
                try:
                    q=rigging.requests.get(rigging.COMFY_URL+'/queue',timeout=3).json()
                    if q.get('queue_running') or q.get('queue_pending'):
                        continue
                except Exception:
                    continue
            elif job_type!='rigging' and runner is None:
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
            target_engine=rigging if job_type=='rigging' else engine
            target_engine.update_job=update
            try:
                target_runner=(rigging_runner or rigging.run_job) if job_type=='rigging' else (runner or engine.run_job)
                target_runner(jid,job_payload)
            except Exception as error:
                update(jid,state='error',message=str(error) or '생성 중 오류가 발생했습니다.')
            finally:
                with db() as con:
                    p=json.loads(row['payload'])
                    for key in ('imageData','eyeLeftMask','eyeRightMask','mouthMask'):
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
    app.start_worker()
    print('Team Sprite Lab: http://127.0.0.1:7866',flush=True)
    print('First admin setup code: data/admin-setup-code.txt (local only)',flush=True)
    serve(app,host='127.0.0.1',port=int(os.environ.get('SPRITE_PORT','7866')),threads=6)
