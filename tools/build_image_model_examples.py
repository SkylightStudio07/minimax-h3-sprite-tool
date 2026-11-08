"""Actual original-character comparisons for the image studio's base picker."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import image_engine
import image_pixel
from tools import verify_pixel_minimax as executor
from tools.generate_asset_illustration_example import PROMPT, NEGATIVE
from tools.verify_rpg_sprite_styles import ensure_idle

OUT = ROOT / 'outputs/image-model-examples-20261020'
PUBLIC = ROOT / 'web/assets/image-model-examples'
CHOICES = [
    ('soya-anima-flanime', '기본 일러스트', '부드러운 채색과 섬세한 디테일', '추천'),
    ('anima-base', '담백한 애니메이션', '가벼운 선과 깔끔한 색면', ''),
    ('anima-turbo', '빠른 시안', '외형과 의상 아이디어를 먼저 확인', ''),
    ('animagine-xl', '선명한 애니메이션', '또렷한 윤곽과 밝은 셀 채색', ''),
    ('illustrious-xl', '섬세한 일러스트', '얼굴과 의상의 작은 디테일', ''),
    ('flanime-xl', '선명한 게임 일러스트', '깔끔한 선과 깊이 있는 명암', ''),
    ('wai-cutscene-counter', '셀 채색 · 전투 캐릭터', '전투 원화와 측면 스프라이트에 사용', ''),
    ('pixel-art-xl', '픽셀 아트', '픽셀 격자와 제한된 색의 도트 초안', '도트'),
]


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def generate(ids):
    for model_id, *_ in CHOICES:
        if ids and model_id not in ids:
            continue
        folder = OUT / model_id
        folder.mkdir(parents=True, exist_ok=True)
        if (folder / 'generation.json').exists():
            print('RETAINED', model_id, flush=True)
            continue
        ensure_idle()
        model = image_engine.MODELS[model_id]
        width, height = map(int, model.get('defaultSize', '832x1216').split('x'))
        if model_id == 'soya-anima-flanime':
            width, height = 768, 1024
        raw = dict(model=model_id, mode='text', preset='illustration', prompt=PROMPT,
                   negativePrompt=NEGATIVE.replace('pixel art, ', '') if model_id == image_pixel.MODEL_ID else NEGATIVE,
                   width=width, height=height, seed=2026102081,
                   steps=model['steps'], cfg=model['cfg'], count=1, background='keep')
        if model_id == image_pixel.MODEL_ID:
            raw.update(pixelSize=128, pixelColors=32)
        p = image_engine.validate(raw)
        backend = image_engine.backend_url(p)
        if backend == image_engine.image_soya.URL:
            requests.post(image_engine.COMFY_URL + '/free', json={'unload_models': True, 'free_memory': True}, timeout=30).raise_for_status()
        graph = image_engine.build_workflow(p, p['seed'])
        graph['9']['inputs']['filename_prefix'] = 'image_model_original_20261020/' + model_id
        executor.OUT = folder
        history = executor.execute(graph, backend, 'example')
        r = requests.get(backend + '/view', params=history['outputs']['9']['images'][0], timeout=60)
        r.raise_for_status()
        (folder / 'raw.png').write_bytes(r.content)
        with Image.open(folder / 'raw.png') as source:
            image = source.convert('RGB')
            if model_id == image_pixel.MODEL_ID:
                image = image_pixel.finish(image, p['pixelSize'], p['pixelColors'])
            image.save(folder / 'example.png')
        write(folder / 'generation.json', dict(model=model_id, settings=p,
              originalCharacter=True, references=[], additionalStyle=None,
              rawSha256=hashlib.sha256(r.content).hexdigest()))
        requests.post(backend + '/free', json={'unload_models': True, 'free_memory': True}, timeout=30).raise_for_status()
        print('GENERATED', model_id, flush=True)


def publish():
    PUBLIC.mkdir(parents=True, exist_ok=True)
    items = []
    for model_id, title, note, badge in CHOICES:
        folder = OUT / model_id
        if not (folder / 'review.json').exists() or not json.loads((folder / 'review.json').read_text(encoding='utf-8')).get('publish'):
            raise RuntimeError('Inspect and review each example first: ' + model_id)
        record = json.loads((folder / 'generation.json').read_text(encoding='utf-8'))
        with Image.open(folder / 'example.png') as image:
            if model_id == image_pixel.MODEL_ID:
                image.save(PUBLIC / (model_id + '.webp'), lossless=True, method=6)
            else:
                image.thumbnail((600, 800), Image.Resampling.LANCZOS)
                image.save(PUBLIC / (model_id + '.webp'), quality=88, method=6)
        items.append(dict(id=model_id, title=title, description=note, badge=badge,
                          preview='assets/image-model-examples/' + model_id + '.webp',
                          pixel=model_id == image_pixel.MODEL_ID, originalCharacter=True,
                          sampleSize=list(Image.open(folder / 'example.png').size)))
    write(PUBLIC / 'catalog.json', dict(version=1,
          note='Same original character description; independent text generation, no identity reference.',
          examples=items))
    print('PUBLISHED', len(items), flush=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['generate', 'publish'])
    parser.add_argument('--model', action='append')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    generate(args.model) if args.stage == 'generate' else publish()
