"""Character collections and immutable sprite frame revisions on the existing team database."""
import base64
import copy
import io
import json
import math
from pathlib import Path
import re
import secrets
import shutil
import time
import zipfile
from flask import request,jsonify,send_file
from PIL import Image
import idle_tool as engine
import image_engine
import rigging_engine
import sprite_breathe
import sprite_finish
import sprite_gif

RECIPE_KEYS=('model','preset','prompt','negativePrompt','styleId','styleStrength','lookId','width','height','steps','cfg','denoise','assetSpec','counterMixStrength','cutsceneMixStrength','cutsceneFaceStrength')
ROLES=('art','style','direction','motion','rig')


def png_bytes(image):
    out=io.BytesIO();image.save(out,'PNG');return out.getvalue()


def image_data(image):return 'data:image/png;base64,'+base64.b64encode(png_bytes(image)).decode()


def integer(value,lo,hi,label):
    if type(value) is not int or not lo<=value<=hi:raise ValueError(label+' 범위를 확인하세요.')
    return value


def text(value,limit,label):
    if not isinstance(value,str) or len(value)>limit:raise ValueError(label+' 길이와 형식을 확인하세요.')
    return value.strip()


def register(app,db,auth,data,payload):
    root=Path(data)/'frame-workspaces';root.mkdir(exist_ok=True)
    art_root=Path(data)/'characters';art_root.mkdir(exist_ok=True)
    with db() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS characters(id TEXT PRIMARY KEY,owner INTEGER,name TEXT,notes TEXT,recipe TEXT,reference TEXT,created REAL,updated REAL,revision INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS character_jobs(character_id TEXT,job_id TEXT,role TEXT,direction TEXT,action TEXT,created REAL,PRIMARY KEY(character_id,job_id));
        CREATE TABLE IF NOT EXISTS frame_workspaces(id TEXT PRIMARY KEY,job_id TEXT,character_id TEXT,owner INTEGER,document TEXT,created REAL,updated REAL);
        CREATE TABLE IF NOT EXISTS frame_versions(workspace_id TEXT,revision INTEGER,document TEXT,created REAL,PRIMARY KEY(workspace_id,revision));
        ''')

    def editable(row):
        return row and (row['owner']==request.team_user['id'] or request.team_user['role']=='admin')

    def character(cid,write=False,con=None):
        if con is None:
            with db() as connection:return character(cid,write,connection)
        row=con.execute('SELECT * FROM characters WHERE id=?',(cid,)).fetchone()
        if not row:raise ValueError('캐릭터 묶음을 찾을 수 없습니다.')
        if write and not editable(row):raise PermissionError('본인 캐릭터 묶음 또는 관리자만 수정할 수 있습니다.')
        return row

    def char_json(row):
        return dict(id=row['id'],name=row['name'],notes=row['notes'],recipe=json.loads(row['recipe']),revision=row['revision'],owner=row['owner'],editable=editable(row),
                    reference='/api/characters/'+row['id']+'/reference' if row['reference'] else None,updated=row['updated'])

    def owned_job(con,jid):
        row=con.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
        if not row:raise ValueError('작업을 찾을 수 없습니다.')
        if row['user_id']!=request.team_user['id'] and request.team_user['role']!='admin':raise PermissionError('본인 작업 또는 관리자만 연결·수정할 수 있습니다.')
        return row

    def link_job(con,jid):
        p=request.get_json(silent=True) or {}
        cid=p.get('characterId')
        if not cid:return
        if not isinstance(cid,str):raise ValueError('캐릭터 묶음을 확인하세요.')
        character(cid,True,con)
        row=owned_job(con,jid);settings=json.loads(row['payload'])
        kind=settings.get('jobType','video')
        role='art' if kind=='image' else 'rig' if kind=='rigging' else 'motion'
        spec=p.get('assetSpec') or {}
        if not isinstance(spec,dict):raise ValueError('에셋 방향을 확인하세요.')
        con.execute('INSERT OR REPLACE INTO character_jobs VALUES(?,?,?,?,?,?)',(cid,jid,role,text(spec.get('facing',p.get('facing','')),40,'방향'),text(settings.get('animationType',''),80,'동작'),time.time()))
        con.execute('UPDATE characters SET updated=? WHERE id=?',(time.time(),cid))

    @app.errorhandler(PermissionError)
    def studio_permission(error):return jsonify(error=str(error)),403

    @app.get('/character-studio')
    @auth()
    def character_page():return send_file(Path(__file__).parent/'web/character-studio.html',max_age=0)

    @app.get('/frame-editor')
    @auth()
    def frame_page():return send_file(Path(__file__).parent/'web/frame-editor.html',max_age=0)

    @app.get('/sprite-viewer')
    @auth()
    def sprite_viewer_page():return send_file(Path(__file__).parent/'web/sprite-viewer.html',max_age=0)

    @app.route('/api/characters',methods=['GET','POST'])
    @auth()
    def characters():
        if request.method=='GET':
            with db() as con:rows=con.execute('SELECT * FROM characters ORDER BY updated DESC').fetchall()
            return jsonify(characters=[char_json(r) for r in rows])
        p=payload();name=text(p.get('name',''),80,'이름')
        if not name:raise ValueError('캐릭터 이름을 입력하세요.')
        cid=secrets.token_hex(16)
        with db() as con:
            con.execute('INSERT INTO characters VALUES(?,?,?,?,?,?,?,?,?)',(cid,request.team_user['id'],name,'','{}',None,time.time(),time.time(),0))
        return jsonify(id=cid),201

    @app.route('/api/characters/<cid>',methods=['GET','POST'])
    @auth()
    def character_detail(cid):
        with db() as con:
            if request.method=='POST':
                con.execute('BEGIN IMMEDIATE');row=character(cid,True,con);p=payload()
                if type(p.get('revision')) is not int or p['revision']!=row['revision']:return jsonify(error='다른 창에서 묶음이 변경되었습니다. 새로고침하세요.'),409
                name=text(p.get('name',row['name']),80,'이름');notes=text(p.get('notes',row['notes']),4000,'메모')
                if not name:raise ValueError('이름을 입력하세요.')
                recipe=json.loads(row['recipe'])
                if p.get('recipeFrom'):
                    job=owned_job(con,p['recipeFrom']);settings=json.loads(job['payload'])
                    if settings.get('jobType')!='image':raise ValueError('그림체 설정은 이미지 결과에서 가져오세요.')
                    recipe={k:settings[k] for k in RECIPE_KEYS if k in settings}
                con.execute('UPDATE characters SET name=?,notes=?,recipe=?,updated=?,revision=revision+1 WHERE id=?',(name,notes,json.dumps(recipe),time.time(),cid))
            row=character(cid,False,con)
            jobs=con.execute('SELECT c.*,j.state,j.payload,j.result FROM character_jobs c JOIN jobs j ON j.id=c.job_id WHERE character_id=? ORDER BY c.created DESC',(cid,)).fetchall()
            sets=con.execute('SELECT * FROM frame_workspaces WHERE character_id=? ORDER BY updated DESC',(cid,)).fetchall()
        entries=[]
        for j in jobs:
            p=json.loads(j['payload']);r=json.loads(j['result'] or '{}')
            entries.append(dict(jobId=j['job_id'],role=j['role'],direction=j['direction'],action=j['action'],state=j['state'],kind=p.get('jobType','video'),
                                title=p.get('resultTitle') or p.get('title') or p.get('animationType','결과'),image=r.get('image') or r.get('composite') or r.get('transparentSheet') or r.get('spriteSheet'),
                                frameWorkspace=r.get('frameWorkspace'),hasFrames=p.get('jobType','video')=='video' or bool(p.get('sheetLayout'))))
        return jsonify(character=char_json(row),jobs=entries,frames=[workspace_json(s) for s in sets])

    @app.route('/api/characters/<cid>/reference',methods=['GET','POST'])
    @auth()
    def character_reference(cid):
        row=character(cid,request.method=='POST')
        if request.method=='GET':
            if not row['reference']:return jsonify(error='대표 원화가 없습니다.'),404
            return send_file(art_root/cid/row['reference'],mimetype='image/png',max_age=0)
        image=image_engine.read_image(payload().get('imageData'))
        folder=art_root/cid;folder.mkdir(exist_ok=True);name=secrets.token_hex(12)+'.png';image.save(folder/name)
        with db() as con:
            con.execute('UPDATE characters SET reference=?,updated=?,revision=revision+1 WHERE id=?',(name,time.time(),cid))
        return jsonify(ok=True)

    @app.post('/api/characters/<cid>/jobs')
    @auth()
    def attach_job(cid):
        p=payload();jid=p.get('jobId');role=p.get('role','art')
        if role not in ROLES:raise ValueError('결과 분류를 확인하세요.')
        with db() as con:
            con.execute('BEGIN IMMEDIATE');character(cid,True,con);job=owned_job(con,jid)
            if json.loads(job['payload']).get('jobType','video') not in ('image','video','rigging'):raise ValueError('이미지·스프라이트·리깅 결과를 선택하세요.')
            if p.get('detach') is True:con.execute('DELETE FROM character_jobs WHERE character_id=? AND job_id=?',(cid,jid))
            else:con.execute('INSERT OR REPLACE INTO character_jobs VALUES(?,?,?,?,?,?)',(cid,jid,role,text(p.get('direction',''),40,'방향'),text(p.get('action',''),80,'동작'),time.time()))
            con.execute('UPDATE characters SET updated=? WHERE id=?',(time.time(),cid))
        return jsonify(ok=True)

    def workspace(wid,write=False,con=None):
        if con is None:
            with db() as connection:return workspace(wid,write,connection)
        row=con.execute('SELECT * FROM frame_workspaces WHERE id=?',(wid,)).fetchone()
        if not row:raise ValueError('프레임 작업을 찾을 수 없습니다.')
        if write and not editable(row):raise PermissionError('본인 프레임 작업 또는 관리자만 수정할 수 있습니다.')
        return row

    def workspace_json(row):
        doc=json.loads(row['document']);wid=row['id']
        return dict(doc,id=wid,jobId=row['job_id'],characterId=row['character_id'],editable=editable(row),
                    frames=[dict(f,url=f'/api/frames/{wid}/media/{f["file"]}') for f in doc['frames']])

    def save_document(con,row,doc):
        doc['revision']=json.loads(row['document'])['revision']+1
        con.execute('INSERT INTO frame_versions VALUES(?,?,?,?)',(row['id'],doc['revision'],json.dumps(doc),time.time()))
        con.execute('UPDATE frame_workspaces SET document=?,updated=? WHERE id=?',(json.dumps(doc),time.time(),row['id']))
        if row['job_id']:
            job=con.execute('SELECT result FROM jobs WHERE id=?',(row['job_id'],)).fetchone()
            if job:
                result=json.loads(job['result'] or '{}');result['frameWorkspace']=dict(id=row['id'],revision=doc['revision'],sheet=f'/api/frames/{row["id"]}/sheet.png',editor=f'/frame-editor?set={row["id"]}')
                con.execute('UPDATE jobs SET result=?,updated=? WHERE id=?',(json.dumps(result),time.time(),row['job_id']))

    def check_revision(doc,p):
        if type(p.get('revision')) is not int or p['revision']!=doc['revision']:raise ValueError('프레임 버전이 바뀌었습니다. 새로고침하세요.')

    def sheet_choices(row):
        p=json.loads(row['payload']);r=json.loads(row['result'] or '{}');jid=row['id'];out=[]
        kind=p.get('jobType','video')
        if kind=='video':
            for key,label in [('gameSheet','게임용 시트'),('transparentSheet','투명 배경 시트'),('spriteSheet','원본 시트'),('loopTransparentSheet','루프 보정 · 투명'),('loopSheet','루프 보정 시트')]:
                if r.get(key):out.append(dict(key=key,label=label,url=r[key],count=r.get('frameCount',p.get('frameCount',8)) if key in ('gameSheet','spriteSheet','transparentSheet') else p.get('frameCount',8),**({k:r['gameExport'][k] for k in ('columns','rows')} if key=='gameSheet' and r.get('gameExport') else {})))
            for key,url in r.get('exportSheets',{}).items():
                if key.endswith('_atlas'):continue
                info=r.get('exportSheetInfo',{}).get(key,{})
                match=re.match(r'sheet_(\d+)_',key)
                count=info.get('frameCount',int(match[1]) if match else 8)
                kind_label='숨쉬기 루프' if info.get('kind')=='breathe' else '투명' if key.endswith('_transparent') else '게임용' if key.endswith('_game') else '재추출'
                out.append(dict(key='export:'+key,label=f'{count}프레임 {kind_label} · {key.split("_")[2][:4] if match else key}',url=url,count=count,**{k:info[k] for k in ('columns','rows') if k in info}))
        elif kind=='image' and p.get('sheetLayout'):
            layout=p['sheetLayout']
            for i,item in enumerate(r.get('images',[])):
                out.append(dict(key='image:'+str(i),label='시트 후보 '+str(i+1),url=item['url'],count=layout['columns']*layout['rows'],columns=layout['columns'],rows=layout['rows']))
        return out

    def sheet_detail(choice,r):
        key=choice['key'];count=int(choice['count']);columns=choice.get('columns',min(count,8))
        sheet=dict(choice,columns=columns,rows=choice.get('rows',math.ceil(count/columns)))
        sheet['alpha']=key in ('gameSheet','transparentSheet','loopTransparentSheet') or (key.startswith('export:') and key.endswith(('_transparent','_game')))
        atlas=r.get('gameAtlas') if key=='gameSheet' else r.get('exportSheets',{}).get(key[len('export:'):-len('_game')]+'_atlas') if key.startswith('export:') and key.endswith('_game') else None
        if atlas:sheet['atlas']=atlas
        return sheet

    @app.get('/api/jobs/<jid>/sheets')
    @auth()
    def job_sheets(jid):
        # Read-only listing for the viewer, for the same team-visible jobs as the result page.
        with db() as con:row=con.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
        if not row or row['state']!='complete':raise ValueError('완료된 결과를 선택하세요.')
        p=json.loads(row['payload']);r=json.loads(row['result'] or '{}')
        timing=(r.get('pixelExport') or {}).get('durationMs') or r.get('sheetTimingMs')
        sheets=[]
        for choice in sheet_choices(row):
            sheet=sheet_detail(choice,r)
            if sheet['key'] in ('gameSheet','spriteSheet','transparentSheet') and isinstance(timing,list) and len(timing)==int(sheet['count']):sheet['durationMs']=timing
            sheets.append(sheet)
        return jsonify(title=p.get('resultTitle') or p.get('title') or p.get('animationType') or '스프라이트',sheets=sheets)

    @app.post('/api/jobs/<jid>/breathe')
    @auth()
    def breathe_sheet(jid):
        p=payload();count=p.get('frameCount');fps=p.get('fps');index=p.get('frame')
        if type(fps) is not int or not 1<=fps<=60:raise ValueError('FPS는 1~60으로 입력하세요.')
        if type(index) is not int:raise ValueError('프레임 번호를 확인하세요.')
        with db() as con:row=con.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
        if not row or row['state']!='complete':raise ValueError('완료된 결과를 선택하세요.')
        if row['user_id']!=request.team_user['id'] and request.team_user['role']!='admin':return jsonify(error='본인 결과 또는 관리자만 만들 수 있습니다.'),403
        r=json.loads(row['result'] or '{}')
        choice=next((c for c in sheet_choices(row) if c['key']==p.get('source')),None)
        if not choice:raise ValueError('시트를 선택하세요.')
        sheet=sheet_detail(choice,r)
        if not sheet['alpha']:raise ValueError('투명 배경 시트에서만 만들 수 있습니다.')
        folder=(engine.RESULT_ROOT/jid).resolve();prefix=f'/outputs/results/{jid}/'
        files=[folder/Path(u[len(prefix):]).name for u in (sheet['url'],sheet.get('atlas')) if u]
        if not sheet['url'].startswith(prefix) or not all(f.is_file() for f in files):return jsonify(error='시트 파일을 찾을 수 없습니다.'),404
        still=sprite_breathe.read_frame(files[0],index,sheet['columns'],sheet['rows'],files[1] if len(files)>1 else None)
        frames=sprite_breathe.loop(still,p.get('neck'),p.get('axis'),p.get('half'),count)
        key=f'sheet_{count}_{secrets.token_hex(8)}';png=folder/(key+'_game.png');atlas=folder/(key+'_game.json')
        try:
            made=sprite_finish.write(frames,'idle',True,sprite_finish.uniform_ms(count,fps),png,atlas,None,fps)
            with db() as con:
                con.execute('BEGIN IMMEDIATE')
                current=con.execute("SELECT result FROM jobs WHERE id=? AND state='complete'",(jid,)).fetchone()
                if not current:return jsonify(error='만드는 중 결과가 삭제되었습니다.'),409
                updated=json.loads(current['result'] or '{}')
                updated.setdefault('exportSheets',{}).update({key+'_game':prefix+png.name,key+'_atlas':prefix+atlas.name})
                updated.setdefault('exportSheetInfo',{})[key+'_game']=dict(kind='breathe',frameCount=made['frameCount'],columns=made['columns'],rows=made['rows'],fps=fps,oversize=made['oversize'],edgeContactFrames=made['edgeContactFrames'])
                con.execute('UPDATE jobs SET result=? WHERE id=?',(json.dumps(updated),jid))
            png=atlas=None
            return jsonify(ok=True,key=f'export:{key}_game')
        finally:
            for leftover in (png,atlas):
                if leftover:leftover.unlink(missing_ok=True)

    @app.get('/api/jobs/<jid>/sheet.gif')
    @auth()
    def job_sheet_gif(jid):
        # Read-only handoff for the same team-visible jobs as the result page.
        with db() as con:row=con.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
        if not row or row['state']!='complete':raise ValueError('완료된 시트를 선택하세요.')
        choices=sheet_choices(row);key=request.args.get('source')
        choice=next((c for c in choices if c['key']==key),None) if key else next(iter(choices),None)
        if not choice:raise ValueError('저장된 시트를 선택하세요.')
        kind=json.loads(row['payload']).get('jobType','video');url=choice['url']
        prefix=f'/outputs/results/{jid}/' if kind=='video' else f'/api/images/{jid}/'
        if not isinstance(url,str) or not url.startswith(prefix):raise ValueError('시트 경로를 확인하세요.')
        name=url[len(prefix):]
        if not name or any(c in name for c in ('/','\\')):raise ValueError('시트 경로를 확인하세요.')
        storage=(engine.RESULT_ROOT if kind=='video' else image_engine.RESULT_ROOT).resolve();folder=(storage/jid).resolve();source=(folder/name).resolve()
        if not folder.is_relative_to(storage) or not source.is_relative_to(folder) or not source.is_file():raise ValueError('저장된 시트가 없습니다.')
        count=integer(choice['count'],1,128,'프레임 수');cols=choice.get('columns',min(count,8));rows=choice.get('rows',math.ceil(count/cols))
        fps=request.args.get('fps','8')
        if not fps.isdecimal() or not 1<=int(fps)<=60:raise ValueError('GIF 재생 FPS는 1~60입니다.')
        with Image.open(source) as sheet:images=sprite_gif.split_sheet(sheet,cols,rows,count)
        report=json.loads(row['result']).get('pixelExport') or {}
        timing=report.get('durationMs') if choice['key'] in ('gameSheet','spriteSheet','transparentSheet') and 'fps' not in request.args else None
        if not timing and choice['key'] in ('gameSheet','spriteSheet','transparentSheet') and 'fps' not in request.args:
            timing=json.loads(row['result']).get('sheetTimingMs')
        if not isinstance(timing,list) or len(timing)!=count:timing=[1000/int(fps)]*count
        content,_=sprite_gif.encode(images,timing)
        return send_file(io.BytesIO(content),mimetype='image/gif',as_attachment=True,download_name=source.stem+'.gif',max_age=0)

    @app.route('/api/jobs/<jid>/frames',methods=['GET','POST'])
    @auth()
    def job_frames(jid):
        with db() as con:row=owned_job(con,jid)
        choices=sheet_choices(row)
        if request.method=='GET':
            with db() as con:sets=con.execute('SELECT * FROM frame_workspaces WHERE job_id=? ORDER BY updated DESC',(jid,)).fetchall()
            return jsonify(sources=choices,workspaces=[workspace_json(s) for s in sets])
        if row['state']!='complete':raise ValueError('완료된 스프라이트 시트를 선택하세요.')
        p=payload();choice=next((c for c in choices if c['key']==p.get('source',choices[0]['key'] if choices else None)),None)
        if not choice:raise ValueError('편집할 시트가 없습니다.')
        kind=json.loads(row['payload']).get('jobType','video')
        url=choice['url']
        prefix=f'/outputs/results/{jid}/' if kind=='video' else f'/api/images/{jid}/'
        if not url.startswith(prefix) or '/' in url[len(prefix):]:raise ValueError('시트 경로를 확인하세요.')
        source=(engine.RESULT_ROOT if kind=='video' else image_engine.RESULT_ROOT)/jid/url[len(prefix):]
        with Image.open(source) as opened:
            count=integer(p.get('count',choice['count']),1,128,'프레임 수')
            cols=integer(p.get('columns',choice.get('columns',min(count,8))),1,64,'열 수')
            rows=integer(p.get('rows',choice.get('rows',math.ceil(count/cols))),1,64,'행 수')
            if count>cols*rows or opened.width<cols or opened.height<rows:raise ValueError('시트 크기와 열·행·프레임 수를 확인하세요.')
            if opened.width*opened.height>64_000_000:raise ValueError('시트는 64MP 이하를 사용하세요.')
            sheet=opened.convert('RGBA')
        wid=secrets.token_hex(16);folder=root/wid;cw,ch=math.ceil(sheet.width/cols),math.ceil(sheet.height/rows)
        if cw*ch>4_000_000:raise ValueError('프레임 하나는 4MP 이하여야 합니다.')
        folder.mkdir()
        doc=dict(revision=0,source=choice['key'],width=cw,height=ch,columns=cols,rows=rows,fps=8,frames=[],originalSheetSize=list(sheet.size),gridNormalized=bool(sheet.width%cols or sheet.height%rows))
        saved_timing=json.loads(row['result'] or '{}').get('sheetTimingMs')
        if choice['key'] not in ('gameSheet','spriteSheet','transparentSheet') or count!=choice['count'] or not isinstance(saved_timing,list) or len(saved_timing)!=count:
            saved_timing=None
        if saved_timing:
            doc['fps']=max(1,min(60,round(1000*count/sum(saved_timing))))
        layout=json.loads(row['payload']).get('sheetLayout') or {}
        directions=layout.get('directions',[]) if kind=='image' else []
        doc['clips']=[dict(name=direction,start=i*cols,end=min(count,(i+1)*cols)-1) for i,direction in enumerate(directions) if i*cols<count]
        try:
            for i in range(count):
                name=f'original-{i:03d}.png'
                box=(round((i%cols)*sheet.width/cols),round((i//cols)*sheet.height/rows),round((i%cols+1)*sheet.width/cols),round((i//cols+1)*sheet.height/rows))
                frame=Image.new('RGBA',(cw,ch));frame.paste(sheet.crop(box),(0,0));frame.save(folder/name)
                doc['frames'].append(dict(file=name,locked=False,**({'durationMs':saved_timing[i]} if saved_timing else {})))
            with db() as con:
                con.execute('BEGIN IMMEDIATE');cid=p.get('characterId')
                if cid:character(cid,True,con)
                else:
                    attached=con.execute('SELECT character_id FROM character_jobs WHERE job_id=? LIMIT 1',(jid,)).fetchone();cid=attached[0] if attached else None
                con.execute('INSERT INTO frame_workspaces VALUES(?,?,?,?,?,?,?)',(wid,jid,cid,request.team_user['id'],json.dumps(doc),time.time(),time.time()))
                con.execute('INSERT INTO frame_versions VALUES(?,?,?,?)',(wid,0,json.dumps(doc),time.time()))
        except Exception:
            shutil.rmtree(folder);raise
        return jsonify(id=wid),201

    @app.get('/api/frames/<wid>')
    @auth()
    def frame_info(wid):
        row=workspace(wid)
        with db() as con:versions=con.execute('SELECT revision,created FROM frame_versions WHERE workspace_id=? ORDER BY revision DESC',(wid,)).fetchall()
        return jsonify(workspace_json(row)|dict(versions=[dict(v) for v in versions]))

    @app.get('/api/frames/<wid>/media/<name>')
    @auth()
    def frame_media(wid,name):
        workspace(wid)
        if not re.fullmatch(r'(original-\d{3}|edit-[a-f0-9]{24})\.png',name):return jsonify(error='프레임을 찾을 수 없습니다.'),404
        response=send_file(root/wid/name,mimetype='image/png',max_age=31536000)
        response.cache_control.public=False;response.cache_control.private=True
        return response

    @app.post('/api/frames/<wid>/settings')
    @auth()
    def frame_settings(wid):
        p=payload()
        with db() as con:
            con.execute('BEGIN IMMEDIATE');row=workspace(wid,True,con);doc=json.loads(row['document']);check_revision(doc,p)
            if 'fps' in p:
                doc['fps']=integer(p['fps'],1,60,'FPS')
                doc.pop('durationMs',None)
                for frame in doc['frames']:frame.pop('durationMs',None)
            if 'locks' in p:
                if not isinstance(p['locks'],list) or len(p['locks'])!=len(doc['frames']) or any(type(v) is not bool for v in p['locks']):raise ValueError('프레임 고정 상태를 확인하세요.')
                for f,v in zip(doc['frames'],p['locks']):f['locked']=v
            if 'characterId' in p:
                character(p['characterId'],True,con);con.execute('UPDATE frame_workspaces SET character_id=? WHERE id=?',(p['characterId'],wid))
            save_document(con,row,doc)
        return jsonify(ok=True,revision=doc['revision'])

    @app.post('/api/frames/<wid>/restore')
    @auth()
    def frame_restore(wid):
        p=payload()
        with db() as con:
            con.execute('BEGIN IMMEDIATE');row=workspace(wid,True,con);check_revision(json.loads(row['document']),p)
            old=con.execute('SELECT document FROM frame_versions WHERE workspace_id=? AND revision=?',(wid,p.get('target'))).fetchone()
            if not old:raise ValueError('복원할 버전이 없습니다.')
            doc=json.loads(old[0]);save_document(con,row,doc)
        return jsonify(ok=True)

    @app.post('/api/frames/<wid>/regenerate')
    @auth()
    def frame_generate(wid):
        p=payload();prompt=text(p.get('prompt',''),1000,'수정 요청')
        if not prompt:raise ValueError('어떻게 고칠지 입력하세요.')
        if not all(path.is_file() for path in rigging_engine.QWEN_MODEL_PATHS):raise ValueError('프레임 편집 모델을 설치해야 합니다.')
        mask=image_engine.read_image(p.get('maskData')).convert('L')
        with db() as con:
            con.execute('BEGIN IMMEDIATE');row=workspace(wid,True,con);doc=json.loads(row['document']);check_revision(doc,p)
            i=integer(p.get('frame'),0,len(doc['frames'])-1,'프레임 번호')
            if doc['frames'][i]['locked']:raise ValueError('고정한 프레임입니다. 고정을 풀고 수정하세요.')
            if mask.size!=(doc['width'],doc['height']) or not mask.getbbox():raise ValueError('선택 프레임의 수정할 영역을 칠하세요.')
            active=con.execute("SELECT count(*) FROM jobs WHERE state NOT IN ('complete','error','cancelled')").fetchone()[0]
            mine=con.execute("SELECT count(*) FROM jobs WHERE user_id=? AND state NOT IN ('complete','error','cancelled')",(request.team_user['id'],)).fetchone()[0]
            if active>=20 or mine>=3:return jsonify(error='대기 한도에 도달했습니다.'),429
            task=secrets.token_hex(16);mask_name='mask-'+task+'.png';mask.save(root/wid/mask_name)
            settings=dict(jobType='frame-edit',workspaceId=wid,_workspaceRoot=str(root),sourceFile=doc['frames'][i]['file'],maskFile=mask_name,revision=doc['revision'],frame=i,prompt=prompt,animationType='스프라이트 프레임 수정')
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(task,request.team_user['id'],'queued',time.time(),time.time(),json.dumps(settings),json.dumps(dict(message='프레임 수정 대기 중'))))
        return jsonify(taskId=task),202

    def candidate(con,wid,task):
        row=con.execute('SELECT * FROM jobs WHERE id=?',(task,)).fetchone()
        if not row or json.loads(row['payload']).get('workspaceId')!=wid or json.loads(row['payload']).get('jobType')!='frame-edit':raise ValueError('수정 후보를 찾을 수 없습니다.')
        return row

    @app.get('/api/frames/<wid>/candidates/<task>')
    @auth()
    def frame_candidate(wid,task):
        workspace(wid)
        with db() as con:row=candidate(con,wid,task)
        r=json.loads(row['result'] or '{}');result=dict(state=row['state'],message=r.get('message',''))
        if row['state']=='complete':
            folder=root/wid/'candidates'/task;result.update(json.loads((folder/'candidate.json').read_text()))
            with Image.open(folder/'candidate.png') as im:result['imageData']=image_data(im)
        return jsonify(result)

    @app.post('/api/frames/<wid>/apply')
    @auth()
    def frame_apply(wid):
        p=payload()
        with db() as con:
            con.execute('BEGIN IMMEDIATE');row=workspace(wid,True,con);doc=json.loads(row['document']);check_revision(doc,p)
            task=p.get('taskId');job=candidate(con,wid,task);settings=json.loads(job['payload'])
            if job['state']!='complete' or settings['revision']!=doc['revision']:raise ValueError('현재 버전에 맞는 완료 후보를 선택하세요.')
            i=settings['frame']
            if doc['frames'][i]['locked']:raise ValueError('고정한 프레임은 바꿀 수 없습니다.')
            name='edit-'+secrets.token_hex(12)+'.png';shutil.copyfile(root/wid/'candidates'/task/'candidate.png',root/wid/name)
            doc['frames'][i]['file']=name;save_document(con,row,doc)
        return jsonify(ok=True,revision=doc['revision'])

    @app.post('/api/frames/<wid>/trim')
    @auth()
    def frame_trim(wid):
        p=payload()
        with db() as con:
            con.execute('BEGIN IMMEDIATE');row=workspace(wid,True,con);doc=json.loads(row['document']);check_revision(doc,p)
            count=len(doc['frames']);start=integer(p.get('start'),0,count-1,'시작 프레임');end=integer(p.get('end'),0,count-1,'끝 프레임')
            if end<start:raise ValueError('끝 프레임은 시작 프레임보다 앞설 수 없습니다.')
            if start==0 and end==count-1:return jsonify(ok=True,revision=doc['revision'])
            doc['frames']=doc['frames'][start:end+1]
            doc['columns']=min(doc['columns'],len(doc['frames']));doc['rows']=math.ceil(len(doc['frames'])/doc['columns'])
            doc['clips']=[dict(clip,start=max(start,clip['start'])-start,end=min(end,clip['end'])-start) for clip in doc.get('clips',[]) if clip['start']<=end and clip['end']>=start]
            motion=doc.get('motion',{})
            if len(motion.get('poses',[]))==count:motion['poses']=motion['poses'][start:end+1]
            anchor=motion.get('appearanceAnchorFrame')
            if anchor is not None:
                if start<=anchor<=end:motion['appearanceAnchorFrame']=anchor-start
                else:motion.pop('appearanceAnchorFrame',None)
            doc['trim']=dict(sourceRevision=doc['revision'],start=start,end=end)
            save_document(con,row,doc)
        return jsonify(ok=True,revision=doc['revision'])

    @app.post('/api/frames/<wid>/select')
    @auth()
    def frame_select(wid):
        p=payload()
        with db() as con:
            con.execute('BEGIN IMMEDIATE');row=workspace(wid,True,con);doc=json.loads(row['document']);check_revision(doc,p)
            count=len(doc['frames']);keep=p.get('keep')
            if not isinstance(keep,list) or not keep or any(type(i) is not int or not 0<=i<count for i in keep) or keep!=sorted(set(keep)):
                raise ValueError('남길 프레임을 확인하세요.')
            if len(keep)==count:return jsonify(ok=True,revision=doc['revision'])
            # A removed frame's time goes to the frame before it, so the action keeps its length.
            spans=[(i,keep[n+1] if n+1<len(keep) else count) for n,i in enumerate(keep)]
            merge=lambda times:[sum(times[a:b]) for a,b in spans]
            if all(isinstance(f.get('durationMs'),(int,float)) for f in doc['frames']):
                for frame,total in zip([doc['frames'][i] for i in keep],merge([f['durationMs'] for f in doc['frames']])):frame['durationMs']=total
            if isinstance(doc.get('durationMs'),list) and len(doc['durationMs'])==count:doc['durationMs']=merge(doc['durationMs'])
            moved={old:new for new,old in enumerate(keep)}
            doc['frames']=[doc['frames'][i] for i in keep]
            doc['columns']=min(doc['columns'],len(keep));doc['rows']=math.ceil(len(keep)/doc['columns'])
            clips=[]
            for clip in doc.get('clips',[]):
                inside=[moved[i] for i in keep if clip['start']<=i<=clip['end']]
                if inside:clips.append(dict(clip,start=inside[0],end=inside[-1]))
            if 'clips' in doc:doc['clips']=clips
            motion=doc.get('motion',{})
            if len(motion.get('poses',[]))==count:motion['poses']=[motion['poses'][i] for i in keep]
            anchor=motion.get('appearanceAnchorFrame')
            if anchor is not None:
                if anchor in moved:motion['appearanceAnchorFrame']=moved[anchor]
                else:motion.pop('appearanceAnchorFrame',None)
            doc['selection']=dict(sourceRevision=doc['revision'],keep=keep)
            save_document(con,row,doc)
        return jsonify(ok=True,revision=doc['revision'])

    @app.get('/api/frames/<wid>/sheet.png')
    @auth()
    def frame_sheet(wid):
        doc=json.loads(workspace(wid)['document']);out=make_sheet(root/wid,doc)
        return send_file(io.BytesIO(png_bytes(out)),mimetype='image/png',download_name='sprite-edited.png',max_age=0)

    @app.get('/api/frames/<wid>/export.zip')
    @auth()
    def frame_export(wid):
        doc=json.loads(workspace(wid)['document']);out=io.BytesIO()
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('sprite-sheet.png',png_bytes(make_sheet(root/wid,doc)))
            metadata=copy.deepcopy(doc)
            for i,f in enumerate(doc['frames']):
                name=f'frames/{i:03d}.png';archive.write(root/wid/f['file'],name);metadata['frames'][i]['file']=name
            archive.writestr('animation.json',json.dumps(metadata,ensure_ascii=False,indent=2))
            archive.writestr('README.txt','PNG는 동일 크기 셀입니다. FPS와 프레임 순서는 animation.json을 참고하세요. 원본 영상은 수정되지 않았습니다.\n')
        out.seek(0)
        action=doc.get('motion',{}).get('action','')
        name='sprite-'+(action if action in ('walk','run') else 'frames')+'-v'+str(doc['revision']+1)+'.zip'
        return send_file(out,mimetype='application/zip',as_attachment=True,download_name=name)

    @app.get('/api/frames/<wid>/animation.gif')
    @auth()
    def frame_gif(wid):
        doc=json.loads(workspace(wid)['document']);selected=doc['frames'];start=0;end=len(selected)
        clip=request.args.get('clip','all')
        if clip!='all':
            if not clip.isdecimal() or int(clip)>=len(doc.get('clips',[])):raise ValueError('재생 구간을 선택하세요.')
            c=doc['clips'][int(clip)];start=c['start'];end=c['end']+1
        images=[]
        for item in selected[start:end]:
            with Image.open(root/wid/item['file']) as image:images.append(image.convert('RGBA'))
        times=doc.get('durationMs')
        times=times[start:end] if isinstance(times,list) and len(times)==len(selected) else [f.get('durationMs',1000/doc['fps']) for f in selected[start:end]]
        content,_=sprite_gif.encode(images,times)
        return send_file(io.BytesIO(content),mimetype='image/gif',as_attachment=True,download_name='sprite-v'+str(doc['revision']+1)+('-clip-'+clip if clip!='all' else '')+'.gif',max_age=0)

    return link_job


def make_sheet(folder,doc):
    image=Image.new('RGBA',(doc['width']*doc['columns'],doc['height']*doc['rows']))
    for i,f in enumerate(doc['frames']):
        with Image.open(folder/f['file']) as frame:image.paste(frame,((i%doc['columns'])*doc['width'],(i//doc['columns'])*doc['height']))
    return image
