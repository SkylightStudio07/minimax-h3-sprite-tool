"""Anime foreground alpha, evaluated on CPU without occupying the video GPU."""
import importlib.util
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
MODEL = ROOT/'models/background/isnetis.onnx'
SHA256 = 'f15622d853e8260172812b657053460e20806f04b9e05147d49af7bed31a6e99'
REVISION = '493cb60893f47441b26ec4fb9a306bce9e342982'
VERIFIED = ROOT/'models/background/validated.txt'
SPRITE_MATTE_REVISION = 'semantic-sprite-v2-contrast-preserve'


def status():
    installed = MODEL.is_file() and importlib.util.find_spec('onnxruntime') is not None
    validated = VERIFIED.is_file() and VERIFIED.read_text(encoding='utf-8').strip() == SHA256
    return dict(installed=installed, ready=installed and validated, model='Anime Segmentation ISNet',
                license='Apache-2.0', source='https://huggingface.co/skytnt/anime-seg')


@lru_cache(maxsize=1)
def load_session():
    """Reuse one CPU session across frames; never allocate video GPU memory."""
    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 4
    opts.inter_op_num_threads = 1
    return ort.InferenceSession(str(MODEL), sess_options=opts, providers=['CPUExecutionProvider'])


def remove(image):
    rgba = image.convert('RGBA')
    rgb = Image.new('RGB', rgba.size, 'white')
    rgb.paste(rgba, mask=rgba.getchannel('A'))
    session = load_session()
    info = session.get_inputs()[0]
    side = info.shape[-1] if isinstance(info.shape[-1], int) else 1024
    width, height = rgb.size
    scale = side/max(width, height)
    w, h = max(1, int(width*scale)), max(1, int(height*scale))
    x, y = (side-w)//2, (side-h)//2
    data = np.zeros((side, side, 3), dtype=np.float32)
    data[y:y+h, x:x+w] = np.asarray(rgb.resize((w,h), Image.Resampling.BILINEAR), dtype=np.float32)/255
    prediction = session.run(None, {info.name:data.transpose(2,0,1)[None]})[0]
    matte = np.asarray(prediction).squeeze()
    if matte.ndim != 2 or not np.isfinite(matte).all():
        raise RuntimeError('배경 제거 마스크를 생성하지 못했습니다.')
    alpha = Image.fromarray(np.clip(matte[y:y+h,x:x+w]*255,0,255).astype('uint8')).resize(rgba.size,Image.Resampling.BILINEAR)
    alpha = np.minimum(np.asarray(alpha),np.asarray(rgba.getchannel('A')))
    # Keep the generated RGB exactly; only replace alpha, with no cropping/resizing.
    rgba.putalpha(Image.fromarray(alpha))
    return rgba


def remove_sheet(image, columns=3, rows=4, hard=False):
    """Preserve sheet coordinates and RGB; matte each cell independently."""
    rgba=image.convert('RGBA')
    result=rgba.copy()
    for row in range(rows):
        for col in range(columns):
            box=(round(col*rgba.width/columns),round(row*rgba.height/rows),round((col+1)*rgba.width/columns),round((row+1)*rgba.height/rows))
            cell=remove(rgba.crop(box))
            if hard:
                alpha=np.asarray(cell.getchannel('A'))
                cell.putalpha(Image.fromarray(np.where(alpha>=128,255,0).astype('uint8')))
            result.paste(cell,box)
    return result


def remove_sprite(image):
    """Semantic cutout for video frames, including enclosed limb gaps.

    Only suppress the flat exterior when the observed border really is uniform.
    Interior gray costume regions are decided by the semantic model, never by
    a global color key. Keep RGB and frame coordinates intact.
    """
    from scipy import ndimage
    result=remove(image)
    alpha=np.array(result.getchannel('A'))
    rgb=np.asarray(image.convert('RGB'),dtype=np.float32)
    border=np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1]))
    background=np.median(border,axis=0)
    if np.mean(np.max(np.abs(border-background),axis=1)<=8)>=.98:
        near=np.max(np.abs(rgb-background),axis=2)<=24
        seed=np.zeros(near.shape,dtype=bool)
        seed[0]=near[0];seed[-1]=near[-1];seed[:,0]=near[:,0];seed[:,-1]=near[:,-1]
        exterior=ndimage.binary_propagation(seed,mask=near)
        # Anime segmentation can classify thin pale blades as background.
        # On a verified flat matte, strong color evidence connected to the
        # detected character preserves those details. Near-matte enclosed
        # gaps still rely on the semantic prediction, including gray clothing.
        distance=np.max(np.abs(rgb-background),axis=2)
        support=ndimage.binary_propagation(alpha>=32,mask=(~exterior)&(distance>24))
        coverage=np.clip((distance-24)/32,0,1)*255
        alpha=np.maximum(alpha,np.where(support,coverage,0).astype('uint8'))
        alpha[exterior & (alpha<192)]=0
    # Low model confidence outside the silhouette otherwise leaves a faint
    # veil on dark/light preview backgrounds. Preserve soft contour coverage.
    alpha[alpha<32]=0
    alpha[alpha>240]=255
    result.putalpha(Image.fromarray(alpha))
    return result


def remove_sprite_with_sparks(image):
    """Opt-in recovery of generated gold sparks on a verified flat neutral key."""
    result=remove_sprite(image)
    rgb=np.asarray(image.convert('RGB'),dtype=float)
    border=np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1]))
    bg=np.median(border,axis=0)
    if np.ptp(bg)>=12 or np.mean(np.max(np.abs(border-bg),axis=1)<12)<=.98:
        return result
    rgba=np.array(result)
    r,g,b=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2]
    warm=(r>155)&(r>g)&(r-g<80)&(r-b>22)&(g-b>8)&(rgba[:,:,3]<192)
    alpha=np.clip(np.maximum(((rgb-bg)/np.maximum(255-bg,1)).max(2),((bg-rgb)/np.maximum(bg,1)).max(2)),0,1)
    recovered=np.clip((rgb-bg*(1-alpha[:,:,None]))/np.maximum(alpha[:,:,None],.01),0,255)
    rgba[warm,:3]=np.rint(recovered[warm]).astype('uint8')
    rgba[warm,3]=np.maximum(rgba[warm,3],np.rint(alpha[warm]*255).astype('uint8'))
    return Image.fromarray(rgba)
