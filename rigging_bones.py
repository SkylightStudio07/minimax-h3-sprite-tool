"""Shared rest skeleton, layer bindings and skin weights for web and Unity V2."""
from __future__ import annotations
import copy
import json
import math
import re
from pathlib import Path
import zipfile

CORE = ('hips', 'spine', 'chest', 'neck', 'head', 'shoulder_l', 'arm_l', 'hand_l',
        'shoulder_r', 'arm_r', 'hand_r', 'leg_l', 'knee_l', 'foot_l', 'leg_r', 'knee_r', 'foot_r')


def records(manifest):
    return [(f'{kind}:{p["id"]}', p) for kind, collection in (('part', 'parts'), ('expression', 'expressions'))
            for p in manifest.get(collection, []) if not p.get('variantOf')]


def validate(config, manifest):
    if not isinstance(config, dict) or config.get('schemaVersion') != 1:
        raise ValueError('본 편집 데이터 형식을 확인하세요.')
    bones = config.get('bones')
    if not isinstance(bones, list) or not 17 <= len(bones) <= 96:
        raise ValueError('본은 기본 17개를 포함하여 96개 이하로 구성하세요.')
    width, height = manifest['canvas']['width'], manifest['canvas']['height']
    by_name = {}
    for bone in bones:
        if not isinstance(bone, dict):
            raise ValueError('본 정보를 확인하세요.')
        name, parent = bone.get('name'), bone.get('parent')
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,79}', name) or name in by_name:
            raise ValueError('본 이름이 잘못되었거나 중복됩니다.')
        x, y = bone.get('x'), bone.get('y')
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in (x, y)) or not 0 <= x <= width or not 0 <= y <= height:
            raise ValueError('관절점은 캔버스 안에 있어야 합니다.')
        if parent is not None and (not isinstance(parent, str) or parent == name):
            raise ValueError('본의 부모 연결을 확인하세요.')
        by_name[name] = dict(name=name, parent=parent, x=float(x), y=float(y))
    if not set(CORE) <= set(by_name) or by_name['hips']['parent'] is not None:
        raise ValueError('기본 전신 본과 골반 루트가 필요합니다.')
    ordered, visiting = [], set()
    def visit(name):
        if name in visiting:
            raise ValueError('본 연결에 순환이 있습니다.')
        bone = by_name[name]
        if bone in ordered:
            return
        visiting.add(name)
        if name != 'hips':
            if bone['parent'] not in by_name:
                raise ValueError('모든 본은 골반 루트에 연결되어야 합니다.')
            visit(bone['parent'])
        visiting.remove(name)
        ordered.append(bone)
    for name in by_name:
        visit(name)
    bindings = config.get('bindings')
    available = dict(records(manifest))
    if not isinstance(bindings, dict) or set(bindings) != set(available):
        raise ValueError('모든 파츠의 본 연결을 지정하세요. 레이어 변경 후 다시 확인하세요.')
    for key, names in bindings.items():
        if not isinstance(names, list) or not 1 <= len(names) <= 16 or any(not isinstance(n, str) or n not in by_name for n in names) or len(set(names)) != len(names):
            raise ValueError('파츠가 따를 본을 확인하세요.')
        if key.startswith('expression:') and names != ['head']:
            raise ValueError('표정 파츠는 머리 본에 연결하세요.')
    for bone in ordered:
        child = next((b for b in ordered if b['parent'] == bone['name']), None)
        bone['length'] = max(1., math.hypot(child['x']-bone['x'], child['y']-bone['y'])) if child else max(1., height * .055)
    return dict(schemaVersion=1, bones=ordered, bindings=copy.deepcopy(bindings), mesh=dict(columns=9, rows=9, maxInfluences=2))


def influences(key, part, bones):
    name = str(part.get('id', '')).lower()
    if key.startswith('expression:') or any(n in name for n in ('eye', 'iride', 'lash', 'brow', 'nose', 'mouth', 'face', 'headwear', 'ears')):
        return ['head']
    if 'hair' in name:
        return ['head', 'hair_'+part['id'], 'hair_tip_'+part['id']]
    if 'neck' in name:
        return ['neck', 'chest']
    if 'hand' in name or 'arm' in name:
        side = 'l' if part['left']+part['width']*.5 < bones[0]['x'] else 'r'
        return ['shoulder_'+side, 'arm_'+side, 'hand_'+side, 'chest']
    if any(n in name for n in ('leg', 'foot', 'shoe')):
        return ['hips', 'leg_l', 'knee_l', 'foot_l', 'leg_r', 'knee_r', 'foot_r']
    if 'bottom' in name or 'skirt' in name:
        return ['hips', 'leg_l', 'leg_r', 'spine', 'skirt_c', 'skirt_l', 'skirt_r']
    if 'top' in name or 'object' in name:
        return ['hips', 'spine', 'chest', 'neck', 'shoulder_l', 'shoulder_r', 'hand_l', 'hand_r']
    return ['hips', 'spine', 'chest', 'neck', 'head', 'leg_l', 'leg_r']


def default_config(manifest, rig):
    bones = copy.deepcopy(rig['bones'])
    width, height = manifest['canvas']['width'], manifest['canvas']['height']
    for bone in bones:
        bone['x'], bone['y'] = min(width, max(0, bone['x'])), min(height, max(0, bone['y']))
    names = {b['name'] for b in bones}
    for key, part in records(manifest):
        if key.startswith('part:') and 'hair' in part['id'].lower():
            root, tip = 'hair_'+part['id'], 'hair_tip_'+part['id']
            if root not in names:
                bones.append(dict(name=root, parent='head', x=part['left']+part['width']*.5, y=part['top']+part['height']*.2))
                names.add(root)
            if tip not in names:
                bones.append(dict(name=tip, parent=root, x=part['left']+part['width']*.5, y=part['top']+part['height']*.85))
                names.add(tip)
    bindings = {key: [n for n in influences(key, p, bones) if n in names] for key, p in records(manifest)}
    return validate(dict(schemaVersion=1, bones=bones, bindings=bindings), manifest)


def get_rig(manifest, folder: Path | None = None, pose=None):
    import rigging_v2
    parts = [p for _, p in records(manifest)]
    size = manifest['canvas']
    bounds = (min((p['left'] for p in parts), default=0), min((p['top'] for p in parts), default=0),
              max((p['left']+p['width'] for p in parts), default=size['width']), max((p['top']+p['height'] for p in parts), default=size['height']))
    base = rigging_v2.build_skeleton(manifest, bounds, pose)
    if pose is None and manifest.get('rigEditor'):
        config = reconcile(manifest['rigEditor'], manifest, base)
    else:
        if pose is None and folder and (folder / rigging_v2.V2_FILENAME).is_file():
            try:
                with zipfile.ZipFile(folder / rigging_v2.V2_FILENAME) as archive:
                    old = json.loads(archive.read('rig-v2.json'))
                    if old.get('sourceRevision') == manifest.get('editRevision', 0):
                        base = old
            except (OSError, ValueError, KeyError, zipfile.BadZipFile):
                pass  # A stale/corrupt derived ZIP must not prevent editing its V1 source.
        config = default_config(manifest, base)
    base.pop('layerMeshes', None)
    return dict(base, **config, poseSource='editor' if manifest.get('rigEditor') and pose is None else base['poseSource'])


def reconcile(config, manifest, base=None):
    """Keep authored bones while filling/removing bindings after layer edits."""
    config = copy.deepcopy(config)
    names = {b['name'] for b in config['bones']}
    old = config.get('bindings', {})
    config['bindings'] = {key: old.get(key) or [n for n in influences(key, p, config['bones']) if n in names] or ['head']
                          for key, p in records(manifest)}
    return validate(config, manifest)


def weights(config, key, x, y):
    candidates = [(i, math.hypot(x-b['x'], y-b['y'])) for i, b in enumerate(config['bones']) if b['name'] in config['bindings'][key]]
    candidates.sort(key=lambda pair: pair[1])
    candidates = candidates[:2]
    values = [1/max(4., distance) for _, distance in candidates]
    total = sum(values)
    return [i for i, _ in candidates], [v/total for v in values]


def layer_meshes(manifest, config):
    output = []
    cols, rows = config['mesh']['columns'], config['mesh']['rows']
    for key, p in records(manifest):
        vertices = []
        for row in range(rows):
            for col in range(cols):
                x, y = p['left']+p['width']*col/(cols-1), p['top']+p['height']*row/(rows-1)
                indices, values = weights(config, key, x, y)
                vertices.append(dict(x=x, y=y, boneIndices=indices, weights=values))
        triangles = []
        for row in range(rows-1):
            for col in range(cols-1):
                a = row*cols+col; b = a+1; c = a+cols; d = c+1
                triangles.extend((a, b, c, b, d, c))
        output.append(dict(layerKey=key, vertices=vertices, indices=triangles))
    return output
