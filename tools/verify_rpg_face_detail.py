"""Compare FaceDetailer strengths on exactly the same saved sprite images."""
import html
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

import requests
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_engine
import image_face_detail
from verify_rpg_sprite_styles import ensure_idle

URL='http://127.0.0.1:8191'
OUT=ROOT/'outputs/rpg-face-detail-20261017'
SOURCE=ROOT/'outputs/rpg-sprite-styles-20261017'


def main():
    sys.stdout.reconfigure(encoding='utf-8');OUT.mkdir(exist_ok=True)
    ensure_idle()
    requests.post(image_engine.COMFY_URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30).raise_for_status()
    records=[]
    for subject in ('rapi','enterprise'):
        name='epic-seven-sprites-'+subject+'-0.6'
        p=json.loads((SOURCE/(name+'.json')).read_text(encoding='utf-8'))['settings']
        with (SOURCE/(name+'.png')).open('rb') as stream:
            r=requests.post(URL+'/upload/image',files={'image':(name+'.png',stream,'image/png')},timeout=30)
        r.raise_for_status();uploaded=r.json()['name']
        for strength in (.25,.4):
            ensure_idle()
            graph=image_engine.build_workflow(p,p['seed'])
            for key in ('4','5','6','7','8','9','11'):graph.pop(key,None)
            graph['30']=dict(class_type='LoadImage',inputs=dict(image=uploaded))
            result=image_face_detail.add(graph,p,p['seed'],['30',0],['1',0],['1',1],['3',0],denoise=strength)
            run_name=subject+'-'+str(strength)
            graph['9']=dict(class_type='SaveImage',inputs=dict(images=result,filename_prefix='rpg_face_detail/'+run_name))
            start=time.monotonic();r=requests.post(URL+'/prompt',json={'prompt':graph},timeout=60)
            if not r.ok:raise RuntimeError(r.text[:1800])
            pid=r.json()['prompt_id'];print('Generating',run_name,flush=True)
            while time.monotonic()-start<600:
                history=requests.get(URL+'/history/'+pid,timeout=20).json().get(pid)
                if history:break
                time.sleep(1)
            else:raise TimeoutError(pid)
            (OUT/(run_name+'-history.json')).write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
            if history['status']['status_str']!='success':raise RuntimeError(str(history['status'])[:2000])
            for key,suffix in [('9','after'),('24','before'),('26','mask')]:
                r=requests.get(URL+'/view',params=history['outputs'][key]['images'][0],timeout=30);r.raise_for_status()
                (OUT/(run_name+'-'+suffix+'.png')).write_bytes(r.content)
            with Image.open(OUT/(run_name+'-mask.png')) as im:
                box=im.convert('L').getbbox();w,h=im.size
            if not box:raise RuntimeError('Face detection empty: '+run_name)
            box=(max(0,box[0]-32),max(0,box[1]-32),min(w,box[2]+32),min(h,box[3]+32))
            comparison=Image.new('RGB',(768,420),'#eeeeee');draw=ImageDraw.Draw(comparison)
            for i,suffix in enumerate(('before','after')):
                with Image.open(OUT/(run_name+'-'+suffix+'.png')) as im:
                    crop=im.crop(box);scale=min(384/crop.width,384/crop.height);crop=crop.resize((round(crop.width*scale),round(crop.height*scale)),Image.Resampling.NEAREST);comparison.paste(crop,((384-crop.width)//2+i*384,30))
                draw.text((i*384+8,8),suffix+' / '+run_name,fill='black')
            comparison.save(OUT/(run_name+'-comparison.jpg'),quality=95)
            records.append(dict(id=run_name,subject=subject,denoise=strength,maskBox=box,seconds=round(time.monotonic()-start,2),settings=p,graph=graph))
            print('Passed',run_name,'face',box,flush=True)
            (OUT/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    cards=''.join(f'<article><h2>{html.escape(r["id"])}</h2><img src="{r["id"]}-comparison.jpg"><a href="{r["id"]}-after.png">Full image</a></article>' for r in records)
    (OUT/'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>FaceDetailer comparison</title><style>body{background:#20232a;color:#eee;font:16px sans-serif}main{display:grid;grid-template-columns:repeat(2,1fr);gap:20px}img{width:100%}a{color:skyblue}</style><h1>FaceDetailer: before / after</h1><p>Same original image; sprite LoRA reduced to 0.25 during face refinement.</p><main>'+cards+'</main>',encoding='utf-8')
    requests.post(URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30).raise_for_status()


def full_smoke():
    sys.stdout.reconfigure(encoding='utf-8');ensure_idle()
    settings=json.loads((SOURCE/'epic-seven-sprites-rapi-0.6.json').read_text(encoding='utf-8'))['settings']
    settings=image_engine.validate(settings|dict(faceDetail=True,background='keep',count=1,
        prompt=settings['prompt']+', character fills most of the canvas, minimal empty margins, feet visible'))
    updates=[]
    with patch.object(image_engine,'RESULT_ROOT',OUT/'full-generation'),patch.object(image_engine,'update_job',side_effect=lambda jid,**v:updates.append(v)):
        image_engine.run_job('smoke',settings)
    result=updates[-1];assert result['state']=='complete';item=result['images'][0]
    assert item['faceDetailApplied'] and item['beforeFaceUrl']
    with Image.open(OUT/'full-generation/smoke/image-1.png') as im:assert im.size==(1792,2304)
    (OUT/'full-smoke.json').write_text(json.dumps(dict(settings=settings,result=result),ensure_ascii=False,indent=2),encoding='utf-8')
    print('Passed full generation + face detail + before image + metadata',flush=True)
    requests.post(URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30).raise_for_status()


if __name__=='__main__':
    if '--full-smoke' in sys.argv:full_smoke()
    else:main()
