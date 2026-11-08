"""Real GPU acceptance for the site's exact pixel recipe, isolated from the team gallery."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

import numpy as np
import requests
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_engine
import image_pixel
from tools.verify_rpg_sprite_styles import ensure_idle


def metrics(path,size,colors):
    with Image.open(path) as im:
        im=im.convert('RGBA');a=np.asarray(im);visible=a[:,:,3]>0
        assert im.size==(size,size),im.size
        assert visible.any(),'Background removal erased the subject'
        assert set(np.unique(a[:,:,3]))<={0,255},'Soft alpha on final pixel grid'
        count=len(np.unique(a[:,:,:3][visible],axis=0))
        assert not colors or count<=colors,(count,colors)
        return dict(width=im.width,height=im.height,visibleColors=count,alphaValues=[int(x) for x in np.unique(a[:,:,3])],opaquePixels=int(visible.sum()),transparentFraction=round(float((~visible).mean()),4),bounds=im.getbbox())


def preview(out,records):
    cards=[]
    comparison=Image.new('RGB',(len(records)*420,510),'#20202a');draw=ImageDraw.Draw(comparison)
    for i,r in enumerate(records):
        folder=r['id'];size=r['settings']['pixelSize']
        draw.text((i*420+16,12),r['id']+f' / {size}px / '+str(r['metrics']['visibleColors'])+' colors',fill='white')
        for y in range(0,440,16):
            for x in range(0,400,16):draw.rectangle((i*420+10+x,42+y,i*420+25+x,57+y),fill='#dadbe3' if (x//16+y//16)%2 else '#f2f3f8')
        with Image.open(out/folder/'image-1.png') as im:
            enlarged=im.convert('RGBA').resize((size*3,size*3),Image.Resampling.NEAREST)
            comparison.paste(enlarged,(i*420+10+(400-enlarged.width)//2,42+(440-enlarged.height)//2),enlarged)
        cards.append(f'''<article><h2>{html.escape(r['label'])}</h2><p>{size}×{size} · {r['metrics']['visibleColors']}색 · {r['seconds']}초</p><div class="checker"><img class="pixel" src="{folder}/image-1.png" alt="{html.escape(r['label'])}"></div><p><a href="{folder}/image-1.png" download>실제 도트 PNG</a> · <a href="{folder}/image-1-pixel-preview.png">8배 미리보기</a> · <a href="{folder}/image-1-original.png">생성 원본</a></p><details><summary>설명과 검증값</summary><p>{html.escape(r['settings']['prompt'])}</p><pre>{html.escape(json.dumps(r['metrics'],ensure_ascii=False,indent=2))}</pre></details></article>''')
    comparison.save(out/'comparison.png')
    variants=''
    potion=out/'potion-64/image-1-before-pixel.png'
    if potion.is_file():
        with Image.open(potion) as source:
            for size,colors in [(64,16),(64,32),(128,64)]:
                name=f'potion-64/compare-{size}-{colors}.png';image_pixel.finish(source,size,colors).save(out/name)
                variants+=f'<article><h2>{size}px · {colors}색</h2><div class="checker"><img class="pixel" src="{name}"></div><p><a href="{name}" download>PNG 저장</a></p></article>'
    ref='<p><a href="reference-source.png">변형에 사용한 원화 보기</a></p>' if (out/'reference-source.png').is_file() else ''
    (out/'preview.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>로컬 픽셀 아트 실제 생성</title><style>body{background:#17171f;color:#eee;font:14px/1.6 system-ui;margin:24px}h1{font-size:24px}h2{font-size:17px}main{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}article{min-width:0;background:#24242e;border:1px solid #454552;padding:16px;border-radius:12px}a{color:#bdb5ff}.checker{height:420px;display:grid;place-items:center;background:repeating-conic-gradient(#ddd 0 25%,#f5f5f5 0 50%) 0/24px 24px;border-radius:8px}.pixel{image-rendering:pixelated;width:384px;max-width:100%;object-fit:contain}pre{white-space:pre-wrap}@media(max-width:850px){main{grid-template-columns:1fr}}</style><h1>픽셀 아트 · 실제 ComfyUI 생성 시험</h1><p>SDXL Base + Pixel Art XL 고정 조합. 생성 → 배경 제거 → 최근접 축소 → 팔레트 제한. 생산 갤러리에는 등록하지 않은 검증 결과입니다.</p>'''+ref+'<main>'+''.join(cards)+'</main><h2>출력 크기·색 수 비교</h2><p>아래는 같은 생성 이미지에서 출력 크기와 팔레트만 바꾼 비교입니다. 서로 다른 AI 생성 결과가 아닙니다.</p><main>'+variants+'</main></html>',encoding='utf-8')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser();parser.add_argument('--reference',type=Path,default=ROOT/'outputs/reference-battle-adjust-20261018/outfit-080.png');parser.add_argument('--output',type=Path,default=ROOT/'outputs/pixel-art-test-20261019');args=parser.parse_args()
    out=args.output;out.mkdir(parents=True,exist_ok=True)
    for entry in json.loads((ROOT/'DOCS/model-licenses/pixel-art-xl/files.json').read_text(encoding='utf-8')):
        path=image_engine.engine.COMFY_ROOT/'models'/entry['target']
        with path.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==entry['sha256'],path.name
    ensure_idle()
    for port in (8190,8191):requests.post(f'http://127.0.0.1:{port}/free',json={'unload_models':True,'free_memory':True},timeout=30).raise_for_status()
    cases=[
        ('knight-128','캐릭터 · 128px / 32색',dict(pixelSize=128,pixelColors=32,preset='sprite',prompt='a single adult female adventurer, short blue hair, white scarf, navy coat with gold trim, brown boots, holding a small sword, standing, full body, three quarter view, simple silhouette')),
        ('potion-64','소품 · 64px / 16색',dict(pixelSize=64,pixelColors=16,preset='illustration',prompt='a single red healing potion in a small round glass bottle, cork stopper, gold rim, simple game inventory icon, centered, isolated')),
        ('reference-96','원화 변형 · 96px / 32색',dict(pixelSize=96,pixelColors=32,preset='sprite',mode='reference',denoise=.6,prompt='a single adult female adventurer, black hood, short purple hair, dark grey long coat with red lining, black trousers and boots, red mechanical gauntlets, facing right, standing, full body')),
    ]
    records=[]
    for name,label,raw in cases:
        ensure_idle()
        if raw.get('mode')=='reference':
            if not args.reference.is_file():raise FileNotFoundError('Supply --reference for the conversion case')
            import base64
            raw=dict(raw,imageData=base64.b64encode(args.reference.read_bytes()).decode())
            with Image.open(args.reference) as ref:ref.save(out/'reference-source.png')
        p=image_engine.validate(dict(model=image_pixel.MODEL_ID,seed=20261019,background='transparent',count=1,**raw))
        signature=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest();meta=out/name/'acceptance.json'
        if meta.is_file() and json.loads(meta.read_text(encoding='utf-8')).get('signature')==signature:
            record=json.loads(meta.read_text(encoding='utf-8'));metrics(out/name/'image-1.png',p['pixelSize'],p['pixelColors']);print('Reuse',name,flush=True)
        else:
            completed={}
            def update(jid,**fields):
                print(jid,fields.get('state',''),fields.get('message',''),flush=True)
                if fields.get('state')=='complete':completed.update(fields)
            print('Generate',name,flush=True);started=time.monotonic()
            with patch.object(image_engine,'RESULT_ROOT',out),patch.object(image_engine,'update_job',side_effect=update):image_engine.run_job(name,p)
            item=completed['images'][0]
            assert item.get('background')=='transparent',item
            m=metrics(out/name/'image-1.png',p['pixelSize'],p['pixelColors'])
            assert 0<m['transparentFraction']<.98,m
            record=dict(id=name,label=label,settings={k:v for k,v in p.items() if k not in ('imageData','maskData')},metrics=m,seconds=round(time.monotonic()-started,2),result=completed,signature=signature)
            meta.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
            print('PASS',name,json.dumps(m),record['seconds'],'seconds',flush=True)
        records.append(record);(out/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8');preview(out,records)

if __name__=='__main__':main()
