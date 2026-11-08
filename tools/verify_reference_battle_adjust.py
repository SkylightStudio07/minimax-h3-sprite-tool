"""Refine right-facing reference pose without silently replacing source details."""
import copy
import json
from pathlib import Path
import sys

import requests
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_engine,image_pose
from verify_rpg_sprite_styles import ensure_idle
import verify_cutscene_cleanup as runner

OUT=ROOT/'outputs/reference-battle-adjust-20261018'
PREVIOUS=ROOT/'outputs/cutscene-reference-right-20261018'


def main():
    sys.stdout.reconfigure(encoding='utf-8');OUT.mkdir(exist_ok=True);ensure_idle();runner.OUT=OUT
    source=json.loads((PREVIOUS/'pose-85.json').read_text())['graph']
    for name in ['prepared-reference.png','pose-85.png']:(OUT/name).write_bytes((PREVIOUS/name).read_bytes())
    # Both wrists project ahead of the torso; narrow profile shoulders, staggered feet.
    points=[(590,245),(520,355),(490,380),(555,520),(715,490),(555,375),(650,425),(750,365),
            (480,790),(420,1070),(365,1400),(555,790),(635,1060),(725,1400),(596,230),(583,231),(568,240),(557,244)]
    pose={'points':[[x/1024,y/1536] for x,y in points],'strength':1.2}
    image_pose.render(pose,(832,1216)).save(OUT/'revised-pose.png')
    with (OUT/'revised-pose.png').open('rb') as stream:
        r=requests.post(image_engine.COMFY_URL+'/upload/image',files={'image':('reference-battle-revised-pose.png',stream,'image/png')},data={'overwrite':'true'},timeout=40)
    r.raise_for_status();uploaded=r.json()['name'];records=[]
    try:
        for name,denoise,control in [('retain-070',.7,1.2),('battle-080',.8,1.2),('strong-pose-080',.8,1.45)]:
            ensure_idle();graph=copy.deepcopy(source)
            graph['7']['inputs']['denoise']=denoise
            graph['4']['inputs']['text']+=', (oversized black segmented mechanical gauntlet:1.35), armored forearm, visible mechanical finger joints, both forearms extended forward away from torso, empty hands, unarmed fighting guard stance, staggered feet, (right-facing side profile:1.2), short bob haircut'
            graph['5']['inputs']['text']+=', holding coat, grabbing clothes, gripping fabric, hands on coat, hands on hips, hands in pockets, handbag, bag, pouches, weapon, long hair'
            graph['51']['inputs']['image']=uploaded;graph['52']['inputs']['strength']=control
            graph['9']['inputs']['filename_prefix']='reference_battle_adjust/'+name
            record=runner.execute(image_engine.COMFY_URL,graph,name);record.update(denoise=denoise,controlStrength=control,pose=pose,referenceInput=True)
            (OUT/(name+'.json')).write_text(json.dumps(record,indent=2),encoding='utf-8');records.append(record)
            (OUT/'results.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
            cards='<article><h2>입력 원화</h2><img src="prepared-reference.png"></article><article><h2>이전 결과 · 변형0.85</h2><img src="pose-85.png"></article>'
            cards+=''.join(f'<article><h2>{r["id"]}</h2><a href="{r["id"]}.png"><img src="{r["id"]}.png"></a><p>변형 {r["denoise"]} / 포즈 {r["controlStrength"]} / {r["seconds"]}초</p></article>' for r in records)
            (OUT/'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>원화 · 우측 전투 자세 조정</title><style>body{background:#20232a;color:#eee;font:16px sans-serif;margin:24px}main{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}img{width:100%}h2{font-size:17px}@media(max-width:700px){main{grid-template-columns:1fr}}</style><h1>손을 몸에서 분리한 우측 전투 자세 비교</h1><p>동일 원화 입력/WAI17/셀채색1.0+전투형식0.4/832×1216/28steps/CFG4.5/seed20261018. 손목과 팔꿈치 위치 수정, 기계장갑 묘사 강화, 옷잡기·긴머리·추가가방 억제. 강도 외 프롬프트/포즈도 바뀌어 이전 결과와 순수한 강도만의 비교는 아닙니다. 원본 의상·장갑 세부 보존은 별도 검수.</p><a href="revised-pose.png">목표 관절 보기</a><main>'+cards+'</main>',encoding='utf-8')
        canvas=Image.new('RGB',(5*250,401),'#ddd');draw=ImageDraw.Draw(canvas)
        for i,(filename,label) in enumerate([('prepared-reference.png','Reference'),('pose-85.png','Previous')]+[(r['id']+'.png',r['id']) for r in records]):
            with Image.open(OUT/filename) as im:canvas.paste(im.convert('RGB').resize((250,365),Image.Resampling.LANCZOS),(i*250,36))
            draw.text((i*250+8,10),label,fill='black')
        canvas.save(OUT/'comparison.webp')
    finally:requests.post(image_engine.COMFY_URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30)


if __name__=='__main__':main()
