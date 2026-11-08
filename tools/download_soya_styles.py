"""Download the pinned Soya illustration inventory; never enable untested models.

Run --prepare once to snapshot upstream metadata and register disabled LoRA cards.
Run without arguments in the background to download/resume the snapshot.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time

import requests

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / 'data/soya-style-import.json'
STATUS = ROOT / 'data/soya-style-download-status.json'
REPO = 'lbh848/comfyui_hooking_server'
STYLE_NAMES = {
    'atomsphere-style': ('Atomsphere · 분위기 채색', '광택을 줄이고 색 구성과 공간감을 보완하는 Anima 화풍'),
    'anima-ci10ranko': ('ci10ranko · 작가 화풍', 'Anima용 작가 화풍 LoRA · 혼합 및 호환성 시험 예정'),
    'anima-n4t4r4p1su': ('Na tarapisu · 작가 화풍', 'Anima용 작가 화풍 LoRA · 혼합 및 호환성 시험 예정'),
    'anima-m4me-v1.2': ('m4me · 작가 화풍', 'Anima용 작가 화풍 LoRA · 혼합 및 호환성 시험 예정'),
    'kieed-style': ('Kieed · 작가 화풍', 'Anima용 LoKr · 로더 호환성 및 화풍 시험 예정'),
    'suujiniku-style': ('suujiniku · 작가 화풍', 'Illustrious 전용 · 현재 Anima 및 Animagine 경로에서는 사용 불가'),
    'anima-screenshot-v5-000009': ('Screenshot · 애니 화면', 'Anima용 애니 화면 스타일 · 실생성 검증 전'),
    'anima-boldline-v13': ('Boldline · 굵은 선', 'Anima용 선화 스타일 · 실생성 검증 전'),
    'blue-archive-style-b1': ('Blue Archive · 게임 화풍', '블루 아카이브 스타일 · 실생성 검증 전'),
    'ix7-style': ('ix7 · 작가 화풍', '작가 화풍 LoRA · 실생성 검증 전'),
    'flat0521-anima-lora': ('Flat0521 · 플랫 화풍', 'Anima용 플랫 스타일 · 실생성 검증 전'),
    'anima-matsuda-hikari-v1.0': ('Matsuda Hikari · 작가 화풍', 'Anima용 작가 화풍 · 실생성 검증 전'),
}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def get_json(url):
    response = requests.get(url, timeout=45)
    response.raise_for_status()
    return response.json()


def prepare():
    commit = get_json(f'https://api.github.com/repos/{REPO}/commits/main')['sha']
    manifest = get_json(f'https://raw.githubusercontent.com/{REPO}/{commit}/comfy_installer/resources/install_manifest.json')
    entries = []
    for model in manifest['models']:
        path = model['relative_path']
        if model['id'].startswith('qwen-'):
            continue
        if not (path.startswith('models/loras/') or path.startswith('models/checkpoints/') or model['id'] in {
            'anima-2.9b-preview-v1', 'anima-base-v1', 'anima-aesthetic-v1.1',
            'anima-yume-v0.2', 'illustrious-xl-v1-vae', 'anima-text-encoder', 'anima-vae',
        }):
            continue
        # Only illustration LoRAs: the same upstream manifest also includes video weights.
        if path.startswith('models/loras/') and any(x in model['id'] for x in ['minimax', 'h3', 'lightx']):
            continue
        entry = dict(model)
        if path.startswith('models/loras/'):
            entry['relative_path'] = 'models/loras/soya-import/' + Path(path).name
        if 'civitai.com' in model['url']:
            version_id = int(re.search(r'/models/(\d+)', model['url'])[1])
            version = get_json(f'https://civitai.com/api/v1/model-versions/{version_id}')
            info = get_json(f"https://civitai.com/api/v1/models/{version['modelId']}")
            entry['metadata'] = {
                'versionId': version_id, 'modelId': version['modelId'],
                'name': info['name'], 'baseModel': version['baseModel'],
                'creator': info.get('creator', {}).get('username', ''),
                'triggers': version.get('trainedWords', []),
                'source': f"https://civitai.com/models/{version['modelId']}?modelVersionId={version_id}",
                'permissions': {k: info.get(k) for k in ['allowNoCredit', 'allowCommercialUse', 'allowDerivatives', 'allowDifferentLicense']},
            }
        entries.append(entry)
    save(INVENTORY, {'source': f'https://github.com/{REPO}/tree/{commit}', 'models': entries})
    catalogue_path = ROOT / 'web/assets/image-styles.json'
    catalogue = json.loads(catalogue_path.read_text(encoding='utf-8'))
    existing = {s['id'] for s in catalogue['styles']}
    for entry in entries:
        if entry['id'] not in STYLE_NAMES or 'soya-' + entry['id'] in existing:
            continue
        meta = entry['metadata']
        name, description = STYLE_NAMES[entry['id']]
        catalogue['styles'].append({
            'id': 'soya-' + entry['id'], 'name': name, 'description': description,
            'family': 'anima' if meta['baseModel'] == 'Anima' else 'illustrious',
            'enabled': False, 'experimental': True,
            'verification': '다운로드 준비 · 실생성 검증 전',
            'filename': entry['relative_path'].removeprefix('models/loras/'),
            'strength': 0.5, 'previews': [], 'license': '기반 모델 및 제작자 이용 조건 확인',
            'downloadUrl': entry['url'], 'bytes': entry['size'], 'sha256': entry['sha256'],
            **meta,
            # Keep the descriptive display name rather than the remote model title.
        })
        catalogue['styles'][-1]['name'] = name
    save(catalogue_path, catalogue)
    print(json.dumps({'models': len(entries), 'GB': round(sum(e['size'] for e in entries) / 1e9, 2), 'source': commit}))


def valid(path, entry):
    if not path.exists() or path.stat().st_size != entry['size']:
        return False
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() == entry['sha256'].lower()


def download(entry):
    target = (ROOT / 'ComfyUI' / entry['relative_path']).resolve()
    if not target.is_relative_to((ROOT / 'ComfyUI/models').resolve()):
        raise ValueError('Invalid model path')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if valid(target, entry):
            return
        raise ValueError('Existing model differs; preserved without overwrite')
    part = target.with_suffix('.download')
    if valid(part, entry):
        part.replace(target)
        return
    key = os.environ.get('CIVITAI_API_KEY', '').strip()
    headers = {'Authorization': 'Bearer ' + key} if key and 'civitai.com' in entry['url'] else {}
    offset = part.stat().st_size if part.exists() else 0
    if offset >= entry['size']:
        offset = 0
    if offset:
        headers['Range'] = f'bytes={offset}-'
    with requests.get(entry['url'], headers=headers, stream=True, timeout=(30, 120)) as response:
        if response.status_code not in (200, 206):
            # Do not log signed redirect URLs or credentials.
            raise RuntimeError(f'HTTP {response.status_code}')
        if response.status_code == 206:
            if not response.headers.get('Content-Range', '').startswith(f'bytes {offset}-'):
                raise RuntimeError('Unexpected byte range')
        else:
            offset = 0
        with part.open('ab' if offset else 'wb') as stream:
            for chunk in response.iter_content(4 * 1024 * 1024):
                stream.write(chunk)
    if not valid(part, entry):
        raise RuntimeError('Size or SHA256 mismatch; not installed')
    part.replace(target)


def main():
    global INVENTORY, STATUS
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--inventory', type=Path, help='Download a separate pinned model inventory')
    args = parser.parse_args()
    if args.inventory:
        INVENTORY = args.inventory.resolve()
        STATUS = INVENTORY.with_name(INVENTORY.stem + '-status.json')
    if args.prepare:
        prepare()
        return
    entries = json.loads(INVENTORY.read_text(encoding='utf-8'))['models']
    # Small files first so the style inventory is available before large checkpoints.
    entries.sort(key=lambda entry: entry['size'])
    state = {'state': 'running', 'models': {}}
    save(STATUS, state)
    for entry in entries:
        state['current'] = entry['id']
        state['models'][entry['id']] = 'downloading'
        save(STATUS, state)
        for attempt in range(3):
            try:
                download(entry)
                state['models'][entry['id']] = 'verified'
                break
            except Exception as exc:
                state['models'][entry['id']] = 'failed: ' + type(exc).__name__
                if attempt < 2:
                    time.sleep(3)
        save(STATUS, state)
        print(entry['id'], state['models'][entry['id']], flush=True)
    state['state'] = 'complete' if all(v == 'verified' for v in state['models'].values()) else 'completed_with_errors'
    state.pop('current', None)
    save(STATUS, state)


if __name__ == '__main__':
    main()
