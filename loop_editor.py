"""Manual video loop selection and immutable frame workspace export; no generation."""
import io
import json
import math
from pathlib import Path
import secrets
import shutil
import time

import av
from flask import jsonify,request,send_file

import character_studio as frames
import idle_tool as engine

ROOT=Path(__file__).resolve().parent
SOURCES={'video':'생성 영상','rawVideo':'보정 전 영상','loopVideo':'자동 루프 보정 영상'}


def inspect_video(path):
    times=[]
    with av.open(str(path)) as container:
        stream=container.streams.video[0];fps=float(stream.average_rate or 24)
        for frame in container.decode(video=0):
            if len(times)>=10000:raise ValueError('반복 구간 편집은 10000프레임 이하 영상을 사용하세요.')
            times.append(float(frame.time) if frame.time is not None else len(times)/fps)
            width,height=frame.width,frame.height
    if len(times)<2:raise ValueError('영상에 두 프레임 이상이 필요합니다.')
    origin=times[0];times=[round(t-origin,8) for t in times]
    if any(b<=a for a,b in zip(times,times[1:])):raise ValueError('영상 프레임의 시간 순서를 확인할 수 없습니다.')
    duration=times[-1]+(times[-1]-times[-2])
    return dict(frameCount=len(times),times=times,fps=fps,width=width,height=height,duration=duration)


def indices(start,end,count):
    # Inclusive endpoints, no repeated frames. Users exclude a duplicated final pose.
    return [start+round(i*(end-start)/(count-1)) for i in range(count)]


def register(app,db,auth,data,payload,extraction_lock):
    root=Path(data)/'frame-workspaces';root.mkdir(exist_ok=True)

    def source(jid,key):
        if key not in SOURCES:raise ValueError('편집할 영상을 선택하세요.')
        with db() as con:row=con.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
        if not row:raise ValueError('영상을 찾을 수 없습니다.')
        if row['user_id']!=request.team_user['id'] and request.team_user['role']!='admin':raise PermissionError('본인 영상 또는 관리자만 반복 구간을 편집할 수 있습니다.')
        if row['state']!='complete' or json.loads(row['payload']).get('jobType','video')!='video':raise ValueError('완료된 스프라이트 영상을 선택하세요.')
        result=json.loads(row['result'] or '{}');url=result.get(key,'');prefix=f'/outputs/results/{jid}/'
        if not isinstance(url,str) or not url.startswith(prefix) or '/' in url[len(prefix):] or '\\' in url[len(prefix):]:raise ValueError('저장된 영상을 찾을 수 없습니다.')
        folder=(engine.RESULT_ROOT/jid).resolve();path=(folder/url[len(prefix):]).resolve()
        if not folder.is_relative_to(engine.RESULT_ROOT.resolve()) or not path.is_relative_to(folder) or not path.is_file():raise ValueError('저장된 영상 파일이 없습니다.')
        return row,path,url,result

    @app.get('/loop-editor')
    @auth()
    def page():return send_file(ROOT/'web/loop-editor.html',max_age=0)

    @app.get('/api/jobs/<jid>/loop-editor')
    @auth()
    def info(jid):
        key=request.args.get('source','video');row,path,url,result=source(jid,key)
        return jsonify(inspect_video(path)|dict(video=url,source=key,sources=[dict(id=k,label=v) for k,v in SOURCES.items() if result.get(k)],backgroundReady=engine.image_background.status()['ready']))

    @app.get('/api/jobs/<jid>/loop-frame')
    @auth()
    def boundary(jid):
        _,path,_,_=source(jid,request.args.get('source','video'))
        try:i=int(request.args.get('frame','-1'))
        except ValueError:raise ValueError('프레임 번호를 확인하세요.')
        if not 0<=i<10000:raise ValueError('프레임 번호를 확인하세요.')
        with av.open(str(path)) as container:
            for n,frame in enumerate(container.decode(video=0)):
                if n==i:
                    image=frame.to_image();image.thumbnail((768,768));out=io.BytesIO();image.save(out,'PNG');out.seek(0)
                    response=send_file(out,mimetype='image/png',max_age=0);response.cache_control.private=True;return response
        raise ValueError('영상에 없는 프레임입니다.')

    @app.post('/api/jobs/<jid>/loop-editor')
    @auth()
    def export(jid):
        p=payload();row,path,_,_=source(jid,p.get('source','video'));meta=inspect_video(path)
        start=frames.integer(p.get('start'),0,meta['frameCount']-1,'시작 프레임');end=frames.integer(p.get('end'),0,meta['frameCount']-1,'끝 프레임')
        if end<=start:raise ValueError('끝은 시작보다 뒤에 지정하세요. 최소 두 프레임이 필요합니다.')
        count=frames.integer(p.get('count'),2,min(64,end-start+1),'출력 장수');fps=frames.integer(p.get('fps'),1,60,'재생 FPS')
        method=p.get('background','keep')
        original_settings=json.loads(row['payload'])
        subtle=original_settings.get('combatEffect')=='subtle' and not original_settings.get('pixelOutput')
        if method not in ('keep','flat','ai'):raise ValueError('배경 제거 방식을 확인하세요.')
        if method!='keep':engine.background_options(dict(removeBackground=True,backgroundRemoval='flat' if subtle else method,combatEffect='subtle' if subtle else 'none'))
        if meta['width']*meta['height']>4_000_000 or meta['width']*meta['height']*count>64_000_000:raise ValueError('프레임은 4MP, 출력 시트는 64MP 이하로 장수를 줄여주세요.')
        if not extraction_lock.acquire(blocking=False):return jsonify(error='다른 시트를 저장 중입니다. 잠시 후 다시 시도하세요.'),409
        wid=secrets.token_hex(16);folder=root/wid;published=False
        try:
            folder.mkdir();selected=indices(start,end,count);lookup={n:i for i,n in enumerate(selected)};items=[]
            with av.open(str(path)) as container:
                for n,frame in enumerate(container.decode(video=0)):
                    if n>end:break
                    if n not in lookup:continue
                    image=frame.to_image().convert('RGBA')
                    if method!='keep' and subtle:
                        import sprite_vfx_matte
                        image,_=sprite_vfx_matte.remove(image)
                    elif method=='flat':image=engine.remove_flat_background(image)
                    elif method=='ai':image=engine.image_background.remove_sprite(image)
                    name=f'original-{lookup[n]:03d}.png';image.save(folder/name)
                    items.append(dict(file=name,locked=False,sourceFrame=n,sourceTime=meta['times'][n]))
            if len(items)!=count:raise ValueError('영상 프레임이 변경되었습니다. 다시 불러오세요.')
            columns=min(8,count);duration=(meta['times'][end+1] if end+1<meta['frameCount'] else meta['duration'])-meta['times'][start]
            doc=dict(revision=0,width=meta['width'],height=meta['height'],columns=columns,rows=math.ceil(count/columns),fps=fps,frames=items,
                     clips=[dict(name='loop',start=0,end=count-1)],source='video-range',
                     videoRange=dict(source=p.get('source','video'),start=start,end=end,sourceFps=meta['fps'],duration=duration,background=method))
            frames.make_sheet(folder,doc).save(folder/'sprite-sheet.png')
            with db() as con:
                con.execute('BEGIN IMMEDIATE');current=con.execute("SELECT * FROM jobs WHERE id=? AND state='complete'",(jid,)).fetchone()
                if not current or current['user_id']!=row['user_id']:raise ValueError('저장 중 원본 작업이 변경되었습니다.')
                now=time.time();attached=con.execute('SELECT character_id FROM character_jobs WHERE job_id=? LIMIT 1',(jid,)).fetchone();cid=attached['character_id'] if attached else None
                con.execute('INSERT INTO frame_workspaces VALUES(?,?,?,?,?,?,?)',(wid,jid,cid,row['user_id'],json.dumps(doc),now,now))
                con.execute('INSERT INTO frame_versions VALUES(?,?,?,?)',(wid,0,json.dumps(doc),now))
                result=json.loads(current['result'] or '{}');result['frameWorkspace']=dict(id=wid,revision=0,sheet=f'/api/frames/{wid}/sheet.png',editor=f'/frame-editor?set={wid}')
                con.execute('UPDATE jobs SET result=?,updated=? WHERE id=?',(json.dumps(result),now,jid))
                if cid:con.execute('UPDATE characters SET updated=? WHERE id=?',(now,cid))
            published=True
            return jsonify(id=wid,editor=f'/frame-editor?set={wid}',sheet=f'/api/frames/{wid}/sheet.png',download=f'/api/frames/{wid}/export.zip',gif=f'/api/frames/{wid}/animation.gif'),201
        finally:
            if not published:shutil.rmtree(folder,ignore_errors=True)
            extraction_lock.release()
