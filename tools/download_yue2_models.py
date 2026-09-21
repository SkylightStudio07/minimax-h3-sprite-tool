"""Download YuE2 model snapshots into the isolated local runtime."""
from pathlib import Path

from huggingface_hub import snapshot_download


ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = ROOT / "yue2-runtime" / "models"

for repo, name in (("m-a-p/YuE2-3B", "YuE2-3B"), ("m-a-p/YuE2-Vae", "YuE2-Vae")):
    destination = MODEL_ROOT / name
    destination.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {repo} -> {destination}")
    snapshot_download(repo_id=repo, local_dir=destination)

print("YuE2 models are ready.")
