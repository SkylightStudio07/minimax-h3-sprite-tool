"""Fetch the official lightweight anime upscaler independently."""
import hashlib
import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'models/live2d-upscale'
URL = 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth'

if __name__ == '__main__':
    DEST.mkdir(parents=True, exist_ok=True)
    target = DEST / 'RealESRGAN_x4plus_anime_6B.pth'
    temp = target.with_suffix('.part')
    response = requests.get(URL, stream=True, timeout=(20, 90))
    response.raise_for_status()
    with temp.open('wb') as stream:
        for chunk in response.iter_content(1024 * 1024):
            stream.write(chunk)
    if temp.stat().st_size != 17938799:
        raise RuntimeError('Unexpected model size')
    digest = hashlib.sha256(temp.read_bytes()).hexdigest()
    temp.replace(target)
    (DEST / 'installation.json').write_text(json.dumps(dict(
        source=URL, sha256=digest, bytes=17938799,
        model='RealESRGAN_x4plus_anime_6B', license='BSD-3-Clause'), indent=2), encoding='utf-8')
    print('Anime upscaler installed from official release.', flush=True)
