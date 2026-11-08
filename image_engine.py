"""Curated ComfyUI image generation; executes only through the team's FIFO worker."""
import base64
import io
import json
import math
import secrets
import time
from pathlib import Path

import requests
from PIL import Image, ImageOps, PngImagePlugin
import idle_tool as engine
import image_styles
import image_background
import image_looks
import image_soya
import image_face_detail
import image_hires
import image_pose
import asset_types
import image_cutscene
import image_pixel

ROOT = Path(__file__).resolve().parent
RESULT_ROOT = ROOT / 'outputs/images'
COMFY_URL = engine.COMFY_URL
MODELS = {
    image_soya.MODEL_ID: image_soya.MODEL,
    'anima-base': dict(name='Anima Base 1.0 · RPG 시트',family='anima',steps=28,cfg=4.0,
        files=['diffusion_models/anima_baseV10.safetensors','text_encoders/qwen_3_06b_base.safetensors','vae/qwen_image_vae.safetensors'],
        defaultSize='512x1024',modes=['text'],source='https://huggingface.co/circlestone-labs/Anima',
        license='CircleStone 모델 조건 · LoRA 생성물 이용 조건 별도 확인',description='RPG Character Sprite Anima용 검토 조합. 3열×4행 시트 초안이며 프레임 정렬·의상 일관성은 검수가 필요합니다.'),
    'anima-turbo': dict(name='Anima Turbo 1.1', family='anima', steps=10, cfg=1.0,
        files=['diffusion_models/anima-turbo-v1.1.safetensors','text_encoders/qwen_3_06b_base.safetensors','vae/qwen_image_vae.safetensors'],
        source='https://huggingface.co/circlestone-labs/Anima',
        license='CircleStone Non-Commercial 1.2 · 생성 이미지 상업 이용 가능, 유료 생성 서비스는 별도 계약'),
    'animagine-xl': dict(name='Animagine XL 4.0', family='sdxl', steps=28, cfg=5.0,
        files=['checkpoints/animagine-xl-4.0-opt.safetensors'],
        source='https://huggingface.co/cagliostrolab/animagine-xl-4.0', license='CreativeML Open RAIL++-M'),
    'illustrious-xl': dict(name='Illustrious XL 1.0 · RPG 스프라이트 (실험)', family='illustrious', steps=28, cfg=5.0,
        files=['checkpoints/illustriousXL10_v10.safetensors','vae/illustriousXLV10_v10.safetensors'],
        source='https://civitai.com/models/1232765?modelVersionId=1389133', defaultSize='896x1152',
        license='제작자 크레딧 요구 · Civitai Image 이용 허용 · 기반 모델 및 LoRA 조건 별도 확인',
        description='현대·판타지 전투 등 Illustrious용 LoRA 경로. 캐릭터 태그로 외형, LoRA로 스프라이트 화풍을 지정합니다. 동작 프레임은 별도 제작합니다.'),
    'flanime-xl': dict(name='Flanime · RPG 원본 고해상도',family='illustrious',steps=40,cfg=5.0,
        files=['checkpoints/rinFlanimeIllustrious_v30.safetensors','vae/illustriousXLV10_v10.safetensors'],
        source='https://civitai.com/models/1544647?modelVersionId=2710976',defaultSize='1024x1536',modes=['text','reference'],
        license='Civitai Image 이용 허용 · 기반 모델 및 LoRA 조건 별도 확인',
        description='1024×1536 생성·원화 변형. 전투 형식 / 판타지 전투 LoRA와 관절 포즈 편집 지원. 원화 보존 변형 강도는 0.3부터 권장합니다.'),
}
MODELS[image_cutscene.MODEL_ID]=image_cutscene.MODEL
MODELS[image_pixel.MODEL_ID]=image_pixel.MODEL
DEFAULT_MODEL = image_soya.MODEL_ID

def backend_url(p):
    return image_soya.URL if p.get('operation')=='face-refine' or p['model']==image_soya.MODEL_ID or p.get('faceDetail') or p.get('hiresFix') else COMFY_URL
PRESETS = {
    'illustration': '',
    'rpg-sheet': 'rpgchara, transparent background, multiple views, reference sheet, chibi, full body, A sprite sheet of full-body pixel art characters arranged in a 3x4 grid, featuring front, side, and back views',
    'sprite': 'solo, full body, standing, three-quarter view, feet visible, simple white background. A single character is shown once, centered in the image with their entire body visible and empty space around them.',
    'live2d': 'solo, full body, front view, looking at viewer, standing, arms slightly away from torso, feet visible, simple white background. A single character is shown once, centered in the image with their entire body visible and empty space around them.',
}

def status_payload():
    return dict(comfy=engine.comfy_online(), pose=image_pose.status(), background=image_background.status(), hiresFix=dict(ready=image_hires.ready(),models=list(image_hires.SUPPORTED)), faceDetail=dict(ready=image_face_detail.ready(),models=list(image_face_detail.SUPPORTED),nativeModels=list(image_face_detail.NATIVE_MODELS)), styles=image_styles.public_styles(), models=[dict(id=k, **{n:v for n,v in m.items() if n!='files'},
        ready=all((engine.COMFY_ROOT/'models'/f).is_file() for f in m['files'])) for k,m in MODELS.items()])

def read_image(value):
    if not isinstance(value,str) or len(value)>29*1024*1024:
        raise ValueError('이미지는 20MB 이하로 선택하세요.')
    try:
        raw=base64.b64decode(value.split(',')[-1],validate=True)
        with Image.open(io.BytesIO(raw)) as source:
            if source.width*source.height>24000000: raise ValueError()
            return ImageOps.exif_transpose(source).convert('RGBA')
    except Exception as e:
        raise ValueError('유효한 24MP 이하 이미지를 선택하세요.') from e

def validate(p):
    model=p.get('model',DEFAULT_MODEL)
    if model not in MODELS: raise ValueError('지원하지 않는 이미지 모델입니다.')
    preset=p.get('preset','illustration')
    if preset not in PRESETS: raise ValueError('용도 프리셋을 확인하세요.')
    mode=p.get('mode','text')
    if mode not in ('text','reference','inpaint'): raise ValueError('생성 방식을 확인하세요.')
    if model=='flanime-xl' and mode=='inpaint':raise ValueError('Flanime은 새로 생성·참고 이미지 변형을 지원합니다.')
    if model==image_soya.MODEL_ID and mode!='text':
        raise ValueError('Soya 기본 워크플로는 새로 생성을 지원합니다. 참고 이미지·부분 수정은 Anima Turbo 또는 Animagine을 선택하세요.')
    result=dict(jobType='image',model=model,preset=preset,mode=mode)
    pixel=image_pixel.settings(p) if model==image_pixel.MODEL_ID else None
    sheet=preset=='rpg-sheet'
    if sheet:
        expected='rpgchara-anima' if model=='anima-base' else 'rpgchara-illustrious' if model=='flanime-xl' else None
        if not expected or p.get('styleId')!=expected or mode!='text' or p.get('pose') is not None or p.get('faceDetail') or p.get('hiresFix'):
            raise ValueError('RPG 시트는 전용 Anima Base/Flanime + RPG Character Sprite LoRA의 새로 생성을 사용하세요. 포즈·얼굴·확대 보정은 꺼 주세요.')
        result['sheetLayout']=dict(columns=3,rows=4,directions=['front','left','right','back'],alignment='unverified',version='rpgchara-3x4-v1')
    if model=='anima-base' and mode!='text':raise ValueError('Anima Base 시트 모델은 새로 생성을 지원합니다.')
    asset_spec=asset_types.validate(p.get('assetSpec'))
    if asset_spec:
        if sheet:asset_spec.update(directionCount=4,outputMode='four-direction-sheet')
        result['assetSpec']=asset_spec
    hires=p.get('hiresFix',False)
    if type(hires) is not bool:raise ValueError('고해상도 보정 옵션을 확인하세요.')
    if hires:
        if model not in image_hires.SUPPORTED or mode!='text':
            raise ValueError('고해상도 보정은 Illustrious / Animagine의 새로 생성에서 지원합니다.')
        if not image_hires.ready():raise ValueError('고해상도 확대 모델을 설치 중입니다.')
        result.update(hiresFix=True,hiresFixVersion=image_hires.VERSION,hiresDenoise=.2)
    detail=p.get('faceDetail',False)
    if type(detail) is not bool:raise ValueError('얼굴 보정 옵션을 확인하세요.')
    if detail:
        if model not in image_face_detail.SUPPORTED or mode!='text':
            raise ValueError('얼굴 보정은 Illustrious / Animagine의 새로 생성에서 지원합니다.')
        if not image_face_detail.ready():raise ValueError('얼굴 보정 검출 모델·노드를 설치 중입니다.')
        result.update(faceDetail=True,faceDetailVersion=image_face_detail.NATIVE_VERSION if model in image_face_detail.NATIVE_MODELS else image_face_detail.VERSION)
        if model in image_face_detail.NATIVE_MODELS:result['faceDetailDenoise']=.15
    background=p.get('background','keep')
    if background not in ('keep','transparent'):
        raise ValueError('배경 옵션을 확인하세요.')
    if mode=='inpaint': background='keep'
    if background=='transparent' and not image_background.status()['ready']:
        raise ValueError('투명 배경 모델을 설치·검증 중입니다. 배경 유지를 선택해 주세요.')
    result['background']=background
    for key,default,limit in [('prompt','',6000),('negativePrompt','worst quality, low quality, blurry, text, watermark',3000),('title','캐릭터 원화',80)]:
        val=p.get(key,default)
        if not isinstance(val,str) or len(val)>limit: raise ValueError(key+' 길이 또는 형식을 확인하세요.')
        result[key]=val.strip()
    if not result['prompt']: raise ValueError('그릴 캐릭터를 설명해 주세요.')
    default_width,default_height=(image_pixel.generation_size(pixel['pixelSize']),)*2 if pixel else map(int,MODELS[model].get('defaultSize','832x1216').split('x'))
    for key,default,lo,hi in [('width',default_width,512,1536),('height',default_height,512,1536),('steps',MODELS[model]['steps'],1,50),('count',1,1,4)]:
        val=p.get(key,default)
        if type(val) is not int or not lo<=val<=hi: raise ValueError(key+' 범위를 확인하세요.')
        result[key]=val
    if result['width']%64 or result['height']%64 or result['width']*result['height']>1572864:
        raise ValueError('해상도는 64 단위, 최대 1.5MP입니다.')
    if pixel:
        if (result['width'],result['height'])!=(image_pixel.generation_size(pixel['pixelSize']),)*2:raise ValueError('픽셀 생성 크기는 전용 세팅의 768·1024px 정사각형을 사용하세요.')
        result.update(pixel)
    if model==image_soya.MODEL_ID:
        if result['width']*result['height']>image_soya.MODEL['maxBasePixels']:
            raise ValueError('Soya 기본 생성은 최대 768×1024 상당 해상도입니다. 결과는 가로·세로 2배로 출력됩니다.')
        result.update(workflowVersion='soya-anima-flanime-v1',outputWidth=result['width']*2,outputHeight=result['height']*2,
            refinerLora='Detailed anime style Illustrious v0.7 · Git 원본과 동일성 미확인 후보',baseLora='Kieed 0.3')
    if detail or hires:
        factor=1 if model in image_face_detail.NATIVE_MODELS and not hires else 2
        result.update(outputWidth=result['width']*factor,outputHeight=result['height']*factor)
    for key,default,lo,hi in [('cfg',MODELS[model]['cfg'],1,12),('denoise',0.65,0.05,1)]:
        val=p.get(key,default)
        if type(val) not in (int,float) or not math.isfinite(val) or not lo<=val<=hi: raise ValueError(key+' 범위를 확인하세요.')
        result[key]=val
    seed=p.get('seed')
    seed_max=MODELS[model].get('maxSeed',2**53-5)-result['count']+1
    if seed in (None,''): seed=secrets.randbelow(seed_max+1)
    if type(seed) is not int or not 0<=seed<=seed_max: raise ValueError(f'이 그림체와 후보 장수의 재현 번호는 0~{seed_max} 정수입니다. 비우면 자동으로 정합니다.')
    result['seed']=seed
    pose=image_pose.validate(p.get('pose'),model,mode,detail,hires)
    if pose:result['pose']=pose
    framing=PRESETS[preset] if sheet else asset_types.prompt(asset_spec) if asset_spec else PRESETS[preset]
    if model==image_cutscene.MODEL_ID and asset_spec and asset_spec['type']=='side':
        facing=asset_types.FACING[asset_spec['facing']]
        framing='full body, feet visible, side view, '+facing+', standing in a battle ready stance, single character game battle sprite, simple white background'
    if asset_spec and asset_spec['type']=='illustration':framing=', '.join(filter(None,[PRESETS[preset],framing]))
    result['resolvedPrompt']=', '.join(filter(None,['masterpiece, best quality, safe',result['prompt'],framing]))
    result['resolvedNegativePrompt']=', '.join(filter(None,[result['negativePrompt'], 'multiple views, reference sheet, turnaround, split screen, multiple characters, cropped, out of frame' if preset not in ('illustration','rpg-sheet') else '']))
    if pixel:
        result['resolvedPrompt']='pixel art, '+', '.join(filter(None,[result['prompt'],framing,'simple shapes, flat colors, crisp pixel edges, single subject']))
        result['resolvedNegativePrompt']+=', photorealistic, 3d render, smooth gradients, antialiasing, blurry edges, text, watermark, sprite sheet, reference sheet, multiple views, grid, panels, collage, icon set, multiple objects, multiple characters, variations, comparison, dividers, border'
    if background=='transparent':
        result['resolvedPrompt']+=', isolated single object, plain white background, no ground shadow' if pixel and preset=='illustration' else ', plain white background, no ground shadow' if sheet else ', isolated single character, plain white background, no ground shadow'
        result['resolvedNegativePrompt']+=', scenery, detailed background, checkerboard background, cast shadow'
    look=image_looks.apply(result,p.get('lookId'))
    result['animationType']='원화 · '+result['title']
    style=image_styles.validate(p.get('styleId'),p.get('styleStrength',.7),MODELS[model]['family'])
    if style:
        if model==image_soya.MODEL_ID: result['baseLora']=style['name']+' '+str(p.get('styleStrength',.7))
        result.update(styleId=style['id'],styleStrength=p.get('styleStrength',.7),styleVersion=style['versionId'],styleSha256=style['sha256'])
        if style.get('integrityStatus'):
            result.update(styleIntegrityStatus=style['integrityStatus'],styleUpstreamSha256=style.get('upstreamSha256'))
        triggers=look.get('triggers',style['triggers']) if look and look.get('styleId')==style['id'] else style['triggers']
        result['resolvedPrompt']=', '.join([result['resolvedPrompt']]+triggers)
        if 'workflowBasePrompt' in result:
            result['workflowBasePrompt']=', '.join([result['workflowBasePrompt']]+triggers)
    if model==image_soya.MODEL_ID and not style and result.get('lookWorkflow'):
        result['baseLora']='Kieed '+str(result['lookWorkflow'].get('kieedStrength',.3))
    if model==image_cutscene.MODEL_ID:
        image_cutscene.validate(p,result)
        result['resolvedPrompt']='(official art:1.1), (game cg:1.1), '+result['resolvedPrompt']
        result['resolvedNegativePrompt']+=', halo, floating ring, ring above head'
    if mode!='text':
        source=read_image(p.get('imageData'))
        result['imageData']=p['imageData']
        if mode=='inpaint':
            mask=read_image(p.get('maskData'))
            if mask.size!=source.size or not mask.convert('L').getbbox(): raise ValueError('수정할 영역을 칠해 주세요. 마스크와 원본 크기는 같아야 합니다.')
            result['maskData']=p['maskData']
    return result

def build_workflow(p,seed,image_name=None,pose_image_name=None):
    if p['model']==image_cutscene.MODEL_ID:return image_cutscene.build(p,seed,image_name,pose_image_name)
    if p['model']==image_soya.MODEL_ID:
        style=image_styles.validate(p.get('styleId'),p.get('styleStrength',.7),'anima')
        return image_soya.build(p,seed,style)
    def node(kind,**inputs): return dict(class_type=kind,inputs=inputs)
    m=MODELS[p['model']]
    if m['family']=='anima':
        workflow={'1':node('UNETLoader',unet_name=Path(m['files'][0]).name,weight_dtype='default'),
            '2':node('CLIPLoader',clip_name='qwen_3_06b_base.safetensors',type='stable_diffusion'),
            '3':node('VAELoader',vae_name='qwen_image_vae.safetensors')}
        model,clip,vae=['1',0],['2',0],['3',0]
    else:
        workflow={'1':node('CheckpointLoaderSimple',ckpt_name=Path(m['files'][0]).name)}
        model,clip,vae=['1',0],['1',1],['1',2]
        if m['family']=='illustrious':
            workflow['3']=node('VAELoader',vae_name='illustriousXLV10_v10.safetensors')
            vae=['3',0]
    if p['model']==image_pixel.MODEL_ID:
        workflow['12']=node('LoraLoader',model=model,clip=clip,lora_name=str(Path('pixel/pixel-art-xl.safetensors')),strength_model=1.,strength_clip=1.)
        model,clip=['12',0],['12',1]
    if p.get('styleId'):
        style=image_styles.validate(p['styleId'],p['styleStrength'],m['family'])
        if m['family']=='anima':
            # Anima style LoRAs patch the DiT, not the separate text encoder.
            workflow['11']=node('LoraLoaderModelOnly',model=model,lora_name=str(Path(style['filename'])),strength_model=p['styleStrength'])
        else:
            workflow['11']=node('LoraLoader',model=model,clip=clip,lora_name=str(Path(style['filename'])),
                strength_model=p['styleStrength'],strength_clip=p['styleStrength'])
            clip=['11',1]
        model=['11',0]
    workflow.update({'4':node('CLIPTextEncode',clip=clip,text=p['resolvedPrompt']),
        '5':node('CLIPTextEncode',clip=clip,text=p['resolvedNegativePrompt']),
        '6':node('EmptyLatentImage',width=p['width'],height=p['height'],batch_size=1)})
    if image_name:
        workflow['10']=node('LoadImage',image=image_name)
        workflow['6']=node('VAEEncode',pixels=['10',0],vae=vae) if p['mode']=='reference' else node('VAEEncodeForInpaint',pixels=['10',0],mask=['10',1],vae=vae,grow_mask_by=0)
    workflow['7']=node('KSampler',model=model,positive=['4',0],negative=['5',0],latent_image=['6',0],seed=seed,steps=p['steps'],cfg=p['cfg'],sampler_name='euler' if m['family']=='anima' else 'euler_ancestral',scheduler='simple' if m['family']=='anima' else 'normal',denoise=1.0 if p['mode']=='text' else p['denoise'])
    if p.get('pose'):
        if not pose_image_name:raise ValueError('포즈 입력 이미지가 없습니다.')
        image_pose.apply(workflow,p['pose'],pose_image_name)
    workflow['8']=node('VAEDecode',samples=['7',0],vae=vae)
    final=['8',0]
    if p.get('hiresFix'):
        final=image_hires.add(workflow,p,seed,final,model,clip,vae,['4',0],['5',0])
    if p.get('faceDetail'):
        if p['model'] in image_face_detail.NATIVE_MODELS:
            final=image_face_detail.add_native(workflow,p,seed,final,['1',0],['1',1],vae)
        else:
            final=image_face_detail.add(workflow,p,seed,final,['1',0],['1',1],vae,upscale=not p.get('hiresFix'))
    workflow['9']=node('SaveImage',images=final,filename_prefix='sprite_lab_image')
    return workflow

def update_job(jid,**changes): pass  # replaced by the queue worker

def run_job(jid,p):
    if p.get('operation')=='face-refine':
        import image_face_refine
        return image_face_refine.run_job(jid,p)
    backend=backend_url(p)
    folder=RESULT_ROOT/jid
    folder.mkdir(parents=True,exist_ok=True)
    source=mask=None
    image_name=None
    if p['mode']!='text':
        original=read_image(p['imageData'])
        source=original.resize((p['width'],p['height']),Image.Resampling.LANCZOS)
        prepare=p['mode']=='reference' and p['model'] in ('flanime-xl',image_cutscene.MODEL_ID)
        upload=image_pose.prepare_reference(original,(p['width'],p['height'])) if prepare else Image.new('RGB',source.size,'white')
        if not prepare:upload.paste(source,mask=source.getchannel('A'))
        if p['model']==image_pixel.MODEL_ID:upload=image_pixel.prepare_reference(original,(p['width'],p['height']))
        if p['mode']=='inpaint':
            mask=read_image(p['maskData']).convert('L').resize(source.size,Image.Resampling.NEAREST)
            upload.putalpha(ImageOps.invert(mask))
        buf=io.BytesIO();upload.save(buf,format='PNG')
        image_name=engine.upload_image(buf.getvalue(),'image-reference.png')
    pose_image_name=None
    if p.get('pose'):
        pose_image=image_pose.render(p['pose'],(p['width'],p['height']))
        pose_image.save(folder/'pose.png')
        buf=io.BytesIO();pose_image.save(buf,format='PNG')
        pose_image_name=engine.upload_image(buf.getvalue(),f'image-pose-{jid}.png')
    images=[]
    prompt_id=None
    try:
        if backend==image_soya.URL:
            response=requests.post(COMFY_URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30)
            response.raise_for_status()
        for i in range(p['count']):
            seed=p['seed']+i
            stage='원화·고해상도 보정 중' if p.get('hiresFix') else '원화 생성 중'
            update_job(jid,state='generating',message=f"{stage} · {i+1}/{p['count']} · {MODELS[p['model']]['name']}")
            workflow=build_workflow(p,seed,image_name,pose_image_name)
            response=requests.post(backend+'/prompt',json={'prompt':workflow},timeout=60)
            if not response.ok: raise RuntimeError('ComfyUI 워크플로 오류: '+response.text[:700])
            prompt_id=response.json()['prompt_id']
            history=None
            deadline=time.monotonic()+1800
            while time.monotonic()<deadline:
                time.sleep(1)
                response=requests.get(backend+'/history/'+prompt_id,timeout=30);response.raise_for_status()
                history=response.json().get(prompt_id)
                if history: break
            if not history: raise TimeoutError('이미지 생성 30분 제한을 초과했습니다. 다시 요청하세요.')
            prompt_id=None
            if history.get('status',{}).get('status_str')=='error': raise RuntimeError('ComfyUI 생성 실패: '+str(history['status'].get('messages',[]))[-700:])
            record=history.get('outputs',{}).get('9',{}).get('images',[])
            if not record: raise RuntimeError('ComfyUI 이미지 출력이 없습니다.')
            response=requests.get(backend+'/view',params=record[0],timeout=60);response.raise_for_status()
            with Image.open(io.BytesIO(response.content)) as im: output=im.convert('RGB')
            if mask is not None: output=Image.composite(output.convert('RGBA'),source,mask)
            metadata={k:v for k,v in p.items() if k not in ('imageData','maskData')}
            metadata.update(seed=seed,modelSource=MODELS[p['model']]['source'],modelLicense=MODELS[p['model']]['license'])
            info=PngImagePlugin.PngInfo();info.add_text('sprite_lab',json.dumps(metadata,ensure_ascii=False))
            filename=f'image-{i+1}.png'
            item=dict(url=f'/api/images/{jid}/{filename}',seed=seed)
            if p.get('hiresFix'):
                before_hires=history.get('outputs',{}).get('46',{}).get('images',[])
                if not before_hires:raise RuntimeError('고해상도 보정 비교 출력이 없습니다.')
                response=requests.get(backend+'/view',params=before_hires[0],timeout=60);response.raise_for_status()
                with Image.open(io.BytesIO(response.content)) as im:
                    im.save(folder/f'image-{i+1}-before-hires.png',pnginfo=info)
                item['beforeHiresUrl']=f'/api/images/{jid}/image-{i+1}-before-hires.png'
            if p.get('faceDetail'):
                before=history.get('outputs',{}).get('24',{}).get('images',[])
                masks=history.get('outputs',{}).get('26',{}).get('images',[])
                if not before or not masks:raise RuntimeError('얼굴 보정 비교 출력이 없습니다.')
                response=requests.get(backend+'/view',params=before[0],timeout=60);response.raise_for_status()
                with Image.open(io.BytesIO(response.content)) as im:
                    im.save(folder/f'image-{i+1}-before-face.png',pnginfo=info)
                item['beforeFaceUrl']=f'/api/images/{jid}/image-{i+1}-before-face.png'
                response=requests.get(backend+'/view',params=masks[0],timeout=60);response.raise_for_status()
                with Image.open(io.BytesIO(response.content)) as im:item['faceDetailApplied']=bool(im.convert('L').getbbox())
                if not item['faceDetailApplied']:item['warning']='얼굴을 검출하지 못해 보정 없이 원본을 저장했습니다.'
            if p.get('background')=='transparent' and mask is None:
                original=f'image-{i+1}-original.png'
                output.save(folder/original,pnginfo=info)
                item['originalUrl']=f'/api/images/{jid}/{original}'
                update_job(jid,state='generating',message=f'배경 제거 중 · {i+1}/{p["count"]}')
                try:
                    if p['model']==image_pixel.MODEL_ID:
                        output,item['backgroundMethod']=image_pixel.remove_background(output,p['preset'],p['pixelSize'])
                    else:output=image_background.remove_sheet(output,3,4,hard=p['model']=='anima-base') if p.get('sheetLayout') else image_background.remove(output)
                    item['background']='transparent'
                except Exception:
                    # Deliver the saved original if inference fails; never claim it is transparent.
                    item['background']='keep'
                    item['warning']='배경 제거에 실패해 원본을 보관했습니다.'
            if p['model']==image_pixel.MODEL_ID:
                output.save(folder/f'image-{i+1}-before-pixel.png',pnginfo=info)
                item['beforePixelUrl']=f'/api/images/{jid}/image-{i+1}-before-pixel.png'
                output=image_pixel.finish(output,p['pixelSize'],p['pixelColors'])
                output.resize((output.width*8,output.height*8),Image.Resampling.NEAREST).save(folder/f'image-{i+1}-pixel-preview.png',pnginfo=info)
                item.update(pixelArt=True,width=output.width,height=output.height,pixelColors=p['pixelColors'],pixelPreviewUrl=f'/api/images/{jid}/image-{i+1}-pixel-preview.png')
            output.save(folder/filename,pnginfo=info)
            images.append(item)
        (folder/'generation.json').write_text(json.dumps({k:v for k,v in p.items() if k not in ('imageData','maskData')},ensure_ascii=False,indent=2),encoding='utf-8')
        message='원화 생성 완료' if not any(x.get('warning') for x in images) else '원화 생성 완료 · 일부 처리 안내 확인'
        update_job(jid,state='complete',message=message,images=images,image=images[0]['url'],metadata=f'/api/images/{jid}/generation.json')
    finally:
        if prompt_id:
            # Target only this request; never interrupt another user's direct Comfy job.
            try:
                requests.post(backend+'/queue',json={'delete':[prompt_id]},timeout=10)
                requests.post(backend+'/interrupt',json={'prompt_id':prompt_id},timeout=10)
            except requests.RequestException: pass
        # Shared video engine should not retain image model memory between team jobs.
        try: requests.post(backend+'/free',json={'unload_models':True,'free_memory':True},timeout=15)
        except requests.RequestException: pass
