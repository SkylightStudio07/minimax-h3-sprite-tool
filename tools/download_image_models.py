"""Download pinned official image models, verify SHA256, then publish atomically."""
import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ('circlestone-labs/Anima', 'f973fc41ec7545364ac9776c2440285f43ff2a30', 'split_files/diffusion_models/anima-turbo-v1.1.safetensors', 'diffusion_models', 4182230656, 'fba11953276b57edf59d1dc4f1857ac05aa079c56f982b4d7c20298d57d3f7eb'),
    ('circlestone-labs/Anima', 'f973fc41ec7545364ac9776c2440285f43ff2a30', 'split_files/text_encoders/qwen_3_06b_base.safetensors', 'text_encoders', 1192135096, 'cd2a512003e2f9f3cd3c32a9c3573f820bb28c940f73c57b1ddaa983d9223eba'),
    ('circlestone-labs/Anima', 'f973fc41ec7545364ac9776c2440285f43ff2a30', 'split_files/vae/qwen_image_vae.safetensors', 'vae', 253806246, 'a70580f0213e67967ee9c95f05bb400e8fb08307e017a924bf3441223e023d1f'),
    ('cagliostrolab/animagine-xl-4.0', '2b7c1b397761bf5bd3cc42e5b39ec99314a75a96', 'animagine-xl-4.0-opt.safetensors', 'checkpoints', 6938350040, '6327eca98bfb6538dd7a4edce22484a1bbc57a8cff6b11d075d40da1afb847ac'),
]

def main():
    for repo, revision, remote, category, size, digest in FILES:
        target = ROOT / 'ComfyUI/models' / category / Path(remote).name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            with target.open('rb') as f:
                if hashlib.file_digest(f, 'sha256').hexdigest() == digest:
                    print('Verified', target.name, flush=True)
                    continue
            raise RuntimeError('Existing model checksum mismatch: '+str(target))
        part = target.with_suffix('.download')
        offset = part.stat().st_size if part.exists() else 0
        remote_url=f'https://huggingface.co/{repo}/resolve/{revision}/{remote}'
        segments=[(start,min(start+128*1024*1024,size)-1) for start in range(offset,size,128*1024*1024)]
        def fetch_segment(bounds):
            start,end=bounds
            segment=target.with_suffix(f'.segment-{start}-{end}')
            if segment.exists() and segment.stat().st_size==end-start+1: return segment
            with requests.get(remote_url,headers={'Range':f'bytes={start}-{end}'},stream=True,timeout=(30,120)) as response:
                response.raise_for_status()
                if response.status_code!=206 or not response.headers.get('Content-Range','').startswith(f'bytes {start}-{end}/'):
                    raise RuntimeError('Download server did not honor byte range')
                with segment.open('wb') as out:
                    for chunk in response.iter_content(4*1024*1024): out.write(chunk)
            if segment.stat().st_size!=end-start+1: raise RuntimeError('Incomplete segment')
            return segment
        with ThreadPoolExecutor(max_workers=6) as pool,part.open('ab') as out:
            for segment in pool.map(fetch_segment,segments):
                with segment.open('rb') as source:
                    while chunk:=source.read(8*1024*1024):out.write(chunk)
                out.flush()
                segment.unlink()
                print('Downloaded',target.name,out.tell(),size,flush=True)
        with part.open('rb') as f:
            if part.stat().st_size != size or hashlib.file_digest(f,'sha256').hexdigest() != digest:
                raise RuntimeError('Download checksum mismatch: '+str(part))
        part.replace(target)
        print('Installed',target.name,size,flush=True)

if __name__ == '__main__':
    main()
