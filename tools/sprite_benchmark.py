"""Measure sprite sheet quality on a fixed set of finished videos. Needs no GPU.

python tools/sprite_benchmark.py --output outputs/sprite-benchmark-20261109
Compares the plain sheet (even sampling, full cell) with sprite_finish output.
"""
import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

import av
import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import image_background  # noqa: E402
import sprite_finish  # noqa: E402
import sprite_loop  # noqa: E402
import sprite_temporal_matte  # noqa: E402

JOBS = {
    'quad-cannon': ('f519ffaece505a009487bcb2c90d738f', '6016c4f326d4501faa86b2e60c55be45'),
    'quad-longgun': ('4ae3f3048bb35f3b83baf9ff6ac1440e', '716380dddbf057cfb99f69b132323a51'),
    'cloak-sniper': ('0700f14ffbbd5595ae368919819cb747', '944c3820add250a39f45b60c2d0db481'),
    'silenced-rifle': ('cb8d6f34b4a75facb13f58175ed9d76a', '25f53432d5735024ae59486cf26aca48'),
    'dagger': ('9f293cd3ba0c5dfcb839519e8e4b2e48', 'fc0b85c2812d5717899a53cabebaba3c'),
    'quad-gatling': ('4a549a44499953e0ada6d252416b73e9', '18014db269325000b35312398b6a3adf'),
}
EXTRA_JOBS = {'chibi-run': '798fb0fe901a5d7f805631b27304f795', 'normal-run': '3cbeac2b05b4520a843d3604153a12d3',
              'chibi-attack': 'dab0bbe6d00e51e48632c77defae9765'}
FILES = {'gait-walk': ('outputs/gait-video-20261018/walk/walk.mp4', 'walk', True), 'gait-run': ('outputs/gait-video-20261018/run/run.mp4', 'run', True),
         'blonde-idle': ('outputs/agent-cli-test-20261109/blonde-idle-new-default/idle.mp4', 'idle', True)}
COUNT = 12


def clips():
    con = sqlite3.connect(f'file:{ROOT}/data/team.sqlite3?mode=ro', uri=True)
    def job(name, jid):
        payload, result = con.execute('select payload,result from jobs where id=?', (jid,)).fetchone()
        payload, result = json.loads(payload), json.loads(result)
        return dict(name=name, video=ROOT / result['video'].lstrip('/'), action=payload['animationType'], loop=bool(payload.get('loop')))
    out = []
    for name, (idle, attack) in JOBS.items():
        out += [dict(job(name, idle), character=name), dict(job(name, attack), character=name)]
    out += [job(name, jid) for name, jid in EXTRA_JOBS.items()]
    out += [dict(name=name, video=ROOT / path, action=action, loop=loop) for name, (path, action, loop) in FILES.items()]
    return out


def decode(path):
    with av.open(str(path)) as clip:
        fps = float(clip.streams.video[0].average_rate or 24)
        return [f.to_image().convert('RGB') for f in clip.decode(video=0)], fps


def lab_median(frame):
    a = np.asarray(frame)
    pixels = a[a[:, :, 3] >= 200][:, :3]
    if not len(pixels):
        return None
    return np.median(cv2.cvtColor(pixels[None].astype(np.float32) / 255, cv2.COLOR_RGB2LAB)[0], axis=0)


def sheet_metrics(frames, shifts, action, cell_area):
    facts = [sprite_finish.measure(f) for f in frames]
    known = [(i, f) for i, f in enumerate(facts) if f]
    height = float(np.median([f['height'] for _, f in known]))
    bottoms = np.asarray([f['bottom'] + shifts[i][1] for i, f in known], float)
    centers = np.asarray([f['center'] + shifts[i][0] for i, f in known], float)
    where = np.asarray([i for i, _ in known], float)
    boxes = [f.getchannel('A').point(lambda v: 255 if v >= 16 else 0).getbbox() for f in frames]
    area = np.mean([(b[2] - b[0]) * (b[3] - b[1]) for b in boxes if b])
    planted = np.abs(bottoms - np.median(bottoms)) <= max(2, height * sprite_finish.MAX_GROUND_SHIFT)
    return dict(groundJitterPct=round(float(bottoms[planted].std() / height * 100), 3),
                driftPct=round(float(abs(np.polyfit(where, centers, 1)[0]) * (len(frames) - 1) / height * 100), 3), occupancyPct=round(float(area / cell_area * 100), 1), characterHeight=height)


def coverage(features, indices):
    distance = sprite_finish.pose_distances(features)
    near = distance[:, indices].min(axis=1)
    peak = int(np.argmax(distance[0]))
    steps = np.asarray([distance[a, b] for a, b in zip(indices, indices[1:])])
    typical = max(float(np.median(steps)), 1e-6)
    return dict(worstMissedPose=round(float(near.max()) * 1000, 2), meanMissedPose=round(float(near.mean()) * 1000, 2), peakMissed=round(float(near[peak]) * 1000, 2), peakFrame=peak,
                seamRatio=round(float(distance[indices[-1], indices[0]]) / typical, 2), stepSpread=round(float(steps.max()) / typical, 2))


def preview(rows, path):
    """Contact sheet: each row is one clip on dark over light, with the cell box drawn."""
    tile = 96
    out = Image.new('RGB', (tile * COUNT, tile * len(rows)), (32, 34, 44))
    for y, frames in enumerate(rows):
        for x, frame in enumerate(frames[:COUNT]):
            back = Image.new('RGBA', frame.size, (235, 235, 235, 255) if y % 2 else (32, 34, 44, 255))
            back.alpha_composite(frame)
            back.thumbnail((tile, tile), Image.Resampling.LANCZOS if max(frame.size) > tile else Image.Resampling.NEAREST)
            out.paste(back.convert('RGB'), (x * tile + (tile - back.width) // 2, y * tile + (tile - back.height) // 2))
    out.save(path)


def evaluate(clip, output):
    frames, fps = decode(clip['video'])
    n, loop, action = len(frames), clip['loop'], clip['action']
    even = sprite_loop.sample_indices(n, COUNT, loop)
    picked = sprite_finish.pick(frames, COUNT, action, loop)
    chosen = picked['indices']
    cuts = {i: image_background.remove_sprite(frames[i].convert('RGBA')).convert('RGBA') for i in sorted(set(even) | set(chosen))}
    before = [cuts[i] for i in even]
    after = [cuts[i] for i in chosen]
    w, h = frames[0].size
    sheet, layout, report = sprite_finish.build(after, action, loop, sprite_finish.durations_ms(chosen, picked['end'], fps))
    folder = output / clip['name'] / action
    folder.mkdir(parents=True, exist_ok=True)
    sheet.save(folder / 'game.png')
    (folder / 'atlas.json').write_text(json.dumps(sprite_finish.atlas('game.png', action, loop, layout, report['durationMs']), indent=1), encoding='utf-8')
    cw, ch = layout['cellWidth'], layout['cellHeight']
    finished = [sheet.crop((i % layout['columns'] * cw, i // layout['columns'] * ch, (i % layout['columns'] + 1) * cw, (i // layout['columns'] + 1) * ch)) for i in range(len(after))]
    preview([before, finished], folder / 'before_after.png')
    colors = [c for c in (lab_median(f) for f in before) if c is not None]
    features = sprite_finish.pose_features(frames)
    return dict(name=clip['name'], character=clip.get('character'), action=action, loop=loop, sourceFrames=n, selection=picked['method'], sheetFrames=len(chosen),
                before=dict(sheet_metrics(before, [(0, 0)] * len(before), action, w * h), cell=[w, h], **coverage(features, even)),
                after=dict(sheet_metrics(after, report['shifts'], action, cw * ch), cell=[cw, ch], **coverage(features, chosen)),
                colorDriftMax=round(float(max(np.linalg.norm(c - colors[0]) for c in colors)), 2),
                colorDriftLast=round(float(np.linalg.norm(colors[-1] - colors[0])), 2),
                matteFlicker=round(sprite_temporal_matte.static_flicker([np.asarray(frames[i]) for i in even], [np.asarray(cuts[i]) for i in even]), 2),
                edgeContact=len(report['edgeContactFrames']), movedFrames=report['movedFrames'], pivot=[layout['pivotX'], layout['pivotY']],
                pickedIndices=[int(i) for i in chosen], firstFrameHeight=sprite_finish.measure(frames_cut(cuts, even))['height'])


def frames_cut(cuts, even):
    return cuts[even[0]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--only', help='comma-separated clip names')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    only = set(args.only.split(',')) if args.only else None
    results = []
    for clip in clips():
        if only and clip['name'] not in only:
            continue
        started = time.time()
        result = evaluate(clip, args.output)
        result['seconds'] = round(time.time() - started, 1)
        results.append(result)
        print(clip['name'], clip['action'], result['seconds'], 's', flush=True)
        (args.output / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
