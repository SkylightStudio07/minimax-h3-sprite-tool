from __future__ import annotations

from pathlib import Path
import os

from huggingface_hub import hf_hub_download


ROOT = Path(__file__).resolve().parents[1]
AMD = os.environ.get("SPRITE_BACKEND") == "amd"
COMFY = ROOT / ("ComfyUI-amd" if AMD else "ComfyUI")
LICENSE_MARKER = ROOT / "MINIMAX_H3_LICENSE_APPROVED.txt"

FILES = [
    ("Comfy-Org/MiniMax-H3", "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors"),
    ("Comfy-Org/MiniMax-H3", "text_encoders/" + ("qwen3vl_32b_minimax_h3_int8_convrot.safetensors" if AMD else "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors")),
    ("Comfy-Org/MiniMax-H3", "vae/minimax_h3_video_vae_fp16.safetensors"),
    ("Comfy-Org/MiniMax-H3", "vae/minimax_h3_audio_vae_fp32.safetensors"),
    ("Comfy-Org/MiniMax-H3", "loras/minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors"),
]


def main() -> None:
    if not LICENSE_MARKER.exists():
        raise SystemExit("License confirmation is missing. Run download_h3_models.bat first.")

    print("Downloading MiniMax H3 FL2VA models (tens of GB; AMD INT8 encoder requires more storage).")
    for repo_id, filename in FILES:
        destination = COMFY / "models" / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.stat().st_size > 1024 * 1024:
            print(f"Already present: {destination.name}")
            continue
        print(f"Downloading: {filename}")
        downloaded = Path(
            hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=COMFY / "models",
            )
        )
        print(f"Ready: {downloaded}")
    print("All MiniMax H3 model files are ready.")


if __name__ == "__main__":
    main()
