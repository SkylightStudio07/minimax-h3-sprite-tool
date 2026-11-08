"""Manual GPU comparison using other-game character tags, without enabling cards."""
import hashlib
import html
import json
from pathlib import Path
import sqlite3
import sys
import time
from unittest.mock import patch

import requests
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_engine
import image_styles

OUT=ROOT/'outputs/rpg-sprite-styles-20261017'
CASES={
    'rapi':'rapi (nikke), goddess of victory: nikke, 1girl, solo, full body, standing, idle, side view, facing right, holding a rifle, grey background, clean lineart, game battle sprite',
    'enterprise':'enterprise (azur lane), azur lane, 1girl, solo, full body, standing, idle, side view, facing right, grey background, clean lineart, game battle sprite',
}


def ensure_idle():
    with sqlite3.connect(f'file:{ROOT/"data/team.sqlite3"}?mode=ro',uri=True) as db:
        if db.execute("SELECT count(*) FROM jobs WHERE state NOT IN ('complete','error','cancelled')").fetchone()[0]:
            raise RuntimeError('Team queue busy')
    for port in (8189,8190,8191):
        try:
            r=requests.get(f'http://127.0.0.1:{port}/queue',timeout=3);r.raise_for_status();q=r.json()
        except requests.ConnectionError:
            continue
        if q.get('queue_running') or q.get('queue_pending'):
            raise RuntimeError(f'GPU queue {port} busy')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    OUT.mkdir(parents=True,exist_ok=True)
    styles=image_styles.catalog()
    selected=[]
    for s in styles:
        if s['id'] not in ('counter-side-sprites','epic-seven-sprites'):continue
        path=image_engine.engine.COMFY_ROOT/'models/loras'/s['filename']
        if not path.exists():print('Skip missing:',s['id'],flush=True);continue
        with path.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=s['sha256']:raise RuntimeError('LoRA hash mismatch: '+s['id'])
        selected.append(s)
    if not selected:raise RuntimeError('No verified sprite LoRA installed')
    local=[dict(s,enabled=True) if s in selected else s for s in styles]
    records=[]
    with patch.object(image_styles,'catalog',return_value=local):
        for s in selected:
            for subject,strength in [('rapi',0),('rapi',.6),('enterprise',.6)]:
                ensure_idle()
                settings=image_engine.validate(dict(model='illustrious-xl',prompt=CASES[subject],
                    negativePrompt='worst quality, low quality, blurry, text, watermark, multiple views, cropped, out of frame',
                    styleId=s['id'],styleStrength=strength,width=896,height=1152,steps=28,cfg=5,seed=20261017))
                graph=image_engine.build_workflow(settings,settings['seed'])
                name=s['id']+'-'+subject+'-'+str(strength)
                graph['9']['inputs']['filename_prefix']='rpg_sprite_test/'+name
                signature=hashlib.sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest()
                meta=OUT/(name+'.json');target=OUT/(name+'.png')
                if target.exists() and meta.exists() and json.loads(meta.read_text(encoding='utf-8')).get('signature')==signature:
                    record=json.loads(meta.read_text(encoding='utf-8'))
                else:
                    start=time.monotonic()
                    r=requests.post(image_engine.COMFY_URL+'/prompt',json={'prompt':graph},timeout=60)
                    if not r.ok:raise RuntimeError(r.text[:1000])
                    pid=r.json()['prompt_id'];print('Generating',name,flush=True)
                    while time.monotonic()-start<600:
                        history=requests.get(image_engine.COMFY_URL+'/history/'+pid,timeout=20).json().get(pid)
                        if history:break
                        time.sleep(1)
                    else:raise TimeoutError(pid)
                    (OUT/(name+'-history.json')).write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
                    if history['status']['status_str']!='success':raise RuntimeError(str(history['status'])[:1500])
                    r=requests.get(image_engine.COMFY_URL+'/view',params=history['outputs']['9']['images'][0],timeout=60);r.raise_for_status()
                    target.write_bytes(r.content)
                    record=dict(id=name,style=s['id'],subject=subject,strength=strength,settings=settings,
                                seconds=round(time.monotonic()-start,2),signature=signature)
                    meta.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
                records.append(record)
                print('Passed',name,record['seconds'],flush=True)
    (OUT/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    cards=''.join(f'<article><h3>{html.escape(r["id"])}</h3><img src="{html.escape(r["id"])}.png"><p>{r["seconds"]}s</p></article>' for r in records)
    (OUT/'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>RPG sprite LoRA comparison</title><style>body{background:#20232a;color:white;font:16px sans-serif}main{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}img{width:100%}h3{font-size:15px}</style><h1>Other-game character tags / Illustrious</h1><p>Same seed; Rapi 0 / 0.6, Enterprise 0.6. Tags do not guarantee exact character identity.</p><main>'+cards+'</main>',encoding='utf-8')
    requests.post(image_engine.COMFY_URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30).raise_for_status()


if __name__=='__main__':main()
