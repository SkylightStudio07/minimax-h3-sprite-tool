"""CounterSide + a second style LoRA, compared with sequential img2img."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import time

import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_engine
import image_styles
from verify_rpg_sprite_styles import ensure_idle

OUT=ROOT/'outputs/counter-style-mix-20261018'
BASE=ROOT/'outputs/counter-side-conversion-20261018'


def main():
    sys.stdout.reconfigure(encoding='utf-8');OUT.mkdir(exist_ok=True)
    ensure_idle()
    try:requests.post('http://127.0.0.1:8191/free',json={'unload_models':True,'free_memory':True},timeout=20).raise_for_status()
    except requests.ConnectionError:pass
    style=next(x for x in image_styles.catalog() if x['id']=='fsthicc-illustrious')
    path=image_engine.engine.COMFY_ROOT/'models/loras'/style['filename']
    with path.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=style['sha256']:raise RuntimeError('Style hash mismatch')
    # Reviewed CounterSide file remains separately identified in every record.
    counter=next(x for x in image_styles.catalog() if x['id']=='counter-side-sprites')
    with (image_engine.engine.COMFY_ROOT/'models/loras'/counter['filename']).open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=counter['sha256']:raise RuntimeError('Counter hash mismatch')
    original=json.loads((BASE/'counter-preserve-030.json').read_text(encoding='utf-8'))['graph']
    original['11']['inputs']['lora_name']=str(Path(counter['filename']))
    for file in ['prepared-reference.png','counter-preserve-030.png']:(OUT/file).write_bytes((BASE/file).read_bytes())
    with (BASE/'counter-preserve-030.png').open('rb') as stream:
        r=requests.post(image_engine.COMFY_URL+'/upload/image',files={'image':('counter-mix-second-pass.png',stream,'image/png')},data={'overwrite':'true'},timeout=30)
    r.raise_for_status();second_input=r.json()['name']
    cases=[('counter-only',0,False),('mixed-outline-030',.3,False),('mixed-outline-050',.5,False),('second-pass-outline-030',.3,True)]
    records=[]
    try:
        for name,strength,second in cases:
            ensure_idle();graph=copy.deepcopy(original)
            if second:
                graph['10']['inputs']['image']=second_input
                graph['11']['inputs'].update(strength_model=0,strength_clip=0)
            if strength:
                graph['12']=dict(class_type='LoraLoader',inputs=dict(model=['11',0],clip=['11',1],lora_name=str(Path(style['filename'])),strength_model=strength,strength_clip=strength))
                graph['7']['inputs']['model']=['12',0]
                for key in ['4','5']:graph[key]['inputs']['clip']=['12',1]
                graph['4']['inputs']['text']+=', thick black outline'
            graph['9']['inputs']['filename_prefix']='counter_style_mix/'+name
            signature=hashlib.sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest()
            meta=OUT/(name+'.json');target=OUT/(name+'.png')
            if target.exists() and meta.exists() and json.loads(meta.read_text(encoding='utf-8')).get('signature')==signature:
                record=json.loads(meta.read_text(encoding='utf-8'));print('Cached',name,flush=True)
            else:
                start=time.monotonic();r=requests.post(image_engine.COMFY_URL+'/prompt',json={'prompt':graph},timeout=60)
                if not r.ok:raise RuntimeError(r.text[:1600])
                pid=r.json()['prompt_id'];print('Generating',name,flush=True)
                while time.monotonic()-start<1200:
                    history=requests.get(image_engine.COMFY_URL+'/history/'+pid,timeout=30).json().get(pid)
                    if history:break
                    time.sleep(1)
                else:raise TimeoutError(pid)
                (OUT/(name+'-history.json')).write_text(json.dumps(history,indent=2),encoding='utf-8')
                if history['status']['status_str']!='success':raise RuntimeError(str(history['status'])[:1600])
                r=requests.get(image_engine.COMFY_URL+'/view',params=history['outputs']['9']['images'][0],timeout=60);r.raise_for_status();target.write_bytes(r.content)
                record=dict(id=name,seconds=round(time.monotonic()-start,2),secondPass=second,outlineStrength=strength,denoise=.3,counterStrength=0 if second else .6,graph=graph,signature=signature,counterIntegrity=counter.get('integrityStatus'),styleSha256=style['sha256'])
                meta.write_text(json.dumps(record,indent=2),encoding='utf-8');print('Generated',name,record['seconds'],flush=True)
            records.append(record)
            (OUT/'results.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
            cards='<article><h2>입력 원화</h2><img src="prepared-reference.png"></article>'
            cards+=''.join(f'<article><h2>{r["id"]}</h2><a href="{r["id"]}.png"><img src="{r["id"]}.png"></a><p>카사 {r["counterStrength"]} / 선화 {r["outlineStrength"]} / 변형0.3 / {r["seconds"]}초</p></article>' for r in records)
            (OUT/'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>카사 + 그림체 LoRA</title><style>body{background:#20232a;color:#eee;font:16px sans-serif;margin:24px}main{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}img{width:100%}h2{font-size:17px}article{background:#30343d;padding:12px}@media(max-width:700px){main{grid-template-columns:1fr}}</style><h1>카사 + 굵은 선화 · 동시 적용 / 후처리 비교</h1><p>Flanime 1024×1536 / 32steps / CFG5 / 동일 seed20261018. FSThicc Illustrious. mixed는 원화에서 카사+선화 동시 적용. second-pass는 카사 결과를 입력해 선화만 적용. 2차 처리의 총시간은 최초 카사 생성 시간도 더해야 합니다. 얼굴/의상/장식 보존 검수. 운영 옵션은 변경하지 않았습니다.</p><main>'+cards+'</main>',encoding='utf-8')
    finally:
        requests.post(image_engine.COMFY_URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30)


if __name__=='__main__':main()
