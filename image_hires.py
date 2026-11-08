"""Conservative SDXL second pass; existing composition is the latent input."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SUPPORTED=('illustrious-xl','animagine-xl')
UPSCALER='2x-AnimeSharpV4_Fast_RCAN_PU.safetensors'
VERSION='sdxl-hires-v1'


def ready():
    return (ROOT/'ComfyUI/models/upscale_models'/UPSCALER).is_file()


def add(graph,p,seed,image,model,clip,vae,positive,negative,denoise=.2):
    def node(kind,**inputs):return dict(class_type=kind,inputs=inputs)
    graph['40']=node('UpscaleModelLoader',model_name=UPSCALER)
    graph['41']=node('ImageUpscaleWithModel',upscale_model=['40',0],image=image)
    graph['42']=node('ImageScale',image=['41',0],upscale_method='lanczos',width=p['width']*2,height=p['height']*2,crop='disabled')
    graph['43']=node('VAEEncodeTiled',pixels=['42',0],vae=vae,tile_size=512,overlap=64,temporal_size=64,temporal_overlap=8)
    graph['44']=node('KSampler',model=model,positive=positive,negative=negative,latent_image=['43',0],
                     seed=seed,steps=16,cfg=5,sampler_name='euler_ancestral',scheduler='normal',denoise=denoise)
    graph['45']=node('VAEDecodeTiled',samples=['44',0],vae=vae,tile_size=512,overlap=64,temporal_size=64,temporal_overlap=8)
    graph['46']=node('SaveImage',images=['42',0],filename_prefix='sprite_lab_before_hires')
    return ['45',0]
