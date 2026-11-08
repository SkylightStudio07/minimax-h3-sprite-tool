"""Isolated, resumable Soya LoRA comparison. Does not auto-enable catalogue entries."""
import argparse
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

import requests
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import image_engine as engine
import image_styles
from verify_fasth3_actions import ensure_idle

OUT = ROOT / 'outputs/soya-styles-20261017'
SUBJECTS = [
    ('operator', 'Adult woman with short silver bob hair, teal eyes, fully covered black tactical jacket, holding a radio, waist-up three-quarter portrait, pale gray background, Japanese anime illustration.'),
    ('swordsman', 'Adult man with dark hair tied back, dark blue coat and scarf, full body with boots, holding a sheathed sword, confident stance, plain pale gray background, Japanese anime game character.'),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--controls', action='store_true', help='Same triggers and seeds, zero LoRA strength')
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    OUT.mkdir(parents=True, exist_ok=True)
    styles = [dict(s, enabled=True) for s in image_styles.catalog() if s['id'].startswith('soya-') and s['family'] == 'anima']
    records = []
    for style in styles if args.controls else [None] + styles:
        sid = style['id'] if style else 'baseline'
        for index, (subject, prompt) in enumerate(SUBJECTS):
            if args.controls and index:
                continue
            name = sid + '-' + subject
            if args.controls:
                name += '-control'
            target = OUT / (name + '.png')
            params = dict(prompt=prompt, model='anima-turbo', width=768, height=1024, seed=202610170 + index)
            if style:
                params.update(styleId=sid, styleStrength=0 if args.controls else style['strength'])
            with patch.object(image_styles, 'catalog', return_value=styles):
                p = engine.validate(params)
                graph = engine.build_workflow(p, p['seed'])
            graph['9']['inputs']['filename_prefix'] = 'soya_validation/' + name
            record = dict(id=name, style=sid, subject=subject, settings=p, file=target.name)
            try:
                if not target.exists():
                    ensure_idle()
                    response = requests.post(engine.COMFY_URL + '/prompt', json={'prompt': graph}, timeout=60)
                    response.raise_for_status()
                    pid = response.json()['prompt_id']
                    print('Generating', name, pid, flush=True)
                    deadline = time.monotonic() + 900
                    while time.monotonic() < deadline:
                        history = requests.get(engine.COMFY_URL + '/history/' + pid, timeout=30).json().get(pid)
                        if history:
                            break
                        time.sleep(2)
                    else:
                        raise TimeoutError('Generation timed out; stop batch to avoid overlapping work')
                    (OUT / (name + '-history.json')).write_text(json.dumps(history, indent=2), encoding='utf-8')
                    if history['status']['status_str'] != 'success':
                        raise RuntimeError(str(history['status']))
                    img = history['outputs']['9']['images'][0]
                    response = requests.get(engine.COMFY_URL + '/view', params=img, timeout=60)
                    response.raise_for_status()
                    target.write_bytes(response.content)
                record['state'] = 'passed'
                print('Passed', name, flush=True)
            except Exception as exc:
                record.update(state='failed', error=str(exc))
                print('FAILED', name, str(exc)[:200], flush=True)
                if isinstance(exc, TimeoutError) or 'Queue busy' in str(exc):
                    raise
            records.append(record)
            (OUT / ('controls.json' if args.controls else 'results.json')).write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
        # One compact, inspectable page per four styles (two subjects per row).
    for page, start in enumerate(range(0, len(records), 8)):
        group = records[start:start + 8]
        grid = Image.new('RGB', (640, ((len(group) + 1) // 2) * 448), '#eeeeee')
        draw = ImageDraw.Draw(grid)
        for i, record in enumerate(group):
            x, y = (i % 2) * 320, (i // 2) * 448
            draw.text((x + 4, y + 4), record['id'].replace('soya-', ''), fill='black')
            if record['state'] == 'passed':
                with Image.open(OUT / record['file']) as im:
                    im.thumbnail((320, 424))
                    grid.paste(im, (x, y + 24))
        grid.save(OUT / f'{"controls" if args.controls else "comparison"}-{page + 1}.jpg')


if __name__ == '__main__':
    main()
