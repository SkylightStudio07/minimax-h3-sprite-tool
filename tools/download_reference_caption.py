"""Download the official caption model independently of ComfyUI and music."""
import json
from pathlib import Path
from huggingface_hub import snapshot_download

ROOT=Path(__file__).resolve().parents[1]
REPO='Qwen/Qwen3-VL-2B-Instruct'
REVISION='89644892e4d85e24eaac8bacfd4f463576704203'
DEST=ROOT/'models/reference-caption/qwen3-vl-2b-instruct'

if __name__=='__main__':
    DEST.mkdir(parents=True,exist_ok=True)
    print('Downloading official Qwen3-VL 2B Instruct: 4,255,140,312 weight bytes',flush=True)
    snapshot_download(REPO,revision=REVISION,local_dir=DEST,
        allow_patterns=['*.json','*.txt','*.jinja','*.safetensors','LICENSE*'],max_workers=2)
    weight=DEST/'model.safetensors'
    if weight.stat().st_size!=4255140312:raise RuntimeError('Unexpected weight size')
    manifest=DEST/'installation.json'
    temp=manifest.with_suffix('.tmp')
    temp.write_text(json.dumps(dict(repo=REPO,revision=REVISION,weightBytes=weight.stat().st_size,license='Apache-2.0'),indent=2),encoding='utf-8')
    temp.replace(manifest)
    print('Download complete. Run a reference caption smoke test before reporting inference verified.',flush=True)
