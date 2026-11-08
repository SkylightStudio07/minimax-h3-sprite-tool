"""Manual GPU sweep of visual presets; no production gallery records are created."""
import json
from pathlib import Path
import sqlite3
import sys
import time

import requests
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_engine as engine
import image_looks


def main():
    out=ROOT/'outputs/look-validation-20261015';out.mkdir(parents=True,exist_ok=True)
    looks=sorted(image_looks.catalog()['looks'],key=lambda x:x['model'])
    records=[]
    for look in looks:
        name=look['id']
        settings=dict(prompt='An adult female adventurer with shoulder-length blue hair and amber eyes, wearing a fully covered navy coat with gold trim and a white scarf. Waist-up portrait, relaxed smile, hands visible, plain white background.',model=look['model'],seed=20261015,width=832,height=1216,lookId=name,styleId=look['styleId'],styleStrength=look['styleStrength'],steps=look['steps'],cfg=look['cfg'])
        p=engine.validate(settings)
        record_path=out/(name+'.json')
        if (out/(name+'.png')).exists() and record_path.exists():
            old=json.loads(record_path.read_text(encoding='utf-8'))
            if old['settings']==p:
                records.append(old);print('Cached',name,flush=True);continue
        with sqlite3.connect('file:'+str(ROOT/'data/team.sqlite3')+'?mode=ro',uri=True) as db:
            assert not db.execute("select id from jobs where state not in ('complete','error','cancelled')").fetchall(),'Team queue busy'
        q=requests.get(engine.COMFY_URL+'/queue',timeout=10).json()
        assert not q['queue_running'] and not q['queue_pending'],'Comfy queue busy'
        graph=engine.build_workflow(p,p['seed']);graph['9']['inputs']['filename_prefix']='look_validation/'+name
        started=time.monotonic()
        r=requests.post(engine.COMFY_URL+'/prompt',json={'prompt':graph},timeout=60)
        if not r.ok:raise RuntimeError(r.text[:1000])
        pid=r.json()['prompt_id'];print('Generating',name,flush=True)
        while time.monotonic()-started<600:
            history=requests.get(engine.COMFY_URL+'/history/'+pid,timeout=30).json().get(pid)
            if history:break
            time.sleep(1)
        else:raise TimeoutError(pid)
        assert history['status']['status_str']=='success',history['status']
        response=requests.get(engine.COMFY_URL+'/view',params=history['outputs']['9']['images'][0],timeout=60);response.raise_for_status()
        (out/(name+'.png')).write_bytes(response.content)
        record=dict(id=name,seconds=round(time.monotonic()-started,2),settings=p,promptId=pid)
        record_path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        records.append(record);print('Passed',len(records),name,record['seconds'],flush=True)
    (out/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    for group in image_looks.catalog()['groups']:
        selected=[x for x in image_looks.catalog()['looks'] if x['group']==group['id']]
        sheet=Image.new('RGB',(936,960),'#eeeeee');draw=ImageDraw.Draw(sheet)
        for i,x in enumerate(selected):
            with Image.open(out/(x['id']+'.png')) as im:
                im.thumbnail((312,456));sheet.paste(im,((i%3)*312,(i//3)*480+24))
            draw.text(((i%3)*312+5,(i//3)*480+5),x['id'],fill='black')
        sheet.save(out/(group['id']+'-comparison.jpg'))


if __name__=='__main__':main()
