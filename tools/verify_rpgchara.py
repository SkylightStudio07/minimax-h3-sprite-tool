"""Manual RPG Maker multi-view LoRA comparison; never changes site defaults."""
import copy
import hashlib
import html
import json
from pathlib import Path
import sys
import time

import requests
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_engine
from verify_rpg_sprite_styles import ensure_idle

OUT=ROOT/'outputs/rpgchara-test-20261018'
SUBJECT='a female adventurer with short blue hair, a white scarf, navy blue coat with gold trim, brown boots, fully clothed, unarmed'
NEGATIVE='worst quality, low quality, blurry, text, watermark, cropped, out of frame'


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    OUT.mkdir(exist_ok=True)
    inventory=json.loads((ROOT/'data/directional-rpg-import.json').read_text(encoding='utf-8'))['models']
    for entry in inventory:
        path=ROOT/'ComfyUI'/entry['relative_path']
        with path.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=entry['sha256']:raise RuntimeError('LoRA integrity failed')
    ensure_idle()
    try:requests.post('http://127.0.0.1:8191/free',json={'unload_models':True,'free_memory':True},timeout=20).raise_for_status()
    except requests.ConnectionError:pass
    cases=[('anima-base-070','anima-turbo',512,1024,.7,4.,28),('anima-base-100','anima-turbo',512,1024,1.,4.,28),
           ('flanime-070','flanime-xl',768,1280,.7,5.,32),('flanime-100','flanime-xl',768,1280,1.,5.,32)]
    records=[]
    try:
        for name,model,width,height,strength,cfg,steps in cases:
            ensure_idle()
            anima=model=='anima-turbo'
            prompt=('rpgchara, transparent background, reference sheet, chibi, full body, A sprite sheet of full-body pixel art characters arranged in a 3x4 grid, featuring front, side, and back views, ' if anima else 'rpgchara, transparent background, multiple views, chibi, reference sheet, ')+SUBJECT
            p=image_engine.validate(dict(model=model,prompt=prompt,negativePrompt=NEGATIVE,preset='illustration',width=width,height=height,steps=steps,cfg=cfg,seed=20261018,background='keep'))
            graph=image_engine.build_workflow(p,p['seed'])
            if anima:
                graph['1']['inputs']['unet_name']='anima_baseV10.safetensors'
                graph['11']=dict(class_type='LoraLoaderModelOnly',inputs=dict(model=['1',0],lora_name=str(Path('requested/rpgchara-anima-base1-v1.safetensors')),strength_model=strength))
            else:
                graph['11']=dict(class_type='LoraLoader',inputs=dict(model=['1',0],clip=['1',1],lora_name=str(Path('requested/rpgchara_v1.safetensors')),strength_model=strength,strength_clip=strength))
                graph['4']['inputs']['clip']=['11',1];graph['5']['inputs']['clip']=['11',1]
            graph['7']['inputs']['model']=['11',0]
            graph['9']['inputs']['filename_prefix']='rpgchara_test/'+name
            signature=hashlib.sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest()
            meta=OUT/(name+'.json');target=OUT/(name+'.png')
            if target.exists() and meta.exists() and json.loads(meta.read_text(encoding='utf-8')).get('signature')==signature:
                record=json.loads(meta.read_text(encoding='utf-8'));print('Cached',name,flush=True)
            else:
                start=time.monotonic();r=requests.post(image_engine.COMFY_URL+'/prompt',json={'prompt':graph},timeout=60)
                if not r.ok:raise RuntimeError(r.text[:1600])
                pid=r.json()['prompt_id'];print('Generating',name,pid,flush=True)
                while time.monotonic()-start<1200:
                    history=requests.get(image_engine.COMFY_URL+'/history/'+pid,timeout=30).json().get(pid)
                    if history:break
                    time.sleep(1)
                else:raise TimeoutError(pid)
                (OUT/(name+'-history.json')).write_text(json.dumps(history,indent=2),encoding='utf-8')
                if history['status']['status_str']!='success':raise RuntimeError(str(history['status'])[:1600])
                r=requests.get(image_engine.COMFY_URL+'/view',params=history['outputs']['9']['images'][0],timeout=60);r.raise_for_status();target.write_bytes(r.content)
                record=dict(id=name,actualBase='Anima Base 1.0' if anima else 'Flanime v3 (Illustrious)',loraStrength=strength,seconds=round(time.monotonic()-start,2),settings=p,graph=graph,signature=signature)
                meta.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');print('Generated',name,record['seconds'],flush=True)
            records.append(record)
            (OUT/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
            cards=''.join(f'<article><h2>{x["id"]}</h2><a href="{x["id"]}.png"><img src="{x["id"]}.png"></a><p>{x["actualBase"]} / LoRA {x["loraStrength"]} / {x["seconds"]}초</p></article>' for x in records)
            (OUT/'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>RPG Character Sprite 시험</title><style>body{background:#20232a;color:#eee;font:16px sans-serif;margin:24px}main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}img{width:100%;max-height:850px;object-fit:contain;background:#ddd}article{background:#30343d;padding:16px}h2{font-size:18px}@media(max-width:650px){main{grid-template-columns:1fr}}</style><h1>RPG Character Sprite · 실제 생성 비교</h1><p>동일 캐릭터 설명·시드. 제작자 해상도/트리거 사용. Anima Base 1.0과 Flanime 기반 Illustrious LoRA 비교. 앞·옆·뒤 시트 생성 실험이며 8방향 보장 기능 아님. 배경 제거·얼굴 보정·확대 없음.</p><p>'+html.escape(SUBJECT)+'</p><main>'+cards+'</main>',encoding='utf-8')
        canvas=Image.new('RGB',(4*320,560),'#ddd');draw=ImageDraw.Draw(canvas)
        for i,record in enumerate(records):
            with Image.open(OUT/(record['id']+'.png')) as im:
                im.thumbnail((320,520));canvas.paste(im,(i*320+(320-im.width)//2,36))
            draw.text((i*320+8,10),record['id'],fill='black')
        canvas.save(OUT/'comparison.webp')
    finally:
        requests.post(image_engine.COMFY_URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30)


if __name__=='__main__':main()
