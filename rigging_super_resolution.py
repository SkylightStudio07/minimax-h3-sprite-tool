"""AI detail upscaling in an isolated CPU process; no generation GPU use."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / 'models/live2d-upscale'
MODEL = MODEL_DIR / 'RealESRGAN_x4plus_anime_6B.pth'


def status():
    try:
        manifest = json.loads((MODEL_DIR / 'installation.json').read_text(encoding='utf-8'))
        ready = (MODEL.stat().st_size == 17938799 and manifest.get('bytes') == 17938799
                 and bool(manifest.get('sha256')) and importlib.util.find_spec('spandrel') is not None)
    except (OSError, ValueError, TypeError):
        ready = False
    return dict(aiReady=ready, model='RealESRGAN anime 6B', device='cpu',
                methods=['lanczos'] + (['anime-ai'] if ready else []))


def validate_method(method):
    if method not in ('lanczos', 'anime-ai'):
        raise ValueError('화질 개선 방식을 확인하세요.')
    if method == 'anime-ai' and not status()['aiReady']:
        raise ValueError('AI 화질 개선 모델을 설치 중입니다. 잠시 후 새로고침하거나 일반 확대를 선택하세요.')
    return method


def upscale_files(files, scale):
    validate_method('anime-ai')
    with tempfile.TemporaryDirectory(prefix='rig-ai-batch-') as name:
        batch = Path(name) / 'batch.json'
        batch.write_text(json.dumps(dict(files=[str(p.resolve()) for p in files], scale=scale)), encoding='utf-8')
        env = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONIOENCODING='utf-8')
        try:
            result = subprocess.run([sys.executable, str(ROOT / 'tools/run_live2d_upscale.py'), str(batch)],
                env=env, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=900,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError('AI 확대 시간이 초과됐습니다. 원본은 유지됩니다.') from error
        if result.returncode:
            raise RuntimeError('AI 레이어 확대에 실패했습니다. 원본은 유지됩니다.')
