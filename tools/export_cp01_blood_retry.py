"""Blood-aware foreground extraction; never key out opaque trouser interiors."""
import gc
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
from scipy import ndimage
from pymatting import estimate_alpha_cf, estimate_foreground_ml
import image_background
from tools import export_cp01_new_reference as export
from tools.sprite_matte import clean_flat_matte

OUT = ROOT / 'outputs/cp01-blood-retry-20261026'
REVISION = 'blood-and-opaque-trouser-alpha-v1'
BASE_BUILD = export.build


def build():
    BASE_BUILD()
    p = OUT / 'preview.html'
    text = p.read_text(encoding='utf-8').replace('CP01 새 원화', 'CP01 혈계 재생성')
    text = text.replace('cp01-new-reference-idle-attack.zip', 'cp01-blood-idle-attack.zip').replace('cp01-new-reference-gifs.zip', 'cp01-blood-gifs.zip')
    p.write_text(text, encoding='utf-8')


def refine_cut(raw, cut):
    rgb = np.array(raw.convert('RGB'))
    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]))
    bg = np.median(border, axis=0)
    delta = np.max(np.abs(rgb.astype(float) - bg), axis=2)
    neutral = (delta < 26) & (np.ptp(rgb.astype(float), axis=2) < 14)
    seeds = np.zeros(neutral.shape, bool)
    seeds[0], seeds[-1], seeds[:, 0], seeds[:, -1] = neutral[0], neutral[-1], neutral[:, 0], neutral[:, -1]
    exterior = ndimage.binary_propagation(seeds, mask=neutral)
    # Only blood and dark boots belong in the original low pool region. Clear
    # neutral holes between its red rings even when the semantic mask fills them.
    yy, _ = np.indices(neutral.shape)
    pool_holes = (yy > 640) & (delta < 16) & (np.ptp(rgb.astype(float), axis=2) < 10)
    rgba = np.dstack((rgb, np.array(cut.getchannel('A'))))
    rgba[exterior | pool_holes, 3] = 0
    result, info = clean_flat_matte(Image.fromarray(rgba), tolerance=26, radius=3)
    info.update(exteriorRemoved=int(exterior.sum()), poolHolesCleared=int(pool_holes.sum()))
    return result, info


def refine():
    configure()
    for action in ('idle', 'attack'):
        folder = OUT / action
        records = []
        with av.open(str(folder / 'raw.mp4')) as video:
            for i, frame in enumerate(video.decode(video=0)):
                p = folder / 'all-frames' / f'frame-{i:03d}.png'
                with Image.open(p) as im:
                    cut, info = refine_cut(frame.to_image(), im.convert('RGBA'))
                cut.save(p)
                records.append(dict(frame=i, **info))
        export.save(folder / 'contour-refinement.json', dict(revision='neutral-exterior-and-pool-holes-v1', frames=records))
        p = folder / 'frames.json'
        if p.exists():
            p.replace(folder / 'pre-refinement-frames.json')
    export.base.export()
    export.validate()
    print('REFINED_PAIR_READY', flush=True)


def matte(raw):
    rgb = np.array(raw.convert('RGB'), dtype=float)
    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]))
    bg = np.median(border, axis=0)
    delta = np.max(np.abs(rgb - bg), axis=2)
    chroma = np.ptp(rgb, axis=2)
    semantic = np.array(image_background.remove(raw))[:, :, 3]
    # No global neutral-component subtraction: that punched holes in gray pants.
    protected = ndimage.distance_transform_edt(semantic > 220) > 1.5
    near = (delta < 12) & (chroma < 9)
    seeds = np.zeros(delta.shape, bool)
    seeds[0], seeds[-1], seeds[:, 0], seeds[:, -1] = near[0], near[-1], near[:, 0], near[:, -1]
    exterior = ndimage.binary_propagation(seeds, mask=near)
    protected[exterior] = False
    red = (rgb[:, :, 0] - rgb[:, :, 1] > 24) & (rgb[:, :, 0] - rgb[:, :, 2] > 12) & (delta > 24)
    red_core = ndimage.distance_transform_edt(red) > 1
    protected |= red_core
    background = exterior | (near & (semantic < 128)) | ((delta < 18) & (chroma < 8) & (semantic < 16))
    trimap = np.full(delta.shape, .5)
    trimap[(delta > 40) | protected] = 1
    trimap[background & ~protected] = 0
    image = rgb / 255
    alpha = np.clip(estimate_alpha_cf(image, trimap), 0, 1)
    foreground = np.clip(estimate_foreground_ml(image, alpha), 0, 1)
    alpha[protected] = 1
    foreground[protected] = image[protected]
    alpha[alpha < .02] = 0
    alpha[alpha > .995] = 1
    rgba = np.rint(np.dstack((foreground, alpha)) * 255).astype('uint8')
    rgba[alpha == 0] = 0
    assert np.all(rgba[:, :, 3][protected] == 255)
    return Image.fromarray(rgba), dict(background=bg.tolist(), protectedInteriorPixels=int(protected.sum()),
         protectedRedPixels=int(red_core.sum()), opaqueInteriorsPreserved=True)


def configure():
    export.OUT = OUT
    export.build = build
    export.configure()
    for action in export.base.ACTIONS:
        export.base.ACTIONS[action]['padding'] = 20
    export.base.configure()


def process():
    configure()
    for action in ('idle', 'attack'):
        folder = OUT / action
        source = ROOT / 'outputs/comfy/cp01_blood_retry_20261026' / (action + '_00001_.mp4')
        if not (folder / 'raw.mp4').exists():
            shutil.copy2(source, folder / 'raw.mp4')
        assert export.checks.digest(source) == export.checks.digest(folder / 'raw.mp4')
        frames = folder / 'all-frames'
        frames.mkdir(exist_ok=True)
        old = json.loads((folder / 'matte-process.json').read_text(encoding='utf-8')) if (folder / 'matte-process.json').exists() else {}
        assert old.get('revision', REVISION) == REVISION
        records = {r['frame']: r for r in old.get('processed', [])}
        with av.open(str(source)) as video:
            s = video.streams.video[0]
            assert (s.width, s.height, s.average_rate, s.frames) == (768, 768, 24, 73)
            for i, frame in enumerate(video.decode(video=0)):
                path = frames / f'frame-{i:03d}.png'
                if path.exists() and i in records:
                    continue
                cut, info = matte(frame.to_image())
                cut.save(path)
                records[i] = dict(frame=i, **info)
                if i % 12 == 0:
                    export.save(folder / 'matte-process.json', dict(revision=REVISION, processed=list(records.values()), geometryUnchanged=True))
                    print('MATTED', action, i, flush=True)
        assert len(records) == 73
        export.save(folder / 'matte-process.json', dict(revision=REVISION, processed=list(records.values()), geometryUnchanged=True))
        if not (folder / 'review.json').exists():
            export.save(folder / 'review.json', dict(reviewed=False, userApproval='pending', note='혈계 원본을 보존한 새 생성 결과. 의상·얼굴·무기 세부의 생성 변화는 남습니다.'))
        settings = json.loads((folder / 'settings.json').read_text(encoding='utf-8'))
        settings.update(removeBackground=True, backgroundRemoval='ai', postProcessing=REVISION)
        export.save(folder / 'settings.json', settings)
        gc.collect()
    export.save(OUT / 'idle/selection.json', dict(start=0, end=71, note='Closing anchor omitted; forward frames only.'))
    export.base.export()
    export.validate()
    print('BLOOD_PAIR_READY_FOR_REVIEW', flush=True)


def package():
    configure()
    export.package()
    old = OUT / 'cp01-new-reference-idle-attack.zip'
    readme = OUT / 'README.txt'
    text = readme.read_text(encoding='utf-8').replace('CP01 new reference', 'CP01 blood-ability retry').replace(
        'Input copy was AI-edited to remove hanging liquid and floor puddle. See source.json.',
        'The input is identical to the original blood-ability artwork, including the red liquid and pool. No source repaint. See source.json.\nNeutral exterior and enclosed blood-pool holes refined separately; opaque trouser interiors protected.\n')
    readme.write_text(text, encoding='utf-8')
    with zipfile.ZipFile(old) as source, zipfile.ZipFile(OUT / 'cp01-blood-idle-attack.zip', 'w', zipfile.ZIP_DEFLATED) as dest:
        for info in source.infolist():
            data = readme.read_bytes() if info.filename == 'README.txt' else source.read(info.filename)
            dest.writestr(info.filename, data)
        for action in ('idle', 'attack'):
            dest.write(OUT / action / 'contour-refinement.json', action + '/contour-refinement.json')
    with zipfile.ZipFile(OUT / 'cp01-blood-idle-attack.zip') as archive:
        assert archive.testzip() is None
    shutil.copy2(OUT / 'cp01-new-reference-gifs.zip', OUT / 'cp01-blood-gifs.zip')
    print('BLOOD_HANDOFF_READY', flush=True)


if __name__ == '__main__':
    globals()[sys.argv[1] if len(sys.argv) > 1 else 'process']()
