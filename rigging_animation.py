"""Validated sparse local-pose clips shared by the editor and Unity export."""
import copy
import math
import re


def validate(config, rig, canvas):
    if not isinstance(config, dict) or config.get('schemaVersion') != 1 or not isinstance(config.get('clips'), list) or len(config['clips']) > 16:
        raise ValueError('애니메이션은 최대 16개 클립으로 구성하세요.')
    names = {b['name'] for b in rig['bones']}
    clips, ids, total_keys = [], set(), 0
    limit = max(canvas['width'], canvas['height']) * 4
    for clip in config['clips']:
        if not isinstance(clip, dict):
            raise ValueError('애니메이션 클립 형식을 확인하세요.')
        cid, name = clip.get('id'), clip.get('name')
        if not isinstance(cid, str) or not re.fullmatch(r'clip_[a-z0-9_]{1,60}', cid) or cid in ids:
            raise ValueError('애니메이션 ID를 확인하세요.')
        if not isinstance(name, str) or not name.strip() or len(name) > 60:
            raise ValueError('클립 이름은 1~60자로 입력하세요.')
        fps, frames, loop, easing = clip.get('fps'), clip.get('frames'), clip.get('loop'), clip.get('easing')
        if type(fps) is not int or not 1 <= fps <= 60 or type(frames) is not int or not 2 <= frames <= 3600 or type(loop) is not bool or easing not in ('linear', 'smooth', 'hold'):
            raise ValueError('FPS는 1~60, 길이는 2~3600프레임으로 지정하세요.')
        keys = clip.get('keys')
        if not isinstance(keys, list) or len(keys) > 512:
            raise ValueError('클립당 키프레임은 512개 이하로 구성하세요.')
        total_keys += len(keys)
        if total_keys > 2048:
            raise ValueError('전체 키프레임은 2048개 이하로 구성하세요.')
        clean, seen = [], set()
        for key in keys:
            if not isinstance(key, dict) or type(key.get('frame')) is not int or not 0 <= key['frame'] < frames or key['frame'] in seen or not isinstance(key.get('pose'), dict):
                raise ValueError('키프레임 위치가 잘못되었거나 중복됩니다.')
            seen.add(key['frame']); pose = {}
            for bone, transform in key['pose'].items():
                if bone not in names or not isinstance(transform, dict):
                    raise ValueError('키프레임에 없는 본이 연결되어 있습니다.')
                values = {field: transform.get(field, 0) for field in ('dx', 'dy', 'angle')}
                if any(type(value) not in (int, float) or not math.isfinite(value) for value in values.values()) or abs(values['dx']) > limit or abs(values['dy']) > limit or abs(values['angle']) > 720:
                    raise ValueError('키프레임 이동·회전 값을 확인하세요.')
                pose[bone] = values
            clean.append(dict(frame=key['frame'], pose=pose))
        ids.add(cid)
        clips.append(dict(id=cid, name=name.strip(), fps=fps, frames=frames, loop=loop, easing=easing, keys=sorted(clean, key=lambda k:k['frame'])))
    return dict(schemaVersion=1, clips=clips)


def reconcile(config, rig):
    config = copy.deepcopy(config)
    names = {b['name'] for b in rig['bones']}
    for clip in config['clips']:
        for key in clip['keys']:
            key['pose'] = {name: values for name, values in key['pose'].items() if name in names}
    return config


def sample(clip, frame):
    keys = clip['keys']
    if not keys:
        return {}
    if clip['loop']:
        frame %= clip['frames']
    else:
        frame = max(0, min(clip['frames']-1, frame))
    a, b, fa, fb = keys[0], keys[0], keys[0]['frame'], keys[0]['frame']
    if frame < keys[0]['frame']:
        if clip['loop']:a, b, fa, fb = keys[-1], keys[0], keys[-1]['frame']-clip['frames'], keys[0]['frame']
    elif frame >= keys[-1]['frame']:
        a, b, fa, fb = keys[-1], keys[-1], keys[-1]['frame'], keys[-1]['frame']
        if clip['loop']:b, fb = keys[0], keys[0]['frame']+clip['frames']
    else:
        for left, right in zip(keys, keys[1:]):
            if left['frame'] <= frame < right['frame']:
                a, b, fa, fb = left, right, left['frame'], right['frame'];break
    t = 0 if fa == fb else (frame-fa)/(fb-fa)
    t = 0 if clip['easing']=='hold' else t*t*(3-2*t) if clip['easing']=='smooth' else t
    output = {}
    for name in set(a['pose']) | set(b['pose']):
        av, bv = a['pose'].get(name, {}), b['pose'].get(name, {})
        aa, ba = av.get('angle', 0), bv.get('angle', 0)
        output[name] = {field: av.get(field, 0)+(bv.get(field, 0)-av.get(field, 0))*t for field in ('dx', 'dy')}
        output[name]['angle'] = aa + ((ba-aa+180)%360-180)*t
    return output


def unity_clips(config):
    clips = []
    for clip in config['clips']:
        names = sorted({name for key in clip['keys'] for name in key['pose']})
        if clip['keys'] and not names:
            names = ['hips']
        tracks = [dict(bone=name, keys=[dict(frame=key['frame'], **{field:key['pose'].get(name, {}).get(field, 0) for field in ('dx','dy','angle')}) for key in clip['keys']]) for name in names]
        clips.append({key:clip[key] for key in ('id','name','fps','frames','loop','easing')} | {'tracks':tracks})
    return clips
