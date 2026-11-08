"""Refine a saved image's detected faces; keep dimensions and alpha unchanged."""
import io
import json
import math
import secrets
import time
from pathlib import Path

import requests
from PIL import Image, ImageChops, ImageFilter, PngImagePlugin
import image_face_detail as face
import image_cutscene as cutscene
import image_soya

VERSION='saved-face-detail-v1'


def settings(source,request,parent,index,size):
    import image_engine as engine
    strength=request.get('strength',.12)
    if type(strength) not in (int,float) or not math.isfinite(strength) or strength not in (.12,.20):
        raise ValueError('얼굴 보정 강도는 0.12 또는 0.20을 선택하세요.')
    model=source.get('model') if source.get('model') in face.SUPPORTED else 'flanime-xl'
    title=(source.get('title') or '캐릭터 원화')[:65]+' · 얼굴 보정'
    return dict(jobType='image',operation='face-refine',faceRefineVersion=VERSION,
                parentJob=parent,sourceImage=index,sourceModel=source.get('model'),
                model=model,title=title,animationType='원화 · '+title,preset='illustration',mode='reference',
                prompt=source.get('prompt') or 'same character, same facial expression',
                negativePrompt=source.get('negativePrompt',''),
                width=size[0],height=size[1],count=1,steps=20,cfg=4.5,denoise=float(strength),
                faceRefineStrength=float(strength),seed=secrets.randbelow(2**32),
                assetSpec=source.get('assetSpec'),background=source.get('background','keep'),
                cutsceneMixStrength=source.get('cutsceneMixStrength',1.))


def build(p,image_name):
    import image_engine as engine
    def node(kind,**kw):return dict(class_type=kind,inputs=kw)
    model=p['model']
    graph={'1':node('CheckpointLoaderSimple',ckpt_name=Path(engine.MODELS[model]['files'][0]).name),
           '30':node('LoadImage',image=image_name)}
    m,c,v=['1',0],['1',1],['1',2]
    if model==cutscene.MODEL_ID:
        graph['2']=node('CLIPSetLastLayer',clip=c,stop_at_clip_layer=-2)
        graph['14']=node('LoraLoader',model=m,clip=['2',0],lora_name=str(Path(cutscene.CUTSCENE)),
                         strength_model=p['cutsceneMixStrength'],strength_clip=p['cutsceneMixStrength'])
        m,c=['14',0],['14',1]
    elif engine.MODELS[model]['family']=='illustrious':
        graph['3']=node('VAELoader',vae_name='illustriousXLV10_v10.safetensors');v=['3',0]
    out=face.add(graph,dict(p,styleId=None),p['seed'],['30',0],m,c,v,
                 denoise=p['faceRefineStrength'],upscale=False)
    graph['21']['inputs']['text']+=', same facial expression, same gaze direction, preserve character identity'
    graph['22']['inputs']['text']+=', different expression, changed eye color, halo, floating ring'
    graph['23']['inputs'].update(guide_size=512,max_size=1024,cfg=4.5,feather=6,bbox_dilation=2)
    graph['9']=node('SaveImage',images=out,filename_prefix='sprite_lab_saved_face')
    return graph


def composite(original,generated,mask):
    if generated.size!=original.size or mask.size!=original.size:
        raise RuntimeError('얼굴 보정 출력 크기가 원본과 다릅니다.')
    mask=mask.convert('L')
    box=mask.getbbox()
    if not box:return original.copy(),None
    # Include the detailer's feathered edge, but never touch the rest of the body.
    mask=mask.filter(ImageFilter.MaxFilter(17)).filter(ImageFilter.GaussianBlur(4))
    mask=ImageChops.multiply(mask,original.getchannel('A'))
    out=Image.composite(generated.convert('RGBA'),original,mask)
    out.putalpha(original.getchannel('A'))
    return out,box


def run_job(jid,p):
    import image_engine as engine
    folder=engine.RESULT_ROOT/jid;source=folder/'image-1-before-face.png'
    with Image.open(source) as im:original=im.convert('RGBA')
    upload=Image.new('RGB',original.size,(210,210,210));upload.paste(original,mask=original.getchannel('A'))
    stream=io.BytesIO();upload.save(stream,format='PNG');backend=image_soya.URL;pid=None
    try:
        requests.post(engine.COMFY_URL+'/free',json={'unload_models':True,'free_memory':True},timeout=30).raise_for_status()
        r=requests.post(backend+'/upload/image',files={'image':(jid+'-face.png',stream.getvalue(),'image/png')},timeout=30);r.raise_for_status()
        uploaded=r.json();name='/'.join(filter(None,[uploaded.get('subfolder'),uploaded['name']]))
        engine.update_job(jid,state='generating',message='얼굴 검출·보정 중 · 원본 크기와 몸은 유지합니다.')
        r=requests.post(backend+'/prompt',json={'prompt':build(p,name)},timeout=60)
        if not r.ok:raise RuntimeError('얼굴 보정 워크플로 오류: '+r.text[:600])
        pid=r.json()['prompt_id'];deadline=time.monotonic()+900;history=None
        while time.monotonic()<deadline:
            r=requests.get(backend+'/history/'+pid,timeout=30);r.raise_for_status();history=r.json().get(pid)
            if history:break
            time.sleep(1)
        if not history:raise TimeoutError('얼굴 보정 시간이 초과됐어요. 다시 시도해 주세요.')
        pid=None
        if history.get('status',{}).get('status_str')!='success':raise RuntimeError('얼굴 보정 생성 실패: '+str(history.get('status'))[-600:])
        def read(node):
            images=history.get('outputs',{}).get(node,{}).get('images',[])
            if not images:raise RuntimeError('얼굴 보정 결과를 찾을 수 없습니다.')
            r=requests.get(backend+'/view',params=images[0],timeout=60);r.raise_for_status()
            with Image.open(io.BytesIO(r.content)) as im:return im.copy()
        result,box=composite(original,read('9'),read('26'))
        metadata=dict(p,faceBox=box,faceDetailApplied=box is not None)
        info=PngImagePlugin.PngInfo();info.add_text('sprite_lab',json.dumps(metadata,ensure_ascii=False))
        result.save(folder/'image-1.png',pnginfo=info)
        (folder/'generation.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
        item=dict(url=f'/api/images/{jid}/image-1.png',beforeFaceUrl=f'/api/images/{jid}/image-1-before-face.png',
                  seed=p['seed'],faceBox=box,faceDetailApplied=box is not None,background=p['background'])
        if not box:item['warning']='얼굴을 찾지 못해 원본을 그대로 저장했어요. 부분 수정에서 얼굴을 직접 칠해 주세요.'
        engine.update_job(jid,state='complete',message='얼굴 보정 완료 · 전후를 비교하세요.' if box else item['warning'],
                          images=[item],image=item['url'],metadata=f'/api/images/{jid}/generation.json')
    finally:
        if pid:
            try:
                requests.post(backend+'/queue',json={'delete':[pid]},timeout=10)
                requests.post(backend+'/interrupt',json={'prompt_id':pid},timeout=10)
            except requests.RequestException:pass
        try:requests.post(backend+'/free',json={'unload_models':True,'free_memory':True},timeout=15)
        except requests.RequestException:pass
