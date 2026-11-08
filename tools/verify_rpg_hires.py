"""Same-source comparison of face-only versus whole-image Hires fix + face."""
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
import image_hires
import image_face_detail
from verify_rpg_sprite_styles import ensure_idle

URL='http://127.0.0.1:8191'
OUT=ROOT/'outputs/rpg-hires-20261017'


def main():
    sys.stdout.reconfigure(encoding='utf-8');OUT.mkdir(exist_ok=True)
    ensure_idle()
    requests.post(image_engine.COMFY_URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30).raise_for_status()
    records=[]
    for subject in ('rapi','enterprise'):
        source=ROOT/f'outputs/rpg-sprite-styles-20261017/epic-seven-sprites-{subject}-0.6'
        p=json.loads(Path(str(source)+'.json').read_text(encoding='utf-8'))['settings']
        with Path(str(source)+'.png').open('rb') as stream:
            r=requests.post(URL+'/upload/image',files={'image':(subject+'-hires-source.png',stream,'image/png')},data={'overwrite':'true'},timeout=30)
        r.raise_for_status();uploaded=r.json()['name']
        for strength in (None,.18,.28):
            ensure_idle()
            graph=image_engine.build_workflow(p,p['seed'])
            for key in ('6','7','8','9'):graph.pop(key,None)
            graph['30']=dict(class_type='LoadImage',inputs=dict(image=uploaded))
            result=['30',0]
            if strength is not None:result=image_hires.add(graph,p,p['seed'],result,['11',0],['11',1],['3',0],['4',0],['5',0],denoise=strength)
            result=image_face_detail.add(graph,p,p['seed'],result,['1',0],['1',1],['3',0],upscale=strength is None)
            run_name=subject+'-'+('face-only' if strength is None else str(strength))
            graph['9']=dict(class_type='SaveImage',inputs=dict(images=result,filename_prefix='rpg_hires/'+run_name))
            signature=__import__('hashlib').sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest()
            meta=OUT/(run_name+'.json')
            if meta.exists() and json.loads(meta.read_text(encoding='utf-8')).get('signature')==signature:
                record=json.loads(meta.read_text(encoding='utf-8'));print('Cached',run_name,flush=True)
            else:
                start=time.monotonic();r=requests.post(URL+'/prompt',json={'prompt':graph},timeout=60)
                if not r.ok:raise RuntimeError(r.text[:1800])
                pid=r.json()['prompt_id'];print('Generating',run_name,flush=True)
                while time.monotonic()-start<1200:
                    history=requests.get(URL+'/history/'+pid,timeout=20).json().get(pid)
                    if history:break
                    time.sleep(1)
                else:raise TimeoutError(pid)
                (OUT/(run_name+'-history.json')).write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
                if history['status']['status_str']!='success':raise RuntimeError(str(history['status'])[:2000])
                for key,suffix in [('9','after'),('24','before-face')]+([('46','upscale-only')] if strength is not None else []):
                    images=history['outputs'].get(key,{}).get('images',[])
                    if not images:raise RuntimeError(f'Missing output {key}')
                    r=requests.get(URL+'/view',params=images[0],timeout=60);r.raise_for_status()
                    (OUT/(run_name+'-'+suffix+'.png')).write_bytes(r.content)
                record=dict(id=run_name,subject=subject,denoise=strength,seconds=round(time.monotonic()-start,2),settings=p,graph=graph,signature=signature)
                meta.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
                print('Passed',run_name,record['seconds'],flush=True)
            records.append(record)
            (OUT/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    for subject in ('rapi','enterprise'):
        paths=[OUT/f'{subject}-face-only-after.png',OUT/f'{subject}-0.18-after.png',OUT/f'{subject}-0.28-after.png']
        grid=Image.new('RGB',(1152,1550),'#eeeeee');draw=ImageDraw.Draw(grid)
        for i,path in enumerate(paths):
            with Image.open(path) as im:
                assert im.size==(1792,2304)
                small=im.copy();small.thumbnail((384,550));grid.paste(small,(i*384,32))
                # Identical absolute crops show face and weapon/clothing at equal scale.
                for row,box in enumerate([(880,450,1220,800),(350,850,1150,1300)]):
                    crop=im.crop(box);scale=min(384/crop.width,450/crop.height);crop=crop.resize((round(crop.width*scale),round(crop.height*scale)),Image.Resampling.LANCZOS)
                    grid.paste(crop,(i*384,610+row*460))
            draw.text((i*384+6,8),['Face only','Hires 0.18 + face','Hires 0.28 + face'][i],fill='black')
        grid.save(OUT/(subject+'-comparison.jpg'),quality=95)
    cards=''.join(f'<article><h2>{s}</h2><a href="{s}-comparison.jpg"><img src="{s}-comparison.jpg"></a></article>' for s in ('rapi','enterprise'))
    (OUT/'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>RPG Hires comparison</title><style>body{background:#20232a;color:#eee;font:16px sans-serif}main{display:grid;grid-template-columns:1fr 1fr;gap:20px}img{width:100%}</style><h1>Face only / Hires 0.18 / Hires 0.28</h1><p>Same source and seed. Face denoise is 0.35 for all three variants. Body and clothes are also regenerated.</p><main>'+cards+'</main>',encoding='utf-8')
    requests.post(URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30).raise_for_status()


def full_smoke():
    sys.stdout.reconfigure(encoding='utf-8');ensure_idle()
    p=json.loads((ROOT/'outputs/rpg-sprite-styles-20261017/epic-seven-sprites-rapi-0.6.json').read_text(encoding='utf-8'))['settings']
    p=image_engine.validate(p|dict(hiresFix=True,faceDetail=True,background='keep',count=1))
    updates=[];started=time.monotonic()
    with patch.object(image_engine,'RESULT_ROOT',OUT/'full-generation'),patch.object(image_engine,'update_job',side_effect=lambda jid,**v:updates.append(v)):
        image_engine.run_job('smoke',p)
    final=updates[-1];assert final['state']=='complete';item=final['images'][0]
    assert item['beforeHiresUrl'] and item['beforeFaceUrl'] and item['faceDetailApplied']
    folder=OUT/'full-generation/smoke'
    for name in ('image-1.png','image-1-before-hires.png','image-1-before-face.png'):
        with Image.open(folder/name) as im:
            assert im.size==(1792,2304)
            metadata=json.loads(im.info['sprite_lab']);assert metadata['hiresFix'] and metadata['faceDetail'] and metadata['hiresDenoise']==.2
    (OUT/'full-smoke.json').write_text(json.dumps(dict(settings=p,result=final,seconds=round(time.monotonic()-started,2)),ensure_ascii=False,indent=2),encoding='utf-8')
    print('Passed whole-generation Hires + FaceDetailer + comparison outputs + PNG metadata',round(time.monotonic()-started,2),'seconds',flush=True)
    requests.post(URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30).raise_for_status()


if __name__=='__main__':
    if '--full-smoke' in sys.argv:full_smoke()
    else:main()
