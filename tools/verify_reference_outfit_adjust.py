"""Follow-up outfit constraints for the reference battle-pose experiment."""
import copy
import json
from pathlib import Path
import sys

import requests
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import image_engine
from verify_rpg_sprite_styles import ensure_idle
import verify_cutscene_cleanup as runner

OUT = ROOT / 'outputs/reference-battle-adjust-20261018'


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    runner.OUT = OUT
    source = json.loads((OUT / 'battle-080.json').read_text())['graph']
    records = []
    try:
        for name, denoise in [('outfit-075', .75), ('outfit-080', .80)]:
            ensure_idle()
            graph = copy.deepcopy(source)
            graph['7']['inputs']['denoise'] = denoise
            graph['4']['inputs']['text'] += ', (hood up covering the top of her head:1.5), black hood with dark red lining, (full length fitted black trousers:1.4), (black knee high boots:1.3), covered legs, long black coat with red inner lining, single bulky mechanical gauntlet on one hand, other hand normal, planted feet'
            graph['5']['inputs']['text'] += ', bare legs, exposed calves, shorts, cropped pants, capri pants, sandals, high heels, hood down, uncovered head, detached hand, extra hands, extra arms'
            graph['9']['inputs']['filename_prefix'] = 'reference_battle_adjust/' + name
            record = runner.execute(image_engine.COMFY_URL, graph, name)
            record.update(denoise=denoise, controlStrength=1.2, referenceInput=True)
            (OUT / (name + '.json')).write_text(json.dumps(record, indent=2), encoding='utf-8')
            records.append(record)
    finally:
        requests.post(image_engine.COMFY_URL + '/free', json={'unload_models': True, 'free_memory': True}, timeout=30)
    cards = [('prepared-reference', '입력 원화'), ('pose-85', '이전 결과'), ('battle-080', '전투 자세 조정'), ('outfit-075', '의상 보존 강조 · 0.75'), ('outfit-080', '의상 보존 강조 · 0.80')]
    canvas = Image.new('RGB', (1250, 401), '#ddd')
    draw = ImageDraw.Draw(canvas)
    for i, (name, label) in enumerate(cards):
        with Image.open(OUT / (name + '.png')) as im:
            canvas.paste(im.convert('RGB').resize((250, 365), Image.Resampling.LANCZOS), (i * 250, 36))
        draw.text((i * 250 + 8, 10), name, fill='black')
    canvas.save(OUT / 'outfit-comparison.webp')
    (OUT / 'outfit-preview.html').write_text('<!doctype html><meta charset="utf-8"><title>우측 전투 자세 · 의상 보존 비교</title><style>body{background:#20232a;color:#eee;font:16px sans-serif;margin:24px}main{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}img{width:100%}h2{font-size:17px}</style><h1>우측 전투 자세 · 의상 보존 비교</h1><p>실제 원화 입력. 후드를 쓴 상태·긴 바지·부츠를 강조한 추가 비교. 원본 장갑과 의상 세부는 별도 검수해야 합니다.</p><main>' + ''.join(f'<article><h2>{label}</h2><a href="{name}.png"><img src="{name}.png"></a></article>' for name, label in cards) + '</main><a href="preview.html">첫 조정 전체 비교</a>', encoding='utf-8')


if __name__ == '__main__':
    main()
