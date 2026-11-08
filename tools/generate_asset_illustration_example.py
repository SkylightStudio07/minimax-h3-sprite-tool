"""Generate the original illustration type example through the local image engine."""
import hashlib
import json
from pathlib import Path
import sys

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import image_engine
from tools import verify_pixel_minimax as executor
from tools.verify_rpg_sprite_styles import ensure_idle

OUT = ROOT / 'outputs/asset-illustration-original-20261020'
PROMPT = (
    'original character, 1girl, adult woman, solo, fantasy cartographer, '
    'wavy shoulder-length dark plum bob hair, amber eyes, brass geometric hair clip, '
    'ivory high-collared blouse, moss green short travel cape, terracotta waistcoat, '
    'brown leather satchel strap, holding a rolled star map, small brass compass at waist, '
    'gentle confident smile, looking at viewer, three-quarter view, cowboy shot, '
    'head to upper thighs, centered composition, space above head, '
    'refined anime illustration, delicate clean lineart, detailed expressive eyes, '
    'crisp cel shading, subtle painted accents, warm soft light, '
    'pale warm cream background, faint star chart lines, tasteful character concept art'
)
NEGATIVE = (
    'worst quality, low quality, blurry, bad anatomy, bad hands, extra fingers, '
    'extra arms, missing pupils, child, chibi, pixel art, photorealistic, 3d, '
    'text, logo, watermark, signature, halo, floating ring, school uniform, '
    'multiple characters, character sheet, split screen, cropped head'
)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / 'original-cartographer.png'
    if target.exists():
        print('Existing original retained:', target)
        return
    ensure_idle()
    settings = image_engine.validate(dict(
        model='flanime-xl', preset='illustration', mode='text',
        prompt=PROMPT, negativePrompt=NEGATIVE, title='Original cartographer example',
        width=1024, height=1536, steps=32, cfg=5.0, seed=2026102081,
        count=1, background='keep',
    ))
    graph = image_engine.build_workflow(settings, settings['seed'])
    graph['9']['inputs']['filename_prefix'] = 'asset_original_20261020/cartographer'
    executor.OUT = OUT
    history = executor.execute(graph, image_engine.COMFY_URL, 'original-cartographer')
    response = requests.get(image_engine.COMFY_URL + '/view',
                            params=history['outputs']['9']['images'][0], timeout=60)
    response.raise_for_status()
    target.write_bytes(response.content)
    record = dict(
        originalCharacter=True, referenceImages=[], characterLoras=[],
        generationMode='local-comfy-image-engine', settings=settings,
        sha256=hashlib.sha256(response.content).hexdigest(),
        siteAsset='assets/asset-type-previews/original-cartographer.png',
    )
    (OUT / 'generation.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print('GENERATED', target)


if __name__ == '__main__':
    main()
