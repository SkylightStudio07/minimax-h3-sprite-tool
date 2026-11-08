"""Allowlisted sprite workflow profiles. FastH3 remains gated until real validation."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent
FAST_FILENAME='fastvideo_fasth3_8step_v2_pruned_int8_convrot.safetensors'
FAST_SHA256='0922785978dc9bfe1adf27d8b291b0ca763f9f165f882e6cb297c72fbb6deda8'
FAST_REVISION='ec1e3aa374a91c57b0b94a1623b7e657c0498cf2'
FAST_BYTES=22128378696
VERIFIED=ROOT/'data/fasth3-validated.txt'


def status(comfy_root):
    installed=(comfy_root/'models/diffusion_models'/FAST_FILENAME).is_file()
    validated=VERIFIED.is_file() and VERIFIED.read_text(encoding='utf-8').strip()==FAST_SHA256
    return [dict(id='standard',name='기존 H3 · 20/4스텝',ready=True),
            dict(id='fasth3-sprite',name='FastH3 스프라이트 · 8스텝 · 실험적',installed=installed,ready=installed and validated,bytes=FAST_BYTES)]


def validate(p,comfy_root,require_ready=True):
    workflow=p.get('workflowId','standard')
    if workflow not in ('standard','fasth3-sprite'):
        raise ValueError('지원하지 않는 스프라이트 워크플로우입니다.')
    if workflow=='fasth3-sprite':
        if p.get('width')!=512 or p.get('height')!=512:
            raise ValueError('FastH3 스프라이트는 현재 512×512로 검증합니다.')
        if p.get('negativeEnabled',False):
            raise ValueError('FastH3 8스텝은 별도 CFG 네거티브를 지원하지 않습니다.')
        if require_ready and not status(comfy_root)[1]['ready']:
            raise ValueError('FastH3 모델 설치·실생성 검증 중입니다. 기존 H3를 선택하세요.')
    return workflow
