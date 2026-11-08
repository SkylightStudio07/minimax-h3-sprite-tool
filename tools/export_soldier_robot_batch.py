"""CPU-only matte, native sprite handoff and review for the completed 12 jobs."""
import argparse
import gc
import html
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import av
import cv2
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from pymatting import estimate_alpha_cf, estimate_foreground_ml
import image_background
from tools import verify_masked_rifleman_motion as base
from tools import export_guardian_drone_batch as checks
from tools.submit_soldier_robot_batch import OUT, INPUT, PREFIX, CASES as SUBMITTED

CASES = [dict(c, file=PREFIX + c['sourceSeed'] + '.png') for c in SUBMITTED]
REVISION = 'soldier-robot-protected-alpha-v1'


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def configure(case):
    folder = OUT / case['id']
    base.OUT = folder
    base.SOURCE = INPUT / case['file']
    base.ACTIONS = {a: dict(title=a, loop=a == 'idle', padding=case['padding'], frames=24) for a in ('idle', 'attack')}
    base.build = lambda: build_case(case)
    base.configure()
    return folder


def prepare():
    for case in CASES:
        root = configure(case)
        assert checks.digest(base.SOURCE) == checks.digest(root / 'source-original.png')
        for action in ('idle', 'attack'):
            source = ROOT / 'outputs/comfy/soldier_robot_batch_20261025' / case['id'] / (action + '_00001_.mp4')
            dest = root / action / 'raw.mp4'
            assert source.is_file()
            if not dest.exists():
                shutil.copy2(source, dest)
            assert checks.digest(source) == checks.digest(dest)
            with av.open(str(dest)) as video:
                stream = video.streams.video[0]
                assert (stream.width, stream.height, stream.average_rate, stream.frames) == (768, 768, 24, 73)


def machine_reference(case):
    root = OUT / case['id']
    with Image.open(root / 'reference.png') as ref:
        scale = min(768 / ref.width, 768 / ref.height) * (1 - case['padding'] / 100)
        size = (round(ref.width * scale), round(ref.height * scale))
        alpha = ref.getchannel('A').resize(size, Image.Resampling.LANCZOS)
    canvas = Image.new('L', (768, 768))
    canvas.paste(alpha, ((768 - size[0]) // 2, (768 - size[1]) // 2))
    core = ndimage.distance_transform_edt(np.array(canvas) > 230) > 5
    yy, _ = np.indices(core.shape)
    core &= yy < 500
    with Image.open(root / 'idle/reference-prepared.png') as im:
        grey = cv2.cvtColor(np.array(im.convert('RGB')), cv2.COLOR_RGB2GRAY)
    points = cv2.goodFeaturesToTrack(grey, maxCorners=240, qualityLevel=.01, minDistance=5, mask=core.astype('uint8') * 255)
    return core, grey, points


def emission_patch(rgb, semantic, protect, warm, roi, bg):
    # White flash cores often have no orange hue. Exclude the whole connected
    # bright core when estimating the local backdrop, or it cancels itself out.
    bright = roi & (rgb.mean(2) > float(np.mean(bg)) + 35)
    flashmask = ndimage.binary_propagation(warm, mask=bright | warm)
    distance = ndimage.distance_transform_edt(~flashmask)
    support = (distance < 24) & roi
    weight = ((semantic < 8) & (distance > 18)).astype(float)
    denominator = ndimage.gaussian_filter(weight, 35)
    local = np.stack([ndimage.gaussian_filter(rgb[:, :, c] * weight, 35) / np.maximum(denominator, 1e-5) for c in range(3)], axis=2)
    local[denominator < .02] = bg
    emission = np.clip(np.max((rgb - local) / np.maximum(255 - local, 1), axis=2), 0, 1)
    emission[emission < .035] = 0
    bright_emission = rgb.max(2) > float(np.max(bg)) + 12
    recover = ((support & (semantic < 32)) | (support & bright_emission & (semantic < 192))) & ~protect
    unmixed = np.clip((rgb - local * (1 - emission[:, :, None])) / np.maximum(emission[:, :, None], .01), 0, 255) / 255
    return recover, emission, unmixed


def muzzle_roi(case, shape):
    yy, xx = np.indices(shape)
    limits = {
        '01-gatling-walker': (450, 60, 250),
        '03-suppressed-rifleman': (350, 100, 440),
        '04-cloaked-marksman': (300, 120, 400),
        '05-mast-gun-walker': (350, 80, 250),
        '06-compact-turret-walker': (350, 90, 260),
    }
    xmax, ymin, ymax = limits.get(case['id'], (0, 0, 0))
    return (xx < xmax) & (yy > ymin) & (yy < ymax)


def matte(raw, case, action, reference=None):
    rgb = np.array(raw.convert('RGB'), dtype=float)
    image = rgb / 255
    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]))
    bg = np.median(border, axis=0)
    delta = np.max(np.abs(rgb - bg), axis=2)
    chroma, lum = np.ptp(rgb, axis=2), rgb.mean(2)
    semantic = np.array(image_background.remove(raw))[:, :, 3]
    protect = ndimage.distance_transform_edt(semantic > 240) > 2.5
    near = (delta < 9) & (chroma < 8)
    labels, _ = ndimage.label(near)
    gaps = (labels > 0) & (np.bincount(labels.ravel())[labels] >= 100)
    neutral_band = (delta < 24) & (chroma < 12)
    seeds = np.zeros(delta.shape, bool)
    seeds[0], seeds[-1], seeds[:, 0], seeds[:, -1] = neutral_band[0], neutral_band[-1], neutral_band[:, 0], neutral_band[:, -1]
    exterior = ndimage.binary_propagation(seeds, mask=neutral_band)
    protect[gaps | exterior] = False
    if reference is not None and action == 'idle':
        protect |= checks.tracked_hull_core(raw, reference) & ~exterior
    neutral = (chroma < 12) & (lum > 88) & (lum < 158) & ~protect
    trimap = np.full(delta.shape, .5)
    trimap[(delta > 40) | protect] = 1
    trimap[((delta < 9) | neutral | exterior) & ~protect] = 0
    roi = muzzle_roi(case, delta.shape)
    warm = roi & (rgb[:, :, 0] > 215) & (rgb[:, :, 1] > 160) & (rgb[:, :, 0] - rgb[:, :, 2] > 60)
    flash = action == 'attack' and case['id'] != '02-knife-soldier' and warm.sum() >= 3
    support = (ndimage.distance_transform_edt(~warm) < 42) & roi if flash else np.zeros(delta.shape, bool)
    if flash:
        # A relit flat backdrop must not become an opaque patch around the gun.
        outside = (ndimage.distance_transform_edt(semantic < 16) > 3) & ~support
        trimap[(delta > 40) & ~protect] = .5
        trimap[(semantic > 240) & (delta > 20)] = 1
        trimap[outside] = 0
        protect[outside] = False
    alpha = np.clip(estimate_alpha_cf(image, trimap), 0, 1)
    foreground = np.clip(estimate_foreground_ml(image, alpha), 0, 1)
    recovered = 0
    if flash:
        recover, emission, unmixed = emission_patch(rgb, semantic, protect, warm, roi, bg)
        alpha[recover], foreground[recover] = emission[recover], unmixed[recover]
        recovered = int((recover & (emission > 0)).sum())
    alpha[alpha < .02], alpha[alpha > .995], alpha[protect] = 0, 1, 1
    foreground[protect] = image[protect]
    rgba = np.rint(np.dstack((foreground, alpha)) * 255).astype('uint8')
    rgba[alpha == 0] = 0
    return Image.fromarray(rgba), dict(background=bg.tolist(), gapSeedPixels=int(gaps.sum()),
        protectedInteriorPixels=int(protect.sum()), protectedInteriorPreserved=bool(np.all(rgba[:, :, 3][protect] == 255)),
        flashDetected=bool(flash), recoveredEmissionPixels=recovered)


def samples():
    prepare()
    for case in CASES:
        root = OUT / case['id']
        reference = machine_reference(case) if case['subject'] == 'ground_machine' else None
        board = Image.new('RGB', (1536, 1024))
        raw_strip = Image.new('RGB', (1280, 640))
        for row, action in enumerate(('idle', 'attack')):
            chosen, peak, best = {}, -1, 24
            with av.open(str(root / action / 'raw.mp4')) as video:
                for i, frame in enumerate(video.decode(video=0)):
                    im = frame.to_image()
                    if i in (0, 18, 36, 55):
                        chosen[i] = im
                    a = np.array(im, dtype=float)
                    n = ((a[:500, :500, 0] > 215) & (a[:500, :500, 1] > 160) & (a[:500, :500, 0] - a[:500, :500, 2] > 60)).sum()
                    if n > peak:
                        peak, best, selected = n, i, im
            index = 36 if action == 'idle' else best
            raw = chosen[36] if action == 'idle' else selected
            cut, info = matte(raw, case, action, reference)
            cut.save(root / action / 'matte-sample.png')
            save(root / action / 'matte-sample.json', dict(frame=index, **info))
            for col, color in enumerate(('#142436', '#fff4dc', '#226b54')):
                bg = Image.new('RGBA', cut.size, color)
                bg.alpha_composite(cut)
                board.paste(bg.resize((512, 512)).convert('RGB'), (col * 512, row * 512))
            for col, (i, im) in enumerate(chosen.items()):
                raw_strip.paste(im.resize((320, 320)), (col * 320, row * 320))
        board.save(root / 'matte-tests.jpg', quality=96)
        raw_strip.save(root / 'motion-review.jpg', quality=95)
        print('SAMPLES_READY', case['id'], flush=True)


def validate(case):
    checks.OUT, checks.INPUT, checks.configure = OUT, INPUT, configure
    return checks.validate(case)


def repair():
    """Repair only recorded flash frames, then rebuild derived sheets/previews."""
    for case in CASES:
        root = configure(case)
        folder = root / 'attack'
        report = json.loads((folder / 'matte-process.json').read_text(encoding='utf-8'))
        records = {r['frame']: r for r in report['processed']}
        changed = 0
        baseline = None
        with av.open(str(folder / 'raw.mp4')) as video:
            for i, frame in enumerate(video.decode(video=0)):
                rec = records[i]
                raw = frame.to_image()
                rgb = np.array(raw.convert('RGB'), dtype=float)
                if baseline is None:
                    baseline = rgb.copy()
                if rec.get('emissionRepair') == 'connected-white-core-v3':
                    continue
                roi = muzzle_roi(case, rgb.shape[:2])
                warm = roi & (rgb[:, :, 0] > 215) & (rgb[:, :, 1] > 160) & (rgb[:, :, 0] - rgb[:, :, 2] > 60) & (np.max(rgb - baseline, axis=2) > 40)
                if warm.sum() < 3:
                    rec['trueMuzzleFlash'] = False
                    continue
                semantic = np.array(image_background.remove(raw))[:, :, 3]
                protect = ndimage.distance_transform_edt(semantic > 240) > 2.5
                recover, emission, foreground = emission_patch(rgb, semantic, protect, warm, roi, np.array(rec['background']))
                target = folder / 'all-frames' / f'frame-{i:03d}.png'
                with Image.open(target) as im:
                    rgba = np.array(im.convert('RGBA'))
                rgba[recover, :3] = np.rint(foreground[recover] * 255).astype('uint8')
                rgba[recover, 3] = np.rint(emission[recover] * 255).astype('uint8')
                rgba[rgba[:, :, 3] < 5] = 0
                Image.fromarray(rgba).save(target)
                rec.update(emissionRepair='connected-white-core-v3', trueMuzzleFlash=True, recoveredEmissionPixels=int((recover & (emission > 0)).sum()))
                changed += 1
        report.update(processed=list(records.values()), emissionRepair='connected-white-core-v3')
        save(folder / 'matte-process.json', report)
        if changed:
            meta = folder / 'frames.json'
            if meta.exists():
                meta.replace(folder / 'pre-emission-v3-frames.json')
            base.export()
        validate(case)
        print('FLASH_REVIEW_READY', case['id'], changed, flush=True)
        gc.collect()
    build_all()


def process():
    prepare()
    # Serial cases avoid concurrent ONNX and full-sheet allocations on this PC.
    for case in CASES:
        root = configure(case)
        reference = machine_reference(case) if case['subject'] == 'ground_machine' else None
        for action in ('idle', 'attack'):
            folder = root / action
            frames = folder / 'all-frames'
            frames.mkdir(exist_ok=True)
            old = json.loads((folder / 'matte-process.json').read_text(encoding='utf-8')) if (folder / 'matte-process.json').exists() else {}
            assert old.get('revision', REVISION) == REVISION
            records = {r['frame']: r for r in old.get('processed', [])}
            with av.open(str(folder / 'raw.mp4')) as video:
                for i, frame in enumerate(video.decode(video=0)):
                    target = frames / f'frame-{i:03d}.png'
                    if target.exists() and i in records:
                        continue
                    cut, info = matte(frame.to_image(), case, action, reference)
                    cut.save(target)
                    records[i] = dict(frame=i, **info)
                    if i % 12 == 0:
                        save(folder / 'matte-process.json', dict(revision=REVISION, processed=list(records.values()), geometryUnchanged=True))
                        print('MATTED', case['id'], action, i, flush=True)
            assert len(records) == 73
            save(folder / 'matte-process.json', dict(revision=REVISION, processed=list(records.values()), geometryUnchanged=True, originalVideoPreserved=True))
            if not (folder / 'review.json').exists():
                save(folder / 'review.json', dict(reviewed=False, userApproval='pending', generatedDetailDrift=True,
                     note='원화와 생성 영상을 보존했습니다. 가는 총열·장비·위장 무늬에는 생성 변화가 남을 수 있습니다.'))
        save(root / 'idle/selection.json', dict(start=0, end=71, note='Duplicate closing anchor omitted; forward playback only.'))
        base.export()
        validate(case)
        build_all()
        gc.collect()
        print('CASE_EXPORTED', case['id'], flush=True)


def build_case(case):
    root = OUT / case['id']
    cards = []
    for action in ('idle', 'attack'):
        if not (root / action / 'game-animation.webp').exists():
            continue
        cards.append(f'<article><h2>{"대기" if action == "idle" else "공격"}</h2><img src="{action}/game-animation.webp" alt="{action}"><p><a href="{action}/game-animation.gif">GIF</a> · <a href="{action}/native-sheet.png">전체 PNG 시트</a> · <a href="{action}/native-frames.json">프레임 시간</a> · <a href="{action}/matte-review.jpg">밝은·어두운 배경</a></p></article>')
    (root / 'preview.html').write_text(checks.page_head(case['label']) + f'<h1>{html.escape(case["label"])} · Idle / Attack</h1><p>768×768 · 24FPS · 투명 PNG와 개별 프레임. 장비·위장 무늬·총열의 생성 변화는 남을 수 있습니다.</p>' + checks.buttons() + f'<p><a href="{case["id"]}-idle-attack.zip">캐릭터 ZIP</a></p><main>' + ''.join(cards) + '</main></html>', encoding='utf-8')


def build_all():
    cards = []
    for case in CASES:
        build_case(case)
        for action in ('idle', 'attack'):
            if (OUT / case['id'] / action / 'game-animation.webp').exists():
                cards.append(f'<article><h2>{html.escape(case["label"])} · {action}</h2><img src="{case["id"]}/{action}/game-animation.webp" alt="{action}"><p><a href="{case["id"]}/preview.html">상세·캐릭터 ZIP</a></p></article>')
    (OUT / 'preview.html').write_text(checks.page_head('병사·사족 기계 6종') + '<h1>병사·사족 기계 6종 · Idle / Attack</h1><p>6종, 12개 동작 · 768×768 · 24FPS. 공격은 미리보기에서 반복되며 게임에서는 한 번 재생하세요.</p>' + checks.buttons() + '<p><a href="soldier-robot-all-idle-attack.zip">전체 ZIP</a> · <a href="soldier-robot-gifs.zip">GIF만 ZIP</a></p><main>' + ''.join(cards) + '</main></html>', encoding='utf-8')


def package():
    summaries = []
    whole = OUT / 'soldier-robot-all-idle-attack.zip'
    with zipfile.ZipFile(whole, 'w', zipfile.ZIP_DEFLATED) as batch, zipfile.ZipFile(OUT / 'soldier-robot-gifs.zip', 'w', zipfile.ZIP_DEFLATED) as gifs:
        for case in CASES:
            root = OUT / case['id']
            validate(case)
            summaries.append(json.loads((root / 'validation.json').read_text(encoding='utf-8')))
            (root / 'README.txt').write_text(case['label'] + '\n\n768x768 native cells, 24FPS. Idle: 72 frames / 3 seconds; attack: 73 frames / 3.042 seconds.\nUse action/native-sheet.png + native-frames.json or action/frames/*.png.\n24-frame alternative: game-sheet.png + game-frames.json.\nBoth actions retain the same canvas coordinates and source scale.\nPNG/WebP retain soft alpha; GIF uses binary alpha and 10ms timing.\nOriginal source and videos retained; no interpolation, reversal or synthetic effects.\nInspect review.json and matte-review.jpg for observed generation limits.\n', encoding='utf-8')
            files = [root / name for name in ('source-original.png', 'source.json', 'reference.png', 'preview.html', 'README.txt', 'validation.json', 'game-registration.json', 'matte-tests.jpg', 'motion-review.jpg')]
            for action in ('idle', 'attack'):
                folder = root / action
                files += [folder / name for name in ('game-animation.gif', 'game-animation.webp', 'native-sheet.png', 'native-frames.json', 'game-sheet.png', 'game-frames.json', 'settings.json', 'native-v1-workflow.json', 'raw.mp4', 'reference-prepared.png', 'matte-review.jpg', 'review.json', 'matte-process.json')]
                meta = json.loads((folder / 'native-frames.json').read_text(encoding='utf-8'))
                files += [folder / 'all-frames' / f'frame-{i:03d}.png' for i in meta['sourceIndices']]
                gifs.write(folder / 'game-animation.gif', case['id'] + '-' + action + '.gif')
            with zipfile.ZipFile(root / (case['id'] + '-idle-attack.zip'), 'w', zipfile.ZIP_DEFLATED) as individual:
                for path in files:
                    relative = str(path.relative_to(root)).replace('\\', '/').replace('/all-frames/', '/frames/')
                    individual.write(path, relative)
                    if relative == 'preview.html':
                        page = path.read_text(encoding='utf-8').replace(f'<p><a href="{case["id"]}-idle-attack.zip">캐릭터 ZIP</a></p>', '')
                        batch.writestr(case['id'] + '/' + relative, page)
                    else:
                        batch.write(path, case['id'] + '/' + relative)
        reviewed = all(s['cases'][a]['review'].get('reviewed') for s in summaries for a in ('idle', 'attack'))
        save(OUT / 'batch-validation.json', dict(fileChecksPassed=True, cases=summaries, generationUnchanged=True,
             visualReview='completed' if reviewed else 'pending'))
        batch.write(OUT / 'batch-validation.json', 'batch-validation.json')
        page = (OUT / 'preview.html').read_text(encoding='utf-8')
        page = page.replace('<p><a href="soldier-robot-all-idle-attack.zip">전체 ZIP</a> · <a href="soldier-robot-gifs.zip">GIF만 ZIP</a></p>', '')
        batch.writestr('preview.html', page)
    for path in (whole, OUT / 'soldier-robot-gifs.zip'):
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
    print('PACKAGED', whole, round(whole.stat().st_size / 1024**2, 1), 'MiB', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=('samples', 'process', 'repair', 'package', 'build'))
    args = parser.parse_args()
    globals()['build_all' if args.stage == 'build' else args.stage]()
