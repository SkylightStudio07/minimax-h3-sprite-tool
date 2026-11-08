"""Pinned LoRA download with SHA256 verification; leave all existing weights intact."""
import hashlib,json,sys
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]
REV='43a74557ac3f6539db8e0f2a959d03feb7a81480'
NAME='minimax_h3_turbo_v4_step600_ema.safetensors'
SHA='5f3a626cd72c93a8b9318d6760c510bc5092d2ab13aaba1f932c5bab07a416d3'
SIZE=779849816
OUT=ROOT/'outputs/turbo-v4-comparison-20261108'

def main():
    OUT.mkdir(exist_ok=True)
    dest=ROOT/'ComfyUI/models/loras'/NAME
    url=f'https://huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora/resolve/{REV}/{NAME}'
    if not dest.exists():
        temp=dest.with_suffix('.download')
        with requests.get(url,stream=True,timeout=(20,90)) as r:
            r.raise_for_status()
            with temp.open('wb') as f:
                total=0;last=0
                for chunk in r.iter_content(4*1024*1024):
                    f.write(chunk);total+=len(chunk)
                    if total-last>100*1024**2:
                        print('DOWNLOAD_MB',round(total/1024**2),flush=True);last=total
        assert temp.stat().st_size==SIZE
        assert hashlib.file_digest(temp.open('rb'),'sha256').hexdigest()==SHA
        temp.replace(dest)
    with dest.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
    assert actual==SHA and dest.stat().st_size==SIZE
    record=dict(repository='larryvrh/MiniMax-H3-Turbo-Lora',revision=REV,file=NAME,sha256=SHA,bytes=SIZE,verified=True,existingWeightsPreserved=True)
    (OUT/'installation.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print('INSTALLED_VERIFIED',dest,flush=True)

if __name__=='__main__':main()
