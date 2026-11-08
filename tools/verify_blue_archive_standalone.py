"""Author-prompt style check with no CounterSide, sprite tags or source latent."""
import hashlib
import html
import json
from pathlib import Path
import sys
import time

import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from verify_rpg_sprite_styles import ensure_idle
import image_engine

OUT=ROOT/'outputs/blue-archive-standalone-20261018'
PROMPTS={
 'arona':'masterpiece, best quality, 1girl, solo, arona (blue archive), blue archive, halo, smile, school uniform, classroom, window, sunlight, blue sky, looking at viewer, upper body',
 'original':'masterpiece, best quality, 1girl, solo, adult woman, dark purple bob hair, blunt bangs, blue eyes, black coat with dark red lining, black turtleneck, smile, upper body, looking at viewer, classroom, window, sunlight, blue sky',
}
NEGATIVE='lowres, worst quality, bad quality, bad anatomy, bad hands, extra fingers, blurry, jpeg artifacts, watermark, signature, text'


def main():
    sys.stdout.reconfigure(encoding='utf-8');OUT.mkdir(exist_ok=True);ensure_idle()
    entries={}
    for name,manifest in [('base','wai-illustrious'),('kivotos','blue-archive-illustrious'),('cutscene','blue-archive-cutscene')]:
        e=json.loads((ROOT/f'data/{manifest}-import.json').read_text())['models'][0]
        p=ROOT/'ComfyUI'/e['relative_path']
        with p.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=e['sha256']:raise RuntimeError('Hash mismatch '+name)
        entries[name]=e
    try:requests.post('http://127.0.0.1:8191/free',json={'unload_models':True,'free_memory':True},timeout=20).raise_for_status()
    except requests.ConnectionError:pass
    log=ROOT/'logs/comfy.stderr.log';offset=log.stat().st_size if log.exists() else 0
    records=[]
    try:
        for subject in PROMPTS:
            for style in ['none','kivotos','cutscene']:
                ensure_idle();name=subject+'-'+style
                graph={'1':dict(class_type='CheckpointLoaderSimple',inputs=dict(ckpt_name=Path(entries['base']['relative_path']).name)),
                       '2':dict(class_type='CLIPSetLastLayer',inputs=dict(clip=['1',1],stop_at_clip_layer=-2)),
                       '6':dict(class_type='EmptyLatentImage',inputs=dict(width=832,height=1216,batch_size=1))}
                model,clip=['1',0],['2',0];prompt=PROMPTS[subject]
                if style!='none':
                    graph['3']=dict(class_type='LoraLoader',inputs=dict(model=model,clip=clip,lora_name=str(Path(entries[style]['relative_path'].removeprefix('models/loras/'))),strength_model=1.,strength_clip=1.))
                    model,clip=['3',0],['3',1]
                    prompt=('bastory, ' if style=='kivotos' else '(official art:1.1), (game cg:1.1), blue archive, ')+prompt
                graph['4']=dict(class_type='CLIPTextEncode',inputs=dict(clip=clip,text=prompt))
                graph['5']=dict(class_type='CLIPTextEncode',inputs=dict(clip=clip,text=NEGATIVE))
                graph['7']=dict(class_type='KSampler',inputs=dict(model=model,positive=['4',0],negative=['5',0],latent_image=['6',0],seed=20261018,steps=28,cfg=4.5,sampler_name='euler_ancestral',scheduler='normal',denoise=1.))
                graph['8']=dict(class_type='VAEDecode',inputs=dict(samples=['7',0],vae=['1',2]))
                graph['9']=dict(class_type='SaveImage',inputs=dict(images=['8',0],filename_prefix='blue_standalone/'+name))
                signature=hashlib.sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest();meta=OUT/(name+'.json');target=OUT/(name+'.png')
                if target.exists() and meta.exists() and json.loads(meta.read_text())['signature']==signature:
                    record=json.loads(meta.read_text());print('Cached',name,flush=True)
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
                    record=dict(id=name,subject=subject,style=style,seconds=round(time.monotonic()-start,2),signature=signature,graph=graph,baseSha256=entries['base']['sha256'],styleSha256=entries[style]['sha256'] if style!='none' else None)
                    meta.write_text(json.dumps(record,indent=2),encoding='utf-8');print('Generated',name,record['seconds'],flush=True)
                records.append(record);(OUT/'results.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
                cards=''.join(f'<article><h2>{x["id"]}</h2><a href="{x["id"]}.png"><img src="{x["id"]}.png"></a><p>{x["seconds"]}초</p></article>' for x in records)
                (OUT/'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>블아 LoRA 단독 검증</title><style>body{background:#20232a;color:#eee;font:16px sans-serif;margin:24px}main{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}img{width:100%}h2{font-size:17px}article{background:#30343d;padding:12px}@media(max-width:700px){main{grid-template-columns:1fr}}</style><h1>블아 LoRA 단독 · 제작자 설정 근접 비교</h1><p>WAI17 내장 VAE / 832×1216 / Euler a / 28steps / CFG4.5 / CLIPskip2 / seed20261018. 카사·스프라이트·full body·clean lineart 지시 없음. 첫 행 제작자 Arona 예시 프롬프트에 upper body/solo 추가. 둘째 행 자체 캐릭터. 좌: LoRA없음 / 중: Kivotos1.0 / 우: Cutscene1.0. 공개 예시는 이미지별 seed/전체 메타가 없어 픽셀 단위 재현이 아닌 설정 근접 시험입니다.</p><main>'+cards+'</main>',encoding='utf-8')
    finally:
        requests.post(image_engine.COMFY_URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30)
        if log.exists():
            with log.open('rb') as f:f.seek(offset);(OUT/'comfy-stderr-segment.log').write_bytes(f.read())


if __name__=='__main__':main()
