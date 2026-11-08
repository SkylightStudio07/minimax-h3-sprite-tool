"""Pinned download only; real-image acceptance enables the feature separately."""
import hashlib
from pathlib import Path
import sys
import requests

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from image_background import MODEL, REVISION, SHA256


def main():
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    if MODEL.exists():
        with MODEL.open('rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()==SHA256:
                print('Already installed; visual validation still required',flush=True)
                return
        raise RuntimeError('Existing model hash mismatch')
    target=MODEL.with_suffix('.download')
    url=f'https://huggingface.co/skytnt/anime-seg/resolve/{REVISION}/isnetis.onnx'
    print('Downloading anime foreground model: 176069933 bytes',flush=True)
    with requests.get(url,stream=True,timeout=(30,120)) as r:
        r.raise_for_status()
        with target.open('wb') as f:
            for chunk in r.iter_content(4*1024*1024):
                f.write(chunk)
    with target.open('rb') as f:
        if hashlib.file_digest(f,'sha256').hexdigest()!=SHA256:
            raise RuntimeError('Downloaded model hash mismatch')
    target.replace(MODEL)
    print('Installed; visual validation still required',flush=True)


if __name__=='__main__':main()
