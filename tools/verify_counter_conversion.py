"""Isolated CounterSide/Illustrious pose experiment; does not enable site models."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

import requests
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from verify_rpg_sprite_styles import ensure_idle
import image_engine

OUT = ROOT / 'outputs/counter-side-conversion-20261018'
PREVIOUS = ROOT / 'outputs/sprite-conversion-20261018'
EXPECTED = 'd5224d243d68bef339f09b728d315a4fb7d796a0d9fe21652a69dbb241a972f2'


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--pose-only', action='store_true')
    parser.add_argument('--isolated-unverified', action='store_true', help='Use repeatedly returned official payload; never marks it verified.')
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    ensure_idle()
    for port in (8191,):
        try:
            requests.post(f'http://127.0.0.1:{port}/free', json={'unload_models': True, 'free_memory': True}, timeout=20).raise_for_status()
        except requests.ConnectionError:
            pass
    for name in ('prepared-reference.png', 'battle-pose.png'):
        shutil.copy2(PREVIOUS / name, OUT / name)
    base = json.loads((PREVIOUS / 'preserve-030.json').read_text(encoding='utf-8'))['graph']
    cases = [('epic-dedicated-pose-080', .8, True, False), ('epic-dedicated-pose-100', 1., True, False)]
    provenance = {'counterSideUsed': False}
    if not args.pose_only:
        relative = 'isolated-tests/counter-side-unverified-9f3a0f44.safetensors' if args.isolated_unverified else 'requested/counter-side-sprites-refresh.safetensors'
        lora = ROOT / 'ComfyUI/models/loras' / relative
        if not lora.exists():
            raise RuntimeError('Verified CounterSide download not present; use --pose-only independently.')
        digest = hashlib.sha256(lora.read_bytes()).hexdigest()
        if digest != ('9f3a0f44bea6c093c178700521a22576f4e10ae5a8ffe30a2c1c6680f02030d8' if args.isolated_unverified else EXPECTED):
            raise RuntimeError('CounterSide integrity check failed; not loading.')
        provenance = dict(counterSideUsed=True, sha256=digest, integrityVerified=not args.isolated_unverified, source='https://civitai.com/models/1942132?modelVersionId=2198107')
        cases = [('counter-preserve-030', .3, False, True), ('counter-style-050', .5, False, True),
                 ('counter-dedicated-pose-080', .8, True, True), ('counter-dedicated-pose-100', 1., True, True)]
    for name, denoise, pose, counter in cases:
        ensure_idle()
        graph = copy.deepcopy(base)
        graph['7']['inputs']['denoise'] = denoise
        if counter:
            graph['11']['inputs']['lora_name'] = str(Path(relative))
            graph['4']['inputs']['text'] = graph['4']['inputs']['text'].replace(', e7sprites', '')
        if pose:
            graph['4']['inputs']['text'] = graph['4']['inputs']['text'].replace('standing', 'battle ready stance, bent arms, legs apart').replace('three-quarter view', 'side view, facing right')
            graph['50'] = dict(class_type='ControlNetLoader', inputs=dict(control_net_name='illustrious-openpose-v1.safetensors'))
            graph['51'] = dict(class_type='LoadImage', inputs=dict(image='sprite-conversion-20261018-pose.png'))
            graph['52'] = dict(class_type='ControlNetApplyAdvanced', inputs=dict(positive=['4', 0], negative=['5', 0], control_net=['50', 0], image=['51', 0], strength=1., start_percent=0., end_percent=1.))
            graph['7']['inputs'].update(positive=['52', 0], negative=['52', 1])
        graph['9']['inputs']['filename_prefix'] = 'counter_conversion/' + name
        target = OUT / (name + '.png')
        metadata = OUT / (name + '.json')
        signature = hashlib.sha256(json.dumps(graph, sort_keys=True).encode()).hexdigest()
        if target.exists() and metadata.exists() and json.loads(metadata.read_text())['signature'] == signature:
            print('Cached', name, flush=True)
            continue
        started = time.monotonic()
        response = requests.post(image_engine.COMFY_URL + '/prompt', json={'prompt': graph}, timeout=60)
        if not response.ok:
            raise RuntimeError(response.text[:2000])
        pid = response.json()['prompt_id']
        print('Generating', name, pid, flush=True)
        while time.monotonic() - started < 1200:
            history = requests.get(image_engine.COMFY_URL + '/history/' + pid, timeout=30).json().get(pid)
            if history:
                break
            time.sleep(1)
        else:
            raise TimeoutError(pid)
        (OUT / (name + '-history.json')).write_text(json.dumps(history, indent=2), encoding='utf-8')
        if history['status']['status_str'] != 'success':
            raise RuntimeError(str(history['status'])[:2000])
        result = requests.get(image_engine.COMFY_URL + '/view', params=history['outputs']['9']['images'][0], timeout=60)
        result.raise_for_status()
        target.write_bytes(result.content)
        metadata.write_text(json.dumps(dict(id=name, seconds=round(time.monotonic()-started, 2), signature=signature, provenance=provenance if counter else {'counterSideUsed':False}, graph=graph), indent=2), encoding='utf-8')
        print('Generated', name, round(time.monotonic()-started, 2), flush=True)
    requests.post(image_engine.COMFY_URL + '/free', json={'unload_models':True,'free_memory':True}, timeout=30).raise_for_status()
    cards = '<article><h2>입력 원화</h2><img src="prepared-reference.png"></article><article><h2>목표 포즈</h2><img src="battle-pose.png"></article>'
    for path in sorted(OUT.glob('*.json')):
        if path.name.endswith('-history.json'):
            continue
        record=json.loads(path.read_text(encoding='utf-8'))
        if 'id' not in record:
            continue
        name=record['id']
        cards += f'<article><h2>{name}</h2><a href="{name}.png"><img src="{name}.png"></a><p>{record["seconds"]}초</p></article>'
    (OUT/'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>카사 / 전투 자세 비교</title><style>body{background:#20232a;color:#eee;font:16px sans-serif}main{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}img{width:100%}h2{font-size:16px}</style><h1>카사 화풍 · Illustrious 전용 포즈 제어</h1><p>카사: 공식 다운로드에서 반복 수신한 파일이나 게시 SHA256과 불일치. 격리 실험이며 정식 라이브러리 비활성 상태.</p><main>'+cards+'</main>',encoding='utf-8')


if __name__ == '__main__':
    main()
