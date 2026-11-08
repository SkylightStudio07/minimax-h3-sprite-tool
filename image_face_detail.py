"""Optional Impact Pack face-only refinement on the isolated workflow backend."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DETECTOR='bbox/anime-face-v1.4-n.pt'
SUPPORTED=('illustrious-xl','animagine-xl','flanime-xl','wai-cutscene-counter')
NATIVE_MODELS=('flanime-xl','wai-cutscene-counter')
NATIVE_VERSION='native-face-detail-v1'
VERSION='anime-face-detail-v1'


def ready():
    return all(path.exists() for path in (
        ROOT/'ComfyUI-workflows/models/ultralytics'/DETECTOR,
        ROOT/'ComfyUI-workflows/custom_nodes/ComfyUI-Impact-Pack',
        ROOT/'ComfyUI-workflows/custom_nodes/ComfyUI-Impact-Subpack'))


def add(graph,p,seed,image,model,clip,vae,denoise=.35,upscale=True):
    def node(kind,**inputs):return dict(class_type=kind,inputs=inputs)
    if upscale:
        graph['28']=node('ImageScale',image=image,upscale_method='lanczos',width=p['width']*2,height=p['height']*2,crop='disabled')
        image=['28',0]
    # Reuse the same checkpoint; reduce the sprite LoRA during the face pass.
    # Start from the unpatched MODEL/CLIP to avoid applying the LoRA twice.
    if p.get('styleId'):
        import image_styles
        style=image_styles.validate(p['styleId'],p['styleStrength'],'illustrious' if p['model'] in ('illustrious-xl','flanime-xl') else 'sdxl')
        graph['27']=node('LoraLoader',model=model,clip=clip,lora_name=str(Path(style['filename'])),
                         strength_model=min(.25,p['styleStrength']),strength_clip=min(.25,p['styleStrength']))
        model,clip=['27',0],['27',1]
    remove={'full body','full_body','standing','idle','side view','facing right','grey background','gray background',
            'clean lineart','game battle sprite','holding a rifle','solo','1girl'}
    parts=[part.strip() for part in p['prompt'].split(',') if part.strip().lower() not in remove]
    prompt=', '.join(parts+['masterpiece','best quality','close-up portrait','detailed eyes','clean facial lineart'])
    graph['20']=node('UltralyticsDetectorProvider',model_name=DETECTOR)
    graph['21']=node('CLIPTextEncode',clip=clip,text=prompt)
    graph['22']=node('CLIPTextEncode',clip=clip,text='worst quality, low quality, blurry, malformed eyes, extra eyes, text, watermark')
    graph['23']=node('FaceDetailer',image=image,model=model,clip=clip,vae=vae,guide_size=384,guide_size_for=True,max_size=768,
                     seed=seed,steps=20,cfg=5,sampler_name='euler_ancestral',scheduler='normal',positive=['21',0],negative=['22',0],
                     denoise=denoise,feather=8,noise_mask=True,force_inpaint=True,bbox_threshold=.3,bbox_dilation=4,bbox_crop_factor=2.5,
                     sam_detection_hint='center-1',sam_dilation=0,sam_threshold=.93,sam_bbox_expansion=0,
                     sam_mask_hint_threshold=.7,sam_mask_hint_use_negative='False',drop_size=10,bbox_detector=['20',0],wildcard='',cycle=1)
    graph['24']=node('SaveImage',images=image,filename_prefix='sprite_lab_before_face')
    graph['25']=node('MaskToImage',mask=['23',3])
    graph['26']=node('SaveImage',images=['25',0],filename_prefix='sprite_lab_face_mask')
    return ['23',0]


def add_native(graph,p,seed,image,model,clip,vae,denoise=.15):
    # Use Flanime's face detail without the sprite LoRA and without resizing.
    face=dict(p,styleId=None)
    result=add(graph,face,seed,image,model,clip,vae,denoise=denoise,upscale=False)
    remove={'full body','full_body','standing','idle','side view','facing right','grey background','gray background',
            'clean lineart','game battle sprite','holding a rifle','solo','1girl'}
    parts=[part.strip() for part in p['prompt'].split(',') if part.strip().lower() not in remove]
    if 'side view' in p['prompt'].lower():parts.append('side profile')
    graph['21']['inputs']['text']=', '.join(parts+['masterpiece','best quality','closed mouth','clean skin','detailed eyes','fine eyelashes','crisp lineart'])
    graph['22']['inputs']['text']='worst quality, low quality, blurry, malformed eyes, extra eyes, face paint, white marks on face, drooling, tears, open mouth, text, watermark'
    graph['23']['inputs'].update(guide_size=512,max_size=1024,cfg=4,feather=6,bbox_dilation=2)
    return result
