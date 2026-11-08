"""Test Soya's shared graph with explicit local filenames and candidate LoRA.

Does not change original workflow files or enable a production preset.
"""
import copy
import json
from pathlib import Path
import sys
import time

import requests
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
URL = 'http://127.0.0.1:8191'
OUT = ROOT / 'outputs/soya-workflow-test-20261017'
CASES = [
    ('operator', '1girl, solo, adult woman, short silver bob hair, teal eyes, fully covered black tactical jacket, holding a radio, waist-up three-quarter portrait, pale gray background, anime illustration'),
    ('swordsman', '1boy, solo, adult man, dark hair tied back, dark blue coat, scarf, full body, boots, holding a sheathed sword, standing, plain pale gray background, anime game character'),
    ('maid', '1girl, solo, adult woman, long turquoise twin tails, purple eyes, white maid headdress, fully covered black and white maid dress, white apron, white gloves, smiling, upper body, holding a wooden sign that says Welcome to ComfyUI, yellow background, anime illustration'),
]


def ensure_idle():
    sys.path.insert(0, str(ROOT / 'tools'))
    from verify_fasth3_actions import ensure_idle as check_team
    check_team()
    queue = requests.get(URL + '/queue', timeout=15).json()
    if queue.get('queue_running') or queue.get('queue_pending'):
        raise RuntimeError('Workflow server queue busy')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    OUT.mkdir(parents=True, exist_ok=True)
    graph = json.loads((ROOT / 'workflows/soya/anima-flanime.local-paths.api.json').read_text(encoding='utf-8'))
    graph['184']['inputs']['lora_name'] = str(Path('soya-candidates/Detailed_anime_style_Illustrious_v0.7.safetensors'))
    info = requests.get(URL + '/object_info', timeout=30).json()
    missing = sorted({n['class_type'] for n in graph.values()} - set(info))
    if missing:
        raise RuntimeError('Missing nodes: ' + ', '.join(missing))
    ensure_idle()
    # Release only idle production model caches before loading the comparison stack.
    response = requests.post('http://127.0.0.1:8189/free', json={'unload_models': True, 'free_memory': True}, timeout=30)
    response.raise_for_status()
    records = []
    for i, (name, prompt) in enumerate(CASES):
        ensure_idle()
        work = copy.deepcopy(graph)
        work['125']['inputs']['value'] = 'masterpiece, best quality, safe, ' + prompt
        work['126']['inputs']['value'] = 'worst quality, low quality, blurry, text watermark, multiple views, duplicate person, nude'
        work['290']['inputs']['seed'] = 202610170 + i
        work['291']['inputs']['seed'] = 202610170 + i
        work['404']['inputs']['filename_prefix'] = 'soya_test/' + name + '-final'
        work['900'] = dict(class_type='SaveImage', inputs=dict(images=['63', 0], filename_prefix='soya_test/' + name + '-anima'))
        work['901'] = dict(class_type='SaveImage', inputs=dict(images=['283:15', 0], filename_prefix='soya_test/' + name + '-pre-refine'))
        (OUT / (name + '-workflow.json')).write_text(json.dumps(work, ensure_ascii=False, indent=2), encoding='utf-8')
        if (OUT / (name + '-final.png')).exists():
            print('Reusing saved result', name, flush=True)
            records.append(json.loads((OUT / (name + '-record.json')).read_text(encoding='utf-8')))
            continue
        start = time.monotonic()
        response = requests.post(URL + '/prompt', json={'prompt': work}, timeout=60)
        if not response.ok:
            (OUT / (name + '-validation-error.json')).write_text(response.text, encoding='utf-8')
            raise RuntimeError('Graph validation failed; inspect ' + name + '-validation-error.json')
        pid = response.json()['prompt_id']
        print('Generating', name, pid, flush=True)
        while time.monotonic() - start < 1200:
            history = requests.get(URL + '/history/' + pid, timeout=30).json().get(pid)
            if history:
                break
            time.sleep(2)
        else:
            raise TimeoutError('Generation still queued; do not submit another job')
        (OUT / (name + '-history.json')).write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding='utf-8')
        if history['status']['status_str'] != 'success':
            raise RuntimeError(str(history['status']))
        for node, stage in [('900', 'anima'), ('901', 'pre-refine'), ('404', 'final')]:
            result = history['outputs'][node]['images'][0]
            response = requests.get(URL + '/view', params=result, timeout=90)
            response.raise_for_status()
            (OUT / (name + '-' + stage + '.png')).write_bytes(response.content)
        record = dict(name=name, prompt=prompt, seconds=round(time.monotonic() - start, 2), seed=202610170 + i,
                      candidateLora='Civitai model 1547435 / version 1750914; original Soya equivalence unverified')
        records.append(record)
        (OUT / (name + '-record.json')).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        (OUT / 'results.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Passed', name, record['seconds'], flush=True)
    grid = Image.new('RGB', (960, len(CASES) * 440), '#eeeeee')
    draw = ImageDraw.Draw(grid)
    for row, (name, _) in enumerate(CASES):
        for col, stage in enumerate(['anima', 'pre-refine', 'final']):
            x, y = col * 320, row * 440
            draw.text((x + 4, y + 4), name + ' / ' + stage, fill='black')
            with Image.open(OUT / (name + '-' + stage + '.png')) as im:
                im = im.convert('RGB'); im.thumbnail((320, 412)); grid.paste(im, (x, y + 24))
    grid.save(OUT / 'comparison.jpg')
    requests.post(URL + '/free', json={'unload_models': True, 'free_memory': True}, timeout=30)


if __name__ == '__main__':
    main()
