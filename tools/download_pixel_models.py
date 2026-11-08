"""Download the pinned local pixel-art recipe; publish only after size/SHA256 verification."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]

def main():
    entries=json.loads((ROOT/'DOCS/model-licenses/pixel-art-xl/files.json').read_text(encoding='utf-8'))
    for item in entries:
        target=ROOT/'ComfyUI/models'/item['target'];target.parent.mkdir(parents=True,exist_ok=True)
        if target.is_file():
            with target.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
            if digest!=item['sha256']:raise RuntimeError('Existing model hash mismatch: '+target.name)
            print('Verified',target.name,flush=True);continue
        url=f"https://huggingface.co/{item['repo']}/resolve/{item['revision']}/{item['filename']}"
        size=item['size'];part=target.with_suffix('.download')
        print('Downloading',target.name,size,flush=True)
        def fetch(bounds):
            start,end=bounds;segment=target.with_suffix(f'.segment-{start}-{end}')
            if segment.is_file() and segment.stat().st_size==end-start+1:return segment
            with requests.get(url,headers={'Range':f'bytes={start}-{end}'},stream=True,timeout=(30,120)) as r:
                r.raise_for_status()
                if r.status_code!=206 or not r.headers.get('Content-Range','').startswith(f'bytes {start}-{end}/'):
                    raise RuntimeError('Download server did not honor byte range')
                with segment.open('wb') as out:
                    for chunk in r.iter_content(4*1024*1024):out.write(chunk)
            if segment.stat().st_size!=end-start+1:raise RuntimeError('Incomplete model segment')
            return segment
        bounds=[(s,min(s+128*1024*1024,size)-1) for s in range(0,size,128*1024*1024)]
        with ThreadPoolExecutor(max_workers=4) as pool,part.open('wb') as out:
            for segment in pool.map(fetch,bounds):
                with segment.open('rb') as f:
                    while chunk:=f.read(8*1024*1024):out.write(chunk)
                print(target.name,out.tell(),size,flush=True)
        with part.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        if part.stat().st_size!=size or digest!=item['sha256']:raise RuntimeError('Model hash mismatch')
        part.replace(target)
        for start,end in bounds:target.with_suffix(f'.segment-{start}-{end}').unlink(missing_ok=True)
        print('Installed',target.name,flush=True)

if __name__=='__main__':main()
