"""Canvas-space idle fields shared in behaviour with RigRuntime.idleOffset.

The coat remains anchored at the waist; hems lag behind the driving cycle.
Legs use a continuous field so crossed legs are never cut into screen halves.
"""
import math

from PIL import Image


def _ease(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


def idle_profile(parts, anchors, canvas_height):
    bottom = max([p['top'] + p['height'] for p in parts] + [1])
    top = min([p['top'] for p in parts] + [bottom - 1])
    height = max(1, bottom - top)
    clothing = next((p for p in parts if p['id'] == 'topwear'), None)
    pants = next((p for p in parts if p['id'] == 'bottomwear'), None)
    legs = next((p for p in parts if p['id'] == 'legwear'), None)
    waist = pants['top'] + pants['height'] * .28 if pants else (legs['top'] if legs else top + height * .43)
    cx = pants['left'] + pants['width'] / 2 if pants else anchors.get('neckPivot', {}).get('cx', 0)
    coat_bottom = clothing['top'] + clothing['height'] if clothing else 0
    return dict(height=height, bottom=bottom, waist=waist, cx=cx,
                coatBottom=coat_bottom if coat_bottom > waist + height * .22 else 0)


def idle_offset(layer_id, x, y, p, phase):
    h = p['height']
    dx = 0.0
    dy = -h * .0045 * (.5 + .5 * math.sin(phase)) * _ease((p['bottom'] - y) / (h * .65))
    if layer_id == 'topwear' and p['coatBottom']:
        u = max(0, min(1, (y - p['waist']) / max(1, p['coatBottom'] - p['waist'])))
        side = max(-1, min(1, (x - p['cx']) / (h * .22)))
        wave = math.sin(phase - side * .65 - u * 1.8) + .24 * math.sin(phase * 2 - side - u * 3.2)
        dx += h * .016 * u * u * wave
        dy += h * .0035 * u * u * math.sin(phase - side * .65 - u * 1.8 + .8)
    if layer_id == 'topwear' or layer_id.startswith('handwear'):
        side = max(-1, min(1, (x - p['cx']) / (h * .12)))
        shoulder_y = p['waist'] - h * .22
        weight = _ease((abs(x - p['cx']) / h - .085) / .10) * (1 - _ease((y - p['waist'] - h * .07) / (h * .13)))
        angle = math.sin(phase - .45) * .016 * side
        dx += -(y - shoulder_y) * angle * weight
        dy += (x - (p['cx'] + side * h * .14)) * angle * weight
    if layer_id == 'legwear':
        u = max(0, min(1, (y - p['waist']) / max(1, p['bottom'] - p['waist'])))
        dx += h * .0035 * math.sin(phase - .35) * math.sin(math.pi * u)
    return dx, dy


def warp_idle(image, layer_id, left, top, profile, phase):
    """Inverse mesh warp with transparent padding so moving hems are not clipped."""
    pad = max(4, math.ceil(profile['height'] * .035))
    padded = Image.new('RGBA', (image.width + pad * 2, image.height + pad * 2))
    padded.alpha_composite(image, (pad, pad))
    origin_x, origin_y = left - pad, top - pad
    cell = max(8, round(profile['height'] / 36))
    mesh = []

    def source(x, y):
        sx, sy = x + origin_x, y + origin_y
        for _ in range(3):
            dx, dy = idle_offset(layer_id, sx, sy, profile, phase)
            sx, sy = x + origin_x - dx, y + origin_y - dy
        return sx - origin_x, sy - origin_y

    for y in range(0, padded.height, cell):
        for x in range(0, padded.width, cell):
            right, bottom = min(x + cell, padded.width), min(y + cell, padded.height)
            quad = (*source(x, y), *source(x, bottom), *source(right, bottom), *source(right, y))
            mesh.append(((x, y, right, bottom), quad))
    warped = padded.convert('RGBa').transform(padded.size, Image.Transform.MESH, mesh, Image.Resampling.BICUBIC).convert('RGBA')
    return warped, origin_x, origin_y
