"""Convert the completed new-reference pair on CPU, preserving native geometry."""
import gc
import html
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import av
import numpy as np
from PIL import Image, ImageDraw
import requests
from tools import export_soldier_robot_batch as matte_tools
from tools import verify_masked_rifleman_motion as base
from tools import export_guardian_drone_batch as checks

OUT = ROOT / 'outputs/cp01-new-reference-20261026'
REVISION = 'cp01-new-reference-protected-alpha-v1'


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def configure():
    base.OUT = OUT
    base.SOURCE = OUT / 'source-original.png'
    base.ACTIONS = {a: dict(title=a, loop=a == 'idle', padding=30, frames=24) for a in ('idle', 'attack')}
    base.build = build
    base.configure()


def build():
    cards = []
    for action in ('idle', 'attack'):
        folder = OUT / action
        if not (folder / 'game-animation.webp').exists():
            continue
        review = json.loads((folder / 'review.json').read_text(encoding='utf-8'))
        cards.append(f'<article><h2>{action}</h2><p>{html.escape(review["note"])}</p><img src="{action}/game-animation.webp"><p><a href="{action}/game-animation.gif">GIF</a> · <a href="{action}/native-sheet.png">전체 PNG 시트</a> · <a href="{action}/native-frames.json">프레임 시간</a> · <a href="{action}/matte-review.jpg">밝은·어두운 배경</a> · <a href="{action}/raw.mp4">원본 영상</a></p></article>')
    (OUT / 'preview.html').write_text(checks.page_head('CP01 새 원화') + '<h1>CP01 새 원화 · Idle / Attack</h1><p>768×768 · 24FPS · 원본 좌표 유지. PNG/WebP는 반투명, GIF는 이진 투명도입니다.</p>' + checks.buttons() + '<p><a href="cp01-new-reference-idle-attack.zip">전체 ZIP</a> · <a href="cp01-new-reference-gifs.zip">GIF만 ZIP</a></p><main>' + ''.join(cards) + '</main></html>', encoding='utf-8')


def process():
    q = requests.get('http://127.0.0.1:8189/queue', timeout=10).json()
    if not q.get('queue_running') and not q.get('queue_pending'):
        requests.post('http://127.0.0.1:8189/free', json=dict(unload_models=True, free_memory=True), timeout=30).raise_for_status()
    configure()
    for action in ('idle', 'attack'):
        folder = OUT / action
        source = ROOT / 'outputs/comfy/cp01_new_reference_20261026' / (action + '_00001_.mp4')
        if not (folder / 'raw.mp4').exists():
            shutil.copy2(source, folder / 'raw.mp4')
        assert checks.digest(source) == checks.digest(folder / 'raw.mp4')
        frames = folder / 'all-frames'
        frames.mkdir(exist_ok=True)
        meta = json.loads((folder / 'matte-process.json').read_text(encoding='utf-8')) if (folder / 'matte-process.json').exists() else {}
        assert meta.get('revision', REVISION) == REVISION
        records = {r['frame']: r for r in meta.get('processed', [])}
        with av.open(str(source)) as video:
            stream = video.streams.video[0]
            assert (stream.width, stream.height, stream.average_rate, stream.frames) == (768, 768, 24, 73)
            for i, frame in enumerate(video.decode(video=0)):
                dest = frames / f'frame-{i:03d}.png'
                if dest.exists() and i in records:
                    continue
                cut, info = matte_tools.matte(frame.to_image(), dict(id='cp01-new-reference', subject='human'), action)
                cut.save(dest)
                records[i] = dict(frame=i, **info)
                if i % 12 == 0:
                    save(folder / 'matte-process.json', dict(revision=REVISION, processed=list(records.values()), geometryUnchanged=True))
                    print('MATTED', action, i, flush=True)
        assert len(records) == 73
        save(folder / 'matte-process.json', dict(revision=REVISION, processed=list(records.values()), geometryUnchanged=True, originalVideoPreserved=True))
        if not (folder / 'review.json').exists():
            save(folder / 'review.json', dict(reviewed=False, userApproval='pending', note='새 원화를 참조한 생성 결과입니다. 원본 영상의 얼굴·장비·의상 세부 변화는 남습니다.'))
        settings = json.loads((folder / 'settings.json').read_text(encoding='utf-8'))
        settings.update(removeBackground=True, backgroundRemoval='ai', postProcessing=REVISION)
        save(folder / 'settings.json', settings)
        gc.collect()
    save(OUT / 'idle/selection.json', dict(start=0, end=71, note='Repeated closing anchor omitted; native forward frames only.'))
    base.export()
    validate()
    print('PAIR_READY_FOR_REVIEW', flush=True)


def validate():
    records = {}
    for action in ('idle', 'attack'):
        folder = OUT / action
        native = json.loads((folder / 'native-frames.json').read_text(encoding='utf-8'))
        with Image.open(folder / 'native-sheet.png') as sheet:
            assert sheet.size == (6144, 6912 if action == 'idle' else 7680)
            for n, i in enumerate(native['sourceIndices']):
                with Image.open(folder / 'all-frames' / f'frame-{i:03d}.png') as im:
                    assert np.array_equal(np.array(im.convert('RGBA')), np.array(sheet.crop((n % 8 * 768, n // 8 * 768, (n % 8 + 1) * 768, (n // 8 + 1) * 768)).convert('RGBA')))
        with Image.open(folder / 'game-animation.gif') as gif:
            assert gif.n_frames == native['frameCount']
            total = 0
            for i in range(gif.n_frames):
                gif.seek(i)
                total += gif.info['duration']
        assert abs(total - sum(native['durationMs'])) <= 10
        records[action] = dict(frames=native['frameCount'], durationMs=total)
    save(OUT / 'validation.json', dict(fileChecksPassed=True, originalSourceSha256=checks.digest(OUT / 'source-original.png'), originalVideosPreserved=True, geometryUnchanged=True, cases=records))


def package():
    validate()
    build()
    (OUT / 'README.txt').write_text('CP01 new reference / Idle + Attack\n768x768 native cells, 24FPS. Idle 72 frames / 3 seconds; attack 73 frames / 3.042 seconds.\nUse action/native-sheet.png + native-frames.json, or action/frames/*.png.\n24-frame alternative: game-sheet.png + game-frames.json. Both actions retain common scale and coordinates.\nGIF has binary alpha and 10ms timing; PNG/WebP preserve soft alpha.\nNo new generation, interpolation or reverse playback. Original source and MP4s preserved.\nInput copy was AI-edited to remove hanging liquid and floor puddle. See source.json.\n', encoding='utf-8')
    target = OUT / 'cp01-new-reference-idle-attack.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z, zipfile.ZipFile(OUT / 'cp01-new-reference-gifs.zip', 'w', zipfile.ZIP_DEFLATED) as gifs:
        for name in ('source-original.png', 'source.json', 'reference.png', 'README.txt', 'preview.html', 'validation.json', 'game-registration.json'):
            z.write(OUT / name, name)
        for action in ('idle', 'attack'):
            folder = OUT / action
            for name in ('game-animation.gif', 'game-animation.webp', 'native-sheet.png', 'native-frames.json', 'game-sheet.png', 'game-frames.json', 'settings.json', 'raw.mp4', 'reference-prepared.png', 'review.json', 'matte-review.jpg', 'matte-process.json'):
                z.write(folder / name, action + '/' + name)
            native = json.loads((folder / 'native-frames.json').read_text(encoding='utf-8'))
            for i in native['sourceIndices']:
                z.write(folder / 'all-frames' / f'frame-{i:03d}.png', action + f'/frames/frame-{i:03d}.png')
            gifs.write(folder / 'game-animation.gif', action + '.gif')
    for path in (target, OUT / 'cp01-new-reference-gifs.zip'):
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
    print('PACKAGED', target, round(target.stat().st_size / 1024**2, 1), 'MiB', flush=True)


if __name__ == '__main__':
    globals()[sys.argv[1] if len(sys.argv) > 1 else 'process']()
