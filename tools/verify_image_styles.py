"""Manual GPU acceptance check; never enables the production catalog."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time
from unittest.mock import patch

import requests
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import image_engine as engine
import image_styles


def main():
    out = ROOT / 'outputs/style-validation-20261015'
    out.mkdir(parents=True, exist_ok=True)
    styles = [dict(s, enabled=True) for s in image_styles.catalog()]
    for s in styles:
        with (engine.engine.COMFY_ROOT/'models/loras'/s['filename']).open('rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == s['sha256']
    records = []
    with patch.object(image_styles, 'catalog', return_value=styles):
        for style in styles:
            for strength in (0, .5, .7):
                with sqlite3.connect('file:'+str(ROOT/'data/team.sqlite3')+'?mode=ro', uri=True) as db:
                    assert not db.execute("select id from jobs where state not in ('complete','error','cancelled')").fetchall(), 'Team queue busy; retry later'
                queue = requests.get(engine.COMFY_URL+'/queue', timeout=15).json()
                assert not queue.get('queue_running') and not queue.get('queue_pending'), 'Comfy queue busy; retry later'
                p = engine.validate(dict(prompt='An adult female adventurer with short blue hair and amber eyes, wearing a fully covered navy coat with gold trim and a white scarf. Waist-up portrait, relaxed smile, plain pale blue background, detailed anime illustration.',
                    model='anima-turbo', preset='illustration', width=832, height=1216,
                    seed=20261015, styleId=style['id'], styleStrength=strength))
                graph = engine.build_workflow(p, p['seed'])
                name = style['id']+'-'+str(strength)
                graph['9']['inputs']['filename_prefix'] = 'style_validation/'+name
                started = time.monotonic()
                response = requests.post(engine.COMFY_URL+'/prompt', json={'prompt':graph}, timeout=60)
                response.raise_for_status()
                pid = response.json()['prompt_id']
                print('Generating', name, pid, flush=True)
                deadline = started + 600
                while time.monotonic() < deadline:
                    history = requests.get(engine.COMFY_URL+'/history/'+pid, timeout=30).json().get(pid)
                    if history:
                        break
                    time.sleep(1)
                else:
                    raise TimeoutError(pid)
                (out/(name+'-history.json')).write_text(json.dumps(history, indent=2), encoding='utf-8')
                assert history['status']['status_str']=='success', history['status']
                result = history['outputs']['9']['images'][0]
                response = requests.get(engine.COMFY_URL+'/view', params=result, timeout=60)
                response.raise_for_status()
                (out/(name+'.png')).write_bytes(response.content)
                record = dict(style=style['id'], strength=strength, seconds=round(time.monotonic()-started,2), settings=p, file=name+'.png')
                records.append(record)
                (out/'results.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
                print('Passed', name, record['seconds'], flush=True)
    grid = Image.new('RGB', (3*312,3*480), '#eeeeee')
    draw = ImageDraw.Draw(grid)
    for i,r in enumerate(records):
        with Image.open(out/r['file']) as im:
            im.thumbnail((312,456))
            grid.paste(im, ((i%3)*312,(i//3)*480+24))
        draw.text(((i%3)*312+5,(i//3)*480+5), r['style']+' / '+str(r['strength']), fill='black')
    grid.save(out/'comparison.jpg')


if __name__ == '__main__':
    main()
