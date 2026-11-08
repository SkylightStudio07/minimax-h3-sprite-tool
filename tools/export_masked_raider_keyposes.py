"""Split generated 2D keyposes; deterministic chroma extraction and frame timing."""
import json
import shutil
import sys
import zipfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sprite_gif

OUT = ROOT / 'outputs/masked-raider-flat2d-20261023/keypose-attack'
GENERATED = Path(r'C:/Users/SKYLIGHT/.codex/generated_images/01a0943f-e4b7-7e11-af05-20d776c93f13/exec-4bac27af-e581-422c-8eb6-82596e7e6ab4.png')


def extract(im):
    original_alpha = np.asarray(im.convert('RGBA'))[:, :, 3].astype(np.float32) / 255
    rgb = np.asarray(im.convert('RGB')).astype(np.float32)
    excess = rgb[:, :, 1] - np.maximum(rgb[:, :, 0], rgb[:, :, 2])
    green = (rgb[:, :, 1] > 20) & (excess > 15)
    a = np.ones(excess.shape, np.float32)
    a[green] = 1 - np.clip((excess[green] - 15) / 65, 0, 1)
    a *= original_alpha
    # Remove key-color contamination only on pixels classified as chroma edges.
    edge = green & (a > 0)
    rgb[edge, 1] = np.minimum(rgb[edge, 1], np.maximum(rgb[edge, 0], rgb[edge, 2]))
    rgb[a == 0] = 0
    rgba = np.dstack((rgb, a * 255)).clip(0, 255).astype(np.uint8)
    return Image.fromarray(rgba)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(GENERATED, OUT / 'generated-sheet-original.png')
    source = Image.open(GENERATED).convert('RGB')
    # Generators can cross nominal cell boundaries: segment complete silhouettes
    # first instead of clipping boots or coat tails at a guessed grid line.
    keyed = extract(source)
    keyed_array = np.array(keyed)
    count, labels, stats, centers = cv2.connectedComponentsWithStats((keyed_array[:, :, 3] > 25).astype(np.uint8))
    components = sorted(range(1, count), key=lambda j: stats[j, cv2.CC_STAT_AREA], reverse=True)[:8]
    assert len(components) == 8 and all(stats[j, cv2.CC_STAT_AREA] > 20000 for j in components)
    components.sort(key=lambda j: (int(centers[j][1] > source.height / 2), centers[j][0]))
    raw = []
    for j in components:
        near = cv2.dilate((labels == j).astype(np.uint8), np.ones((5, 5), np.uint8))
        pixels = keyed_array.copy()
        pixels[near == 0] = 0
        cell = Image.fromarray(pixels)
        raw.append(cell.crop(cell.getbbox()))
    frames, registrations, prepared = [], [], []
    for i, cell in enumerate(raw):
        alpha = np.asarray(cell)[:, :, 3]
        ys, xs = np.where(alpha > 128)
        yy, xx = np.indices(alpha.shape)
        rear_region = (alpha > 128) & (xx >= cell.width * .6) & (yy >= cell.height - 70)
        assert rear_region.any()
        baseline = int(np.where(rear_region)[0].max())
        # Rear-foot contact is the stable anchor; do not rescale each pose.
        foot = rear_region & (yy >= baseline - 10)
        count, labels, stats, centers = cv2.connectedComponentsWithStats(foot.astype(np.uint8))
        candidates = [j for j in range(1, count) if stats[j, cv2.CC_STAT_AREA] >= 15]
        anchor = max((centers[j][0] for j in candidates), default=float(xs.max()))
        prepared.append((cell, round(anchor), baseline))
    relative = [(c.getbbox()[0]-x, c.getbbox()[1]-y, c.getbbox()[2]-x, c.getbbox()[3]-y)
                for c, x, y in prepared]
    left, top = min(b[0] for b in relative), min(b[1] for b in relative)
    right, bottom = max(b[2] for b in relative), max(b[3] for b in relative)
    size = max(right-left, bottom-top) + 48
    origin = ((size-(right-left))//2-left, size-24-bottom)
    for i, (cell, anchor, baseline) in enumerate(prepared):
        shift = (origin[0]-anchor, origin[1]-baseline)
        canvas = Image.new('RGBA', (size, size))
        canvas.paste(cell, shift)
        box = canvas.getbbox()
        assert box and box[0] > 0 and box[1] > 0 and box[2] < size and box[3] < size
        frames.append(canvas)
        registrations.append(dict(index=i, sourceSize=list(cell.size), sourceBaseline=baseline,
                                  rearFootAnchor=anchor, translation=list(shift), bounds=list(box)))
    durations = [260, 160, 160, 60, 110, 150, 160, 300]
    frame_dir = OUT / 'frames'
    frame_dir.mkdir(exist_ok=True)
    sheet = Image.new('RGBA', (size * 4, size * 2))
    for i, frame in enumerate(frames):
        frame.save(frame_dir / f'{i:02d}.png')
        sheet.paste(frame, ((i % 4) * size, (i // 4) * size))
    sheet.save(OUT / 'sheet.png')
    frames[0].save(OUT / 'animation.webp', save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, lossless=True)
    data, gif = sprite_gif.encode(frames, durations)
    (OUT / 'animation.gif').write_bytes(data)
    meta = dict(method='reference-conditioned image generation: 8 drawn keyposes; no video interpolation',
                frameWidth=size, frameHeight=size, columns=4, rows=2, frameCount=8,
                durationMs=durations, totalMs=sum(durations), registrations=registrations,
                source=str(GENERATED), gif=gif,
                limitations=['Club grip changed to two hands.', 'Eight discrete keyposes, not smooth video.',
                             'Equipment details and pose outlines may vary between drawings.'])
    (OUT / 'frames.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'README.txt').write_text('2D style correction experiment\n\nAttack: built-in image generation, reference-conditioned eight keyposes.\nChroma background removed; rear foot aligned without per-frame scale changes.\nPrompt: prompt.txt. PNG frames retain alpha; GIF uses one shared palette and binary alpha.\nIdle: original supplied artwork with subtle mesh displacement, no AI repainting.\n\nLimitations: attack uses a two-handed grip; eight discrete poses; small equipment/shape drift.\nThe last pose is similar to, but not identical to, the first.\nOriginal rejected video experiments are preserved separately.\n', encoding='utf-8')
    (OUT / 'preview.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>2D 대기·공격 시험</title><style>body{background:#202735;color:#eef0f7;font:16px/1.6 system-ui;margin:24px}main{display:flex;gap:24px;flex-wrap:wrap}article{max-width:520px}img{width:100%;background:repeating-conic-gradient(#303c50 0 25%,#43516a 0 50%) 0/24px 24px}a{color:#c9c0ff}</style><h1>2D 대기·공격 시험</h1><p>영상 생성에서 발생한 입체 표현 대신, 원화 변형 대기와 이미지 기반 공격 키포즈를 비교합니다.</p><main><article><h2>대기 · 원화 픽셀 기반</h2><img src="../source-pixel-idle/animation.webp" alt="원화 기반 미세 대기"><p>새로 그리지 않고 어깨와 코트 끝에 작은 변형만 적용했습니다.</p><a href="../source-pixel-idle/animation.gif">대기 GIF</a></article><article><h2>공격 · 8장 키포즈</h2><img src="animation.webp" alt="2D 키포즈 공격"><p>참조 이미지로 새로 생성한 8장입니다. 양손 그립으로 바뀌었으며, 자세 사이 끊김과 장비 세부 차이가 남습니다.</p><a href="animation.gif">공격 GIF</a> · <a href="sheet.png">PNG 시트</a> · <a href="frames.json">프레임·재생 시간</a> · <a href="prompt.txt">생성 프롬프트</a></article></main><p><a href="../masked-raider-2d-handoff.zip">대기·공격 파일 묶음</a></p></html>''', encoding='utf-8')
    idle = OUT.parent / 'source-pixel-idle'
    package = OUT.parent / 'masked-raider-2d-handoff.zip'
    with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in OUT.rglob('*'):
            if path.is_file(): z.write(path, 'attack/' + path.relative_to(OUT).as_posix())
        for name in ['animation.gif', 'animation.webp', 'sheet.png', 'frames.json', 'reference.png']:
            z.write(idle / name, 'idle/' + name)
    with Image.open(OUT / 'animation.gif') as check:
        assert check.n_frames == 8
        times = []
        for i in range(check.n_frames):
            check.seek(i)
            times.append(check.info['duration'])
        assert times == durations
    with zipfile.ZipFile(package) as check:
        assert check.testzip() is None
    for i, frame in enumerate(frames):
        assert np.array_equal(np.array(sheet.crop(((i % 4) * size, (i // 4) * size,
                              (i % 4 + 1) * size, (i // 4 + 1) * size))), np.array(frame))
    (OUT / 'validation.json').write_text(json.dumps(dict(frameCount=8, timingVerified=True,
        sheetFramesPixelEqual=True, packageIntegrityVerified=True, artApproval='pending user review',
        limitations=meta['limitations']), indent=2), encoding='utf-8')
    print(json.dumps(dict(output=str(OUT), package=str(package), frameSize=size,
                          sourceSize=source.size, frameCount=8, gifTimingVerified=True)))


if __name__ == '__main__':
    main()
