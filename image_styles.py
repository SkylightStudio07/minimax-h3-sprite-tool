"""Curated style allowlist. User input never selects a filesystem path."""
import json
import math
from pathlib import Path
import idle_tool as engine

CATALOG = Path(__file__).resolve().parent/'web/assets/image-styles.json'

def catalog():
    return json.loads(CATALOG.read_text(encoding='utf-8'))['styles']

def public_styles():
    return [dict(s, installed=(engine.COMFY_ROOT/'models/loras'/s['filename']).is_file()) for s in catalog()]

def validate(style_id, strength, family):
    if style_id in (None,''): return None
    if not isinstance(style_id,str): raise ValueError('그림체를 선택하세요.')
    style=next((s for s in catalog() if s['id']==style_id),None)
    if not style or style['family']!=family: raise ValueError('현재 모델과 호환되는 그림체를 선택하세요.')
    if not style['enabled']: raise ValueError('이 그림체는 설치·호환성 검증 중입니다.')
    if not (engine.COMFY_ROOT/'models/loras'/style['filename']).is_file(): raise ValueError('그림체 모델 파일이 없습니다.')
    if type(strength) not in (int,float) or not math.isfinite(strength) or not 0<=strength<=1.2:
        raise ValueError('그림체 강도는 0~1.2입니다.')
    return style
