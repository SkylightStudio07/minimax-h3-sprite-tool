import asyncio, json, os, subprocess, sys, time, uuid
from pathlib import Path
import aiohttp, psutil, requests

ROOT = Path(r'G:\Minimax')
OUT = ROOT / 'outputs/character-variations-20261101'
COMFY = 'http://127.0.0.1:8189'
PROGRESS = OUT / 'luna-progress.json'

def resume_prompts():
    if not PROGRESS.exists(): return []
    try:
        s=json.loads(PROGRESS.read_text(encoding='utf-8'))
        if s.get('active') and s.get('promptId') and s.get('phase') in ('running','starting'):
            return [(s['active'],s['promptId'])]
    except Exception: pass
    return []

PROMPTS = resume_prompts()

def save(obj):
    tmp = PROGRESS.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(PROGRESS)

def mem_gb():
    return psutil.virtual_memory().available / (1024**3)

def history(pid):
    r = requests.get(f'{COMFY}/history/{pid}', timeout=10)
    r.raise_for_status()
    return r.json().get(pid)

def get_outputs(h):
    files=[]
    for node in (h or {}).get('outputs', {}).values():
        for vid in node.get('videos', []): files.append(vid)
        for img in node.get('images', []): files.append(img)
    return files

def local_video(name):
    if name.get('type') == 'output':
        return ROOT / 'outputs/comfy' / name.get('filename', '')
    return ROOT / name.get('filename', '')

def verify_video(path):
    ffprobe = shutil_which('ffprobe')
    if ffprobe:
        p = subprocess.run([ffprobe, '-v','error','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,nb_frames','-of','json',str(path)],capture_output=True,text=True,timeout=30)
        if p.returncode == 0:
            try:
                st=json.loads(p.stdout)['streams'][0]
                return {'width':st.get('width'),'height':st.get('height'),'fps':st.get('r_frame_rate'),'frames':st.get('nb_frames')}
            except Exception: pass
    try:
        import cv2
        cap=cv2.VideoCapture(str(path))
        ans={'width':int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),'height':int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)), 'fps':cap.get(cv2.CAP_PROP_FPS),'frames':int(cap.get(cv2.CAP_PROP_FRAME_COUNT))}
        cap.release(); return ans
    except Exception: return {'bytes':path.stat().st_size}

def shutil_which(cmd):
    import shutil
    return shutil.which(cmd)

async def monitor_one(name,pid,state,session,client):
    state.update({'active':name,'promptId':pid,'phase':'running','lastUpdate':time.strftime('%Y-%m-%dT%H:%M:%S')})
    save(state)
    wsurl=COMFY.replace('http://','ws://')+f'/ws?clientId={client}'
    try:
        async with session.ws_connect(wsurl,heartbeat=30,timeout=15) as ws:
            last_msg=time.monotonic()
            while True:
                try:
                    msg=await asyncio.wait_for(ws.receive(),timeout=8)
                except asyncio.TimeoutError:
                    msg=None
                if msg and msg.type == aiohttp.WSMsgType.TEXT:
                    last_msg=time.monotonic()
                    try: data=json.loads(msg.data)
                    except Exception: data={}
                    if data.get('type')=='progress':
                        d=data.get('data',{})
                        v=int(d.get('value',0)); m=int(d.get('max',0))
                        state.update({'step':v,'steps':m,'percent':round(v*100/m,1) if m else None,'lastUpdate':time.strftime('%Y-%m-%dT%H:%M:%S'),'freeRamGB':round(mem_gb(),2)})
                        save(state)
                    elif data.get('type') in ('executing','status'):
                        state['lastEvent']=data.get('type'); state['lastUpdate']=time.strftime('%Y-%m-%dT%H:%M:%S'); save(state)
                elif msg and msg.type in (aiohttp.WSMsgType.ERROR,aiohttp.WSMsgType.CLOSED):
                    raise RuntimeError(f'WebSocket closed/error: {msg.type}')
                if time.monotonic()-last_msg>300:
                    raise RuntimeError('No WebSocket events for 300 seconds')
                h=history(pid)
                if h:
                    status=h.get('status',{}).get('status_str')
                    if status!='success':
                        raise RuntimeError(f'Comfy history terminal status: {status}; {h.get("status",{}).get("messages",[])}')
                    # This Comfy SaveVideo node records only `animated: true` in history;
                    # resolve the known, task-specific output prefix on disk.
                    output=ROOT / 'outputs/comfy/character_variations_20261101' / f'{name}_00001_.mp4'
                    deadline=time.monotonic()+120
                    while not output.exists() and time.monotonic()<deadline: await asyncio.sleep(2)
                    if not output.exists(): raise RuntimeError(f'Output file missing: {output}')
                    meta=verify_video(output)
                    item={'id':name,'promptId':pid,'status':'success','file':str(output),'bytes':output.stat().st_size,'video':meta,'completedAt':time.strftime('%Y-%m-%dT%H:%M:%S')}
                    state.setdefault('completed',[]).append(item)
                    state.update({'active':None,'phase':'completed','step':40,'steps':40,'percent':100,'freeRamGB':round(mem_gb(),2)})
                    save(state)
                    return item
                await asyncio.sleep(0.25)
    except Exception as e:
        state.update({'phase':'error','error':str(e),'failedAt':time.strftime('%Y-%m-%dT%H:%M:%S'),'freeRamGB':round(mem_gb(),2)})
        save(state)
        raise

async def main():
    state={'batch':'character-variations-20261101','expectedJobs':9,'completed':[],'active':None,'phase':'starting','updatedAt':time.strftime('%Y-%m-%dT%H:%M:%S')}
    if PROGRESS.exists():
        old=json.loads(PROGRESS.read_text(encoding='utf-8'))
        state.update(old)
    state.setdefault('completed',[])
    client=str(uuid.uuid4())
    timeout=aiohttp.ClientTimeout(total=None,connect=15,sock_read=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while len(state['completed'])<9:
            if PROMPTS:
                name,pid=PROMPTS.pop(0)
            else:
                free=mem_gb()
                if free<2:
                    q=requests.get(COMFY+'/queue',timeout=10).json()
                    if not q.get('queue_running') and not q.get('queue_pending'):
                        requests.post(COMFY+'/free',json={'unload_models':True,'free_memory':True},timeout=30).raise_for_status()
                    state.update({'phase':'waiting-for-ram','freeRamGB':round(mem_gb(),2),'updatedAt':time.strftime('%Y-%m-%dT%H:%M:%S')}); save(state)
                    while mem_gb()<2: await asyncio.sleep(10)
                proc=subprocess.run([str(ROOT/'.venv/Scripts/python.exe'),str(ROOT/'tools/submit_character_variations_20261101.py'),'next'],cwd=ROOT,capture_output=True,text=True,timeout=120)
                print(proc.stdout.strip(),flush=True)
                if proc.returncode:
                    raise RuntimeError('next command failed: '+proc.stderr[-2000:])
                if 'ALL_NINE_COMPLETE' in proc.stdout:
                    state.update({'phase':'complete','allCompleteAt':time.strftime('%Y-%m-%dT%H:%M:%S')}); save(state); break
                recs=json.loads((OUT/'generation-submissions.json').read_text(encoding='utf-8'))['records']
                seen={x['id'] for x in state['completed']}
                rec=next((x for x in recs if x['id'] not in seen),None)
                if not rec: raise RuntimeError('next command did not add a new record')
                name,pid=rec['id'],rec['promptId']
                state.setdefault('submitted',[]).append({'id':name,'promptId':pid,'submittedAt':time.strftime('%Y-%m-%dT%H:%M:%S')})
                save(state)
                print('SUBMITTED_ONE',name,pid,flush=True)
            item=await monitor_one(name,pid,state,session,client)
            print('COMPLETED',item['id'],item['file'],item['video'],flush=True)
        if len(state['completed'])==9:
            state.update({'phase':'submitting-check','updatedAt':time.strftime('%Y-%m-%dT%H:%M:%S')}); save(state)
            free=mem_gb()
            if free>=2:
                proc=subprocess.run([str(ROOT/'.venv/Scripts/python.exe'),str(ROOT/'tools/submit_character_variations_20261101.py'),'next'],cwd=ROOT,capture_output=True,text=True,timeout=120)
                print(proc.stdout.strip(),flush=True)
            state.update({'phase':'complete','allCompleteAt':time.strftime('%Y-%m-%dT%H:%M:%S')}); save(state)

asyncio.run(main())

