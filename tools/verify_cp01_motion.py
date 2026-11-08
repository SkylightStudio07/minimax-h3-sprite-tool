"""Private reference-conditioned MiniMax idle and dagger attack for CP01."""
import argparse
import hashlib
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
import idle_tool as engine
import image_background
from tools import verify_masked_raider_motion as exporter
from tools import verify_pixel_minimax as executor
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release

SOURCE = Path('C:/Users/SKYLIGHT/Documents/Graduation/Project-Vertex/Assets/Art/Characters/Joining Characters/CP_01/15ed2637-342f-487e-97ad-bc230d60251c.png')
OUT = ROOT / 'outputs/cp01-dagger-motion-20261023'
IDENTITY = (
    'Animate the EXACT SAME single hand-drawn 2D anime character from the input illustration. '
    'Keep the white short bob haircut, single crimson hair streak/headband, red eyes, white long-sleeve '
    'collared blouse, slim black tie, long grey flared trousers, crimson gloves and black platform '
    'ankle boots. Same facial features and adult body proportions. Preserve the original ink outlines '
    'and flat cel-painted shadow regions and original colors. This remains a drawn 2D illustration in '
    'every frame, without realistic relighting or 3D material rendering. '
    'Same screen-RIGHT-facing profile view, one eye visible, gaze to the right. Do not turn toward the '
    'camera or show a back view. ONE short dark triangular dagger with circular pommel remains in '
    'the original extended gloved hand; maintain the blade length, shape and grip. Other hand stays '
    'empty near the torso. Keep the existing thin crimson graphic ribbons following the hand with '
    'small motion; no new weapons, giant effects, blood splatter or extra characters. ')
ACTIONS = {
    'idle': dict(title='대기 · 오른쪽', seed=2026102331, padding=20, loop=True, strength='low', frames=16,
        prompt='A very restrained combat-ready idle in the supplied pose. Both boots remain planted '
        'on the same coordinates, dagger arm stays extended toward screen RIGHT at its original '
        'height. Only shallow natural breathing, a tiny relaxed shoulder movement, and subtle sway '
        'of the bob hair tips, black tie and crimson ribbon. Keep face and open eyes stable. No '
        'stepping, crouching, arm lowering, weapon attack, head rotation or speaking. End in the '
        'original pose for a quiet loop.'),
    'attack': dict(title='단검 찌르기 · 오른쪽', seed=2026102332, padding=20, loop=False, strength='normal', frames=24,
        prompt='Perform exactly ONE fast short DAGGER THRUST toward SCREEN RIGHT and recover. '
        'The opening reference already has the knife arm extended. First briefly draw that same '
        'hand back to beside the ribs by bending the elbow while knees flex, keeping the blade '
        'pointing right. Then sharply extend the arm in ONE straight horizontal thrust to the RIGHT, '
        'with a small forward weight transfer onto the front boot. Keep a compact clean silhouette '
        'and an upright balanced spine. The empty hand counterbalances near the chest. The wrist, '
        'knife and forearm travel together; the short blade does not stretch or turn into a sword. '
        'A narrow crimson ribbon briefly follows the dagger without obscuring the face or body. '
        'After a short impact hold, retract slightly and return to the original extended ready '
        'stance. No second attack, spin, running, jump, full body turn, kicking, giant slash wave '
        'or target. Keep both boots and the full knife motion inside the canvas.'),
}


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ('source-original.png', 'reference.png'):
        p = OUT / name
        if not p.exists(): shutil.copyfile(SOURCE, p)
        assert digest(p) == digest(SOURCE)
    save(OUT / 'source.json', dict(sourcePath=str(SOURCE), sha256=digest(SOURCE),
         sourceUnchanged=True, sourceSize=list(Image.open(SOURCE).size), published=False,
         preparation='Exact original RGBA; fit on neutral matte with 20 percent motion padding.'))
    for name in ACTIONS: (OUT / name).mkdir(exist_ok=True)


def generate():
    prepare()
    for name, item in ACTIONS.items():
        folder = OUT / name
        if (folder / 'raw.mp4').exists(): continue
        if (folder / 'native-v1-pending.json').exists():
            graph = json.loads((folder / 'native-v1-workflow.json').read_text(encoding='utf-8'))
        else:
            ensure_idle()
            engine.start_comfy()
            release((8190, 8191))
            prepared = engine.prepare_reference_image((OUT / 'reference.png').read_bytes(), 768, 768, item['padding'])
            (folder / 'reference-prepared.png').write_bytes(prepared)
            uploaded = engine.upload_image(prepared, 'cp01-dagger-' + name + '.png')
            prompt = IDENTITY + item['prompt'] + (
                ' Fixed camera and lighting, no pan, zoom, shake or cuts. Entire body, hair and dagger '
                'stay within the frame with empty margins. Uniform flat medium GREY background '
                'including the gaps between limbs; no floor plane, cast shadow, scenery or text.')
            graph = engine.build_workflow(uploaded, prompt, 3, 768, 768, item['seed'],
                animation_type=name, loop=item['loop'], facing='preserve', flat_background=True,
                blink_mode='none', motion_strength=item['strength'], sampling_mode='quality', workflow_id='standard')
            graph['15']['inputs'].pop('audio', None)
            graph.pop('14', None)
            graph.pop('5', None)
            graph['16']['inputs']['filename_prefix'] = 'cp01_dagger_20261023/' + name
            save(folder / 'settings.json', dict(animationType=name, seed=item['seed'], width=768,
                height=768, duration=3, fps=24, steps=20, loop=item['loop'], facing='preserve',
                motionPadding=item['padding'], motionStrength=item['strength'], samplingMode='quality',
                workflowId='standard', prompt=prompt, actualPrompt=graph['6']['inputs']['prompt'],
                referenceOffsetX=0, sourceSha256=digest(SOURCE), published=False))
        executor.OUT = folder
        history = executor.execute(graph, engine.COMFY_URL, 'native-v1')
        shutil.copyfile(engine.find_saved_video(history), folder / 'raw.mp4')
        print('VIDEO_READY', name, flush=True)
    ensure_idle()
    release((8189,))


semantic_remove = image_background.remove_sprite


def cut_with_crimson(image):
    cut = semantic_remove(image)
    rgb = np.asarray(image.convert('RGB'), dtype=np.float32)
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    red = (r > 65) & (r - g > 30) & (r - b > 20)
    # The input deliberately includes detached crimson graphic ribbons. Keep
    # strongly chromatic red shapes that the character-only mask can discard.
    confidence = np.minimum(np.clip((r - g - 18) / 30, 0, 1), np.clip((r - b - 8) / 18, 0, 1))
    alpha = np.array(cut.getchannel('A'))
    alpha[red] = np.maximum(alpha[red], (confidence[red] * 255).astype(np.uint8))
    cut.putalpha(Image.fromarray(alpha))
    return cut


def configure():
    exporter.OUT = OUT
    exporter.SOURCE = SOURCE
    exporter.ACTIONS = ACTIONS
    exporter.build = build


def export():
    configure()
    idle = OUT / 'idle'
    if (idle / 'raw.mp4').exists() and not (idle / 'selection.json').exists():
        with av.open(str(idle / 'raw.mp4')) as v: count = sum(1 for _ in v.decode(video=0))
        save(idle / 'selection.json', dict(start=0, end=count-2, note='Omit repeated final reference frame.'))
    image_background.remove_sprite = cut_with_crimson
    try: exporter.export()
    finally: image_background.remove_sprite = semantic_remove
    exporter.game()


def build():
    cards = []
    for name, item in ACTIONS.items():
        folder = OUT / name
        if not (folder / 'animation.webp').exists(): continue
        prefix = 'game-' if (folder / 'game-animation.webp').exists() else ''
        note = ('움직임이 매우 작은 대기입니다.' if name == 'idle' else
                '단검이 원본보다 길게 변하며, 붉은 궤적 끝이 화면 밖으로 나가는 프레임이 있습니다. 뒤쪽 정지 구간을 덜어내고 1.15배속으로 표시합니다.')
        cards.append(f'<article><h2>{item["title"]}</h2><p>{note}</p><img src="{name}/{prefix}animation.webp">'
            f'<p><a href="{name}/{prefix}animation.gif">GIF</a> · <a href="{name}/{prefix}sheet.png">PNG 시트</a> · '
            f'<a href="{name}/{prefix}frames.json">프레임 시간</a> · <a href="{name}/raw.mp4">원본 영상</a> · '
            f'<a href="{name}/review-strip.webp">프레임 비교</a></p></article>')
    page = ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        '<title>단검 캐릭터 · idle / 공격</title><style>body{margin:24px;background:#182130;color:#eef0f6;font:16px/1.6 system-ui}'
        'main{display:flex;gap:20px;flex-wrap:wrap}article{width:512px}img{width:100%;background:repeating-conic-gradient(#263247 0 25%,#43516a 0 50%) 0/24px 24px}'
        'a{color:#c9c0ff}.source{height:400px;width:auto}</style><h1>단검 캐릭터 · 대기 / 오른쪽 찌르기</h1>'
        '<p>첨부 원화를 직접 입력한 MiniMax 영상 생성 시험입니다. 768×768, 24FPS, 20단계. '
        '배경을 제거하고 공통 크기의 GIF와 PNG 시트로 내보냈습니다. 붉은 리본은 입력 이미지에 포함된 요소입니다.</p>'
        '<p>얼굴·손·무기의 세부와 그림체에는 생성에 따른 변화가 남을 수 있습니다. 공격은 단발 동작이며 GIF에서는 반복 표시합니다.</p>'
        '<a href="cp01-dagger-handoff.zip">전체 파일 ZIP</a> · <a href="source-original.png">입력 원화</a>'
        '<main>' + ''.join(cards) + '</main></html>')
    (OUT / 'preview.html').write_text(page, encoding='utf-8')


def check():
    assert digest(SOURCE) == digest(OUT / 'source-original.png')
    records = {}
    for name in ACTIONS:
        folder = OUT / name
        meta = json.loads((folder / 'frames.json').read_text(encoding='utf-8'))
        with Image.open(folder / 'game-animation.gif') as gif:
            assert gif.n_frames == len(meta['previewSourceIndices'])
            duration = 0
            for i in range(gif.n_frames):
                gif.seek(i)
                duration += gif.info['duration']
            assert abs(duration - sum(meta['previewDurationMs'])) <= 10
        sheet = Image.open(folder / 'game-sheet.png').convert('RGBA')
        selected = sorted((folder / 'game-selected').glob('*.png'))
        for i, path in enumerate(selected):
            cell = sheet.crop((i%4*768, i//4*768, (i%4+1)*768, (i//4+1)*768))
            assert np.array_equal(np.array(cell), np.array(Image.open(path).convert('RGBA')))
        records[name] = dict(sourceFrames=meta['sourceFrames'], sheetFrames=len(selected),
            gifFrames=len(meta['previewSourceIndices']), durationMs=duration,
            edgeContactFrames=[x['frame'] for x in meta['diagnostics'] if x['edgeContact']])
    save(OUT / 'validation.json', dict(fileChecksPassed=True, visualApproval='pending user review',
         visualReview=dict(idle='Very restrained movement; drawn source appearance retained.',
             attack='One rightward thrust; dagger elongation and ribbon tip clipping remain.'),
         sourceUnchanged=True, websiteUnchanged=True, cases=records))
    (OUT / 'README.txt').write_text('CP01 idle / dagger attack\n\nMiniMax reference-conditioned video, 768px 24FPS 20 steps.\n'
        'Game assets: idle/ and attack/ game-sheet.png, game-frames.json, game-selected/*.png.\n'
        'GIF/WebP previews share a common crop and character scale.\n'
        'One-shot attack repeats for preview only.\n'
        'AI generation may change face, fingers, knife and costume details.\n'
        'Observed: dagger becomes longer during attack; some crimson trail tips cross the frame edge.\n'
        'Attack preview: raw frames 0-47 at 1.15x speed; original 73-frame video preserved.\n'
        'Original user image preserved. Nothing published to the site.\n', encoding='utf-8')
    with zipfile.ZipFile(OUT / 'cp01-dagger-handoff.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for name in ACTIONS:
            for filename in ['game-animation.gif','game-animation.webp','game-sheet.png','game-frames.json',
                             'raw.mp4','settings.json','reference-prepared.png']:
                z.write(OUT / name / filename, name + '/' + filename)
            for p in (OUT / name / 'game-selected').glob('*.png'):
                z.write(p, name + '/game-selected/' + p.name)
        for filename in ['source-original.png','source.json','README.txt','validation.json','preview.html']:
            z.write(OUT / filename, filename)
    with zipfile.ZipFile(OUT / 'cp01-dagger-handoff.zip') as z: assert z.testzip() is None
    print('VALIDATED', json.dumps(records), flush=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['generate','export','build','check','all'])
    args = parser.parse_args()
    if args.stage == 'all': generate(); export(); check()
    else: globals()[args.stage]()
