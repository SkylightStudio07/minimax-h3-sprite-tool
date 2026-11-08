"""CounterSide + Blue Archive Illustrious, character-style experiment."""
import copy
import argparse
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

OUT=ROOT/'outputs/counter-blue-archive-20261018'
BASE=ROOT/'outputs/counter-side-conversion-20261018'


def main():
    global OUT
    parser=argparse.ArgumentParser()
    parser.add_argument('--base',choices=['flanime','wai17'],default='flanime')
    parser.add_argument('--style',choices=['kivotos','cutscene'],default='kivotos')
    args=parser.parse_args()
    if args.base!='flanime' or args.style!='kivotos':OUT=ROOT/f'outputs/counter-blue-{args.base}-{args.style}-20261018'
    sys.stdout.reconfigure(encoding='utf-8');OUT.mkdir(exist_ok=True)
    ensure_idle()
    try:requests.post('http://127.0.0.1:8191/free',json={'unload_models':True,'free_memory':True},timeout=20).raise_for_status()
    except requests.ConnectionError:pass
    manifest='blue-archive-illustrious-import.json' if args.style=='kivotos' else 'blue-archive-cutscene-import.json'
    entry=json.loads((ROOT/'data'/manifest).read_text(encoding='utf-8'))['models'][0]
    style=dict(filename=entry['relative_path'].removeprefix('models/loras/'),sha256=entry['sha256'])
    path=image_engine.engine.COMFY_ROOT/'models/loras'/style['filename']
    with path.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=style['sha256']:raise RuntimeError('Style hash mismatch')
    # Reviewed CounterSide file remains separately identified in every record.
    counter=next(x for x in image_styles.catalog() if x['id']=='counter-side-sprites')
    with (image_engine.engine.COMFY_ROOT/'models/loras'/counter['filename']).open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=counter['sha256']:raise RuntimeError('Counter hash mismatch')
    original=json.loads((BASE/'counter-preserve-030.json').read_text(encoding='utf-8'))['graph']
    original['11']['inputs']['lora_name']=str(Path(counter['filename']))
    if args.base=='wai17':
        checkpoint=json.loads((ROOT/'data/wai-illustrious-import.json').read_text(encoding='utf-8'))['models'][0]
        cp=ROOT/'ComfyUI'/checkpoint['relative_path']
        with cp.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=checkpoint['sha256']:raise RuntimeError('WAI hash mismatch')
        original['1']['inputs']['ckpt_name']=cp.name
        original.pop('3',None)
        original['8']['inputs']['vae']=['1',2]
        original['6']['inputs']['vae']=['1',2]
    for file in ['prepared-reference.png','counter-preserve-030.png']:(OUT/file).write_bytes((BASE/file).read_bytes())
    cases=[('text-counter-only',0,False),('text-blue-060',.6,False),('text-blue-100',1.,False),('reference-blue-080',.8,True),('text-counter030-blue100',1.,False),('text-blue-only100',1.,False)]
    records=[]
    try:
        for name,strength,second in cases:
            ensure_idle();graph=copy.deepcopy(original)
            if second:
                graph['7']['inputs']['denoise']=.65
            else:
                graph.pop('10',None)
                graph['6']=dict(class_type='EmptyLatentImage',inputs=dict(width=1024,height=1536,batch_size=1))
                graph['7']['inputs']['denoise']=1.
            if name=='text-counter030-blue100':graph['11']['inputs'].update(strength_model=.3,strength_clip=.3)
            if name=='text-blue-only100':graph['11']['inputs'].update(strength_model=0,strength_clip=0)
            graph['13']=dict(class_type='CLIPSetLastLayer',inputs=dict(clip=['11',1],stop_at_clip_layer=-2))
            for key in ['4','5']:graph[key]['inputs']['clip']=['13',0]
            graph['7']['inputs']['cfg']=4.5
            if strength:
                graph['12']=dict(class_type='LoraLoader',inputs=dict(model=['11',0],clip=['13',0],lora_name=str(Path(style['filename'])),strength_model=strength,strength_clip=strength))
                graph['7']['inputs']['model']=['12',0]
                for key in ['4','5']:graph[key]['inputs']['clip']=['12',1]
                graph['4']['inputs']['text']=('bastory, ' if args.style=='kivotos' else '(official art:1.1), (game cg:1.1), blue archive, ')+graph['4']['inputs']['text']
            graph['9']['inputs']['filename_prefix']='counter_blue_'+args.base+'_'+args.style+'/'+name
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
                record=dict(base=args.base,style=args.style,id=name,seconds=round(time.monotonic()-start,2),referenceInput=second,blueStyleStrength=strength,denoise=.65 if second else 1.,counterStrength=graph['11']['inputs']['strength_model'],graph=graph,signature=signature,counterIntegrity=counter.get('integrityStatus'),styleSha256=style['sha256'])
                meta.write_text(json.dumps(record,indent=2),encoding='utf-8');print('Generated',name,record['seconds'],flush=True)
            records.append(record)
            (OUT/'results.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
            cards='<article><h2>입력 원화</h2><img src="prepared-reference.png"></article>'
            cards+=''.join(f'<article><h2>{r["id"]}</h2><a href="{r["id"]}.png"><img src="{r["id"]}.png"></a><p>카사 {r["counterStrength"]} / 블아풍 {r["blueStyleStrength"]} / 변형 {r["denoise"]} / {r["seconds"]}초</p></article>' for r in records)
            (OUT/'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>카사 + 블아풍 LoRA</title><style>body{background:#20232a;color:#eee;font:16px sans-serif;margin:24px}main{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}img{width:100%}h2{font-size:17px}article{background:#30343d;padding:12px}@media(max-width:700px){main{grid-template-columns:1fr}}</style><h1>카사 + 블아풍 · 얼굴/채색 변화 비교</h1><p>BASE_MODEL STYLE_LORA 1024×1536 / 32steps / CFG4.5 / CLIP skip2 / seed20261018. STYLE_DESCRIPTION. text는 같은 캐릭터 설명으로 신규 생성하며 카사0.6+블아풍을 동시 적용합니다. reference는 원본 원화에서 변형0.65로 두 LoRA를 동시 적용합니다. 원화와 카사 결과를 다시 그리는 후처리 방식이 아닙니다. 같은 캐릭터 보존을 보장하지 않습니다. 운영 설정은 변경하지 않았습니다.</p><main>'+cards+'</main>',encoding='utf-8')
            page=OUT/'preview.html';page.write_text(page.read_text(encoding='utf-8').replace('BASE_MODEL',args.base).replace('STYLE_LORA',args.style).replace('STYLE_DESCRIPTION','Kivotos Story Style / bastory' if args.style=='kivotos' else 'Blue Archive Cutscene Style / official art, game cg, blue archive'),encoding='utf-8')
    finally:
        requests.post(image_engine.COMFY_URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30)


if __name__=='__main__':main()
