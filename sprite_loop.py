"""Conservative loop trimming. No synthesis, reverse playback, or frame blending."""
import math
import shutil
from pathlib import Path

import av
import numpy as np
from PIL import Image

VERSION = 1


def sample_indices(length, count, loop):
    count = max(2, min(count, length)) if length > 1 else 1
    if loop:
        return [i * length // count for i in range(count)]
    return [round(i * (length - 1) / (count - 1)) for i in range(count)] if count > 1 else [0]


def select_interval(thumbnails, fps):
    """End is exclusive; compare the real wrap transition and both neighboring velocities."""
    pixels = np.asarray(thumbnails, dtype=np.float32) / 255.0
    n = len(pixels)
    if n < 8:
        return dict(version=VERSION, method='unchanged', startFrame=0, endFrame=n,
                    inputFrames=n, outputFrames=n, quality='needs_review', reason='too_short')
    # Downweight stationary background without assuming that the character is centered.
    background = np.median(pixels[:, [0, -1], :, :], axis=(0, 1, 2))
    foreground = np.max(np.abs(pixels - background), axis=(0, 3)) > 0.08
    moving = np.max(np.std(pixels, axis=0), axis=2) > 0.015
    weights = 0.03 + np.maximum(foreground, moving).astype(np.float32)
    features = (pixels * np.sqrt(weights)[None, :, :, None]).reshape(n, -1)
    norm = float(weights.sum() * 3)
    velocity = np.diff(features, axis=0)
    typical = float(np.median(np.sqrt(np.sum(velocity ** 2, axis=1) / norm)))

    def measure(start, end):
        wrap = features[start] - features[end - 1]
        jump = float(np.sqrt(np.sum(wrap ** 2) / norm))
        incoming, outgoing = velocity[end - 2], velocity[start]
        acceleration = float(np.sqrt((np.sum((wrap - incoming) ** 2) +
                                      np.sum((outgoing - wrap) ** 2)) / (2 * norm)))
        return jump + 0.5 * acceleration, jump

    baseline, before = measure(0, n)
    best, start, end, after = baseline, 0, n, before
    minimum = min(n, max(8, math.ceil(n * 0.65), math.ceil(fps * 0.8)))
    if baseline > 0.002:
        for a in range(n - minimum + 1):
            for b in range(a + minimum, n + 1):
                score, jump = measure(a, b)
                # Prefer longer clips and never reduce velocity mismatch by increasing the jump.
                penalized = score + baseline * 0.12 * (1 - (b - a) / n)
                if penalized < best and jump <= before:
                    best, start, end, after = penalized, a, b, jump
    changed = best < baseline * 0.85 and (start != 0 or end != n)
    if not changed:
        start, end, after = 0, n, before
    final_score, _ = measure(start, end)
    ratio = after / max(typical, 0.002)
    quality = 'good' if ratio <= 1.8 and final_score <= max(typical * 3, 0.008) else 'fair' if ratio <= 3 else 'needs_review'
    return dict(version=VERSION, method='trim' if changed else 'unchanged',
                startFrame=start, endFrame=end, inputFrames=n, outputFrames=end-start,
                inputSeconds=round(n/fps, 3), outputSeconds=round((end-start)/fps, 3),
                quality=quality, seamBefore=round(before, 6), seamAfter=round(after, 6),
                seamRatio=round(ratio, 3), improvement=round(max(0, 1-after/max(before, 1e-9)), 3))


def optimize_video(source, destination):
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError('루프 보정은 원본과 다른 파일에 저장해야 합니다.')
    thumbnails = []
    with av.open(str(source)) as container:
        rate = container.streams.video[0].average_rate or 24
        for frame in container.decode(video=0):
            image = frame.to_image().convert('RGB')
            image.thumbnail((96, 96), Image.Resampling.BILINEAR)
            thumbnails.append(np.asarray(image))
    if not thumbnails:
        raise ValueError('영상에서 프레임을 읽지 못했습니다.')
    report = select_interval(thumbnails, float(rate))
    destination.parent.mkdir(parents=True, exist_ok=True)
    if report['method'] == 'unchanged':
        shutil.copyfile(source, destination)
        return report
    with av.open(str(source)) as container, av.open(str(destination), 'w') as output:
        src = container.streams.video[0]
        stream = output.add_stream('libx264', rate=rate)
        stream.width, stream.height = src.width, src.height
        stream.pix_fmt = 'yuv420p'
        stream.options = {'crf': '18', 'preset': 'medium'}
        for i, frame in enumerate(container.decode(video=0)):
            if i >= report['endFrame']:
                break
            if i < report['startFrame']:
                continue
            clean = av.VideoFrame.from_image(frame.to_image())
            for packet in stream.encode(clean):
                output.mux(packet)
        for packet in stream.encode():
            output.mux(packet)
    return report
