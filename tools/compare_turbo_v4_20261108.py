"""Isolated sequential 768px comparison; never changes production defaults."""
import argparse,copy,hashlib,json,shutil,subprocess,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import av,psutil,requests
import idle_tool as engine
from tools.verify_rpg_sprite_styles import ensure_idle

OUT=ROOT/'outputs/turbo-v4-comparison-20261108'
OLD=ROOT/'outputs/blonde-grip-retry-20261101'
PREFIX='turbo_v4_comparison_20261108'
LORA='minimax_h3_turbo_v4_step600_ema.safetensors'
SOURCE={'idle':'01-blonde-idle-grip','attack':'02-blonde-fire-v2'}
JOBS=[dict(id=f'{mode}-{action}',mode=mode,action=action,steps=steps) for mode,steps in [('turbo-v4',8),('base',20)] for action in SOURCE]

def save(p,obj):
    temp=p.with_suffix('.tmp');temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(p)

def verify(path):
    with av.open(str(path)) as v:
        s=v.streams.video[0]
        meta=dict(width=s.width,height=s.height,fps=float(s.average_rate),frames=s.frames)
    assert meta==dict(width=768,height=768,fps=24.,frames=73),meta
    return meta

def ram():return psutil.virtual_memory().available/1024**3

def available():
    if ram()<2:raise RuntimeError('RAM below 2 GB; waiting is required before starting')
    ensure_idle()

def prepare():
    OUT.mkdir(exist_ok=True)
    install=json.loads((OUT/'installation.json').read_text(encoding='utf-8'))
    assert install['verified']
    node=ROOT/'ComfyUI/custom_nodes/ComfyUI-MiniMax-H3-Turbo'
    install['nodeRevision']=subprocess.check_output(['git','-C',str(node),'rev-parse','HEAD'],text=True).strip()
    save(OUT/'installation.json',install)
    for job in JOBS:
        folder=OUT/job['id'];folder.mkdir(exist_ok=True)
        src=OLD/SOURCE[job['action']]
        original=json.loads((src/'native-v1-workflow.json').read_text(encoding='utf-8'))
        graph=copy.deepcopy(original)
        if job['mode']=='turbo-v4':
            graph['7']=dict(class_type='MiniMaxH3TurboLoRA',inputs=dict(model=['2',0],lora_name=LORA,strength=1.0,low_vram=False))
            graph['9']=dict(class_type='MiniMaxH3TurboSampler',inputs={})
            graph['10']['inputs']['model']=['7',0]
            graph['11']['inputs']['model']=['7',0]
        graph['10']['inputs']['steps']=job['steps']
        graph['16']['inputs']['filename_prefix']=PREFIX+'/'+job['id']
        save(folder/'workflow-template.json',graph)
        save(folder/'recipe.json',dict(**job,sourceWorkflow=str(src/'native-v1-workflow.json'),samePrompt=True,sameSeed=True,sameReference=True,loopLastFrame=job['action']=='idle',width=768,height=768,fps=24,frames=73,lowVram=False if job['mode']=='turbo-v4' else None,postprocessing=False))
        shutil.copy2(src/'reference-prepared.png',folder/'reference-prepared.png')
    for action,mid in SOURCE.items():
        raw=ROOT/'outputs/comfy/blonde_grip_retry_20261101'/(mid+'_00001_.mp4')
        verify(raw);dest=OUT/('archive-40-'+action);dest.mkdir(exist_ok=True)
        if not (dest/'raw.mp4').exists():shutil.copy2(raw,dest/'raw.mp4')
        save(dest/'provenance.json',dict(originalVideo=str(raw),steps=40,archival=True,timingComparable=False))
    build()
    save(OUT/'plan.json',dict(jobs=JOBS,onlyOneAtATime=True,productionDefaultsUnchanged=True,matting=False))
    print('COMPARISON_PREPARED',flush=True)

def next_job():
    available();engine.start_comfy();available()
    schemas=requests.get(engine.COMFY_URL+'/object_info',timeout=20).json()
    assert 'MiniMaxH3TurboLoRA' in schemas and 'MiniMaxH3TurboSampler' in schemas,'New nodes failed to load'
    for job in JOBS:
        folder=OUT/job['id'];result=folder/'result.json'
        if result.exists():
            r=json.loads(result.read_text(encoding='utf-8'))
            assert r['status']=='complete'
            verify(folder/'raw.mp4');continue
        pending=folder/'pending.json'
        if pending.exists():
            record=json.loads(pending.read_text(encoding='utf-8'))
            print('ALREADY_SUBMITTED',job['id'],record['promptId'],flush=True);return
        graph=json.loads((folder/'workflow-template.json').read_text(encoding='utf-8'))
        uploaded=engine.upload_image((folder/'reference-prepared.png').read_bytes(),job['id']+'-comparison.png')
        graph['1']['inputs']['image']=uploaded
        save(folder/'workflow.json',graph)
        available()
        started=time.time();response=requests.post(engine.COMFY_URL+'/prompt',json=dict(prompt=graph,client_id='turbo-v4-comparison'),timeout=40)
        response.raise_for_status();info=response.json()
        assert not info.get('node_errors'),info.get('node_errors')
        record=dict(**job,promptId=info['prompt_id'],submittedEpoch=started,submittedAt=time.strftime('%Y-%m-%dT%H:%M:%S'),ramBeforeGB=ram(),output=str(ROOT/'outputs/comfy'/PREFIX/(job['id']+'_00001_.mp4')))
        save(pending,record);save(OUT/'progress.json',dict(phase='running',active=job['id'],promptId=info['prompt_id']))
        print('SUBMITTED',job['id'],info['prompt_id'],flush=True);return
    save(OUT/'progress.json',dict(phase='complete',completedJobs=4));build();print('ALL_COMPARISONS_COMPLETE',flush=True)

def build():
    rows=[]
    for action in SOURCE:
        cards=[]
        for mode,label in [('archive-40','기존 40스텝 · 보관본'),('base','기본 H3 · 20스텝'),('turbo-v4','Turbo v4 · 8스텝')]:
            folder=OUT/(mode+'-'+action)
            result=folder/'result.json'
            note='시간 측정 대상 아님' if mode=='archive-40' else '생성 대기 중'
            if result.exists():
                r=json.loads(result.read_text(encoding='utf-8'))
                sampling=r.get('samplingSeconds')
                note=f"총 {r['elapsedSeconds']:.1f}초 · 샘플링 "+(f'{sampling:.1f}초' if sampling is not None else '개별 시간 미측정')
            video=f'<video controls muted loop playsinline preload="metadata" src="{folder.name}/raw.mp4"></video>' if (folder/'raw.mp4').exists() else '<p>생성 대기 중</p>'
            cards.append(f'<article><h3>{label}</h3><p>{note}</p>{video}</article>')
        rows.append(f'<h2>{action}</h2><main>'+''.join(cards)+'</main>')
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Turbo v4 비교</title><style>body{background:#18212c;color:#eee;font:16px/1.5 system-ui;margin:24px}main{display:flex;flex-wrap:wrap;gap:16px}article{width:480px;max-width:100%}video{width:100%}button{padding:10px;margin:5px}a{color:#ccbcff}</style><h1>기본 H3 / Turbo v4 비교</h1><p>동일 원화·프롬프트·seed·768×768·73프레임·24FPS. 배경 제거 전 영상입니다. 모델·샘플러·스텝 수가 달라 같은 seed여도 동작은 달라질 수 있습니다.</p><p>40스텝은 과거 보관본. 새 실행 시간에는 모델·프롬프트 캐시와 로딩 차이가 포함되므로 샘플링 시간도 함께 확인하세요.</p><button onclick="document.querySelectorAll('video').forEach(v=>{v.currentTime=0;v.play()})">처음부터 함께 재생</button><button onclick="document.querySelectorAll('video').forEach(v=>v.pause())">모두 정지</button>'''+''.join(rows)+'</html>'
    (OUT/'preview.html').write_text(page,encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','next','build']);args=parser.parse_args()
    {'prepare':prepare,'next':next_job,'build':build}[args.stage]()
