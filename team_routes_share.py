"""Link-based internal rig sharing routes. Holding the token is the access control by design."""
import io
import json
from flask import jsonify
import re
from flask import redirect
from flask import request
import rigging_editor as rig_edit
import rigging_showcase as rig_showcase
import rigging_v2 as rig_v2
import rigging_engine as rigging
from flask import send_file
from flask import send_from_directory
import zipfile


def register(app, *, ROOT, build_rig_v2_response, db, export_rig_upscale, payload, regenerate_rig_part,
             render_page, restore_rig_version, rig_candidate, rig_editor_payload, save_rig_revision,
             showcase_lock):
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
