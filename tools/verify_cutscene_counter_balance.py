"""Keep the user-approved Cutscene recipe fixed; sweep CounterSide strength."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import time

import requests
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_engine
import image_styles
from verify_rpg_sprite_styles import ensure_idle

OUT=ROOT/'outputs/cutscene-counter-balance-20261018'
APPROVED=ROOT/'outputs/blue-archive-standalone-20261018'


def main():
    sys.stdout.reconfigure(encoding='utf-8');OUT.mkdir(exist_ok=True);ensure_idle()
    source=json.loads((APPROVED/'original-cutscene.json').read_text(encoding='utf-8'))
    counter=next(s for s in image_styles.catalog() if s['id']=='counter-side-sprites')
    files=[('data/wai-illustrious-import.json','baseSha256'),('data/blue-archive-cutscene-import.json','styleSha256')]
    for manifest,key in files:
        entry=json.loads((ROOT/manifest).read_text())['models'][0]
        with (ROOT/'ComfyUI'/entry['relative_path']).open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=source[key]:raise RuntimeError('Integrity mismatch '+manifest)
    with (image_engine.engine.COMFY_ROOT/'models/loras'/counter['filename']).open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=counter['sha256']:raise RuntimeError('Counter integrity mismatch')
    try:requests.post('http://127.0.0.1:8191/free',json={'unload_models':True,'free_memory':True},timeout=20).raise_for_status()
    except requests.ConnectionError:pass
    records=[]
    try:
        for framing in ['portrait','sprite']:
            for strength in [0.,.2,.4]:
                ensure_idle();name=framing+'-counter-'+str(round(strength*10)).zfill(2)
                graph=copy.deepcopy(source['graph'])
                if framing=='sprite':
                    graph['4']['inputs']['text']=graph['4']['inputs']['text'].replace('black coat with dark red lining','long black coat with dark red lining, black fitted pants, black boots, mechanical black glove').replace('upper body, looking at viewer, classroom, window, sunlight, blue sky','full body, feet visible, side view, facing right, standing in a battle ready stance, single character game battle sprite, simple white background')
                if strength:
                    graph['11']=dict(class_type='LoraLoader',inputs=dict(model=['1',0],clip=['2',0],lora_name=str(Path(counter['filename'])),strength_model=strength,strength_clip=strength))
                    graph['3']['inputs'].update(model=['11',0],clip=['11',1])
                graph['9']['inputs']['filename_prefix']='cutscene_counter_balance/'+name
                signature=hashlib.sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest();meta=OUT/(name+'.json');target=OUT/(name+'.png')
                if target.exists() and meta.exists() and json.loads(meta.read_text())['signature']==signature:
                    record=json.loads(meta.read_text());print('Cached',name,flush=True)
                elif framing=='portrait' and strength==0:
                    target.write_bytes((APPROVED/'original-cutscene.png').read_bytes())
                    record=dict(id=name,framing=framing,counterStrength=strength,cutsceneStrength=1.,seconds=source['seconds'],reusedFrom=str(APPROVED/'original-cutscene.json'),signature=signature,graph=graph)
                    meta.write_text(json.dumps(record,indent=2),encoding='utf-8');print('Reused approved baseline',flush=True)
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
                    record=dict(id=name,framing=framing,counterStrength=strength,cutsceneStrength=1.,seconds=round(time.monotonic()-start,2),signature=signature,graph=graph,counterSha256=counter['sha256'],counterIntegrity=counter.get('integrityStatus'))
                    meta.write_text(json.dumps(record,indent=2),encoding='utf-8');print('Generated',name,record['seconds'],flush=True)
                records.append(record);(OUT/'results.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
                cards=''.join(f'<article><h2>{x["framing"]} · 카사 {x["counterStrength"]}</h2><a href="{x["id"]}.png"><img src="{x["id"]}.png"></a><p>Cutscene 1.0 / {x["seconds"]}초</p></article>' for x in records)
                (OUT/'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>블아풍 고정 · 카사 강도 비교</title><style>body{background:#20232a;color:#eee;font:16px sans-serif;margin:24px}main{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}img{width:100%}h2{font-size:17px}article{background:#30343d;padding:12px}@media(max-width:700px){main{grid-template-columns:1fr}}</style><h1>Cutscene1.0 고정 → 카사0 / 0.2 / 0.4</h1><p>사용자가 블아풍으로 확인한 WAI17+Cutscene1.0 레시피 기준.832×1216 / 28steps / CFG4.5 / CLIPskip2 / seed20261018 / 내장VAE. 첫행은 상반신 동일prompt, 둘째행은 측면 전신 스프라이트prompt. 행 간에는 구도/배경/의상설명이 달라지므로 카사 효과는 같은 행 안에서 비교합니다. 같은 캐릭터 정체성 보장이나 1개seed 이상 검증은 아닙니다. 카사0 상반신은 승인받은 원본 결과 재사용. 사이트 설정은 그대로.</p><main>'+cards+'</main>',encoding='utf-8')
        for framing in ['portrait','sprite']:
            canvas=Image.new('RGB',(3*350,550),'#ddd');draw=ImageDraw.Draw(canvas)
            for i,r in enumerate([r for r in records if r['framing']==framing]):
                with Image.open(OUT/(r['id']+'.png')) as im:canvas.paste(im.resize((350,512),Image.Resampling.LANCZOS),(i*350,36))
                draw.text((i*350+8,10),'Cutscene 1.0 / Counter '+str(r['counterStrength']),fill='black')
            canvas.save(OUT/(framing+'-comparison.webp'))
    finally:
        requests.post(image_engine.COMFY_URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30)


if __name__=='__main__':main()
