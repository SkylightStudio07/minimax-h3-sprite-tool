"""Turn one transparent still into a closed breathing loop without the GPU.

The chest and shoulders are warped, while the head above the neck line and the
legs stay exactly as drawn. Poses vary too much to find the neck reliably, so the
caller names the neck row, body axis and torso half width.
"""
import json

import cv2
import numpy as np
from PIL import Image

CHEST_RISE, CHEST_SWELL = .0085, .028
SHOULDER_RISE, SHOULDER_LAG = .5, .08
INHALE = .4


def validate(still, neck, axis, half, count):
    for value, name in ((neck, '목 높이'), (axis, '몸 중심'), (half, '몸통 반폭'), (count, '프레임 수')):
        if type(value) is not int:raise ValueError(f'{name}는 정수로 입력하세요.')
    if not 6 <= count <= 64:raise ValueError('프레임 수는 6~64로 입력하세요.')
    if not 0 <= axis < still.width or not 2 <= half <= still.width//2:raise ValueError('몸 중심과 몸통 반폭을 프레임 안에서 지정하세요.')
    box = still.getchannel('A').point(lambda v:255 if v >= 16 else 0).getbbox()
    if not box:raise ValueError('이 프레임에는 보이는 캐릭터가 없습니다.')
    if not box[1] <= neck <= box[3]-8:raise ValueError('목 높이는 캐릭터의 머리와 발 사이로 지정하세요.')
    return box[3]-neck


def _rise(phase):
    phase %= 1
    return np.sin(np.pi/2*phase/INHALE)**2 if phase < INHALE else np.cos(np.pi/2*(phase-INHALE)/(1-INHALE))**2


def _bump(x, y, cx, cy, rx, ry):
    return np.cos(np.pi/2*np.minimum(np.hypot((x-cx)/rx, (y-cy)/ry), 1))**2


def loop(still, neck, axis, half, count):
    """Return `count` frames that start on the untouched still and close back onto it."""
    still = still.convert('RGBA')
    body = validate(still, neck, axis, half, count)
    rgba = np.asarray(still, dtype=np.float32)
    height, width = rgba.shape[:2]
    y, x = np.mgrid[0:height, 0:width].astype(np.float32)
    chest = _bump(x, y, axis, neck+.31*body, .83*half, .28*body)
    below_neck = np.clip((y-neck)/max(.02*body, 1), 0, 1)
    shoulders = below_neck*sum(_bump(x, y, axis+side*.55*half, neck+.05*body, .45*half, .1*body) for side in (-1, 1))
    touched = cv2.dilate(((chest > 0) | (shoulders > 0)).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    premultiplied = np.dstack((rgba[..., :3]*rgba[..., 3:]/255, rgba[..., 3]))
    frames = []
    for i in range(count):
        phase = i/count
        breath, delayed = float(_rise(phase)), float(_rise(phase-SHOULDER_LAG))
        if i == 0 or (breath == 0 and delayed == 0):
            frames.append(still.copy())
            continue
        dy = -(chest*breath+SHOULDER_RISE*shoulders*delayed)*CHEST_RISE*body
        dx = chest*breath*CHEST_SWELL*(x-axis)
        warped = np.clip(cv2.remap(premultiplied, x-dx, y-dy, cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=0), 0, 255)
        alpha = warped[..., 3:]
        color = np.where(alpha > 0, np.minimum(warped[..., :3]*255/np.maximum(alpha, 1e-3), 255), 0)
        out = np.dstack((color, alpha)).round().astype(np.uint8)
        frames.append(Image.fromarray(np.where(touched[..., None], out, rgba.astype(np.uint8)), 'RGBA'))
    return frames


def read_frame(sheet_path, index, columns=None, rows=None, atlas_path=None):
    """One frame of a sheet at its full size, cut by the atlas when there is one and otherwise by the grid."""
    with Image.open(sheet_path) as opened:
        sheet = opened.convert('RGBA')
    if atlas_path:
        listed = json.loads(atlas_path.read_text(encoding='utf-8'))['frames']
        entries = listed if isinstance(listed, list) else list(listed.values())
        if not 0 <= index < len(entries):raise ValueError('프레임 번호를 확인하세요.')
        entry = entries[index]
        q = entry['frame']
        full = entry.get('sourceSize', q)
        offset = entry.get('spriteSourceSize', dict(x=0, y=0))
        out = Image.new('RGBA', (full['w'], full['h']), (0, 0, 0, 0))
        out.paste(sheet.crop((q['x'], q['y'], q['x']+q['w'], q['y']+q['h'])), (offset['x'], offset['y']))
        return out
    if not 0 <= index < columns*rows:raise ValueError('프레임 번호를 확인하세요.')
    w, h = sheet.width//columns, sheet.height//rows
    x, y = (index % columns)*w, (index//columns)*h
    return sheet.crop((x, y, x+w, y+h))
