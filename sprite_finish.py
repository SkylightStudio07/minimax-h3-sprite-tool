"""Game-ready sheet from cut-out frames: key poses, shared ground line, tight cell, atlas.

Frames only ever move by whole pixels, so outlines and pixel art are not resampled.
"""
import json

import cv2
import numpy as np
from PIL import Image

import sprite_loop

VERSION = 1
GROUNDED = ('idle', 'walk', 'run', 'attack', 'cast', 'hit')
ALPHA_VISIBLE = 16
ALPHA_SOLID = 128
MAX_GROUND_SHIFT = .05   # of character height; beyond this the frame is treated as a real leap
TIME_WEIGHT = .012       # keeps a long hold from leaving a gap in the timeline
MIN_STRIDE = 8           # frames; anything shorter is a half stride with the legs swapped


def pose_features(frames, size=96):
    """Foreground-only thumbnails of PIL frames, so background noise is not read as motion."""
    small = np.stack([np.asarray(f.convert('RGB').resize((size, size), Image.Resampling.BILINEAR), np.float32) / 255 for f in frames])
    background = np.median(np.concatenate((small[:, 0], small[:, -1], small[:, :, 0], small[:, :, -1]), axis=1), axis=(0, 1))
    return small * (np.max(np.abs(small - background), axis=3, keepdims=True) > .09)


def pose_distances(features):
    flat = features.reshape(len(features), -1)
    return np.stack([np.abs(flat - row).mean(axis=1) for row in flat])


def key_indices(frames, count):
    """Pick the frames that best cover a one-shot action, always keeping first, last and its peak."""
    n = len(frames)
    if count >= n:
        return list(range(n))
    distance = pose_distances(pose_features(frames))
    picked = list(dict.fromkeys([0, n - 1, int(np.argmax(distance[0])), int(np.argmax(np.diag(distance, 1))) + 1]))[:max(count, 2)]
    # Reserve about half the frames evenly in time, or one big blast takes them all from a slow windup.
    for share in range(1, count // 2 + 1):
        even = round((n - 1) * share / (count // 2 + 1))
        if even not in picked and len(picked) < count:
            picked.append(even)
    cost = distance + TIME_WEIGHT * np.abs(np.arange(n)[:, None] - np.arange(n)[None]) / max(n - 1, 1)
    while len(picked) < count:
        picked.append(int(np.argmax(cost[:, picked].min(axis=1))))
    return sorted(picked)


def cycle_indices(frames, count):
    """Sample one full stride of a walk or run, or None when the clip has no clear repeat."""
    n = len(frames)
    if n < MIN_STRIDE * 2:
        return None
    distance = pose_distances(pose_features(frames))
    profile = np.asarray([0.] + [float(np.diag(distance, lag).mean()) for lag in range(1, n - 1)])
    limit = min(len(profile) - 2, int(n * .6))
    dips = [lag for lag in range(MIN_STRIDE, limit + 1) if profile[lag] < profile[lag - 1] and profile[lag] <= profile[lag + 1]]
    if not dips:
        return None
    best = min(profile[lag] for lag in dips)
    period = next(lag for lag in dips if profile[lag] <= best * 1.2)
    if profile[period] > profile.max() * .75:
        return None
    start = int(np.argmin(np.diag(distance, period)))
    count = min(count, period)
    return dict(indices=[start + i * period // count for i in range(count)], end=start + period)


def pick(frames, count, action, loop):
    """Choose sheet frames: key poses for one-shots, one stride for gaits, even spacing otherwise."""
    n = len(frames)
    count = max(2, min(count, n))
    if not loop:
        return dict(indices=key_indices(frames, count), end=n, method='key-poses')
    if action in ('walk', 'run'):
        cycle = cycle_indices(frames, count)
        if cycle:
            return dict(cycle, method='one-stride')
    return dict(indices=sprite_loop.sample_indices(n, count, loop), end=n, method='even')


def durations_ms(indices, total, fps):
    """Each picked frame lasts until the next one, so the action keeps its real length."""
    bounds = [round(int(i) * 1000 / fps) for i in indices] + [round(total * 1000 / fps)]
    return [max(1, b - a) for a, b in zip(bounds, bounds[1:])]


def measure(frame):
    """Silhouette facts for one RGBA frame, ignoring stray specks away from the body."""
    mask = (np.asarray(frame.getchannel('A')) >= ALPHA_SOLID).astype(np.uint8)
    total, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if total < 2:
        return None
    main = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    left, width = stats[main, cv2.CC_STAT_LEFT], stats[main, cv2.CC_STAT_WIDTH]
    reach = width * .1
    keep = [i for i in range(1, total) if stats[i, cv2.CC_STAT_AREA] >= stats[main, cv2.CC_STAT_AREA] * .02
            and stats[i, cv2.CC_STAT_LEFT] < left + width + reach and stats[i, cv2.CC_STAT_LEFT] + stats[i, cv2.CC_STAT_WIDTH] > left - reach]
    body = np.isin(labels, keep)
    ys, xs = np.nonzero(body)
    top, right_edge = int(ys.min()), int(xs.max()) + 1
    left_edge = int(xs.min())
    rows = body.sum(axis=1)
    solid = np.nonzero(rows >= max(2, (right_edge - left_edge) * .03))[0]
    bottom = int(solid.max()) + 1 if len(solid) else int(ys.max()) + 1
    return dict(top=top, bottom=bottom, height=max(1, bottom - top), center=float(xs.mean()))


def plan_shifts(facts, action, loop):
    """Whole-pixel offsets per frame plus the shared ground row and center column."""
    known = [f for f in facts if f]
    if not known:
        return [(0, 0)] * len(facts), 0, 0
    grounded = action in GROUNDED
    # A whole row, so every frame lands on exactly the same line.
    ground = int(round(float(np.median([f['bottom'] for f in known])))) if grounded else known[0]['bottom']
    height = float(np.median([f['height'] for f in known]))
    center = float(np.median([f['center'] for f in known]))
    dx, dy = [0.] * len(facts), [0.] * len(facts)
    if grounded:
        for i, f in enumerate(facts):
            if f and abs(ground - f['bottom']) <= max(2, height * MAX_GROUND_SHIFT):
                dy[i] = ground - f['bottom']
    if action in ('walk', 'run') and loop and len(known) >= 3:
        where = np.asarray([i for i, f in enumerate(facts) if f], float)
        slope = np.polyfit(where, [f['center'] for f in known], 1)[0]
        middle = (len(facts) - 1) / 2
        dx = [-slope * (i - middle) if f else 0. for i, f in enumerate(facts)]
    return [(int(round(x)), int(y)) for x, y in zip(dx, dy)], ground, int(round(center))


def edge_frames(frames):
    """Frames whose visible pixels touch the source canvas, meaning something was clipped."""
    touching = []
    for i, frame in enumerate(frames):
        a = np.asarray(frame.getchannel('A')) >= ALPHA_SOLID
        if a[0].any() or a[-1].any() or a[:, 0].any() or a[:, -1].any():
            touching.append(i)
    return touching


def build(frames, action, loop, durations):
    """Return (sheet, cell layout, report) for equal-size RGBA frames."""
    facts = [measure(f) for f in frames]
    shifts, ground, center = plan_shifts(facts, action, loop)
    boxes = [f.getchannel('A').point(lambda v: 255 if v >= ALPHA_VISIBLE else 0).getbbox() for f in frames]
    shown = [(b[0] + s[0], b[1] + s[1], b[2] + s[0], b[3] + s[1]) for b, s in zip(boxes, shifts) if b]
    if not shown:
        raise ValueError('투명 프레임에서 캐릭터를 찾지 못했습니다.')
    margin = max(2, round(max(frames[0].size) * .012))
    x0, y0 = min(b[0] for b in shown) - margin, min(b[1] for b in shown) - margin
    x1, y1 = max(b[2] for b in shown) + margin, max(b[3] for b in shown) + margin
    width, height = x1 - x0, y1 - y0
    width += width % 2
    height += height % 2
    columns = min(len(frames), 8)
    rows = (len(frames) + columns - 1) // columns
    sheet = Image.new('RGBA', (width * columns, height * rows), (0, 0, 0, 0))
    for i, (frame, shift) in enumerate(zip(frames, shifts)):
        cell = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        cell.paste(frame, (shift[0] - x0, shift[1] - y0))
        sheet.paste(cell, ((i % columns) * width, (i // columns) * height))
    heights = [f['height'] for f in facts if f]
    layout = dict(columns=columns, rows=rows, cellWidth=width, cellHeight=height, pivotX=center - x0, pivotY=ground - y0)
    report = dict(version=VERSION, action=action, loop=loop, frameCount=len(frames), durationMs=[int(d) for d in durations],
                  characterHeight=int(np.median(heights)), shifts=[list(s) for s in shifts],
                  movedFrames=sum(1 for s in shifts if s != (0, 0)), edgeContactFrames=edge_frames(frames), **layout)
    return sheet, layout, report


def atlas(image_name, action, loop, layout, durations):
    """TexturePacker-style JSON hash, readable by Phaser and PixiJS, with pivot and per-frame time."""
    w, h = layout['cellWidth'], layout['cellHeight']
    pivot = dict(x=round(layout['pivotX'] / w, 4), y=round(layout['pivotY'] / h, 4))
    names = [f'{action}_{i:02d}' for i in range(len(durations))]
    frames = {}
    for i, (name, duration) in enumerate(zip(names, durations)):
        frames[name] = dict(frame=dict(x=(i % layout['columns']) * w, y=(i // layout['columns']) * h, w=w, h=h), rotated=False, trimmed=False,
                            spriteSourceSize=dict(x=0, y=0, w=w, h=h), sourceSize=dict(w=w, h=h), pivot=pivot, anchor=pivot, duration=int(duration))
    return dict(frames=frames, animations={action: names},
                meta=dict(app='Sprite Lab', version=str(VERSION), image=image_name, format='RGBA8888', scale='1', loop=bool(loop),
                          size=dict(w=w * layout['columns'], h=h * layout['rows']), pivotPixels=dict(x=layout['pivotX'], y=layout['pivotY'])))


def write(frames, action, loop, durations, png_path, json_path):
    """Write the game sheet and its atlas next to the untouched original sheets."""
    sheet, layout, report = build(frames, action, loop, durations)
    sheet.save(png_path, optimize=True)
    json_path.write_text(json.dumps(atlas(png_path.name, action, loop, layout, durations), ensure_ascii=False, indent=1), encoding='utf-8')
    return report
