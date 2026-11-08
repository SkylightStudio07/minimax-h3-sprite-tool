"""CPU-only comparison of per-frame cutouts vs temporal stabilisation. Writes only to its own folder."""
import json
import sys
import time
from pathlib import Path

import av
import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sprite_temporal_matte as matte

cv2.setNumThreads(2)
OUT = ROOT / 'outputs/temporal-matte-experiment-20261108'
V2 = ROOT / 'outputs/character-variations-cutout-v2-20261102'
BLONDE = ROOT / 'outputs/blonde-from-raw-20261102'
CASES = [
    ('pistol-a-attack', V2 / 'pistol-a/attack', False),
    ('pistol-a-idle', V2 / 'pistol-a/idle', True),
    ('blonde-idle', BLONDE / 'idle', True),
    ('blonde-attack', BLONDE / 'attack', False),
]


def load(folder):
    with av.open(str(folder / 'raw.mp4')) as video:
        raws = [frame.to_ndarray(format='rgb24') for frame in video.decode(video=0)]
    cuts = [np.array(Image.open(path).convert('RGBA')) for path in sorted((folder / 'all-frames').glob('frame-*.png'))]
    return raws[:len(cuts)], cuts


def over(rgba, colour=(20, 36, 54)):
    image = Image.new('RGBA', (rgba.shape[1], rgba.shape[0]), colour + (255,))
    image.alpha_composite(Image.fromarray(rgba))
    return image.convert('RGB')


def strip(cuts, fixed, name, indices, box):
    scale = 3
    width, height = (box[2] - box[0]) * scale, (box[3] - box[1]) * scale
    sheet = Image.new('RGB', (width * len(indices), height * 2 + 2), (200, 0, 80))
    draw = ImageDraw.Draw(sheet)
    for col, index in enumerate(indices):
        for row, frames in enumerate((cuts, fixed)):
            crop = over(frames[index]).crop(box).resize((width, height), Image.Resampling.NEAREST)
            sheet.paste(crop, (col * width, row * (height + 2)))
            draw.text((col * width + 4, row * (height + 2) + 4), f"{'BEFORE' if row == 0 else 'AFTER'} {index}", fill=(255, 255, 0))
    sheet.save(OUT / f'{name}-strip.png')


def save_webp(frames, path):
    images = [Image.fromarray(frame) for frame in frames]
    images[0].save(path, save_all=True, append_images=images[1:], duration=42, loop=0, lossless=True, method=2)


def main():
    OUT.mkdir(exist_ok=True)
    report = []
    for name, folder, loop in CASES:
        raws, cuts = load(folder)
        started = time.time()
        fixed = matte.stabilize(raws, cuts, loop=loop)
        seconds = round(time.time() - started, 1)
        changed = [float(np.mean(np.abs(a[:, :, 3].astype(int) - b[:, :, 3].astype(int)))) for a, b in zip(cuts, fixed)]
        interior = 0
        for a, b in zip(cuts, fixed):
            solid = cv2.erode((a[:, :, 3] == 255).astype(np.uint8), np.ones((3, 3), np.uint8), iterations=5) > 0
            interior += int(np.count_nonzero(np.any(a[solid] != b[solid], axis=1)))
        row = dict(name=name, frames=len(cuts), seconds=seconds, flickerBefore=round(matte.static_flicker(raws, cuts), 3),
                   flickerAfter=round(matte.static_flicker(raws, fixed), 3), meanAlphaChange=round(float(np.mean(changed)), 3), interiorPixelsChanged=interior)
        row['reductionPercent'] = round(100 * (1 - row['flickerAfter'] / max(row['flickerBefore'], 1e-6)), 1)
        report.append(row)
        print(json.dumps(row), flush=True)
        alpha = np.max(np.stack([c[:, :, 3] for c in cuts]), axis=0)
        ys, xs = np.nonzero(alpha > 127)
        centre_y, left = int(ys.min() + (ys.max() - ys.min()) * .12), int(np.median(xs))
        box = (max(left - 90, 0), max(centre_y - 70, 0), min(left + 90, alpha.shape[1]), min(centre_y + 110, alpha.shape[0]))
        step = max(len(cuts) // 3, 1)
        base = step
        strip(cuts, fixed, name, [base, base + 1, base + 2, base + 3], box)
        side = np.concatenate((np.array(over(cuts[0]).convert('RGBA')), np.array(over(fixed[0]).convert('RGBA'))), axis=1)
        pairs = [np.concatenate((np.array(over(a).convert('RGBA')), np.array(over(b).convert('RGBA'))), axis=1) for a, b in zip(cuts, fixed)]
        del side
        save_webp(pairs, OUT / f'{name}-before-after.webp')
        destination = OUT / name / 'all-frames'
        destination.mkdir(parents=True, exist_ok=True)
        for index, frame in enumerate(fixed):
            Image.fromarray(frame).save(destination / f'frame-{index:03d}.png')
    (OUT / 'report.json').write_text(json.dumps(dict(revision=matte.REVISION, cases=report), ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
