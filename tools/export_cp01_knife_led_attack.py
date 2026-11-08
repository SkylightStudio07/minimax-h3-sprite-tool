"""New knife-led attack plus the accepted idle with its enclosed arm gap fixed."""
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import av
import numpy as np
from PIL import Image
import requests
from tools import export_cp01_blood_retry as blood

OUT = ROOT / 'outputs/cp01-knife-led-attack-20261026'
PREVIOUS = ROOT / 'outputs/cp01-blood-retry-20261026'
BASE_BUILD = blood.BASE_BUILD


def gap_fix(raw, cut):
    rgb = np.asarray(raw.convert('RGB'), dtype=float)
    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]))
    bg = np.median(border, axis=0)
    yy, xx = np.indices(rgb.shape[:2])
    roi = (xx >= 350) & (xx <= 480) & (yy >= 145) & (yy <= 230)
    neutral = (np.max(np.abs(rgb - bg), axis=2) < 28) & (np.ptp(rgb, axis=2) < 14)
    mask = roi & neutral
    rgba = np.array(cut.convert('RGBA'))
    removed = int((mask & (rgba[:, :, 3] > 0)).sum())
    rgba[mask] = 0
    return Image.fromarray(rgba), dict(removedPixels=removed, region=[350, 145, 480, 230],
        background=bg.tolist(), method='Known neutral matte inside the enclosed kunai/forearm gap; red glove, black blade and colored cuff excluded')


def build():
    BASE_BUILD()
    p = OUT / 'preview.html'
    text = p.read_text(encoding='utf-8').replace('CP01 새 원화', 'CP01 · 단검 주도 공격과 Idle 틈 수정')
    text = text.replace('cp01-new-reference-idle-attack.zip', 'cp01-knife-led-idle-attack.zip').replace('cp01-new-reference-gifs.zip', 'cp01-knife-led-gifs.zip')
    p.write_text(text, encoding='utf-8')


def configure():
    blood.export.OUT = OUT
    blood.export.build = build
    blood.export.configure()
    for action in blood.export.base.ACTIONS:
        blood.export.base.ACTIONS[action]['padding'] = 20
    blood.export.base.configure()


def process():
    configure()
    if not (OUT / 'idle').exists():
        shutil.copytree(PREVIOUS / 'idle', OUT / 'idle')
    assert blood.export.checks.digest(OUT / 'idle/raw.mp4') == blood.export.checks.digest(PREVIOUS / 'idle/raw.mp4')
    try:
        q = requests.get('http://127.0.0.1:8189/queue', timeout=5).json()
        if not q.get('queue_running') and not q.get('queue_pending'):
            requests.post('http://127.0.0.1:8189/free', json=dict(unload_models=True, free_memory=True), timeout=30).raise_for_status()
    except requests.ConnectionError:
        pass
    source = ROOT / 'outputs/comfy/cp01_knife_led_attack_20261026/attack_00001_.mp4'
    folder = OUT / 'attack'
    if not (folder / 'raw.mp4').exists():
        shutil.copy2(source, folder / 'raw.mp4')
    assert blood.export.checks.digest(source) == blood.export.checks.digest(folder / 'raw.mp4')
    frames = folder / 'all-frames'
    frames.mkdir(exist_ok=True)
    meta = json.loads((folder / 'matte-process.json').read_text(encoding='utf-8')) if (folder / 'matte-process.json').exists() else {}
    records = {r['frame']: r for r in meta.get('processed', [])}
    with av.open(str(source)) as video:
        s = video.streams.video[0]
        assert (s.width, s.height, s.average_rate, s.frames) == (768, 768, 24, 73)
        for i, frame in enumerate(video.decode(video=0)):
            path = frames / f'frame-{i:03d}.png'
            if path.exists() and i in records:
                continue
            raw = frame.to_image()
            cut, info = blood.matte(raw)
            cut, contour = blood.refine_cut(raw, cut)
            cut, gap = gap_fix(raw, cut)
            cut.save(path)
            records[i] = dict(frame=i, **info, contour=contour, armGap=gap)
            if i % 12 == 0:
                blood.export.save(folder / 'matte-process.json', dict(revision='knife-led-blood-alpha-v1', processed=list(records.values()), geometryUnchanged=True))
                print('MATTED_ATTACK', i, flush=True)
    assert len(records) == 73
    blood.export.save(folder / 'matte-process.json', dict(revision='knife-led-blood-alpha-v1', processed=list(records.values()), geometryUnchanged=True))
    idle_records = []
    with av.open(str(OUT / 'idle/raw.mp4')) as video:
        for i, frame in enumerate(video.decode(video=0)):
            # Always start with the accepted idle cutout, preserving its pixels
            # everywhere except this explicitly selected neutral-background gap.
            with Image.open(PREVIOUS / 'idle/all-frames' / f'frame-{i:03d}.png') as original:
                cut, gap = gap_fix(frame.to_image(), original.convert('RGBA'))
            cut.save(OUT / 'idle/all-frames' / f'frame-{i:03d}.png')
            idle_records.append(dict(frame=i, **gap))
    blood.export.save(OUT / 'idle/arm-gap-repair.json', dict(frames=idle_records, originalMotionPreserved=True,
        totalRemovedPixels=sum(r['removedPixels'] for r in idle_records)))
    for action in ('idle', 'attack'):
        folder = OUT / action
        p = folder / 'frames.json'
        if p.exists():
            p.replace(folder / 'pre-gap-frames.json')
        note = ('기존 혈계 idle 동작을 유지하고 쿠나이·팔 사이에 남은 회색 배경만 정리했습니다.' if action == 'idle' else
                '단검을 쥔 팔로 오른쪽으로 베고 칼날을 따라 붉은 궤적이 나타납니다. 손·얼굴·칼날 세부에는 생성 변화가 남습니다.')
        blood.export.save(folder / 'review.json', dict(reviewed=False, userApproval='pending', note=note))
    blood.export.base.export()
    blood.export.validate()
    print('PAIR_READY_FOR_REVIEW', flush=True)


def package():
    configure()
    blood.export.package()
    original = OUT / 'cp01-new-reference-idle-attack.zip'
    readme = OUT / 'README.txt'
    text = readme.read_text(encoding='utf-8').replace('CP01 new reference', 'CP01 knife-led attack + repaired accepted idle').replace(
        'Input copy was AI-edited to remove hanging liquid and floor puddle. See source.json.',
        'Original blood-ability artwork retained without repaint. Accepted idle motion reused; neutral background in the kunai/forearm gap repaired. Attack is a new generation. See source.json and idle/arm-gap-repair.json.')
    readme.write_text(text, encoding='utf-8')
    with zipfile.ZipFile(original) as src, zipfile.ZipFile(OUT / 'cp01-knife-led-idle-attack.zip', 'w', zipfile.ZIP_DEFLATED) as dest:
        for info in src.infolist():
            data = readme.read_bytes() if info.filename == 'README.txt' else src.read(info.filename)
            dest.writestr(info.filename, data)
        dest.write(OUT / 'idle/arm-gap-repair.json', 'idle/arm-gap-repair.json')
    shutil.copy2(OUT / 'cp01-new-reference-gifs.zip', OUT / 'cp01-knife-led-gifs.zip')
    with zipfile.ZipFile(OUT / 'cp01-knife-led-idle-attack.zip') as z:
        assert z.testzip() is None
    print('HANDOFF_READY', flush=True)


if __name__ == '__main__':
    globals()[sys.argv[1] if len(sys.argv) > 1 else 'process']()
