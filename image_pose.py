"""Validated COCO-18 joint controls; render the conditioning map on the server."""
import math
from PIL import Image, ImageDraw, ImageOps
import idle_tool as engine

VERSION = 'illustrious-joints-v1'
MODEL = 'illustrious-openpose-v1.safetensors'
SUPPORTED = ('flanime-xl','wai-cutscene-counter')
LINKS = [(1,2),(1,5),(2,3),(3,4),(5,6),(6,7),(1,8),(8,9),(9,10),(1,11),(11,12),(12,13),(1,0),(0,14),(14,16),(0,15),(15,17)]
COLORS = [(255,0,0),(255,85,0),(255,170,0),(255,255,0),(170,255,0),(85,255,0),(0,255,0),(0,255,85),(0,255,170),(0,255,255),(0,170,255),(0,85,255),(0,0,255),(85,0,255),(170,0,255),(255,0,255),(255,0,170),(255,0,85)]


def status():
    return dict(ready=(engine.COMFY_ROOT/'models/controlnet'/MODEL).is_file(), models=list(SUPPORTED), version=VERSION)


def validate(value, model, mode, face=False, hires=False, *, require_ready=True):
    if value is None:
        return None
    if not isinstance(value, dict) or model not in SUPPORTED or mode == 'inpaint':
        raise ValueError('관절 포즈는 Flanime·셀 채색 혼합의 새로 생성·참고 이미지 변형에서 지원합니다.')
    if face or hires:
        raise ValueError('관절 포즈 사용 시 얼굴 보정·고해상도 2차 생성은 꺼 주세요.')
    if require_ready and not status()['ready']:
        raise ValueError('전용 포즈 모델이 설치되지 않았습니다.')
    points = value.get('points')
    if not isinstance(points, list) or len(points) != 18:
        raise ValueError('포즈 관절 18개를 지정하세요.')
    clean = []
    for point in points:
        if not isinstance(point, list) or len(point) != 2 or any(type(v) not in (int,float) or not math.isfinite(v) or not 0 <= v <= 1 for v in point):
            raise ValueError('관절 좌표는 화면 안의 유효한 위치여야 합니다.')
        clean.append([float(v) for v in point])
    strength = value.get('strength', 1.)
    if type(strength) not in (int,float) or not math.isfinite(strength) or not .1 <= strength <= 1.5:
        raise ValueError('포즈 강도는 0.1~1.5입니다.')
    return dict(points=clean, strength=float(strength), version=VERSION)


def render(pose, size):
    image = Image.new('RGB', size, 'black')
    draw = ImageDraw.Draw(image)
    points = [(round(x*(size[0]-1)), round(y*(size[1]-1))) for x,y in pose['points']]
    scale = min(size)/1024
    for i,(a,b) in enumerate(LINKS):
        draw.line([points[a],points[b]],fill=COLORS[i],width=max(2,round(8*scale)))
    radius = max(3,round(9*scale))
    for i,(x,y) in enumerate(points):
        draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=COLORS[i])
    return image


def prepare_reference(source, size):
    """Same alpha crop and aspect-preserving framing as the reviewed experiment."""
    source = source.convert('RGBA')
    bounds = source.getchannel('A').getbbox()
    if not bounds:
        raise ValueError('참고 이미지가 비어 있습니다.')
    crop = ImageOps.contain(source.crop(bounds),(max(1,round(size[0]*960/1024)), max(1,round(size[1]*1472/1536))),Image.Resampling.LANCZOS)
    canvas = Image.new('RGB',size,(210,210,210))
    canvas.paste(crop,((size[0]-crop.width)//2,(size[1]-crop.height)//2),crop)
    return canvas


def apply(graph, pose, image_name):
    graph['50'] = dict(class_type='ControlNetLoader',inputs=dict(control_net_name=MODEL))
    graph['51'] = dict(class_type='LoadImage',inputs=dict(image=image_name))
    graph['52'] = dict(class_type='ControlNetApplyAdvanced',inputs=dict(positive=['4',0],negative=['5',0],control_net=['50',0],image=['51',0],strength=pose['strength'],start_percent=0.,end_percent=1.))
    graph['7']['inputs'].update(positive=['52',0],negative=['52',1])
