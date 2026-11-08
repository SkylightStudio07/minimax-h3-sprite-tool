"""Isolated four-pose pixel animation experiment; never changes the site gallery.

This is high-resolution reference editing followed by fixed-palette pixel export,
not a native low-resolution animation model. Keep raw edits for visual review.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import sys
import time
import zipfile

import numpy as np
import requests
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import idle_tool
import image_pose
import motion_identity
import rigging_engine as rig
from tools.verify_rpg_sprite_styles import ensure_idle

VERSION = 'pixel-reference-four-poses-v1'
LABELS = ['left-contact', 'left-passing', 'right-contact', 'right-passing']
ACTIONS = [
    'The left boot is forward and lower on the canvas; the right boot is behind. The sword arm swings slightly backward and the empty arm slightly forward.',
    'Weight is on the left leg. Lift the right knee and bend the right leg, keeping the right boot visibly off the ground. The empty arm moves backward and the sword arm moves forward.',
    'The right boot is forward and lower on the canvas; the left boot is behind. The sword arm swings slightly forward and the empty arm slightly backward.',
    'Weight is on the right leg. Lift the left knee and bend the left leg, keeping the left boot visibly off the ground. The empty arm moves forward and the sword arm moves backward.',
]


def poses():
    # COCO-18 joints placed over the ORIGINAL 128px character, not an anime template.
    base = [[.50,.235],[.50,.315],[.465,.335],[.445,.445],[.42,.54],
            [.55,.335],[.575,.445],[.605,.54],[.48,.60],[.47,.715],[.46,.825],
            [.53,.60],[.535,.715],[.54,.825],[.51,.225],[.49,.225],[.525,.235],[.475,.235]]
    changes = [
        {3:[.43,.43],4:[.415,.515],6:[.58,.46],7:[.62,.56],9:[.45,.73],10:[.435,.84],12:[.55,.70],13:[.565,.80]},
        {3:[.45,.46],4:[.45,.56],6:[.58,.42],7:[.62,.50],9:[.475,.73],10:[.48,.84],12:[.55,.69],13:[.555,.765]},
        {3:[.44,.46],4:[.42,.56],6:[.57,.43],7:[.595,.515],9:[.46,.70],10:[.445,.80],12:[.55,.73],13:[.565,.84]},
        {3:[.43,.42],4:[.415,.50],6:[.55,.46],7:[.55,.56],9:[.46,.69],10:[.455,.765],12:[.535,.73],13:[.53,.84]},
    ]
    result = []
    for change in changes:
        points = [point[:] for point in base]
        for index, point in change.items(): points[index] = point
        result.append(dict(points=points, strength=1.0))
    return result


def palette_from(source):
    a = np.asarray(source.convert('RGBA'))
    colors = np.unique(a[:,:,:3][a[:,:,3] >= 128], axis=0)
    if not 1 <= len(colors) <= 256: raise ValueError('Reference must have 1-256 visible colors')
    palette = Image.new('P', (1,1))
    entries = colors.reshape(-1).tolist()
    palette.putpalette(entries + colors[0].tolist() * (256-len(colors)))
    return palette, colors.tolist()


def pixel_export(raw, palette):
    # White matte is explicit in the prompt. Remove edge-connected matte only;
    # do not run an anime mask that could erase tiny hands or the sword.
    cut = idle_tool.remove_flat_background(raw, tolerance=24).convert('RGBA')
    small = cut.resize((128,128), Image.Resampling.NEAREST)
    alpha = small.getchannel('A').point(lambda v: 255 if v >= 128 else 0)
    # Pillow's palette quantizer uses a reduced-bit lookup and can remap even an
    # exact palette member to a nearby color. Use exact RGB distance so existing
    # reference pixels round-trip unchanged and every output uses original colors.
    colors = np.unique(np.asarray(palette.getpalette(), dtype=np.int32).reshape(-1,3), axis=0)
    pixels = np.asarray(small.convert('RGB'), dtype=np.int32)
    distances = ((pixels[:,:,None,:]-colors[None,None,:,:])**2).sum(axis=3)
    rgb = Image.fromarray(colors[distances.argmin(axis=2)].astype(np.uint8))
    rgb.putalpha(alpha)
    if not rgb.getbbox(): raise RuntimeError('Background cleanup erased the frame')
    return rgb


def metrics(frame, source, allowed):
    a = np.asarray(frame); b = np.asarray(source)
    visible = a[:,:,3] > 0
    colors = {tuple(c) for c in np.unique(a[:,:,:3][visible], axis=0)}
    if not colors <= {tuple(c) for c in allowed}: raise AssertionError('Palette drift')
    if set(np.unique(a[:,:,3])) - {0,255}: raise AssertionError('Soft alpha')
    union = visible | (b[:,:,3] > 0)
    changed = np.any(a != b, axis=2) & union
    box = frame.getbbox()
    return dict(size=list(frame.size), colors=len(colors), bounds=list(box),
                groundY=box[3]-1, referenceGroundY=source.getbbox()[3]-1,
                changedForegroundFraction=round(float(changed.sum()/max(1,union.sum())),4),
                note='Pixel changes are diagnostic; they do not measure identity or pose quality.')


def checker(size):
    bg = Image.new('RGB',size,'#e4e5ec'); draw = ImageDraw.Draw(bg)
    for y in range(0,size[1],16):
        for x in range(0,size[0],16):
            if (x//16+y//16)%2: draw.rectangle((x,y,x+15,y+15),fill='#f6f7fb')
    return bg


def frozen_head_preview(out, frames, source):
    """Explicit hand-selected region lock, not automatic part segmentation."""
    box = (53,17,76,39)
    mask = Image.new('L',source.size,0)
    ImageDraw.Draw(mask).rectangle((box[0],box[1],box[2]-1,box[3]-1),fill=255)
    mask.save(out/'head-lock-mask.png')
    locked=[]
    for i,frame in enumerate(frames):
        copy = frame.copy()
        # No alpha mask: transparent pixels in the source region must also replace
        # the generated pixels, so the generated hairstyle is fully cleared here.
        copy.paste(source.crop(box),box)
        assert copy.crop(box).tobytes() == source.crop(box).tobytes()
        copy.save(out/f'frame-{i:02d}-head-locked.png')
        locked.append(copy)
    sheet=Image.new('RGBA',(128*len(locked),128))
    for i,frame in enumerate(locked): sheet.paste(frame,(128*i,0))
    sheet.save(out/'sprite-sheet-head-locked.png')
    large=[f.resize((512,512),Image.Resampling.NEAREST) for f in locked]
    large[0].save(out/'animation-head-locked.webp',save_all=True,append_images=large[1:],duration=180,loop=0,lossless=True)
    (out/'head-lock.json').write_text(json.dumps(dict(method='manual rectangle from original reference; exact RGBA replacement',box=list(box),automaticSegmentation=False,warning='Only head/scarf region is frozen. Sword shape, body proportions and pose drift remain.'),indent=2),encoding='utf-8')
    return locked


def review_extras(out, frames, records, source):
    frozen_head_preview(out,frames,source)
    pose_strip=Image.new('RGB',(256*len(records),256),'black')
    for i,r in enumerate(records):
        with Image.open(out/r['pose']) as pose_image:
            pose_strip.paste(pose_image.resize((256,256),Image.Resampling.NEAREST),(i*256,0))
    pose_strip.save(out/'target-poses.png')
    with zipfile.ZipFile(out/'pixel-animation-draft.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for i,r in enumerate(records):
            archive.write(out/r['pixel'],'generated/'+r['pixel'])
            archive.write(out/f'frame-{i:02d}-head-locked.png',f'head-locked/frame-{i:02d}.png')
        for filename in ('reference.png','sprite-sheet.png','sprite-sheet-head-locked.png','animation.png','results.json','palette.json','target-poses.png','head-lock.json','head-lock-mask.png'):
            archive.write(out/filename,filename)
    path=out/'preview.html'
    page=path.read_text(encoding='utf-8')
    fragment='''<h2>원본 머리·얼굴 잠금 비교</h2><p>수동 지정한 원본 영역 x=53~75, y=17~38의 RGBA 픽셀을 각 프레임에 그대로 복사했습니다. 자동 파츠 분리가 아닙니다. 검·몸통·다리는 생성 결과라 여전히 바뀔 수 있고, 목 경계도 검수해야 합니다.</p><div class="lead"><article><h3>전체 생성</h3><div class="checker"><img class="pixel" src="animation.webp"></div></article><article><h3>원본 머리·얼굴 잠금</h3><div class="checker"><img class="pixel" src="animation-head-locked.webp"></div></article></div><p><a href="pixel-animation-draft.zip" download>생성본 + 머리 잠금본 + PNG 시트 + 팔레트·시간 정보 ZIP</a> · <a href="head-lock-mask.png">수동 잠금 영역</a></p><details><summary>목표 관절 포즈</summary><img class="wide" src="target-poses.png"></details>'''
    page=page.replace('<h2>프레임 비교</h2>',fragment+'<h2>전체 생성 프레임 비교</h2>')
    path.write_text(page,encoding='utf-8')


def preview(out, records, source):
    if not records: return
    frames = [Image.open(out/r['pixel']).convert('RGBA') for r in records]
    sheet = Image.new('RGBA',(128*len(frames),128))
    for i,frame in enumerate(frames): sheet.paste(frame,(128*i,0))
    sheet.save(out/'sprite-sheet.png')
    # Preserve RGBA and exact colors in APNG; WebP is lossless too.
    frames[0].save(out/'animation.png',save_all=True,append_images=frames[1:],duration=180,loop=0,disposal=0,blend=0)
    large = [f.resize((512,512),Image.Resampling.NEAREST) for f in frames]
    large[0].save(out/'animation.webp',save_all=True,append_images=large[1:],duration=180,loop=0,lossless=True)
    montage = checker((320*(len(frames)+1),350)); draw = ImageDraw.Draw(montage)
    for i,(label,im) in enumerate([('reference',source)] + list(zip(LABELS,frames))):
        enlarged = im.resize((320,320),Image.Resampling.NEAREST)
        montage.paste(enlarged,(i*320,30),enlarged)
        draw.text((i*320+12,8),label,fill='black')
    montage.save(out/'comparison.png')
    cards = ''.join(f'<article><h3>{html.escape(r["label"])}</h3><div class="checker"><img src="{r["pixel"]}" class="pixel"></div><p>{r["seconds"]}초 · {r["metrics"]["colors"]}색 · 발바닥 y={r["metrics"]["groundY"]}</p><details><summary>생성 원본 / 목표 뼈대 / 수치</summary><img class="raw" src="{r["raw"]}"><img class="raw" src="{r["pose"]}"><pre>{html.escape(json.dumps(r["metrics"],ensure_ascii=False,indent=2))}</pre></details><p><a href="{r["pixel"]}" download>128px PNG</a> · <a href="{r["workflow"]}">실행 그래프</a></p></article>' for r in records)
    (out/'preview.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>도트 캐릭터 · 네 포즈 일관성 시험</title><style>body{background:#171923;color:#eef0fa;font:15px/1.6 system-ui;margin:24px}h1{font-size:25px}main{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}article{background:#242735;padding:16px;border:1px solid #474d65;border-radius:12px;min-width:0}h3{font-size:16px}a{color:#b8c8ff}.checker{background:repeating-conic-gradient(#ddd 0 25%,#f7f7f7 0 50%) 0/24px 24px;display:grid;place-items:center}.pixel{image-rendering:pixelated;width:100%;max-width:512px}.raw{width:100%}pre{white-space:pre-wrap}.lead{display:flex;gap:20px;flex-wrap:wrap}.lead>article{flex:1;min-width:260px;max-width:512px}.wide{width:100%;image-rendering:pixelated}@media(max-width:900px){main{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:520px){main{grid-template-columns:1fr}}</style><h1>같은 도트 캐릭터 → 4개 걷기 포즈</h1><p>실험: 동일한 원본 도트 + 프레임별 관절 뼈대 → Qwen 2.1 편집 → 128px 최근접 축소 → 원본 공통 팔레트. 저해상도 전용 애니메이션 모델이 아닙니다. Aseprite·영상 생성·프레임 보간·얼굴 덮어쓰기·발 위치 자동 정렬은 사용하지 않았습니다.</p><div class="lead"><article><h2>기준 캐릭터</h2><div class="checker"><img class="pixel" src="reference.png"></div></article><article><h2>생성 프레임 반복 재생</h2><div class="checker"><img class="pixel" src="animation.webp"></div><p>프레임당 180ms. 완성 루프가 아니라 프레임 일관성을 확인하는 초안입니다.</p><p><a href="sprite-sheet.png" download>PNG 시트</a> · <a href="animation.png" download>APNG</a> · <a href="results.json">검증 기록</a></p></article></div><h2>프레임 비교</h2><img class="wide" src="comparison.png"><main>'''+cards+'</main></html>',encoding='utf-8')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--frames',type=int,default=4,choices=range(1,5))
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/pixel-animation-test-20261019')
    args = parser.parse_args()
    out = args.output; out.mkdir(parents=True,exist_ok=True)
    source_path = ROOT/'outputs/pixel-art-test-20261019/knight-128/image-1.png'
    source = Image.open(source_path).convert('RGBA')
    if source.size != (128,128): raise ValueError('Expected original 128px sprite')
    source.save(out/'reference.png')
    palette, allowed = palette_from(source)
    (out/'palette.json').write_text(json.dumps(allowed),encoding='utf-8')
    ensure_idle()
    for port in (8189,8191):
        requests.post(f'http://127.0.0.1:{port}/free',json=dict(unload_models=True,free_memory=True),timeout=30).raise_for_status()
    if not all(p.is_file() for p in rig.QWEN_MODEL_PATHS): raise RuntimeError('Qwen models missing')
    source_canvas = Image.new('RGB',(768,768),'white')
    enlarged = source.resize((768,768),Image.Resampling.NEAREST)
    source_canvas.paste(enlarged,mask=enlarged.getchannel('A'))
    source_canvas.save(out/'reference-input.png')
    token = hashlib.sha256(source_path.read_bytes()+VERSION.encode()).hexdigest()[:16]
    rig.INPUT_ROOT.mkdir(parents=True,exist_ok=True)
    reference_input = rig.INPUT_ROOT/f'pixel_anim_{token}_reference.png'
    source_canvas.save(reference_input)
    records=[]
    for i,pose in enumerate(poses()[:args.frames]):
        name = f'frame-{i:02d}'
        target = rig.INPUT_ROOT/f'pixel_anim_{token}_pose_{i}.png'
        pose_image=image_pose.render(pose,(768,768));pose_image.save(target);pose_image.save(out/f'{name}-pose.png')
        prompt = ('Create exactly ONE pixel-art animation frame, not a sheet or collage. '
                  'Image 1 is the fixed character design and pixel-art style reference. Image 2 is ONLY the target body skeleton, not a character or style reference. '
                  'Repose the EXACT character from image 1 to match image 2. A small forward-facing walking step, three-quarter/front view, in place. '
                  'Preserve the short blue bob haircut, same small face and eyes, white scarf, navy long coat with narrow gold trim, brown belt, tall brown boots, '
                  'and the same single silver sword with a brown hilt held in the hand on the RIGHT side of the image. Never remove, duplicate, bend or redesign the sword. '
                  'Keep the head facing the viewer, at the same location, same head size and same facial features. Keep the original torso proportions and coat design. '
                  + ACTIONS[i] + ' Follow both the leg pose and arm pose. The coat hem follows the legs slightly. '
                  'Same full-body size, same canvas framing, entire head and both boots visible. Plain solid pure WHITE background, no ground shadow, no text, no skeleton lines. '
                  'Match the chunky square pixel clusters and flat limited colors in image 1. No smooth painting, gradients or new costume details.')
        graph = motion_identity.workflow(reference_input.name,target.name,f'pixel_anim_{token}/{name}',20261019,768)
        graph['5']['inputs']['prompt']=prompt
        graph['5']['inputs']['negative_prompt']='sprite sheet, collage, multiple characters, new outfit, different hairstyle, missing sword, extra limbs, blurred face, skeleton, text, watermark, floor shadow'
        signature=hashlib.sha256(json.dumps(graph,sort_keys=True).encode()+VERSION.encode()).hexdigest()
        record_path=out/f'{name}.json'
        if record_path.is_file() and json.loads(record_path.read_text(encoding='utf-8')).get('signature')==signature and (out/f'{name}-raw.png').is_file():
            record=json.loads(record_path.read_text(encoding='utf-8'));print('REUSE',name,flush=True)
        else:
            ensure_idle()
            print('GENERATE',name,LABELS[i],flush=True)
            start=time.monotonic()
            (out/f'{name}-workflow.json').write_text(json.dumps(graph,ensure_ascii=False,indent=2),encoding='utf-8')
            response=requests.post(rig.COMFY_URL+'/prompt',json=dict(prompt=graph),timeout=60)
            if not response.ok: raise RuntimeError(response.text[:2000])
            pid=response.json()['prompt_id']
            (out/f'{name}-pending.json').write_text(json.dumps(dict(promptId=pid,signature=signature)),encoding='utf-8')
            history=motion_identity.wait_for_prompt(pid)
            (out/f'{name}-history.json').write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
            raw=Image.open(rig._saved_image(history,'9')).convert('RGBA');raw.save(out/f'{name}-raw.png')
            record=dict(label=LABELS[i],seconds=round(time.monotonic()-start,2),signature=signature,promptId=pid,
                        raw=f'{name}-raw.png',pixel=f'{name}.png',pose=f'{name}-pose.png',workflow=f'{name}-workflow.json')
        raw=Image.open(out/record['raw']).convert('RGBA')
        frame=pixel_export(raw,palette);frame.save(out/record['pixel'])
        record['metrics']=metrics(frame,source,allowed)
        record_path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        records.append(record)
        (out/'results.json').write_text(json.dumps(dict(version=VERSION,recipe='Qwen 2.1 reference + skeleton, 768px edit, fixed original palette, nearest 128px export',frameDurationMs=180,palette=allowed,frames=records),ensure_ascii=False,indent=2),encoding='utf-8')
        preview(out,records,source)
        review_extras(out,[Image.open(out/r['pixel']).convert('RGBA') for r in records],records,source)
        print('DONE',name,record['seconds'],json.dumps(record['metrics']),flush=True)
        # Release the edit-prefix cache between poses on the shared 16GB GPU.
        requests.post(rig.COMFY_URL+'/free',json=dict(unload_models=True,free_memory=True),timeout=30).raise_for_status()
    print('PREVIEW',out/'preview.html',flush=True)


if __name__=='__main__': main()
