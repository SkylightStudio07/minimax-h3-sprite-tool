"""Existing illustration -> sprite-style img2img and pose-conditioned experiments."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

import requests
from PIL import Image,ImageOps,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_engine
from verify_rpg_sprite_styles import ensure_idle

SOURCE=ROOT/'outputs/rigging/5ed3fddd3383252008ecd0c8e7dce9df/source-original.png'
OUT=ROOT/'outputs/sprite-conversion-20261018'
URL=image_engine.COMFY_URL
PROMPT='1girl, solo, adult woman, dark purple bob hair, blunt bangs, black hood, long black coat with dark red lining, black turtleneck, black fitted pants, black boots, mechanical black glove, full body, standing, clean lineart, game battle sprite, simple grey background'


def upload(path,name):
    with path.open('rb') as stream:
        r=requests.post(URL+'/upload/image',files={'image':(name,stream,'image/png')},data={'overwrite':'true'},timeout=40)
    r.raise_for_status();return r.json()['name']


def pose_image():
    # OpenPose COCO-18 connections and colors; fixed test fixture, not a detector.
    points=[(575,245),(515,360),(480,385),(505,540),(650,555),(550,385),(610,460),(725,435),
            (480,790),(440,1070),(390,1400),(555,790),(625,1060),(705,1400),(583,229),(568,230),(560,242),(545,245)]
    links=[(1,2),(1,5),(2,3),(3,4),(5,6),(6,7),(1,8),(8,9),(9,10),(1,11),(11,12),(12,13),(1,0),(0,14),(14,16),(0,15),(15,17)]
    colors=[(255,0,0),(255,85,0),(255,170,0),(255,255,0),(170,255,0),(85,255,0),(0,255,0),(0,255,85),(0,255,170),
            (0,255,255),(0,170,255),(0,85,255),(0,0,255),(85,0,255),(170,0,255),(255,0,255),(255,0,170),(255,0,85)]
    image=Image.new('RGB',(1024,1536),'black');draw=ImageDraw.Draw(image)
    for i,(a,b) in enumerate(links):draw.line([points[a],points[b]],fill=colors[i],width=8)
    for i,(x,y) in enumerate(points):draw.ellipse((x-9,y-9,x+9,y+9),fill=colors[i])
    image.save(OUT/'battle-pose.png')


def main():
    sys.stdout.reconfigure(encoding='utf-8');OUT.mkdir(exist_ok=True);ensure_idle()
    try:requests.post('http://127.0.0.1:8191/free',json={'unload_models':True,'free_memory':True},timeout=20).raise_for_status()
    except requests.ConnectionError:pass
    shutil.copy2(SOURCE,OUT/'source-original.png')
    with Image.open(SOURCE) as im:
        im=im.convert('RGBA');box=im.getchannel('A').getbbox()
        if not box:raise RuntimeError('Empty source')
        crop=ImageOps.contain(im.crop(box),(960,1472),Image.Resampling.LANCZOS)
        prepared=Image.new('RGB',(1024,1536),(210,210,210));prepared.paste(crop,((1024-crop.width)//2,(1536-crop.height)//2),crop)
        prepared.save(OUT/'prepared-reference.png')
    pose_image();reference=upload(OUT/'prepared-reference.png','sprite-conversion-20261018-reference.png');pose=upload(OUT/'battle-pose.png','sprite-conversion-20261018-pose.png')
    cases=[('preserve-030',.30,.6,False),('style-050',.50,.6,False),('style-070',.70,.6,False),
           ('no-lora-050',.50,0,False),('battle-pose-065',.65,.6,True),('battle-pose-080',.80,.6,True)]
    records=[]
    for name,denoise,lora,controlled in cases:
        ensure_idle()
        p=image_engine.validate(dict(model='flanime-xl',prompt=PROMPT+(', side view, facing right, battle ready stance' if controlled else ', three-quarter view'),
            negativePrompt='worst quality, low quality, blurry, text, watermark, multiple views, reference sheet, duplicate character, cropped, out of frame',
            styleId='epic-seven-sprites',styleStrength=lora,width=1024,height=1536,steps=32,cfg=5,seed=20261018,denoise=denoise))
        # Prototype img2img branch; production Flanime remains text-only until review.
        p['mode']='reference';graph=image_engine.build_workflow(p,p['seed'],image_name=reference)
        if controlled:
            graph['50']=dict(class_type='ControlNetLoader',inputs=dict(control_net_name=str(Path('xinsir-openpose-sdxl/diffusion_pytorch_model.safetensors'))))
            graph['51']=dict(class_type='LoadImage',inputs=dict(image=pose))
            graph['52']=dict(class_type='ControlNetApplyAdvanced',inputs=dict(positive=['4',0],negative=['5',0],control_net=['50',0],image=['51',0],strength=.65,start_percent=0,end_percent=.85))
            graph['7']['inputs'].update(positive=['52',0],negative=['52',1])
        graph['9']['inputs']['filename_prefix']='sprite_conversion/'+name
        signature=hashlib.sha256(json.dumps(graph,sort_keys=True).encode()+SOURCE.read_bytes()).hexdigest()
        meta=OUT/(name+'.json');target=OUT/(name+'.png')
        if target.exists() and meta.exists() and json.loads(meta.read_text(encoding='utf-8')).get('signature')==signature:
            record=json.loads(meta.read_text(encoding='utf-8'));print('Cached',name,flush=True)
        else:
            start=time.monotonic();r=requests.post(URL+'/prompt',json={'prompt':graph},timeout=60)
            if not r.ok:raise RuntimeError(r.text[:1800])
            pid=r.json()['prompt_id'];print('Generating',name,flush=True)
            while time.monotonic()-start<1200:
                history=requests.get(URL+'/history/'+pid,timeout=30).json().get(pid)
                if history:break
                time.sleep(1)
            else:raise TimeoutError(pid)
            (OUT/(name+'-history.json')).write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
            if history['status']['status_str']!='success':raise RuntimeError(str(history['status'])[:1800])
            images=history['outputs'].get('9',{}).get('images',[])
            if not images:raise RuntimeError('Missing conversion output')
            r=requests.get(URL+'/view',params=images[0],timeout=60);r.raise_for_status();target.write_bytes(r.content)
            record=dict(id=name,denoise=denoise,loraStrength=lora,poseControl=controlled,seconds=round(time.monotonic()-start,2),settings=p,graph=graph,signature=signature)
            meta.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');print('Generated',name,record['seconds'],flush=True)
        records.append(record);(OUT/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
        cards='<article><h2>입력 원화</h2><img src="prepared-reference.png"></article>'
        cards+=''.join(f'<article><h2>{r["id"]}</h2><a href="{r["id"]}.png"><img src="{r["id"]}.png"></a><p>변형 {r["denoise"]} / LoRA {r["loraStrength"]} / 포즈 {r["poseControl"]}</p></article>' for r in records)
        (OUT/'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>원화 → 전투 스프라이트 실험</title><style>body{background:#20232a;color:#eee;font:16px sans-serif}main{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}img{width:100%}h2{font-size:16px}</style><h1>원화 업로드 → 스프라이트 화풍 / 전투 포즈</h1><p>Flanime + Epic Seven LoRA. 생성 전 몸 이미지 새로 만들지 않고 입력 PNG를 VAE latent로 사용. 포즈 변경의 외형 보존은 별도 검토.</p><main>'+cards+'</main>',encoding='utf-8')
    requests.post(URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30).raise_for_status()


if __name__=='__main__':main()
