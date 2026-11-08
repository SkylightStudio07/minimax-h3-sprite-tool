"""Use the existing resumable, checksum-verified downloader for one pinned model."""
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import sprite_workflows as profiles
import download_image_models as downloader

if __name__=='__main__':
    downloader.FILES=[('FastVideo/FastVideo-FastH3-Comfy',profiles.FAST_REVISION,
        'diffusion_models/'+profiles.FAST_FILENAME,'diffusion_models',profiles.FAST_BYTES,profiles.FAST_SHA256)]
    downloader.main()
