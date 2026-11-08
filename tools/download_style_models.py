"""Download allowlisted style weights in background, verify SHA256, do not enable them."""
import hashlib
import json
import os
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]

def main():
    api_key=os.environ.get('CIVITAI_API_KEY','').strip()
    headers={'Authorization': 'Bearer '+api_key} if api_key else {}
    styles=json.loads((ROOT/'web/assets/image-styles.json').read_text(encoding='utf-8'))['styles']
    for s in styles:
        target=ROOT/'ComfyUI/models/loras'/s['filename']
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            with target.open('rb') as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()==s['sha256']:
                    print('Verified',s['id'],flush=True);continue
            raise RuntimeError('Existing file hash mismatch: '+s['id'])
        print('Downloading',s['id'],s['bytes'],flush=True)
        part=target.with_suffix('.download')
        with requests.get(s['downloadUrl'],headers=headers,stream=True,timeout=(30,120)) as response:
            if response.status_code==401:
                raise RuntimeError('Civitai authentication required. Set CIVITAI_API_KEY locally and retry; do not paste the key into chat.')
            response.raise_for_status()
            with part.open('wb') as stream:
                for block in response.iter_content(4*1024*1024):stream.write(block)
        with part.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=s['sha256']:raise RuntimeError('Download hash mismatch: '+s['id'])
        part.replace(target)
        print('Installed; validation pending',s['id'],flush=True)

if __name__=='__main__':main()
