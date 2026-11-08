"""Use one deterministic CPU upscaler for every layer in a temporary package."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def upscale_image(image, scale, model, torch):
    import numpy as np
    from PIL import Image
    from scipy.ndimage import distance_transform_edt
    from rigging_upscale import resize_layer
    source = image.convert('RGBA')
    safe = resize_layer(source, scale)
    alpha = np.asarray(source.getchannel('A'))
    if not alpha.any():
        return safe
    rgb = np.asarray(source)[:, :, :3].copy()
    # Extend foreground colors underneath transparency to avoid dark fringes.
    nearest = distance_transform_edt(alpha == 0, return_distances=False, return_indices=True)
    rgb[alpha == 0] = rgb[nearest[0][alpha == 0], nearest[1][alpha == 0]]
    h, w = alpha.shape
    factor = int(model.scale)
    output = np.empty((h * factor, w * factor, 3), dtype=np.uint8)
    tile, pad = 128, 16
    with torch.inference_mode():
        for y in range(0, h, tile):
            for x in range(0, w, tile):
                x0, y0 = max(0, x-pad), max(0, y-pad)
                x1, y1 = min(w, x+tile+pad), min(h, y+tile+pad)
                tensor = torch.from_numpy(rgb[y0:y1, x0:x1].copy()).permute(2, 0, 1).unsqueeze(0).float()/255
                prediction = model(tensor).squeeze(0).permute(1, 2, 0).clamp(0, 1).mul(255).round().byte().numpy()
                tw, th = min(tile, w-x), min(tile, h-y)
                output[y*factor:(y+th)*factor, x*factor:(x+tw)*factor] = prediction[
                    (y-y0)*factor:(y-y0+th)*factor, (x-x0)*factor:(x-x0+tw)*factor]
    result = Image.fromarray(output).resize(safe.size, Image.Resampling.LANCZOS).convert('RGBA')
    result.putalpha(safe.getchannel('A'))
    return result


def main():
    import torch
    from PIL import Image
    from spandrel import ModelLoader
    import rigging_super_resolution as sr
    torch.set_num_threads(min(4, os.cpu_count() or 4))
    batch = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    scale = batch['scale']
    if type(scale) is not int or scale not in (2, 4):
        raise ValueError('Invalid scale')
    model = ModelLoader(device='cpu').load_from_file(str(sr.MODEL)).eval()
    for filename in batch['files']:
        path = Path(filename)
        with Image.open(path) as image:
            result = upscale_image(image, scale, model, torch)
        result.save(path)
    print('OK', flush=True)


if __name__ == '__main__':
    main()
