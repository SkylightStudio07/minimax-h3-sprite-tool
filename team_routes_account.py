"""Sign-in, registration, profile and account approval routes."""
from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash
import ipaddress
import json
from flask import jsonify
import os
import re
from flask import request
import secrets
from flask import session
import sqlite3
import time


def register(app, *, auth, db, password_fingerprint, payload, session_password_current, setup_file):
    def user_json(u):
        return {k:u[k] for k in ('id','username','name','state','role')}

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
