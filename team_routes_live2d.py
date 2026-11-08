"""Public Live2D publishing, listing and player routes."""
import hashlib
import html as html_lib
import json
from flask import jsonify
import os
from flask import request
import rigging_engine as rigging
import secrets
from flask import send_file
import shutil
import time


def register(app, *, ROOT, auth, db, payload, public_live2d_lock, public_live2d_payload, public_live2d_root,
             render_page):
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
