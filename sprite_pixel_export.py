"""Reusable pixel export from generated video; no character-specific masks or effects."""
import io
import av
import cv2
import numpy as np
from PIL import Image
import sprite_finish
import sprite_loop
from tools.sprite_matte import clean_flat_matte

SCALE = 4

def quantize(rgb,palette):
    distances=((rgb.astype(np.float32)[:,:,None,:]-palette[None,None,:,:])**2).sum(axis=3)
    return distances.argmin(axis=2).astype(np.uint8),distances

def vote_grid(rgb,alpha,palette):
 h,w=rgb.shape[0]//SCALE,rgb.shape[1]//SCALE
 lab=cv2.cvtColor(rgb.astype(np.float32)/255,cv2.COLOR_RGB2LAB)
 plab=cv2.cvtColor(palette.astype(np.float32)[None]/255,cv2.COLOR_RGB2LAB)[0]
 labels=np.concatenate([((block[:,:,None,:]-plab[None,None,:,:])**2).sum(axis=3).argmin(axis=2) for block in np.array_split(lab,max(1,len(lab)//16))],axis=0)
 labels=labels.reshape(h,SCALE,w,SCALE).transpose(0,2,1,3).reshape(h,w,SCALE*SCALE)
 weights=alpha.reshape(h,SCALE,w,SCALE).transpose(0,2,1,3).reshape(h,w,SCALE*SCALE)
 scores=np.stack([(weights*(labels==i)).sum(axis=2) for i in range(len(palette))],axis=2)
 rgb=palette[scores.argmax(axis=2)].astype(np.uint8);coverage=weights.mean(axis=2)
 return rgb,coverage

def thin_coverage(raw,alpha,coverage):
 h,w=coverage.shape
 neutral=(raw.min(axis=2)>145)&(np.ptp(raw.astype(float),axis=2)<55)&(alpha>.35)
 density=neutral.reshape(h,SCALE,w,SCALE).mean(axis=(1,3))
 support=cv2.filter2D((density>.12).astype(np.float32),-1,np.ones((3,3),np.float32))
 keep=(coverage>=.2)&(coverage<.5)&(density>=.125)&(support>=3)
 result=coverage.copy();result[keep]=.8
 return result,int(keep.sum())

def flow_pair(previous,current):
 h,w=previous.shape;dis=cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
 f=dis.calc(previous,current,None);b=dis.calc(current,previous,None)
 yy,xx=np.indices((h,w),dtype=np.float32);mx=xx+b[:,:,0];my=yy+b[:,:,1]
 opposite=cv2.remap(f,mx,my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
 error=np.linalg.norm(b+opposite,axis=2)
 return mx,my,(mx>=1)&(my>=1)&(mx<w-2)&(my<h-2)&(error<.65)

def temporal_cleanup(rgbs,coverages,grays,palette):
 frames=[];records=[];previous_labels=None;previous_alpha=None
 for i,(rgb,coverage) in enumerate(zip(rgbs,coverages)):
  labels,distance=quantize(rgb,palette);alpha=coverage>=.5;cc=ca=0
  if i:
   mx,my,valid=flow_pair(grays[i-1],grays[i])
   warped=cv2.remap(previous_labels,mx,my,cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT)
   oldalpha=cv2.remap(previous_alpha.astype(np.uint8),mx,my,cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT)>0
   oldgray=cv2.remap(grays[i-1],mx,my,cv2.INTER_LINEAR)
   valid&=np.abs(grays[i].astype(np.float32)-oldgray.astype(np.float32))<18
   previous_cost=np.take_along_axis(distance,warped[:,:,None],axis=2)[:,:,0];best_cost=distance.min(axis=2)
   keep=valid&oldalpha&alpha&(labels!=warped)&(previous_cost-best_cost<260)&(previous_cost<1500)
   cc=int(keep.sum());labels[keep]=warped[keep]
   keep_alpha=valid&(coverage>.30)&(coverage<.70)&(alpha!=oldalpha);ca=int(keep_alpha.sum());alpha[keep_alpha]=oldalpha[keep_alpha]
  a=np.dstack((palette[labels].astype(np.uint8),alpha.astype(np.uint8)*255));a[~alpha,:3]=0;frames.append(a)
  previous_labels=quantize(rgb,palette)[0];previous_alpha=coverage>=.5
  records.append(dict(frame=i,changedColors=cc,changedAlpha=ca))
 return frames,records


def palette_from_pixels(pixels, count):
    if not len(pixels):
        return [[0, 0, 0]]
    image = Image.fromarray(np.asarray(pixels, np.uint8).reshape(-1, 1, 3))
    quant = image.quantize(colors=count, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    return np.unique(np.array(quant.convert('RGB')).reshape(-1, 3), axis=0).tolist()


def video_palette(video_path, reference):
    # Keep source colors, but admit the new colors actually generated for VFX.
    cut, _ = clean_flat_matte(reference)
    a = np.array(cut)
    pixels = a[:, :, :3][a[:, :, 3] >= 128]
    pixels = pixels[::max(1, len(pixels)//100000)]
    original = np.array(palette_from_pixels(pixels, 32), np.int32)
    samples = []
    with av.open(str(video_path)) as clip:
        for frame in clip.decode(video=0):
            rgb = np.array(frame.to_image().convert('RGB'))
            bg = np.median(np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1])), axis=0)
            candidate = rgb[2::8, 2::8].reshape(-1, 3).astype(np.int32)
            candidate = candidate[(np.ptp(candidate, axis=1)>35) & (np.max(np.abs(candidate-bg), axis=1)>32)]
            if len(candidate):
                distance = ((candidate[:, None, :]-original[None, :, :])**2).sum(axis=2).min(axis=1)
                candidate = candidate[distance>22**2]
                if len(candidate):
                    samples.append(candidate[np.linspace(0, len(candidate)-1, min(512, len(candidate))).round().astype(int)])
    extra = palette_from_pixels(np.concatenate(samples), 16) if samples else []
    palette = original.tolist()
    for color in extra:
        if color not in palette:
            palette.append(color)
    return np.array(palette, np.float32)


def export(video_path, reference_bytes, sheet_path, transparent_path, count, loop, color_lock=True, action=None, game_paths=None):
    """Same 4x palette vote, matte cleanup and flow gating as the accepted tests."""
    reference = Image.open(io.BytesIO(reference_bytes)).convert('RGBA')
    palette = video_palette(video_path, reference)
    colors, coverages, grays = [], [], []
    with av.open(str(video_path)) as clip:
        fps = float(clip.streams.video[0].average_rate or 24)
        for frame in clip.decode(video=0):
            raw = np.array(frame.to_image().convert('RGB'))
            if raw.shape[0] % SCALE or raw.shape[1] % SCALE:
                raise ValueError('도트 출력의 영상 크기는 4의 배수여야 합니다.')
            cut, _ = clean_flat_matte(Image.fromarray(raw), tolerance=26, radius=3)
            a = np.array(cut)
            rgb, coverage = vote_grid(a[:, :, :3], a[:, :, 3].astype(np.float32)/255, palette)
            coverage, _ = thin_coverage(a[:, :, :3], a[:, :, 3].astype(np.float32)/255, coverage)
            colors.append(rgb)
            coverages.append(coverage)
            grays.append(cv2.cvtColor(cv2.resize(raw, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY))
    if not colors:
        raise ValueError('생성 영상에 프레임이 없습니다.')
    if color_lock:
        frames, _ = temporal_cleanup(colors, coverages, grays, palette)
    else:
        frames = [np.dstack((rgb, (alpha>=.5).astype(np.uint8)*255)).astype(np.uint8) for rgb, alpha in zip(colors, coverages)]
    images = [Image.fromarray(a) for a in frames]
    pick = sprite_finish.pick(images, count, action, loop) if action else dict(indices=sprite_loop.sample_indices(len(frames), min(count, len(frames)), loop), end=len(frames), method='even')
    indices = pick['indices']
    h, w = frames[0].shape[:2]
    columns = min(len(indices), 8)
    size = (columns*w, ((len(indices)+columns-1)//columns)*h)
    opaque = Image.new('RGBA', size)
    transparent = Image.new('RGBA', size)
    edges = []
    for index, a in enumerate(frames):
        if np.any(a[0, :, 3]) or np.any(a[-1, :, 3]) or np.any(a[:, 0, 3]) or np.any(a[:, -1, 3]):
            edges.append(index)
    for slot, index in enumerate(indices):
        a = frames[index].copy()
        a[a[:, :, 3]==0, :3] = 0
        image = Image.fromarray(a)
        pos = ((slot % columns)*w, (slot//columns)*h)
        transparent.paste(image, pos)
        background = Image.new('RGBA', (w, h), (128, 128, 128, 255))
        background.alpha_composite(image)
        opaque.paste(background, pos)
    opaque.save(sheet_path)
    if transparent_path:
        transparent.save(transparent_path)
    duration_ms = sprite_finish.durations_ms(indices, pick['end'], fps)
    game = None
    if game_paths and transparent_path:
        try:
            game = sprite_finish.write([images[i] for i in indices], action, loop, duration_ms, *game_paths)
        except Exception:
            for path in game_paths:
                path.unlink(missing_ok=True)
    return dict(version='pixel-video-v1', width=w, height=h, colors=len(palette), durationMs=duration_ms, method=pick['method'], game=game,
                frameCount=len(indices), sourceIndices=[int(i) for i in indices],
                edgeContactFrames=edges, pixelColorLock=color_lock,
                separateEffectLayers=False, palette=palette.astype(np.uint8).tolist())
