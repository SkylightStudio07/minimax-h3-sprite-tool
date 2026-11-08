"""Character art generation and asset routes."""
from PIL import Image
import idle_tool as engine
import image_caption
import image_engine
import image_face_refine
import json
from flask import jsonify
from flask import request
import secrets
from flask import send_file
import shutil
import time


def register(app, *, ROOT, auth, db, image_runner, link_character_job, payload):
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
