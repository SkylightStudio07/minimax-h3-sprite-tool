"""Pinned SDXL + Pixel Art XL recipe and deterministic low-resolution export."""
from PIL import Image, ImageOps

MODEL_ID='pixel-art-xl'
VERSION='pixel-art-xl-grid-v2'
MODEL=dict(name='픽셀 아트 · 로컬 XL (실험)',family='pixel-sdxl',steps=30,cfg=7.0,
    files=['checkpoints/sd_xl_base_1.0_0.9vae.safetensors','loras/pixel/pixel-art-xl.safetensors'],
    defaultSize='1024x1024',modes=['text','reference'],source='https://huggingface.co/nerijs/pixel-art-xl',
    license='SDXL: CreativeML Open RAIL++-M / Pixel Art XL: CreativeML OpenRAIL-M',
    description='SDXL Base + Pixel Art XL 고정 조합. 768·1024px 생성 후 최근접 축소하여 64·96·128px PNG를 만듭니다. 로컬 처리 · 추가 화풍/얼굴 보정 제외 · 정지 이미지 초안.')

def generation_size(size):
    # SDXL loses object composition at 512px. Keep a 1024px pass for 64px exports.
    return 1024 if size==64 else size*8

def remove_background(image,preset,size):
    import numpy as np
    import idle_tool
    import image_background
    def usable(cut):
        opaque=np.asarray(cut.getchannel('A'))>=128
        if not .015<float(opaque.mean())<.98:return False
        return bool(cut.resize((size,size),Image.Resampling.NEAREST).getchannel('A').point(lambda a:255 if a>=128 else 0).getbbox())
    if preset=='sprite':
        cut=image_background.remove(image)
        if usable(cut):return cut,'anime-isnet'
    # Inventory objects are not anime people. Remove only edge-connected flat matte.
    cut=idle_tool.remove_flat_background(image,tolerance=24)
    if not usable(cut):raise RuntimeError('배경과 대상이 구분되지 않아 원본을 유지합니다.')
    return cut,'border-connected-flat'

def settings(raw):
    size=raw.get('pixelSize',128);colors=raw.get('pixelColors',32)
    if type(size) is not int or size not in (64,96,128):raise ValueError('도트 크기는 64·96·128px 중 선택하세요.')
    if type(colors) is not int or colors not in (0,16,32,64):raise ValueError('도트 색상 수는 원본·16·32·64색 중 선택하세요.')
    if raw.get('mode','text') not in ('text','reference'):raise ValueError('픽셀 아트는 새로 생성 또는 참고 이미지 변형을 사용하세요.')
    if any(raw.get(k) for k in ('styleId','lookId','pose','faceDetail','hiresFix')):raise ValueError('픽셀 전용 조합에서는 추가 그림체·포즈·얼굴·확대 보정을 꺼 주세요.')
    if raw.get('preset','illustration') not in ('illustration','sprite'):raise ValueError('픽셀 아트는 단일 이미지 초안을 만듭니다. 시트·Live2D 구도는 지원하지 않습니다.')
    return dict(pixelSize=size,pixelColors=colors,pixelArtVersion=VERSION,outputWidth=size,outputHeight=size)

def prepare_reference(image,size):
    """Keep aspect ratio and center the reference on the square generation canvas."""
    target=Image.new('RGB',size,'white')
    fitted=ImageOps.contain(image.convert('RGBA'),size,Image.Resampling.NEAREST)
    target.paste(fitted,((size[0]-fitted.width)//2,(size[1]-fitted.height)//2),fitted)
    return target

def finish(image,size,colors):
    # Never blur/antialias the final grid. A single optional palette applies to the full sprite.
    small=image.convert('RGBA').resize((size,size),Image.Resampling.NEAREST)
    alpha=small.getchannel('A').point(lambda a:255 if a>=128 else 0)
    rgb=small.convert('RGB')
    # Exclude transparent background colors from palette calculation.
    if colors:
        visible=[rgb.getpixel((x,y)) for y in range(size) for x in range(size) if alpha.getpixel((x,y))]
        if visible:
            sample=Image.new('RGB',(len(visible),1));sample.putdata(visible)
            palette=sample.quantize(colors=colors,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
            used=len(palette.getcolors());entries=palette.getpalette()
            entries[used*3:]=entries[:3]*(256-used);palette.putpalette(entries)
            rgb=rgb.quantize(palette=palette,dither=Image.Dither.NONE).convert('RGB')
    rgb.putalpha(alpha)
    return rgb
