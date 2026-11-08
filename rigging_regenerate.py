"""Private, queued candidates; never modifies a character until an editor revision is saved."""
import base64
import io
import json
from pathlib import Path
import secrets
import requests
from PIL import Image, ImageChops, ImageFilter
import rigging_engine as rigging
import rigging_editor as editor

ROOT = Path(__file__).resolve().parent / 'outputs' / 'rig-candidates'


def eligible(record):
    return (not record.get('variantOf') and
            (record['id'].startswith('eye_close') or record['id'] in ('mouth_open', 'mouth_close') or
             record.get('runtimeName') in ('objects', 'object') or record['id'].startswith(('objects', 'object_'))))


def validate(folder, data):
    manifest = editor.read_manifest(folder)
    if type(data.get('revision')) is not int or data['revision'] != int(manifest.get('editRevision', 0)):
        raise ValueError('작업 버전이 바뀌었습니다. 새로고침한 뒤 다시 시도하세요.')
    key = data.get('layerKey')
    record = dict(editor.layer_records(manifest)).get(key) if isinstance(key, str) else None
    if not record or not eligible(record):
        raise ValueError('감긴 눈·입 차분 또는 object 장비 레이어를 선택하세요.')
    hint = data.get('hint', '')
    if not isinstance(hint, str) or len(hint) > 500:
        raise ValueError('추가 요청은 500자 이하로 입력하세요.')
    try:
        editor.source_reference_path(folder)
    except FileNotFoundError:
        raise ValueError('원본 이미지가 없습니다. 원본 연결 버튼으로 이미지를 먼저 연결하세요.') from None
    return manifest, record


def image_data(image):
    out = io.BytesIO(); image.save(out, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode()


def expression_region(manifest, record):
    w, h = manifest['canvas']['width'], manifest['canvas']['height']
    related = [record]
    if record['id'].startswith('eye_close'):
        related += [r for _, r in editor.layer_records(manifest) if
                    r['id'] == 'eye_open_original']
    else:
        related += [r for _, r in editor.layer_records(manifest) if r['id'] in ('mouth_open', 'mouth_close')]
    # Only the selected eye's slot when the package has separate left/right eyes.
    if record['id'] != 'eye_close':
        related = [record] if record['id'].startswith('eye_close') else related
    pad = max(3, round(w / 180))
    return (max(0, min(r['left'] for r in related)-pad), max(0, min(r['top'] for r in related)-pad),
            min(w, max(r['left']+r['width'] for r in related)+pad),
            min(h, max(r['top']+r['height'] for r in related)+pad))


def run_job(jid, p):
    folder = rigging.RESULT_ROOT / p['parentJob']
    manifest, record = validate(folder, p)
    target = ROOT / jid
    target.mkdir(parents=True, exist_ok=True)
    source = rigging.INPUT_ROOT / ('regenerate_' + jid + '.png')
    try:
        with Image.open(editor.source_reference_path(folder)) as opened:
            original = opened.convert('RGBA').resize((manifest['canvas']['width'], manifest['canvas']['height']), Image.Resampling.LANCZOS)
        prefix = 'rig_candidate_' + jid
        seed = secrets.randbelow(2**32)
        is_expression = record['id'].startswith('eye_close') or record['id'] in ('mouth_open', 'mouth_close')
        if is_expression:
            if not all(path.is_file() for path in rigging.QWEN_MODEL_PATHS):
                raise ValueError('눈·입 재생성에 필요한 Qwen 편집 모델이 설치되지 않았습니다.')
            box = expression_region(manifest, record)
            padding = max(32, box[2]-box[0], 3*(box[3]-box[1]))
            context = (max(0, box[0]-padding), max(0, box[1]-padding), min(original.width, box[2]+padding), min(original.height, box[3]+padding))
            original.crop(context).convert('RGB').save(source)
            graph = rigging.qwen21_workflow(source.name, prefix, 768, 20, seed)
            action = ('Close the eyes naturally with delicate curved eyelash lines. Both eyelids must be fully closed; no irises or eye whites.'
                      if record['id'].startswith('eye_close') else
                      'Make the mouth slightly open, a small natural speaking mouth.' if record['id']=='mouth_open' else
                      'Close the mouth naturally with a delicate short lip line.')
            graph['5']['inputs']['prompt'] = ('Edit this exact anime face. ' + action +
                ' Preserve the original drawing style, face angle, colors, skin, eyebrows, hair and accessories. '
                'Keep the same composition, crop and feature locations. Do not add text. ' + p.get('hint',''))
        else:
            original.save(source)
            graph = rigging.workflow(source.name, prefix, 1024, 30, seed)
        update_job(jid, state='generating', message='선택 파츠 재생성 중 · 기존 결과는 유지됩니다.')
        response = requests.post(rigging.COMFY_URL+'/prompt', json={'prompt':graph}, timeout=60)
        if not response.ok:
            raise RuntimeError('재생성 워크플로 실행 실패: '+response.text[:400])
        history = rigging._wait_for_prompt(response.json()['prompt_id'])
        if is_expression:
            with Image.open(rigging._saved_image(history, '9')) as opened:
                edited = opened.convert('RGBA').resize((context[2]-context[0], context[3]-context[1]), Image.Resampling.LANCZOS)
            image = edited.crop((box[0]-context[0], box[1]-context[1], box[2]-context[0], box[3]-context[1]))
            alpha = Image.new('L', image.size, 255)
            # Feather the small skin patch so it covers old eye pixels without a hard rectangle.
            from PIL import ImageDraw
            ImageDraw.Draw(alpha).rectangle((0,0,image.width-1,image.height-1), outline=0, width=2)
            image.putalpha(alpha.filter(ImageFilter.GaussianBlur(1)))
            left, top = box[:2]
        else:
            info_path = rigging._latest_layers(prefix)
            info = json.loads(info_path.read_text(encoding='utf-8'))
            matches = [r for r in info['layers'] if str(r.get('name','')).split('_')[0] in ('objects','object')]
            if not matches:
                raise ValueError('이번 결과에서 object 장비를 찾지 못했습니다. 원본 복원 도구로 복원할 수도 있습니다.')
            full = Image.new('RGBA', (int(info['width']),int(info['height'])))
            for r in matches:
                path = (info_path.parent / r['filename']).resolve()
                if not path.is_relative_to(rigging.COMFY_OUTPUT.resolve()):
                    raise ValueError('레이어 출력 경로가 올바르지 않습니다.')
                with Image.open(path) as opened:
                    full.alpha_composite(opened.convert('RGBA'), (int(r['left']), int(r['top'])))
            if full.size != original.size:
                full = full.convert('RGBa').resize(original.size,Image.Resampling.LANCZOS).convert('RGBA')
            # Select the component intersecting this slot rather than copying unrelated objects.
            from PIL import ImageDraw
            mask = Image.new('L', full.size)
            pad = max(16, round(min(record['width'],record['height'])*.15))
            ImageDraw.Draw(mask).rectangle((record['left']-pad,record['top']-pad,record['left']+record['width']+pad,record['top']+record['height']+pad),fill=255)
            full.putalpha(ImageChops.multiply(full.getchannel('A'),mask))
            box = full.getbbox()
            if not box: raise ValueError('선택한 위치에서 장비가 검출되지 않았습니다. 기존 레이어는 유지됩니다.')
            image = full.crop(box); left, top = box[:2]
        image.save(target/'candidate.png')
        result = dict(layerKey=p['layerKey'],revision=p['revision'],left=left,top=top,width=image.width,height=image.height,seed=seed)
        (target/'candidate.json').write_text(json.dumps(result),encoding='utf-8')
        update_job(jid,state='complete',message='재생성 완료 · 비교 후 적용하세요.',candidate=result)
    finally:
        source.unlink(missing_ok=True)


def update_job(jid, **changes):
    pass  # installed by the shared FIFO worker
