"""Halo suppression and style-preserving face-only refinement, isolated from site."""
import copy
import json
from pathlib import Path
import sys
import time

import requests
from PIL import Image, ImageChops

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_engine
import image_face_detail
import image_soya
from verify_rpg_sprite_styles import ensure_idle

OUT=ROOT/'outputs/cutscene-cleanup-20261018'
SOURCE=ROOT/'outputs/cutscene-counter-balance-20261018'


def execute(url,graph,name):
    start=time.monotonic();r=requests.post(url+'/prompt',json={'prompt':graph},timeout=60)
    if not r.ok:raise RuntimeError(r.text[:1800])
    pid=r.json()['prompt_id'];print('Generating',name,flush=True)
    while time.monotonic()-start<1200:
        history=requests.get(url+'/history/'+pid,timeout=30).json().get(pid)
        if history:break
        time.sleep(1)
    else:raise TimeoutError(pid)
    (OUT/(name+'-history.json')).write_text(json.dumps(history,indent=2),encoding='utf-8')
    if history['status']['status_str']!='success':raise RuntimeError(str(history['status'])[:1800])
    for node,suffix in [('9',''),('26','-mask')]:
        images=history['outputs'].get(node,{}).get('images',[])
        if not images:
            if node=='9':raise RuntimeError('Missing output')
            continue
        r=requests.get(url+'/view',params=images[0],timeout=60);r.raise_for_status();(OUT/(name+suffix+'.png')).write_bytes(r.content)
    record=dict(id=name,seconds=round(time.monotonic()-start,2),graph=graph)
    (OUT/(name+'.json')).write_text(json.dumps(record,indent=2),encoding='utf-8');print('Generated',name,record['seconds'],flush=True)
    return record


def main():
    sys.stdout.reconfigure(encoding='utf-8');OUT.mkdir(exist_ok=True);ensure_idle()
    source=json.loads((SOURCE/'sprite-counter-04.json').read_text())['graph']
    (OUT/'baseline.png').write_bytes((SOURCE/'sprite-counter-04.png').read_bytes())
    try:requests.post(image_soya.URL+'/free',json={'unload_models':True,'free_memory':True},timeout=20).raise_for_status()
    except requests.ConnectionError:pass
    records=[]
    for name,remove_series in [('negative-halo',False),('no-series-negative-halo',True)]:
        ensure_idle();graph=copy.deepcopy(source)
        graph['5']['inputs']['text']+=', halo, floating ring, ring above head'
        if remove_series:graph['4']['inputs']['text']=graph['4']['inputs']['text'].replace('blue archive, ','')
        graph['9']['inputs']['filename_prefix']='cutscene_cleanup/'+name
        records.append(execute(image_engine.COMFY_URL,graph,name))
    requests.post(image_engine.COMFY_URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30).raise_for_status()
    if not image_face_detail.ready():raise RuntimeError('Face tools missing; generation outputs preserved')
    image_soya.start_server()
    # Use the stronger suppression recipe; keep source unmodified for comparison.
    input_path=OUT/'no-series-negative-halo.png'
    with input_path.open('rb') as stream:
        r=requests.post(image_soya.URL+'/upload/image',files={'image':('cutscene-cleanup-face-input.png',stream,'image/png')},data={'overwrite':'true'},timeout=40)
    r.raise_for_status();uploaded=r.json()['name']
    try:
        for denoise in [.12,.20]:
            ensure_idle();name='face-'+str(round(denoise*100))
            graph={key:copy.deepcopy(source[key]) for key in ['1','2','3']}
            # Preserve Cutscene 1.0 in the face pass; exclude CounterSide.
            graph['3']['inputs'].update(model=['1',0],clip=['2',0])
            graph['30']=dict(class_type='LoadImage',inputs=dict(image=uploaded))
            p=dict(model='flanime-xl',prompt='(official art:1.1), (game cg:1.1), adult woman, purple bob hair, blue eyes, black turtleneck, three-quarter view',width=832,height=1216)
            final=image_face_detail.add_native(graph,p,20261018,['30',0],['3',0],['3',1],['1',2],denoise=denoise)
            graph['23']['inputs'].update(cfg=4.5)
            graph['22']['inputs']['text']+=', halo, floating ring'
            graph['9']=dict(class_type='SaveImage',inputs=dict(images=final,filename_prefix='cutscene_cleanup/'+name))
            record=execute(image_soya.URL,graph,name)
            with Image.open(input_path) as before,Image.open(OUT/(name+'.png')) as after,Image.open(OUT/(name+'-mask.png')) as mask:
                if before.size!=after.size:raise RuntimeError('Face pass resized canvas')
                box=mask.convert('L').getbbox()
                if not box:raise RuntimeError('No face detected')
                changed=ImageChops.difference(before.convert('RGB'),after.convert('RGB')).getbbox()
                margin=24;allowed=(max(0,box[0]-margin),max(0,box[1]-margin),min(before.width,box[2]+margin),min(before.height,box[3]+margin))
                if changed and not(allowed[0]<=changed[0] and allowed[1]<=changed[1] and allowed[2]>=changed[2] and allowed[3]>=changed[3]):raise RuntimeError('Changes outside face region')
                record.update(denoise=denoise,faceBox=box,changedBox=changed)
                (OUT/(name+'.json')).write_text(json.dumps(record,indent=2),encoding='utf-8')
            records.append(record)
    finally:
        requests.post(image_soya.URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30)
        (OUT/'results.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    cards='<article><h2>기존 헤일로 포함</h2><img src="baseline.png"></article>'
    cards+=''.join(f'<article><h2>{r["id"]}</h2><a href="{r["id"]}.png"><img src="{r["id"]}.png"></a><p>{r["seconds"]}초</p></article>' for r in records)
    (OUT/'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>헤일로 억제 · 얼굴 보정</title><style>body{background:#20232a;color:#eee;font:16px sans-serif;margin:24px}main{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}img{width:100%}h2{font-size:17px}@media(max-width:700px){main{grid-template-columns:1fr}}</style><h1>Cutscene1.0 + 카사0.4 · 헤일로 억제 / 얼굴 보정</h1><p>첫 비교: 기존prompt에 halo/floating ring 네거티브 추가. 두번째: 같은 네거티브+blue archive 시리즈태그 제거. 생성 변화는 국소지우개가 아니라 전신 재생성입니다. 얼굴 보정은 두번째 결과에만0.12/0.20 적용하며 Cutscene1.0 유지, 카사 제외.832×1216 유지·얼굴영역 외 픽셀 검사.</p><main>'+cards+'</main>',encoding='utf-8')


if __name__=='__main__':main()
