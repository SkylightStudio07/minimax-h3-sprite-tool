"""Actual uploaded-illustration conditioning for the reviewed mixed recipe."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

import requests
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_engine
import image_pose
from verify_rpg_sprite_styles import ensure_idle
import verify_cutscene_cleanup as runner

OUT=ROOT/'outputs/cutscene-reference-right-20261018'
SOURCE=ROOT/'outputs/rigging/5ed3fddd3383252008ecd0c8e7dce9df/source-original.png'


def main():
    OUT.mkdir(exist_ok=True);sys.stdout.reconfigure(encoding='utf-8');ensure_idle();runner.OUT=OUT
    original_hash=hashlib.sha256(SOURCE.read_bytes()).hexdigest();shutil.copy2(SOURCE,OUT/'source-original.png')
    with Image.open(SOURCE) as im:prepared=image_pose.prepare_reference(im,(832,1216));prepared.save(OUT/'prepared-reference.png')
    try:requests.post(image_engine.image_soya.URL+'/free',json={'unload_models':True,'free_memory':True},timeout=20).raise_for_status()
    except requests.ConnectionError:pass
    with (OUT/'prepared-reference.png').open('rb') as stream:
        r=requests.post(image_engine.COMFY_URL+'/upload/image',files={'image':('cutscene-actual-reference.png',stream,'image/png')},data={'overwrite':'true'},timeout=40)
    r.raise_for_status();uploaded=r.json()['name']
    source=json.loads((ROOT/'outputs/cutscene-cleanup-20261018/no-series-negative-halo.json').read_text())['graph']
    source['4']['inputs']['text']='(official art:1.1), (game cg:1.1), masterpiece, best quality, 1girl, solo, adult woman, dark purple bob hair, blunt bangs, blue eyes, black hood, long black coat with dark red lining, black turtleneck, black fitted pants, black boots, mechanical black glove, full body, (side view:1.2), (facing right:1.35), looking to the right, body turned right, battle ready stance, feet visible, simple white background'
    source['5']['inputs']['text']+=', facing viewer, looking at viewer, front view, facing left'
    source['10']=dict(class_type='LoadImage',inputs=dict(image=uploaded))
    source['6']=dict(class_type='VAEEncode',inputs=dict(pixels=['10',0],vae=['1',2]))
    records=[]
    try:
        for denoise in [.5,.65]:
            ensure_idle();graph=copy.deepcopy(source);name='reference-'+str(round(denoise*100))
            graph['7']['inputs']['denoise']=denoise;graph['9']['inputs']['filename_prefix']='cutscene_reference/'+name
            record=runner.execute(image_engine.COMFY_URL,graph,name)
            record.update(denoise=denoise,sourceSha256=original_hash,referenceInput=True,width=832,height=1216,cutsceneStrength=1.,counterStrength=.4)
            (OUT/(name+'.json')).write_text(json.dumps(record,indent=2),encoding='utf-8');records.append(record)
            (OUT/'results.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
            cards='<article><h2>입력 원화 · 비율 유지 준비본</h2><img src="prepared-reference.png"></article>'
            cards+=''.join(f'<article><h2>변형 {r["denoise"]}</h2><a href="{r["id"]}.png"><img src="{r["id"]}.png"></a><p>{r["seconds"]}초</p></article>' for r in records)
            (OUT/'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>원화 입력 · 셀 채색 전투 변환</title><style>body{background:#20232a;color:#eee;font:16px sans-serif;margin:24px}main{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}img{width:100%}h2{font-size:17px}@media(max-width:700px){main{grid-template-columns:repeat(2,1fr)}}</style><h1>실제 원화 입력 → 우측 전투 방향 유도</h1><p>같은 원화를 VAEEncode로 직접 입력. 텍스트로 외형만 설명하는 신규 생성과 다릅니다.832×1216 / WAI17 / Cutscene1.0 + 전투형식0.4 / 28steps / CFG4.5 / seed20261018. 헤일로 억제. 얼굴 보정·배경 제거·관절 제어는 미적용. 우측 방향/몸 회전/전투 대기 자세를 프롬프트로 유도하며 정면·좌측 시점은 네거티브로 억제합니다. 원본은 보존하고 투명 여백 crop/비율 유지 준비만 했습니다.</p><main>'+cards+'</main>',encoding='utf-8')
        canvas=Image.new('RGB',(3*300,475),'#ddd');draw=ImageDraw.Draw(canvas)
        for i,(filename,label) in enumerate([('prepared-reference.png','Reference')]+[(r['id']+'.png','Denoise '+str(r['denoise'])) for r in records]):
            with Image.open(OUT/filename) as im:canvas.paste(im.convert('RGB').resize((300,438),Image.Resampling.LANCZOS),(i*300,36))
            draw.text((i*300+8,10),label,fill='black')
        canvas.save(OUT/'comparison.webp')
        assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==original_hash
    finally:requests.post(image_engine.COMFY_URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30)


if __name__=='__main__':main()
