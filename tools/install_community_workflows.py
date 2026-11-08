"""Install pinned community nodes in an isolated Comfy base and Python overlay.

Model weights are shared with the working tool. Existing environments are never
modified. Long-running installs report to data/community-workflows-status.json.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'ComfyUI-workflows'
VENV = ROOT / '.venv-workflows'
PYTHON = VENV / 'Scripts/python.exe'
STATE = ROOT / 'data/community-workflows-status.json'
PINS = {
    'n0va39/ComfyUI-EasyUseAnima': 'be9f4b34f3269ff503199b2f76c345366e6935c5',
    'sorryhyun/ComfyUI-Spectrum-KSampler': 'ff25e70203cfd9b83c20307474ceff29dfb2139c',
    'rgthree/rgthree-comfy': '5f940ddfbb83ff9c667f32ae7d0c3ad0bb8cc9ee',
    'kijai/ComfyUI-KJNodes': '17195fcfa8a05f601b766a0f09c9733284f47416',
    'ltdrdata/ComfyUI-Impact-Pack': '429d0159ad429e64d2b3916e6e7be9c22d025c3c',
    'ltdrdata/ComfyUI-Impact-Subpack': '50c7b71a6a224734cc9b21963c6d1926816a97f1',
    'alexopus/ComfyUI-Image-Saver': 'dbf94571699d6750182821cfe7d90c4e8840257d',
    'willmiao/ComfyUI-Lora-Manager': '1276673e0e7790dab751dddfcd3823ebee3559dd',
    'yolain/ComfyUI-Easy-Use': '4ba22aa1ec2dd606995574d93d70c6c8a3744859',
    'ssitu/ComfyUI_UltimateSDUpscale': 'a5547db9e1d07d3318bb21e9e9c474f4c1e9c8df',
    'pythongosssss/ComfyUI-WD14-Tagger': '9e0a6e700299182fc05c58b62e7ad9f72182a78b',
}
SAM2 = '2b90b9f5ceec907a1c18123530e92e794ad901a4'
UPSCALE_SUB = '2322caa480535b1011a1f9c18126d85ea444f146'


def save(state):
    STATE.parent.mkdir(exist_ok=True)
    temp = STATE.with_suffix('.tmp')
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(STATE)


def archive(repo, commit, dest):
    marker = dest / '.spritelab-source.json'
    if marker.exists():
        if json.loads(marker.read_text())['commit'] == commit:
            return
        raise RuntimeError('Existing extension differs; preserved: ' + dest.name)
    if dest.exists() and any(dest.iterdir()):
        raise RuntimeError('Existing extension is unmanaged; preserved: ' + dest.name)
    response = requests.get(f'https://api.github.com/repos/{repo}/zipball/{commit}', timeout=120)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as bundle:
        for item in bundle.infolist():
            parts = Path(item.filename).parts[1:]
            if not parts or item.is_dir():
                continue
            target = dest.joinpath(*parts).resolve()
            if not target.is_relative_to(dest.resolve()):
                raise ValueError('Unsafe archive path')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bundle.read(item))
    marker.write_text(json.dumps(dict(repo=repo, commit=commit, archiveSha256=hashlib.sha256(response.content).hexdigest())), encoding='utf-8')


def prepare():
    BASE.mkdir(exist_ok=True)
    (BASE / 'custom_nodes').mkdir(exist_ok=True)
    if not PYTHON.exists():
        subprocess.run([sys.executable, '-m', 'venv', str(VENV)], check=True)
    # Read-only reuse of the working environment's installed CUDA/core packages.
    # New packages live in the overlay; pip constraints forbid replacing versions
    # inherited from the working environment.
    (VENV / 'Lib/site-packages/spritelab-core.pth').write_text(str(ROOT / '.venv/Lib/site-packages') + '\n', encoding='utf-8')
    constraints = ROOT / 'data/community-core-constraints.txt'
    if not constraints.exists():
        frozen = subprocess.check_output([str(ROOT / '.venv/Scripts/python.exe'), '-m', 'pip', 'freeze'], text=True)
        constraints.write_text(frozen, encoding='utf-8')
    model_paths = {'checkpoints':'checkpoints','diffusion_models':'diffusion_models','text_encoders':'text_encoders',
                   'vae':'vae','loras':'loras','upscale_models':'upscale_models','controlnet':'controlnet',
                   'clip_vision':'clip_vision','ipadapter':'ipadapter','ultralytics':'ultralytics','sams':'sams'}
    config = ['spritelab_shared:', '  base_path: ' + str(ROOT / 'ComfyUI/models').replace('\\', '/')]
    config.extend('  ' + key + ': ' + value for key, value in model_paths.items())
    (BASE / 'extra_model_paths.yaml').write_text('\n'.join(config) + '\n', encoding='utf-8')
    workflows = ROOT / 'ComfyUI/user/default/workflows/SpriteLab-Community'
    if workflows.exists():
        shutil.copytree(workflows, BASE / 'user/default/workflows/SpriteLab-Community', dirs_exist_ok=True)
    soya = ROOT / 'data/research/soya-share-workflow-source.json'
    if soya.exists():
        target = BASE / 'user/default/workflows/SpriteLab-Community/Soya-source-api.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(soya, target)
    return constraints


def install():
    state = dict(state='installing', nodes={}, note='Site generation presets remain disabled until validation')
    save(state)
    constraints = prepare()
    env = dict(os.environ, PIP_CONSTRAINT=str(constraints), PIP_DISABLE_PIP_VERSION_CHECK='1',
               PYTHONUTF8='1', SAM2_BUILD_CUDA='0', COMFYUI_PATH=str(ROOT / 'ComfyUI'),
               COMFYUI_MODEL_PATH=str(BASE / 'models'))
    for repo, commit in PINS.items():
        name = repo.split('/')[1]
        state['current'] = name
        save(state)
        try:
            dest = BASE / 'custom_nodes' / name
            archive(repo, commit, dest)
            if name == 'rgthree-comfy':
                # The legacy recursive executor hook is absent in current Comfy.
                config_file = dest / 'rgthree_config.json'
                if not config_file.exists():
                    config_file.write_text(json.dumps({'patch_recursive_execution': False}), encoding='utf-8')
            if name == 'ComfyUI_UltimateSDUpscale':
                # Use the submodule revision pinned by this checkout, not HEAD.
                tree = requests.get(f'https://api.github.com/repos/{repo}/git/trees/{commit}?recursive=1', timeout=30)
                tree.raise_for_status()
                entry = next(e for e in tree.json()['tree'] if e['path'] == 'repositories/ultimate_sd_upscale')
                archive('Coyote-A/ultimate-upscale-for-automatic1111', entry['sha'], dest / entry['path'])
            requirements = dest / 'requirements.txt'
            if requirements.exists() and requirements.read_text(encoding='utf-8').strip():
                content = requirements.read_text(encoding='utf-8').replace('git+https://github.com/facebookresearch/sam2',
                    'git+https://github.com/facebookresearch/sam2@' + SAM2)
                req = ROOT / 'data' / (name + '-requirements.txt')
                req.write_text(content, encoding='utf-8')
                subprocess.run([str(PYTHON), '-m', 'pip', 'install', '--no-build-isolation', '-r', str(req)], env=env, check=True, timeout=1800)
            state['nodes'][name] = 'dependencies_installed'
        except Exception as exc:
            state['nodes'][name] = 'needs_attention: ' + type(exc).__name__
            print('Node install needs attention:', name, type(exc).__name__, flush=True)
        save(state)
    state.pop('current', None)
    state['state'] = 'installed_pending_restart_validation' if all(v == 'dependencies_installed' for v in state['nodes'].values()) else 'needs_attention'
    save(state)
    print('Installation finished:', state['state'], flush=True)


def serve():
    if not PYTHON.exists():
        raise RuntimeError('Run the installer first')
    args = [str(PYTHON), str(ROOT / 'ComfyUI/main.py'), '--base-directory', str(BASE),
            '--user-directory', str(BASE / 'user'),
            '--database-url', 'sqlite:///' + (BASE / 'user/comfyui.db').as_posix(),
            '--extra-model-paths-config', str(BASE / 'extra_model_paths.yaml'), '--listen', '127.0.0.1',
            '--port', '8191', '--disable-smart-memory', '--disable-pinned-memory']
    # Manual launch only: experimental stack does not restart the working servers.
    subprocess.run(args, cwd=ROOT / 'ComfyUI', check=True)


if __name__ == '__main__':
    if '--serve' in sys.argv:
        serve()
    else:
        install()
