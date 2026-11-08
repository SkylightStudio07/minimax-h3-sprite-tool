"""User-reviewed WAI + Cutscene + CounterSide recipe; isolated from Soya."""
import math
from pathlib import Path
import image_face_detail
import image_pose

MODEL_ID='wai-cutscene-counter'
VERSION='cutscene-counter-reference-v2'
COUNTER='requested/counter-side-sprites-reviewed-9f3a0f44.safetensors'
CUTSCENE='requested/blue-archive-cutscene-illustrious.safetensors'
MODEL=dict(name='셀 채색 전투 스프라이트 · 혼합',family='illustrious',steps=28,cfg=4.5,
    files=['checkpoints/waiIllustriousSDXL_v170.safetensors','loras/'+COUNTER,'loras/'+CUTSCENE],
    defaultSize='832x1216',modes=['text','reference','inpaint'],source='https://civitai.com/models/1884029',
    license='팬 스타일 LoRA · 제작자/기반 모델 이용 조건 확인 · 상업 허용 미확인',
    description='검토한 WAI17 + Cutscene1.0 + 전투 형식0.4 동시 적용. 헤일로 억제, 원본 크기 얼굴 보정0.12/0.20 지원. 원화 변형·관절 포즈·마스크 부분 수정 지원. 원화 디자인은 달라질 수 있으므로 여러 후보 중 선택하세요.')


def validate(p,result):
    if p.get('styleId') or p.get('lookId') or p.get('hiresFix') or p.get('preset')=='rpg-sheet':
        raise ValueError('셀 채색 혼합은 전용 조합을 사용합니다. 다른 LoRA·그림체 프리셋·시트·확대 보정을 해제하세요.')
    for key,default,lo,hi in [('counterMixStrength',.4,0,.6),('cutsceneMixStrength',1.,.5,1.2)]:
        value=p.get(key,default)
        if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError('그림체 혼합 강도를 확인하세요.')
        result[key]=float(value)
    result.update(workflowVersion=VERSION,haloSuppression=True,cutsceneVersion=2132494,
        cutsceneSha256='1919f054b61b43c578de8b2fa3fbf3a5257208acdef36bb4c0e50c74484aceda',
        counterSha256='9f3a0f44bea6c093c178700521a22576f4e10ae5a8ffe30a2c1c6680f02030d8',
        counterIntegrityStatus='upstream-mismatch-user-approved',
        counterUpstreamSha256='d5224d243d68bef339f09b728d315a4fb7d796a0d9fe21652a69dbb241a972f2')
    if result.get('faceDetail'):
        value=p.get('faceDetailDenoise',.12)
        if type(value) not in (int,float) or value not in (.12,.20):raise ValueError('셀 채색 얼굴 보정은0.12 또는0.20을 선택하세요.')
        result.update(faceDetailDenoise=value,faceDetailVersion='cutscene-native-face-v1',outputWidth=result['width'],outputHeight=result['height'])


def build(p,seed,image_name=None,pose_image_name=None):
    def node(kind,**kw):return dict(class_type=kind,inputs=kw)
    graph={'1':node('CheckpointLoaderSimple',ckpt_name='waiIllustriousSDXL_v170.safetensors'),
        '2':node('CLIPSetLastLayer',clip=['1',1],stop_at_clip_layer=-2),
        '11':node('LoraLoader',model=['1',0],clip=['2',0],lora_name=str(Path(COUNTER)),strength_model=p['counterMixStrength'],strength_clip=p['counterMixStrength']),
        '3':node('LoraLoader',model=['11',0],clip=['11',1],lora_name=str(Path(CUTSCENE)),strength_model=p['cutsceneMixStrength'],strength_clip=p['cutsceneMixStrength']),
        '4':node('CLIPTextEncode',clip=['3',1],text=p['resolvedPrompt']),
        '5':node('CLIPTextEncode',clip=['3',1],text=p['resolvedNegativePrompt']),
        '6':node('EmptyLatentImage',width=p['width'],height=p['height'],batch_size=1)}
    if p['mode']!='text':
        graph['10']=node('LoadImage',image=image_name)
        graph['6']=node('VAEEncode',pixels=['10',0],vae=['1',2]) if p['mode']=='reference' else node('VAEEncodeForInpaint',pixels=['10',0],mask=['10',1],vae=['1',2],grow_mask_by=0)
    graph['7']=node('KSampler',model=['3',0],positive=['4',0],negative=['5',0],latent_image=['6',0],seed=seed,steps=p['steps'],cfg=p['cfg'],sampler_name='euler_ancestral',scheduler='normal',denoise=1. if p['mode']=='text' else p['denoise'])
    if p.get('pose'):
        image_pose.apply(graph,p['pose'],pose_image_name)
    graph['8']=node('VAEDecode',samples=['7',0],vae=['1',2]);final=['8',0]
    if p.get('faceDetail'):
        graph['14']=node('LoraLoader',model=['1',0],clip=['2',0],lora_name=str(Path(CUTSCENE)),strength_model=p['cutsceneMixStrength'],strength_clip=p['cutsceneMixStrength'])
        face=dict(p,styleId=None)
        face['prompt']='(official art:1.1), (game cg:1.1), '+p['prompt']
        final=image_face_detail.add_native(graph,face,seed,['8',0],['14',0],['14',1],['1',2],denoise=p['faceDetailDenoise'])
        graph['23']['inputs']['cfg']=4.5
        graph['22']['inputs']['text']+=', halo, floating ring'
    graph['9']=node('SaveImage',images=final,filename_prefix='sprite_lab_cutscene')
    return graph
