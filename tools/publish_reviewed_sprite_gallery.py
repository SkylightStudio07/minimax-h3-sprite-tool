"""Idempotently publish reviewed handoffs, never arbitrary test directories.

CPU-only staging precedes a single SQLite transaction. Existing jobs are preserved.
Run without flags to prepare/validate; --publish backs up SQLite and registers jobs.
"""
import argparse
import hashlib
import json
import math
import shutil
import sqlite3
import sys
import time
import uuid
from fractions import Fraction
from pathlib import Path

import av
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'outputs/reviewed-sprite-gallery-20261025.json'
DB = ROOT / 'data/team.sqlite3'
NAMESPACE = uuid.UUID('ef8892b6-d930-4902-9bee-54aa6c6b7ee4')
ALLOWED = ('prompt', 'seed', 'width', 'height', 'duration', 'workflowId', 'samplingMode',
           'motionStrength', 'motionPadding', 'facing', 'subjectType', 'pixelOutput',
           'pixelColorLock', 'combatEffect', 'effectStrength', 'effectDescription',
           'removeBackground', 'backgroundRemoval', 'negativeEnabled', 'blinkMode')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def curated():
    pairs = [
        ('cp01', 'CP01 · 단검', 'cp01-alive-idle40-20261023', 'cp01-clean-sweep-20261023'),
        ('cp02', 'CP02 · 방패와 장병기', 'cp02-grounded-motion-20261024', None),
        ('robot-dog', '견마 로봇', 'quadruped-robot-motion-20261024', None),
        ('rifleman', '가면 소총수', 'rifleman-scan-idle-20261024', 'masked-rifleman-motion-20261024'),
        ('violet-caster', '보랏빛 마법사', 'violet-caster-matte-v2-20261024', None),
        ('horned-beast', '뿔 달린 야수', 'horned-beast-motion-20261024', None),
        ('dimensional-horror', '차원의 공포', 'dimensional-horror-standard-20261024', None),
    ]
    for case, label in [('01-crystal-guardian', '결정 수호자'), ('02-defensive-guardian', '관문 수호자 · 방어형'),
                        ('03-heavy-gun-drone', '중화기 드론'), ('04-fast-gun-drone', '고속 사격 드론')]:
        pairs.append((case, label, 'guardian-drone-batch-20261024/' + case, None))
    for case, label in [('01-etienne-vasseur', '에티엔 바쇠르'), ('02-desmond-kilroy', '데즈먼드 킬로이'),
                        ('03-van-rieden', '반 리든')]:
        pairs.append((case, label, 'big-three-subtle-final-20261024/' + case, None))
    batch = ROOT / 'outputs/soldier-robot-batch-20261025'
    validation = batch / 'batch-validation.json'
    if validation.exists():
        reviewed = load(validation)
        if reviewed.get('fileChecksPassed') and reviewed.get('visualReview') == 'completed':
            for folder in sorted(p for p in batch.iterdir() if p.is_dir() and (p / 'idle/settings.json').exists()):
                settings = load(folder / 'idle/settings.json')
                pairs.append(('soldier-robot-' + folder.name, settings['label'],
                              'soldier-robot-batch-20261025/' + folder.name, None))
    for key, label, idle, attack in pairs:
        for action in ('idle', 'attack'):
            folder = ROOT / 'outputs' / (idle if action == 'idle' else (attack or idle)) / action
            yield dict(key=key + '-' + action, title=label + ' · ' + ('대기' if action == 'idle' else '공격'),
                       action=action, folder=folder)
    for example in load(ROOT / 'web/assets/sprite-examples/catalog.json')['examples']:
        yield dict(key='example-' + example['id'], title=example['title'], action=example['action'], example=example)


def pack(images, dest):
    count = len(images)
    cols = min(8, count)
    w, h = images[0].size
    sheet = Image.new('RGBA', (cols * w, math.ceil(count / cols) * h))
    for i, im in enumerate(images):
        assert im.size == (w, h)
        sheet.paste(im, (i % cols * w, i // cols * h))
    sheet.save(dest)


def prepare_sheet(item, dest):
    if 'example' in item:
        e = item['example']
        images, timing = [], []
        with Image.open(ROOT / 'web' / e['animation']) as animation:
            for i in range(animation.n_frames):
                animation.seek(i)
                im = animation.convert('RGBA')
                if e.get('pixelGrid'):
                    im = im.resize((e['pixelGrid']['width'], e['pixelGrid']['height']), Image.Resampling.NEAREST)
                images.append(im)
                timing.append(animation.info.get('duration', 125))
        pack(images, dest)
        return timing, e['recipe'], sha(ROOT / 'web' / e['animation'])
    folder = item['folder']
    settings = load(folder / 'settings.json')
    for stem in ('native-frames', 'native-loop'):
        meta = folder / (stem + '.json')
        source = folder / ('native-sheet.png' if stem == 'native-frames' else 'native-loop-sheet.png')
        if meta.exists() and source.exists():
            doc = load(meta)
            assert doc['columns'] == 8
            shutil.copy2(source, dest)
            assert sha(source) == sha(dest)
            return doc['durationMs'], settings, sha(source)
    # The CP01 attack was deliberately trimmed to its clean forward action.
    selection = load(folder / 'selection.json')
    images = []
    for i in range(selection['start'], selection['end'] + 1):
        with Image.open(folder / 'all-frames' / f'frame-{i:03d}.png') as im:
            images.append(im.convert('RGBA'))
    pack(images, dest)
    timing = [round((i + 1) * 1000 / 24) - round(i * 1000 / 24) for i in range(len(images))]
    return timing, settings, sha(dest)


def preview(sheet_path, timing, video_path, poster_path, pixel=False):
    """CFR preview of cleaned RGBA cells, without invoking any model/GPU."""
    with Image.open(sheet_path) as sheet:
        count = len(timing)
        cols, rows = min(8, count), math.ceil(count / min(8, count))
        assert sheet.width % cols == 0 and sheet.height % rows == 0
        w, h = sheet.width // cols, sheet.height // rows
        scale = min(512 / w, 512 / h)
        size = (max(2, round(w * scale) // 2 * 2), max(2, round(h * scale) // 2 * 2))
        bg = Image.new('RGB', size, (29, 34, 45))
        draw = ImageDraw.Draw(bg)
        for y in range(0, size[1], 24):
            for x in range(0, size[0], 24):
                if (x // 24 + y // 24) % 2:
                    draw.rectangle((x, y, x + 23, y + 23), fill=(36, 42, 54))
        ends, total = [], 0
        for ms in timing:
            total += ms
            ends.append(total)
        index, previous, image = 0, -1, None
        with av.open(str(video_path), 'w') as output:
            stream = output.add_stream('libx264', rate=24)
            stream.width, stream.height = size
            stream.pix_fmt = 'yuv420p'
            stream.options = {'crf': '18', 'preset': 'fast', 'threads': '2'}
            for frame_no in range(math.ceil(total * 24 / 1000)):
                while index < count - 1 and frame_no * 1000 / 24 >= ends[index]:
                    index += 1
                if index != previous:
                    x, y = index % cols * w, index // cols * h
                    fg = sheet.crop((x, y, x + w, y + h)).convert('RGBA')
                    fg = fg.resize(size, Image.Resampling.NEAREST if pixel else Image.Resampling.LANCZOS)
                    image = bg.copy()
                    image.paste(fg, (0, 0), fg)
                    if frame_no == 0:
                        image.save(poster_path, quality=92)
                    previous = index
                frame = av.VideoFrame.from_image(image)
                frame.pts, frame.time_base = frame_no, Fraction(1, 24)
                for packet in stream.encode(frame):
                    output.mux(packet)
            for packet in stream.encode():
                output.mux(packet)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    prepared = []
    for item in curated():
        jid = uuid.uuid5(NAMESPACE, item['key']).hex
        folder = ROOT / 'outputs/results' / jid
        folder.mkdir(parents=True, exist_ok=True)
        staging = folder / 'gallery-import.json'
        if staging.exists():
            record = load(staging)
            assert record['key'] == item['key']
        else:
            timing, settings, source_hash = prepare_sheet(item, folder / 'sheet.png')
            assert 1 <= len(timing) <= 128 and all(t > 0 for t in timing)
            pixel = bool(settings.get('pixelOutput'))
            preview(folder / 'sheet.png', timing, folder / 'preview.mp4', folder / 'gallery-poster-v1.jpg', pixel)
            payload = {k: settings[k] for k in ALLOWED if k in settings}
            payload.update(jobType='video', animationType=item['action'], resultTitle=item['title'],
                           frameCount=max(2, min(64, int(settings.get('frameCount', 24)))),
                           loop=bool(settings.get('loop', item['action'] in ('idle', 'walk', 'run'))),
                           duration=settings.get('duration', 3), importedSource='reviewed:' + item['key'])
            prefix = f'/outputs/results/{jid}/'
            result = dict(video=prefix + 'preview.mp4', spriteSheet=prefix + 'sheet.png',
                          transparentSheet=prefix + 'sheet.png', frameCount=len(timing), sheetTimingMs=timing)
            record = dict(key=item['key'], id=jid, title=item['title'], payload=payload, result=result,
                          sheetSha256=sha(folder / 'sheet.png'), reviewedSourceSha256=source_hash,
                          source=str(item.get('folder') or item['example']['animation']))
            staging.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        # Reusable generation settings and the delivered sheet's actual count are
        # separate: native handoffs can exceed the generator's 64-cell selector.
        settings = item['example']['recipe'] if 'example' in item else load(item['folder'] / 'settings.json')
        record['payload']['frameCount'] = max(2, min(64, int(settings.get('frameCount', 24))))
        record['payload']['duration'] = settings.get('duration', 3)
        staging.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        assert sha(folder / 'sheet.png') == record['sheetSha256']
        with Image.open(folder / 'sheet.png') as sheet:
            assert sheet.mode == 'RGBA' and sheet.width * sheet.height <= 64_000_000
        with av.open(str(folder / 'preview.mp4')) as clip:
            assert clip.streams.video[0].frames > 0
        prepared.append(record)
        print('Prepared:', item['title'], record['result']['frameCount'], flush=True)
    inserted = 0
    if args.publish:
        backup = ROOT / 'outputs/gallery-publication-backup-20261025' / ('team-' + time.strftime('%H%M%S') + '.sqlite3')
        backup.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DB, timeout=30) as con:
            with sqlite3.connect(backup) as dest:
                con.backup(dest)
            user = con.execute("SELECT id FROM users WHERE id=1 AND username='skylight' AND state='approved' AND role='admin'").fetchone()
            assert user, 'Expected approved owner missing'
            con.execute('BEGIN IMMEDIATE')
            now = time.time()
            for i, r in enumerate(prepared):
                existing = con.execute('SELECT payload FROM jobs WHERE id=?', (r['id'],)).fetchone()
                if existing:
                    assert load_payload(existing[0]).get('importedSource') == r['payload']['importedSource']
                    p = load_payload(existing[0])
                    p.update({k: r['payload'][k] for k in ('frameCount', 'duration')})
                    con.execute('UPDATE jobs SET payload=? WHERE id=?', (json.dumps(p, ensure_ascii=False), r['id']))
                    continue  # Preserve later renames/edits/withdrawals; never duplicate or republish.
                con.execute('INSERT INTO jobs(id,user_id,state,created,updated,payload,result) VALUES(?,?,?,?,?,?,?)',
                            (r['id'], user[0], 'complete', now - i * .001, now - i * .001,
                             json.dumps(r['payload'], ensure_ascii=False), json.dumps(r['result'])))
                inserted += 1
    REPORT.write_text(json.dumps(dict(published=args.publish, inserted=inserted, total=len(prepared),
                                     entries=prepared), ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(published=args.publish, inserted=inserted, total=len(prepared), report=str(REPORT))))


def load_payload(value):
    return json.loads(value)


if __name__ == '__main__':
    main()
