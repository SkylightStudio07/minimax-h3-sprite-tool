"""Pinned SDXL OpenPose download; run separately from the web server."""
from pathlib import Path
import download_image_models as downloader

# Keep the original filename under a dedicated model folder to avoid collisions.
downloader.FILES = [(
    'xinsir/controlnet-openpose-sdxl-1.0',
    '23f966cd5cfdd3f7729c903e243d87152162d2b7',
    'diffusion_pytorch_model.safetensors',
    'controlnet/xinsir-openpose-sdxl',
    2502139104,
    'b8524e557a7df60d081f5d4a0eb109967d107df217943bf88c2d99b9ebcc06c5',
)]

if __name__ == '__main__':
    print('Starting SDXL OpenPose download: 2,502,139,104 bytes', flush=True)
    downloader.main()
