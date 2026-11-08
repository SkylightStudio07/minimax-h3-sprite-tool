"""Game asset intent, separate from camera direction and generation count."""
TYPES = ('illustration','live2d','side','topdown','isometric')
DIRECTIONS = ('front','front-right','right','back-right','back','back-left','left','front-left')
NAMES = dict(illustration='일러스트',live2d='Live2D 정면',side='측면 전투',topdown='탑다운',isometric='아이소메트릭')
CAMERAS = dict(illustration='',live2d='front view, looking at viewer, standing, arms slightly away from torso',side='side-scrolling game battle sprite, eye-level camera',topdown='top-down game character sprite, viewed from above, overhead camera',isometric='isometric game character sprite, elevated three-quarter camera, orthographic view')
FACING = {'front':'facing toward the camera','front-right':'facing diagonally toward the camera and to the right','right':'facing right','back-right':'facing diagonally away from the camera and to the right','back':'back view, facing away from the camera','back-left':'facing diagonally away from the camera and to the left','left':'facing left','front-left':'facing diagonally toward the camera and to the left'}


def validate(value):
    if value is None:return None
    if not isinstance(value,dict):raise ValueError('에셋 유형 설정을 확인하세요.')
    kind=value.get('type')
    count=value.get('directionCount',1)
    facing=value.get('facing','front')
    if not isinstance(kind,str) or kind not in TYPES or type(count) is not int or count not in (1,4,8) or not isinstance(facing,str) or facing not in DIRECTIONS:
        raise ValueError('에셋 유형·방향 수·기준 방향을 확인하세요.')
    if kind in ('illustration','live2d') and count!=1:
        raise ValueError('일러스트·Live2D는 단일 방향으로 시작하세요.')
    if kind=='live2d' and facing!='front':raise ValueError('Live2D 원화는 정면으로 시작하세요.')
    return dict(type=kind,directionCount=count,facing=facing,version='game-asset-intent-v1',outputMode='single-direction')


def facing_prompt(spec):
    direction=FACING[spec['facing']]
    if spec['type']=='topdown':
        direction={'front':'facing down','front-right':'facing down-right','right':'facing right','back-right':'facing up-right','back':'facing up','back-left':'facing up-left','left':'facing left','front-left':'facing down-left'}[spec['facing']]
    return direction


def prompt(spec):
    if not spec:return ''
    kind=spec['type']
    direction=facing_prompt(spec)
    if kind=='illustration':return direction
    return ', '.join([CAMERAS[kind],direction,'solo, full body, feet visible, single character, centered, simple white background'])


def motion_prompt(spec):
    if not spec:return ''
    return ', '.join(filter(None,[CAMERAS[spec['type']],facing_prompt(spec),'fixed camera angle throughout, maintain the input character proportions and viewing angle']))
