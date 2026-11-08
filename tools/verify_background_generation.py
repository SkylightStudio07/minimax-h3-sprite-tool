"""Manual real-generation acceptance cases; does not change production readiness."""
import json
from pathlib import Path
import sqlite3
import sys
from unittest.mock import patch

import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_engine
import image_background

CASES = [
    ('white-mage','anima-turbo','An adult female mage with long flowing silver hair, a fully covered white robe with gold embroidery, white boots, holding a thin wooden staff topped with a blue crystal. Full body including feet, isolated character, anime illustration.'),
    ('archer','anima-turbo','An adult female elven archer with long flowing blonde hair and a long green ribbon, fully covered forest green tunic, brown trousers and boots, holding a curved wooden bow with a thin bowstring. Full body including feet, isolated character, detailed anime illustration.'),
    ('rifle','animagine-xl','1girl, adult, solo, full body, standing, long hair, black hair, blue eyes, military uniform, pants, boots, rifle, holding rifle, fully clothed, white background, simple background, masterpiece, best quality'),
]

def main():
    out=ROOT/'outputs/background-validation-20261015/generated'
    out.mkdir(parents=True,exist_ok=True)
    records=[]
    def update(jid,**fields):
        if fields.get('state')=='complete':
            records.append(dict(id=jid,**fields))
            (out/'jobs.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
        print(jid,fields.get('message'),flush=True)
    with patch.object(image_background,'status',return_value={'ready':True}),patch.object(image_engine,'RESULT_ROOT',out),patch.object(image_engine,'update_job',side_effect=update):
        for n,(name,model,prompt) in enumerate(CASES):
            with sqlite3.connect('file:'+str(ROOT/'data/team.sqlite3')+'?mode=ro',uri=True) as db:
                assert not db.execute("select id from jobs where state not in ('complete','error','cancelled')").fetchall(),'Team queue busy'
            q=requests.get(image_engine.COMFY_URL+'/queue',timeout=10).json()
            assert not q['queue_running'] and not q['queue_pending'],'Comfy queue busy'
            p=image_engine.validate(dict(prompt=prompt,model=model,preset='sprite',background='transparent',seed=20261016+n))
            image_engine.run_job(name,p)
            assert records[-1]['images'][0]['background']=='transparent',records[-1]


if __name__=='__main__':main()
