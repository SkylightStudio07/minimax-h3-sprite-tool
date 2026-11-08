"""Generate and publish genuine previews for Soya refinement presets, resumably."""
import hashlib
import html
import json
from pathlib import Path
import sys
import time

import requests
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_engine
import image_looks
from verify_fasth3_actions import ensure_idle

URL='http://127.0.0.1:8191'
OUT=ROOT/'outputs/soya-looks-20261017'
CASES={
 'soya-cel':'Adult woman with short silver bob hair, teal eyes, fully covered navy tactical jacket with a high collar, empty hands, waist-up portrait, pale gray background, solo anime character',
 'soya-line':'Adult woman with long auburn hair, round glasses, fully covered ivory scholar robe with a dark scarf, waist-up portrait, plain pale gray background, solo anime character',
 'soya-game':'Adult man with short dark hair, dark blue modern jacket and trousers, boots, standing with both empty hands visible, full body, plain gray background, solo anime game character',
 'soya-paint':'Adult woman with shoulder length black hair, amber eyes, fully covered forest green coat and white scarf, waist-up three-quarter portrait, plain gray background, solo anime character',
}


def main():
 sys.stdout.reconfigure(encoding='utf-8')
 OUT.mkdir(exist_ok=True)
 dest=ROOT/'web/assets/soya-look-previews';dest.mkdir(exist_ok=True)
 catalog=image_looks.catalog()
 looks=[x for x in catalog['looks'] if x['model']=='soya-anima-flanime']
 records=[]
 ensure_idle()
 requests.post(image_engine.COMFY_URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30).raise_for_status()
 for look in looks:
  name=look['id'];target=OUT/(name+'.png');meta=OUT/(name+'.json')
  settings=image_engine.validate(dict(model=look['model'],lookId=name,prompt=CASES[look['group']],seed=202610171,width=768,height=768,steps=16,cfg=2))
  graph=image_engine.build_workflow(settings,settings['seed'])
  graph['9']['inputs']['filename_prefix']='soya_looks/'+name
  signature=hashlib.sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest()
  if target.exists() and meta.exists() and json.loads(meta.read_text(encoding='utf-8')).get('signature')==signature:
   record=json.loads(meta.read_text(encoding='utf-8'));print('Cached',name,flush=True)
  else:
   ensure_idle()
   q=requests.get(URL+'/queue',timeout=15).json()
   if q.get('queue_running') or q.get('queue_pending'):raise RuntimeError('Experiment queue busy')
   start=time.monotonic()
   response=requests.post(URL+'/prompt',json={'prompt':graph},timeout=60)
   if not response.ok:raise RuntimeError(response.text[:1200])
   pid=response.json()['prompt_id'];print('Generating',name,flush=True)
   while time.monotonic()-start<600:
    history=requests.get(URL+'/history/'+pid,timeout=20).json().get(pid)
    if history:break
    time.sleep(1)
   else:raise TimeoutError(pid)
   (OUT/(name+'-history.json')).write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
   if history['status']['status_str']!='success':raise RuntimeError(str(history['status']))
   response=requests.get(URL+'/view',params=history['outputs']['9']['images'][0],timeout=60);response.raise_for_status()
   target.write_bytes(response.content)
   record=dict(id=name,seconds=round(time.monotonic()-start,2),settings=settings,signature=signature)
   meta.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
   print('Passed',len(records)+1,'/',len(looks),name,record['seconds'],flush=True)
  with Image.open(target) as im:
   im.thumbnail((384,384));im.save(dest/(name+'.webp'),quality=88)
  # Re-read catalogue to avoid replacing changes made while the GPU batch runs.
  current=image_looks.catalog()
  item=next(x for x in current['looks'] if x['id']==name)
  item.update(preview='assets/soya-look-previews/'+name+'.webp',verification='Soya 실제 생성 확인 · 1개 시드 · 실험적')
  temp=image_looks.CATALOG.with_suffix('.tmp')
  temp.write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  temp.replace(image_looks.CATALOG)
  records.append(record)
  (OUT/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
 for group in CASES:
  chosen=[x for x in looks if x['group']==group]
  grid=Image.new('RGB',(960,1020),'#eeeeee');draw=ImageDraw.Draw(grid)
  for i,x in enumerate(chosen):
   col,row=i%3,i//3
   with Image.open(OUT/(x['id']+'.png')) as im:
    im.thumbnail((320,312));grid.paste(im,(col*320,row*340+24))
   draw.text((col*320+4,row*340+4),x['id'].replace(group+'-',''),fill='black')
  grid.save(OUT/(group+'-comparison.jpg'))
 sections=[]
 for group in CASES:
  sections.append('<h2>'+html.escape(group)+'</h2><div class="grid">')
  for look in [x for x in looks if x['group']==group]:
   sections.append('<figure><figcaption>'+html.escape(look['name'])+'</figcaption><a href="'+look['id']+'.png"><img loading="lazy" src="'+look['id']+'.png"></a></figure>')
  sections.append('</div>')
 (OUT/'preview.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Soya 그림체 36종</title><style>body{background:#1a202b;color:#eee;font:16px sans-serif;max-width:1400px;margin:24px auto;padding:12px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}figure{margin:0}img{width:100%}@media(max-width:650px){.grid{grid-template-columns:1fr 1fr}}</style><h1>Soya 그림체 36종 · 실제 생성 비교</h1><p>계열별 동일 캐릭터·시드. 각 프리셋 1개 시드 시험이며 캐릭터·구도 전반의 안정성을 보장하지 않습니다.</p>'+''.join(sections),encoding='utf-8')
 requests.post(URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30)


if __name__=='__main__':main()
