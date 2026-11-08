import json,time,subprocess
from pathlib import Path
import requests,psutil,cv2
ROOT=Path(r'G:\Minimax'); OUT=ROOT/'outputs/blonde-grip-retry-20261101'; PROG=OUT/'luna-progress.json'; PID='929ef98a-100b-4c97-8d1e-4a9ab16f47fc'; NAME='02-blonde-fire-v2'; VIDEO=ROOT/'outputs/comfy/blonde_grip_retry_20261101'/f'{NAME}_00001_.mp4'
d=json.loads(PROG.read_text(encoding='utf-8')); d.update(active=NAME,promptId=PID,phase='running',step=0,steps=40,percent=0); d.setdefault('submitted',[]).append({'id':NAME,'promptId':PID,'submittedAt':time.strftime('%Y-%m-%dT%H:%M:%S')})
def save():
 d['updatedAt']=time.strftime('%Y-%m-%dT%H:%M:%S'); d['freeRamGB']=round(psutil.virtual_memory().available/1024**3,2); tmp=PROG.with_suffix('.tmp'); tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(PROG)
save()
while True:
 try:
  h=requests.get(f'http://127.0.0.1:8189/history/{PID}',timeout=15).json().get(PID)
  if h and h.get('status',{}).get('completed'):
   if h['status'].get('status_str')!='success': d.update(phase='error',error=f"Comfy history terminal status: {h['status'].get('status_str')}; {h['status'].get('messages',[])}"); save(); print('ERROR',d['error'],flush=True); break
   if VIDEO.exists():
    cap=cv2.VideoCapture(str(VIDEO)); v={'width':int(cap.get(3)),'height':int(cap.get(4)),'fps':cap.get(5),'frames':int(cap.get(7))}; cap.release()
    item={'id':NAME,'promptId':PID,'status':'success','file':str(VIDEO),'bytes':VIDEO.stat().st_size,'video':v,'completedAt':time.strftime('%Y-%m-%dT%H:%M:%S')}; d.setdefault('completed',[]).append(item); d.update(active=None,phase='complete',step=40,steps=40,percent=100); save(); print('COMPLETED',json.dumps(item),flush=True); break
   d['phase']='saving-output'
  else: d['phase']='running'
  q=requests.get('http://127.0.0.1:8189/queue',timeout=10).json(); d['queueRunning']=len(q.get('queue_running',[])); d['queuePending']=len(q.get('queue_pending',[]))
 except Exception as e: d['lastPollError']=str(e)
 save(); print(time.strftime('%H:%M:%S'),'phase',d['phase'],'RAM',d['freeRamGB'],'queue',d.get('queueRunning'),d.get('queuePending'),flush=True); time.sleep(20)
