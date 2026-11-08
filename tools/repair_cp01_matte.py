"""Reference-specific known-neutral-matte cleanup; no video regeneration."""
import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import verify_cp01_motion as cp
from tools.sprite_matte import clean_flat_matte

PREVIOUS = ROOT / 'outputs/cp01-dagger-motion-20261023'
OUT = ROOT / 'outputs/cp01-dagger-matte-v2-20261023'


def repair(image):
    original = np.array(image.convert('RGBA'))
    rgb = original[:, :, :3].astype(np.float32)
    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]))
    bg = np.median(border, axis=0)
    difference = np.max(np.abs(rgb-bg), axis=2)
    depth_original = ndimage.distance_transform_edt(original[:, :, 3] > 0)
    yy = np.indices(depth_original.shape)[0]
    # Neutral key fragments include the enclosed hair curl. These colours are
    # distinct from this character's purple-grey fabric and white blouse.
    key = (difference <= 8) & (np.ptp(rgb, axis=2) <= 8) & ((depth_original <= 2) | (yy < 320) | (original[:, :, 3] < 180))
    keyed = original.copy()
    keyed[key, 3] = 0
    cleaned, stats = clean_flat_matte(Image.fromarray(keyed), tolerance=12, radius=3)
    result = np.array(cleaned)
    # This outfit includes genuine near-key grey fabric. Keep its semantic
    # interior exactly; the colour key is only allowed to alter its contour.
    body_interior = (yy >= 320) & (depth_original > 1.25) & (original[:, :, 3] >= 240)
    result[body_interior] = original[body_interior]
    visible = result[:, :, 3] > 0
    # Thin red ribbons have no eroded interior for generic contour cleanup.
    # Fit their antialiased edge to a nearby saturated red interior where one
    # exists, without changing the fully opaque red interior itself.
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    red_core = visible & (r-g > 70) & (r-b > 35) & (result[:, :, 3] >= 220)
    red_edges = visible & (r-g > 18) & (r-b > 8) & ~red_core & (depth_original <= 3)
    red_fitted = np.zeros(visible.shape, bool)
    if red_core.any():
        dist, indices = ndimage.distance_transform_edt(~red_core, return_indices=True)
        prior = rgb[indices[0], indices[1]]
        axis = prior-bg
        norm = (axis*axis).sum(2)
        alpha = np.clip(((rgb-bg)*axis).sum(2)/np.maximum(norm, 1), 0, 1)
        residual = np.linalg.norm(rgb-(bg+alpha[:, :, None]*axis), axis=2)
        red_fitted = red_edges & (dist <= 4) & (residual < 18) & (alpha < .97) & (norm > 40**2)
        unmix = np.clip((rgb-bg*(1-alpha[:, :, None]))/np.maximum(alpha[:, :, None], .08), 0, 255)
        result[red_fitted, :3] = np.rint(unmix[red_fitted]).astype(np.uint8)
        result[red_fitted, 3] = np.minimum(result[red_fitted, 3], np.rint(alpha[red_fitted]*255).astype(np.uint8))
    # Tiny near-neutral islands at the fringe are codec/matte contamination.
    result[result[:, :, 3] < 12] = 0
    result[result[:, :, 3] == 0, :3] = 0
    # No resampling, pose modification or blanket erosion of the silhouette.
    protected = (original[:, :, 3] == 255) & (result[:, :, 3] == 255) & (ndimage.distance_transform_edt(result[:, :, 3] > 0) > 4) & ~red_fitted
    assert np.array_equal(result[:, :, :3][protected], original[:, :, :3][protected])
    stats.update(neutralKeyPixelsRemoved=int(((original[:, :, 3] > 0) & key).sum()),
                 redEdgePixelsUnmatted=int(red_fitted.sum()))
    return Image.fromarray(result), stats


def review():
    OUT.mkdir(exist_ok=True)
    canvas = Image.new('RGB', (1536, 1024))
    draw = ImageDraw.Draw(canvas)
    for col, (name, index) in enumerate([('idle', 20), ('attack', 17), ('attack', 26)]):
        old = Image.open(PREVIOUS / name / 'all-frames' / f'frame-{index:03d}.png').convert('RGBA')
        new, stats = repair(old)
        new.save(OUT / f'{name}-{index}-fixed.png')
        for row, im in enumerate([old, new]):
            # Upper portion dark background, lower portion light: edge comparison.
            bg = Image.new('RGBA', im.size, '#142436')
            ImageDraw.Draw(bg).rectangle((0, 400, 768, 768), fill='#ffefd6')
            bg.alpha_composite(im)
            canvas.paste(bg.resize((512, 512)).convert('RGB'), (col*512, row*512))
            draw.text((col*512+10, row*512+10), f'{name} {index} / '+('BEFORE' if row == 0 else 'FIXED'), fill='red')
        print(name, index, stats, flush=True)
    canvas.save(OUT / 'matte-comparison.jpg', quality=96)


def main():
    OUT.mkdir(exist_ok=True)
    for filename in ['source-original.png', 'source.json', 'reference.png']:
        shutil.copy2(PREVIOUS / filename, OUT / filename)
    records = {}
    for name in cp.ACTIONS:
        target = OUT / name
        target.mkdir(exist_ok=True)
        for filename in ['raw.mp4', 'settings.json', 'reference-prepared.png', 'selection.json']:
            shutil.copy2(PREVIOUS / name / filename, target / filename)
        dest = target / 'all-frames'
        dest.mkdir(exist_ok=True)
        stats = []
        for path in sorted((PREVIOUS / name / 'all-frames').glob('*.png')):
            im, stat = repair(Image.open(path))
            im.save(dest / path.name)
            stats.append(dict(frame=path.name, **stat))
        records[name] = stats
        # Existing derived exports must be rebuilt from the corrected frames.
        if (target / 'frames.json').exists(): (target / 'frames.json').unlink()
        print('MATTE_REPAIRED', name, len(stats), flush=True)
    (OUT / 'matte-repair.json').write_text(json.dumps(dict(method='known neutral matte removal including enclosed holes; local colour-line unmatting; thin crimson edge fitting',
        previous=str(PREVIOUS), originalMotionUnchanged=True, cases=records), indent=2), encoding='utf-8')
    cp.OUT = OUT
    cp.export()
    cp.check()
    review()
    finalize()


def finalize():
    records = {}
    for name in cp.ACTIONS:
        old = PREVIOUS / name
        new = OUT / name
        assert hashlib.sha256((old/'raw.mp4').read_bytes()).digest() == hashlib.sha256((new/'raw.mp4').read_bytes()).digest()
        frame_count = 0
        transparent_rgb_clean = True
        for p in sorted((new/'all-frames').glob('*.png')):
            a = np.array(Image.open(p))
            assert not a[a[:, :, 3] == 0, :3].any()
            previous = np.array(Image.open(old/'all-frames'/p.name))
            depth = ndimage.distance_transform_edt(previous[:, :, 3] > 0)
            protected = (np.indices(depth.shape)[0] >= 320) & (depth > 4) & (previous[:, :, 3] >= 240)
            assert np.array_equal(previous[protected], a[protected]), 'Grey clothing interior changed'
            frame_count += 1
        assert frame_count == 73
        records[name] = dict(frames=frame_count, originalVideoHashEqual=True, transparentRGBZero=True, greyClothingInteriorPixelExact=True)
    old = np.array(Image.open(PREVIOUS/'attack/all-frames/frame-026.png'))
    new = np.array(Image.open(OUT/'attack/all-frames/frame-026.png'))
    # Reviewed exterior points in the two erroneous grey patches near gloves.
    patch_checks = []
    for x, y in [(530, 145), (540, 148), (400, 245)]:
        assert old[y, x, 3] >= 180 and new[y, x, 3] == 0
        patch_checks.append(dict(x=x, y=y, beforeAlpha=int(old[y, x, 3]), afterAlpha=0))
    (OUT/'matte-validation.json').write_text(json.dumps(dict(cases=records,
        reviewedBackgroundPatchChecks=patch_checks, originalPoseTimingAndVideoUnchanged=True,
        interiorRGBAssertedDuringProcessing=True, visualReview='Three frames on light/dark; user review pending.'), indent=2), encoding='utf-8')
    cards = []
    for name, title in [('idle', '대기'), ('attack', '단검 찌르기')]:
        cards.append(f'<article><h2>{title} · 배경 보정</h2><img class="media" src="{name}/game-animation.webp" alt="{title} 보정 결과">'
            f'<p><a href="{name}/game-animation.gif">GIF</a> · <a href="{name}/game-animation.webp">WebP</a> · '
            f'<a href="{name}/game-sheet.png">투명 PNG 시트</a> · <a href="{name}/game-frames.json">프레임 시간</a></p></article>')
    page = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>배경 제거 보정</title><style>:root{--matte:#142436}body{background:#1b2230;color:#eee;font:16px/1.65 system-ui;margin:24px}main{display:flex;gap:24px;flex-wrap:wrap}article{width:512px;max-width:100%}img{max-width:100%}.media{display:block;width:100%;background:var(--matte)}a{color:#c9c0ff}button{padding:8px 16px;margin:0 8px 12px 0}</style><h1>대기·공격 · 배경 제거 보정</h1><p>영상과 동작은 그대로 두고, 장갑·이펙트 사이의 회색 잔여물과 윤곽의 배경색 번짐을 정리했습니다. 실제 회색 바지 안쪽은 보호했습니다.</p><p>PNG와 WebP는 부드러운 반투명 경계를 유지합니다. GIF는 형식상 반투명 경계를 표현할 수 없어 더 거칠게 보일 수 있습니다. 단검 길이 변화와 화면 끝의 이펙트 잘림은 이번 보정 범위에 포함되지 않습니다.</p><div><button onclick="document.documentElement.style.setProperty('--matte','#142436')">어두운 배경</button><button onclick="document.documentElement.style.setProperty('--matte','#fff4dc')">밝은 배경</button><button onclick="document.documentElement.style.setProperty('--matte','#226b54')">초록 배경</button></div><p><a href="cp01-dagger-handoff.zip">보정 GIF·PNG 시트·원본 영상 ZIP</a> · <a href="matte-repair.json">보정 기록</a></p><main>'''+''.join(cards)+'''</main><h2>보정 전 / 후</h2><p>윗줄: 이전 · 아랫줄: 보정. 밝은 배경과 어두운 배경으로 비교합니다.</p><img src="matte-comparison.jpg" alt="대기와 공격의 보정 전후 비교"></html>'''
    (OUT/'preview.html').write_text(page, encoding='utf-8')
    (OUT/'README.txt').write_text('CP01 background-matte correction v2\n\nOriginal videos, timing and registration unchanged.\n'
        'Known neutral-key residue removed from upper-body gaps. Grey trouser interior protected.\n'
        'Local edge unmatting and thin crimson contour unmatting; zero RGB in transparent texels.\n'
        'PNG/WebP retain soft alpha. GIF supports binary alpha only and has a 255-colour foreground palette.\n'
        'Game files: idle/ and attack/ game-sheet.png, game-frames.json, game-selected/*.png.\n'
        'Known remaining generation limitations: dagger elongation, crimson trail tip clipping.\n'
        'This correction is tuned to this character and does not change the website pipeline.\n', encoding='utf-8')
    with zipfile.ZipFile(OUT/'cp01-dagger-handoff.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for name in cp.ACTIONS:
            for f in ['game-animation.gif', 'game-animation.webp', 'game-sheet.png', 'game-frames.json', 'raw.mp4', 'settings.json', 'reference-prepared.png']:
                z.write(OUT/name/f, name+'/'+f)
            for p in (OUT/name/'game-selected').glob('*.png'): z.write(p, name+'/game-selected/'+p.name)
        for f in ['source-original.png','source.json','README.txt','validation.json','matte-validation.json','matte-repair.json','matte-comparison.jpg','preview.html']:
            z.write(OUT/f, f)
    with zipfile.ZipFile(OUT/'cp01-dagger-handoff.zip') as z: assert z.testzip() is None
    print('CORRECTED_MATTE_VALIDATED', OUT, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['review', 'all', 'finalize'])
    args = parser.parse_args()
    if args.stage == 'review': review()
    elif args.stage == 'finalize': finalize()
    else: main()
