"""Face-only refinement of approved native PNGs; never regenerate their bodies."""
import json
from pathlib import Path
import sys
import time
import requests
from PIL import Image,ImageDraw,ImageChops

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_engine
import image_face_detail
from verify_rpg_sprite_styles import ensure_idle

URL='http://127.0.0.1:8191'
SOURCE=ROOT/'outputs/rpg-native-1536-20261017'
OUT=ROOT/'outputs/rpg-native-face-20261017'


def main():
    sys.stdout.reconfigure(encoding='utf-8');OUT.mkdir(exist_ok=True);ensure_idle()
    requests.post(image_engine.COMFY_URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30).raise_for_status()
    settings=json.loads((SOURCE/'results.json').read_text(encoding='utf-8'));records=[]
    for subject in ('rapi','enterprise'):
        p=next(r['settings'] for r in settings if r['subject']==subject)
        with (SOURCE/(subject+'-raw.png')).open('rb') as stream:
            r=requests.post(URL+'/upload/image',files={'image':('native-face-'+subject+'.png',stream,'image/png')},data={'overwrite':'true'},timeout=30)
        r.raise_for_status();uploaded=r.json()['name']
        for strength in (.15,.22):
            ensure_idle()
            graph=image_engine.build_workflow(p,p['seed'])
            for key in ('4','5','6','7','8','9','11'):graph.pop(key,None)
            graph['30']=dict(class_type='LoadImage',inputs=dict(image=uploaded))
            final=image_face_detail.add_native(graph,p,p['seed'],['30',0],['1',0],['1',1],['3',0],denoise=strength)
            name=subject+'-'+str(strength)
            graph['9']=dict(class_type='SaveImage',inputs=dict(images=final,filename_prefix='native_face/'+name))
            start=time.monotonic();r=requests.post(URL+'/prompt',json={'prompt':graph},timeout=60)
            if not r.ok:raise RuntimeError(r.text[:1500])
            pid=r.json()['prompt_id'];print('Refining',name,flush=True)
            while time.monotonic()-start<600:
                history=requests.get(URL+'/history/'+pid,timeout=20).json().get(pid)
                if history:break
                time.sleep(1)
            else:raise TimeoutError(pid)
            (OUT/(name+'-history.json')).write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
            if history['status']['status_str']!='success':raise RuntimeError(str(history['status'])[:1500])
            for key,suffix in [('9','after'),('26','mask')]:
                images=history['outputs'].get(key,{}).get('images',[])
                if not images:raise RuntimeError('Missing refinement output')
                r=requests.get(URL+'/view',params=images[0],timeout=40);r.raise_for_status();(OUT/(name+'-'+suffix+'.png')).write_bytes(r.content)
            with Image.open(SOURCE/(subject+'-raw.png')) as before,Image.open(OUT/(name+'-after.png')) as after,Image.open(OUT/(name+'-mask.png')) as mask:
                assert before.size==after.size==(1024,1536)
                box=mask.convert('L').getbbox()
                if not box:raise RuntimeError('Face detection empty')
                audit_box=(max(0,box[0]-24),max(0,box[1]-24),min(1024,box[2]+24),min(1536,box[3]+24))
                changed=ImageChops.difference(before.convert('RGB'),after.convert('RGB')).getbbox()
                assert changed and audit_box[0]<=changed[0] and audit_box[1]<=changed[1] and audit_box[2]>=changed[2] and audit_box[3]>=changed[3]
                grid=Image.new('RGB',(768,430),'#eeeeee');draw=ImageDraw.Draw(grid)
                for i,im in enumerate((before,after)):
                    crop=im.crop(audit_box);ratio=min(384/crop.width,384/crop.height);crop=crop.resize((round(crop.width*ratio),round(crop.height*ratio)),Image.Resampling.NEAREST)
                    grid.paste(crop,(i*384+(384-crop.width)//2,30));draw.text((i*384+8,8),['Original',str(strength)+' / no sprite LoRA'][i],fill='black')
                grid.save(OUT/(name+'-comparison.jpg'),quality=95)
            records.append(dict(id=name,subject=subject,denoise=strength,seconds=round(time.monotonic()-start,2),graph=graph,changedBox=changed,faceBox=box))
            (OUT/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8');print('Passed',name,flush=True)
    cards=''.join(f'<article><h2>{r["id"]}</h2><img src="{r["id"]}-comparison.jpg"><a href="{r["id"]}-after.png">1024×1536 PNG</a></article>' for r in records)
    (OUT/'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>Native face refinement</title><style>body{background:#20232a;color:#eee;font:16px sans-serif}main{display:grid;grid-template-columns:1fr 1fr;gap:18px}img{width:100%}a{color:skyblue}</style><h1>원본 유지 · 얼굴만 약하게 보정</h1><p>왼쪽 원본 / 오른쪽 보정. 스프라이트 LoRA는 얼굴 패스에서 제외. 출력 1024×1536 유지.</p><main>'+cards+'</main>',encoding='utf-8')
    requests.post(URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30).raise_for_status()


if __name__=='__main__':main()
