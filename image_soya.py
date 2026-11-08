"""Pinned Soya Anima -> Flanime production profile (candidate refiner LoRA)."""
import copy
import json
import os
from pathlib import Path
import subprocess
import threading
import time

import requests

ROOT = Path(__file__).resolve().parent
URL = 'http://127.0.0.1:8191'
MODEL_ID = 'soya-anima-flanime'
SOURCE = ROOT / 'workflows/soya/anima-flanime.original.api.json'
FILES = ['diffusion_models/anima-preview.safetensors', 'text_encoders/qwen_3_06b_base.safetensors',
         'vae/qwen_image_vae.safetensors', 'checkpoints/rinFlanimeIllustrious_v30.safetensors',
         'loras/soya-import/dmd2_sdxl_4step_lora.safetensors',
         'loras/soya-import/anima_preview_rdbt_finetuned_cfg_distilled_v0.12.safetensors',
         'loras/soya-import/kieed-anima-lokr-000018.safetensors',
         'loras/soya-candidates/Detailed_anime_style_Illustrious_v0.7.safetensors',
         'upscale_models/2x-AnimeSharpV4_Fast_RCAN_PU.safetensors']
MODEL = dict(name='Soya · Anima → Flanime (기본)', family='anima', steps=16, cfg=2.0,maxSeed=2**50,
             files=FILES, source='https://github.com/lbh848/comfyui_hooking_server',
             license='Soya CC BY-NC-SA 4.0 · 각 모델·LoRA 이용 조건 별도 확인',
             artistName='Kieed', modes=['text'], defaultSize='768x768', maxBasePixels=786432,
             description='Kieed 0.3 → 2배 확대 → Flanime 재처리. Detailed anime 후보 LoRA 사용. 장비·의상이 바뀔 수 있어요.')
_LOCK = threading.Lock()


def online():
    try:
        return requests.get(URL + '/system_stats', timeout=2).ok
    except requests.RequestException:
        return False


def start_server():
    with _LOCK:
        if online():
            return
        if not (ROOT / '.venv-workflows/Scripts/python.exe').is_file():
            raise RuntimeError('Soya 워크플로 실행 환경이 없습니다.')
        logs = ROOT / 'logs'
        logs.mkdir(exist_ok=True)
        env = dict(os.environ, PYTHONUTF8='1')
        with (logs / 'soya.stdout.log').open('a', encoding='utf-8') as stdout, (logs / 'soya.stderr.log').open('a', encoding='utf-8') as stderr:
            process = subprocess.Popen([str(ROOT / '.venv/Scripts/python.exe'), str(ROOT / 'tools/install_community_workflows.py'), '--serve'],
                cwd=ROOT, stdout=stdout, stderr=stderr, env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        for _ in range(120):
            if online():
                return
            if process.poll() is not None:
                raise RuntimeError('Soya 실행 환경 시작 실패. logs/soya.stderr.log를 확인하세요.')
            time.sleep(1)
        raise TimeoutError('Soya 실행 환경을 시작하지 못했습니다.')


def build(p, seed, style=None):
    graph = copy.deepcopy(json.loads(SOURCE.read_text(encoding='utf-8')))
    paths = {'68':'soya-import/dmd2_sdxl_4step_lora.safetensors',
             '120':'soya-import/anima_preview_rdbt_finetuned_cfg_distilled_v0.12.safetensors',
             '386':'soya-import/kieed-anima-lokr-000018.safetensors',
             '184':'soya-candidates/Detailed_anime_style_Illustrious_v0.7.safetensors'}
    for node, filename in paths.items():
        graph[node]['inputs']['lora_name'] = str(Path(filename))
    if style:
        graph['386']['inputs'].update(lora_name=str(Path(style['filename'])), strength_model=p['styleStrength'])
    graph['125']['inputs']['value'] = p.get('workflowBasePrompt',p['resolvedPrompt'])
    graph['126']['inputs']['value'] = p.get('workflowBaseNegativePrompt',p['resolvedNegativePrompt'])
    if p.get('lookId'):
        # Read the trusted catalogue again; never execute arbitrary workflow fields from a request.
        import image_looks
        look=next((x for x in image_looks.catalog()['looks'] if x['id']==p['lookId'] and x['model']==MODEL_ID),None)
        if look is None:raise ValueError('Soya 그림체 프리셋을 확인하세요.')
        cfg=look.get('workflow',{})
        graph['415']['inputs']['value']=look['prompt']+', masterpiece, best quality, 2d anime illustration'
        graph['70']['inputs']['text']=p['resolvedNegativePrompt']
        if not style:graph['386']['inputs']['strength_model']=cfg.get('kieedStrength',.3)
        graph['184']['inputs']['strength_model']=cfg.get('detailStrength',.3)
        graph['80']['inputs']['denoise']=cfg.get('refineDenoise',.2)
        graph['283:6']['inputs']['value']=cfg.get('vibrance',20)
        graph['283:7']['inputs']['value']=cfg.get('saturation',20)
    graph['290']['inputs']['seed'] = seed
    graph['291']['inputs']['seed'] = seed
    # UI dimensions refer to first-pass pixels; final dimensions are doubled.
    graph['180:1']['inputs'].update(width=p['width'], height=p['height'])
    graph['182']['inputs']['scale_by'] = 1.0
    graph['179:109']['inputs']['steps'] = p['steps']
    graph['179:110']['inputs']['cfg'] = p['cfg']
    graph['9'] = graph.pop('404')
    graph['9']['inputs']['filename_prefix'] = 'sprite_lab_soya'
    if p.get('lookId') and look.get('finalTone'):
        ink={'grayscale':'vec3(0.0)','blue':'vec3(0.05, 0.18, 0.55)','sepia':'vec3(0.28, 0.15, 0.06)'}[look['finalTone']]
        shader='#version 300 es\nprecision highp float;\nuniform sampler2D u_image0;\nin vec2 v_texCoord;\nout vec4 fragColor;\nvoid main(){vec4 c=texture(u_image0,v_texCoord);float y=dot(c.rgb,vec3(0.299,0.587,0.114));fragColor=vec4(mix('+ink+',vec3(1.0),y),c.a);}'
        graph['902']=dict(class_type='GLSLShader',inputs={'fragment_shader':shader,'size_mode':'from_input','images.image0':['79',0]})
        graph['9']['inputs']['images']=['902',0]
    return graph
