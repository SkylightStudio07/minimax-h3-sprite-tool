"""Native 1024x1536 generation, without whole-image resampling/diffusion."""
import json
from pathlib import Path
import sys
import time
import requests
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_engine
import image_face_detail
from verify_rpg_sprite_styles import ensure_idle,CASES

URL='http://127.0.0.1:8191'
OUT=ROOT/'outputs/rpg-native-1536-20261017'


def main():
    sys.stdout.reconfigure(encoding='utf-8');OUT.mkdir(exist_ok=True);ensure_idle()
    requests.post(image_engine.COMFY_URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30).raise_for_status()
    records=[]
    for subject in ('rapi','enterprise'):
        ensure_idle()
        p=image_engine.validate(dict(model='flanime-xl',prompt=CASES[subject],
            negativePrompt='worst quality, low quality, blurry, text, watermark, multiple views, cropped, out of frame',
            styleId='epic-seven-sprites',styleStrength=.6,width=1024,height=1536,steps=40,cfg=5,seed=20261017,
            hiresFix=False,faceDetail=False))
        graph=image_engine.build_workflow(p,p['seed'])
        graph['9']['inputs']['filename_prefix']='rpg_native/'+subject+'-raw'
        # One shared base sample: face refinement has exactly the same native size.
        result=image_face_detail.add(graph,p,p['seed'],['8',0],['1',0],['1',1],['3',0],denoise=.25,upscale=False)
        graph['29']=dict(class_type='SaveImage',inputs=dict(images=result,filename_prefix='rpg_native/'+subject+'-face'))
        start=time.monotonic();r=requests.post(URL+'/prompt',json={'prompt':graph},timeout=60)
        if not r.ok:raise RuntimeError(r.text[:1200])
        pid=r.json()['prompt_id'];print('Generating native',subject,flush=True)
        while time.monotonic()-start<1200:
            history=requests.get(URL+'/history/'+pid,timeout=20).json().get(pid)
            if history:break
            time.sleep(1)
        else:raise TimeoutError(pid)
        (OUT/(subject+'-history.json')).write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
        if history['status']['status_str']!='success':raise RuntimeError(str(history['status'])[:1800])
        for key,suffix in [('9','raw'),('29','face'),('26','mask')]:
            images=history['outputs'].get(key,{}).get('images',[])
            if not images:raise RuntimeError('Missing native output '+key)
            r=requests.get(URL+'/view',params=images[0],timeout=60);r.raise_for_status()
            path=OUT/(subject+'-'+suffix+'.png');path.write_bytes(r.content)
            with Image.open(path) as im:assert im.size==(1024,1536)
        record=dict(subject=subject,settings=p,graph=graph,seconds=round(time.monotonic()-start,2))
        records.append(record);(OUT/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Passed',subject,record['seconds'],'seconds',flush=True)
    cards=''.join(f'<article><h2>{subject} · {suffix}</h2><a href="{subject}-{suffix}.png"><img src="{subject}-{suffix}.png"></a></article>' for subject in ('rapi','enterprise') for suffix in ('raw','face'))
    (OUT/'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>Native 1024x1536 RPG</title><style>body{background:#20232a;color:#eee;font:16px sans-serif}main{display:grid;grid-template-columns:1fr 1fr;gap:20px}img{width:100%}</style><h1>Flanime 원본 1024×1536 생성 · 40 steps</h1><p>왼쪽: 원본 / 오른쪽: 얼굴 보정 실험본 0.25 (얼룩·인상 변경이 있어 추천하지 않음). 확대·전신 재생성 없음.</p><main>'+cards+'</main>',encoding='utf-8')
    requests.post(URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30).raise_for_status()


if __name__=='__main__':main()
