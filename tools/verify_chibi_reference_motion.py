"""Resumable motion test for the previously reviewed reference-based chibi."""
import argparse
import hashlib
import html
import json
import shutil
import sys
import zipfile
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import av
import numpy as np
from PIL import Image, ImageDraw
import idle_tool as engine
import image_background
import rigging_engine as rig
from tools import verify_pixel_minimax as executor
from tools import verify_chibi_illustration_examples as exporter
from tools.verify_pixel_female_combat import release
from tools.verify_rpg_sprite_styles import ensure_idle

OUT = ROOT / 'outputs/chibi-reference-motion-20261023'
SOURCE = ROOT / 'outputs/chibi-actual-reference-20261020/direct060/reference.png'
CHARACTER = 'original-reference-chibi-cartographer-20261023'
IDENTITY = (
    'The EXACT SAME single chibi female cartographer from the supplied image: short plum-brown bob, '
    'amber eyes, small brass triangular hair clip, white blouse, tan brown waistcoat, moss green cape '
    'with dark teal lining, purple trousers, brown boots, brown leather satchels, gold star collar brooch '
    'and round brass compass. Preserve the original compact large-head short-body proportions, '
    'face, delicate anime linework, painted texture and colors. ONE short golden star-tipped wand '
    'stays rigid and attached to the same hand. No sword, new armor or new accessories. '
)
ACTIONS = {
    'run': dict(title='오른쪽 달리기', frames=24, loop=True, padding=30,
        speed=1., trim=False, strength='high', effect='none', seed=2026102301,
        pose='A right-facing side-profile RUNNING pose, nose and whole body aimed to SCREEN RIGHT. '
        'One knee forward, the trailing lower leg folded back, torso leaning slightly forward. '
        'The near hand holds the original short star wand close to the hip; empty far arm bent to balance. '
        'Both boots separated, cape trailing to screen left. Show ONE full body with generous margins.',
        prompt='Run continuously IN PLACE toward SCREEN RIGHT for two or three energetic running strides. '
        'Already running at the first frame and still running at the last. Knees drive forward and the '
        'trailing heel folds back, alternating feet pass under the hip; include a brief airborne phase. '
        'Legs move forward/back along screen X, never spread sideways toward the camera. '
        'The empty arm pumps opposite the legs and shoulders counterrotate; wand hand stays near the hip. '
        'The short cape and satchels swing with delayed secondary motion. Keep the hip centered, '
        'nose right, same ground height and body scale. No idle pause, turn, skating or walking. '),
    'attack': dict(title='오른쪽 별봉 공격', frames=24, loop=False, padding=40,
        speed=1., trim=False, strength='high', effect='none', seed=2026102302,
        pose='A compact combat-ready stance facing SCREEN RIGHT, front boot forward and knees softly bent. '
        'Her near hand holds the SAME short star wand raised near the shoulder, star tip points up and right. '
        'The empty hand balances near the chest. Chest lifted, straight firm spine, both boots grounded. '
        'Show one whole body and the entire original short star wand, generous margins.',
        prompt='Perform ONE crisp wand attack toward SCREEN RIGHT. From the loaded stance, briefly bend '
        'the knees then push off the rear foot, stamp the leading boot and rotate hips and shoulders '
        'together. The wand arm drives the original rigid short star wand sharply forward-right in '
        'ONE decisive thrust, with the empty arm counterbalancing behind. The star tip reaches the '
        'space in front of her at chest height. A few tiny golden sparks appear at the star tip only '
        'at the instant of impact and vanish immediately; no beam, projectile or large explosion. '
        'Hold the balanced forward finish briefly, then recover to the opening stance. Cape and '
        'satchels lag and settle. One attack only; no repeated waving, spin, waist bow or extra weapon. '),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / 'accepted-source.png'
    if not target.exists():
        shutil.copyfile(SOURCE, target)
    assert digest(target) == digest(SOURCE)
    save(OUT / 'source.json', dict(path=str(SOURCE.relative_to(ROOT)), sha256=digest(SOURCE),
        originalCharacter=True, pixelOutput=False, published=False))
    for name in ACTIONS:
        (OUT / name).mkdir(exist_ok=True)


def references():
    prepare()
    for name, item in ACTIONS.items():
        folder = OUT / name
        if (folder / 'reference.png').exists():
            continue
        ensure_idle()
        rig.start_comfy()
        release((8189, 8191))
        im = Image.open(SOURCE).convert('RGBA')
        im = im.crop(im.getchannel('A').getbbox())
        im.thumbnail((640, 640), Image.Resampling.LANCZOS)
        canvas = Image.new('RGB', (768, 768), 'white')
        canvas.paste(im, ((768-im.width)//2, (768-im.height)//2), im)
        input_name = 'chibi_reference_motion_20261023_' + name + '.png'
        canvas.save(rig.INPUT_ROOT / input_name)
        canvas.save(folder / 'pose-input.png')
        graph = rig.qwen21_workflow(input_name, 'chibi_reference_motion/' + name, 768, 20, item['seed']-10)
        graph['6']['inputs'].update(device='cpu', dtype='default')
        graph['5']['inputs']['prompt'] = (
            'Edit ONLY the viewing direction and action pose of image 1. ' + IDENTITY + item['pose'] +
            ' Keep the entire head, cape, wand and both boots inside the canvas. '
            'Uniform pure WHITE background, no floor, shadow, rays, panels, text or other characters.')
        graph['5']['inputs']['negative_prompt'] = (
            'front view, facing left, tall body, long legs, pixel art, 3d render, different outfit, '
            'sword, extra wand, duplicate character, extra limbs, cropped, scenery, shadow, text')
        executor.OUT = folder
        history = executor.execute(graph, rig.COMFY_URL, 'pose-v1')
        raw = Image.open(rig._saved_image(history, '9')).convert('RGBA')
        raw.save(folder / 'reference-raw.png')
        image_background.remove_sprite(raw).save(folder / 'reference.png')
        print('POSE_READY', name, flush=True)
    release((8190,))
    build()


def settings(action):
    item = ACTIONS[action]
    data = dict(characterId=CHARACTER, animationType=action, width=768, height=768,
        duration=3, frameCount=item['frames'], seed=item['seed'], prompt=IDENTITY+item['prompt'],
        loop=item['loop'], motionSpeed=item['speed'], trimAction=item['trim'],
        motionStrength=item['strength'], motionPadding=item['padding'], workflowId='standard',
        samplingMode='quality', facing='right', pixelOutput=False, combatEffect='none',
        effectStrength='low', effectDescription='', removeBackground=True, backgroundRemoval='ai',
        optimizeLoop=False, stabilize=False, subjectType='human', blinkMode='none',
        negativeEnabled=False, referenceSha256=digest(OUT/action/'reference.png'))
    graph_path=OUT/action/'native-v1-workflow.json'
    if graph_path.exists():
        graph=json.loads(graph_path.read_text(encoding='utf-8'))
        data['actualPrompt']=graph['6']['inputs']['prompt']
    return data


def motion():
    prepare()
    for name, item in ACTIONS.items():
        folder = OUT / name
        if (folder / 'raw.mp4').exists():
            continue
        pending = folder / 'native-v1-pending.json'
        if pending.exists():
            # Retain the exact uploaded filename and graph when resuming a job.
            engine.start_comfy()
            graph = json.loads((folder/'native-v1-workflow.json').read_text(encoding='utf-8'))
            executor.OUT = folder
            history = executor.execute(graph, engine.COMFY_URL, 'native-v1')
            shutil.copyfile(engine.find_saved_video(history), folder/'raw.mp4')
            release((8189,))
            export(name)
            build()
            continue
        ensure_idle()
        engine.start_comfy()
        release((8190, 8191))
        prepared = engine.prepare_reference_image((folder/'reference.png').read_bytes(), 768, 768, item['padding'])
        (folder/'reference_prepared.png').write_bytes(prepared)
        uploaded = engine.upload_image(prepared, 'chibi-reference-motion-'+name+'.png')
        prompt = (IDENTITY + item['prompt'] + ' Fixed side-view camera, no pan, zoom or cut. '
            'All body parts, wand and cape remain inside the image. Uniform medium grey background '
            'including spaces between limbs. No floor, cast shadows, scenery or text. No style change.')
        graph = engine.build_workflow(uploaded, prompt, 3, 768, 768, item['seed'],
            animation_type=name, loop=item['loop'], facing='right', flat_background=True,
            blink_mode='none', motion_strength=item['strength'], sampling_mode='quality', workflow_id='standard')
        graph['15']['inputs'].pop('audio', None)
        graph.pop('14', None)
        graph.pop('5', None)
        graph['16']['inputs']['filename_prefix'] = 'chibi_reference_motion_20261023/' + name
        save(folder/'settings.json', {**settings(name), 'actualPrompt':graph['6']['inputs']['prompt']})
        executor.OUT = folder
        history = executor.execute(graph, engine.COMFY_URL, 'native-v1')
        shutil.copyfile(engine.find_saved_video(history), folder/'raw.mp4')
        release((8189,))
        print('VIDEO_READY', name, flush=True)
        export(name)
        build()


def export(only=None):
    exporter.OUT = OUT
    exporter.CHARACTER = CHARACTER
    exporter.ACTIONS = ACTIONS
    exporter.settings = settings
    exporter.export(only)
    build()


def select_attack():
    """Keep the first complete strike; preserve the generated two-strike clip."""
    import math
    import sprite_gif
    import sprite_loop
    folder=OUT/'attack'
    for file in ('animation.webp','animation.gif','sheet.png','frames.json','contact.webp','motion.mp4'):
        full=folder/('full-'+file)
        if not full.exists():
            shutil.copyfile(folder/file,full)
    original=json.loads((folder/'full-frames.json').read_text(encoding='utf-8'))
    indices=list(range(34))  # 0..33: anticipation, one strike, recovery; second windup starts at 34.
    # Preserve the tiny golden sparks from the actual video, outside the semantic
    # character matte. Infer minimum opacity against its verified neutral key;
    # no new effect graphics or colors are drawn.
    spark_folder=folder/'spark-frames'
    spark_folder.mkdir(exist_ok=True)
    counts=[]
    with av.open(str(folder/'raw.mp4')) as clip:
        for i,frame in enumerate(clip.decode(video=0)):
            if i>33:break
            rgb=np.asarray(frame.to_image().convert('RGB'),dtype=float)
            rgba=np.array(Image.open(folder/'all-frames'/f'frame-{i:03d}.png').convert('RGBA'))
            border=np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1]))
            bg=np.median(border,axis=0)
            assert np.ptp(bg)<12 and np.mean(np.max(abs(border-bg),axis=1)<12)>.98
            r,g,b=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2]
            warm=(r>155)&(r>g)&(r-g<80)&(r-b>22)&(g-b>8)&(rgba[:,:,3]<192)
            alpha=np.clip(np.maximum(((rgb-bg)/np.maximum(255-bg,1)).max(2),((bg-rgb)/np.maximum(bg,1)).max(2)),0,1)
            recovered=np.clip((rgb-bg*(1-alpha[:,:,None]))/np.maximum(alpha[:,:,None],.01),0,255)
            rgba[warm,:3]=np.rint(recovered[warm]).astype('uint8')
            rgba[warm,3]=np.maximum(rgba[warm,3],np.rint(alpha[warm]*255).astype('uint8'))
            counts.append(int(warm.sum()))
            Image.fromarray(rgba).save(spark_folder/f'frame-{i:03d}.png')
    frames=[Image.open(spark_folder/f'frame-{i:03d}.png').convert('RGBA') for i in indices]
    save(folder/'spark-matte.json',dict(method='original gold-colored video pixels, neutral-key opacity recovery outside semantic matte',
        originalFramesUnchanged=True,recoveredPixels=counts,generatedEffectPixelsAdded=False))
    ticks=[round(i*1000/24) for i in range(len(indices)+1)]
    times=[b-a for a,b in zip(ticks,ticks[1:])]
    boxes=[im.getchannel('A').getbbox() for im in frames]
    left,top,right,bottom=min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)
    side=math.ceil(max(right-left,bottom-top)*1.12)
    x,y=math.floor((left+right-side)/2),math.floor((top+bottom-side)/2)
    crop=(x,y,x+side,y+side)
    preview=[im.crop(crop).resize((512,512),Image.Resampling.LANCZOS) for im in frames]
    preview[0].save(folder/'animation.webp',save_all=True,append_images=preview[1:],duration=times,loop=0,lossless=True)
    data,gifmeta=sprite_gif.encode(preview,times)
    (folder/'animation.gif').write_bytes(data)
    chosen=list(map(int,sprite_loop.sample_indices(len(indices),24,False)))
    sheet=Image.new('RGBA',(768*4,768*6))
    contact=Image.new('RGB',(384*4,384*6),'#263247')
    draw=ImageDraw.Draw(contact)
    for n,index in enumerate(chosen):
        frames[index].save(folder/f'frame-{n:02d}.png')
        sheet.paste(frames[index],(n%4*768,n//4*768))
        small=preview[index].resize((384,384),Image.Resampling.LANCZOS)
        contact.paste(small,(n%4*384,n//4*384),small)
        draw.text((n%4*384+8,n//4*384+8),f'raw {index}',fill='white')
    sheet.save(folder/'sheet.png')
    contact.save(folder/'contact.webp')
    bounds=[ticks[i] for i in chosen]+[ticks[-1]]
    timing={**original['timing'],'sourceIndices':indices,'durationMs':times,'sourceStart':0,'sourceEnd':33,
        'outputFrames':34,'totalMs':sum(times),'method':'manually selected first full attack, original speed'}
    save(folder/'frames.json',{**original,'sourceIndices':chosen,'durationMs':[b-a for a,b in zip(bounds,bounds[1:])],
        'previewTimingMs':times,'previewCropBounds':crop,'gif':gifmeta,'timing':timing,
        'frameSourceDir':'spark-frames',
        'selectionNote':'Original generation repeats the attack. Export uses only original frames 0..33, one complete strike.'})
    current=json.loads((folder/'settings.json').read_text(encoding='utf-8'))
    save(folder/'settings.json',{**current,'selectedSourceRange':[0,33],'frameCount':24,'exportDurationMs':sum(times)})
    with av.open(str(folder/'raw.mp4')) as clip:
        native=[f for i,f in enumerate(clip.decode(video=0)) if i<=33]
    with av.open(str(folder/'motion.mp4'),'w') as output:
        stream=output.add_stream('libx264',rate=24)
        stream.width=stream.height=768
        stream.pix_fmt='yuv420p'
        for i,frame in enumerate(native):
            selected=av.VideoFrame.from_image(frame.to_image())
            selected.pts=i
            selected.time_base=Fraction(1,24)
            for packet in stream.encode(selected):output.mux(packet)
        for packet in stream.encode():output.mux(packet)
    build()
    print('SELECTED_ATTACK',34,'frames',sum(times),'ms',flush=True)


def build():
    cards = []
    for name, item in ACTIONS.items():
        folder = OUT/name
        if not (folder/'reference.png').exists():
            continue
        review = json.loads((folder/'review.json').read_text(encoding='utf-8')) if (folder/'review.json').exists() else {}
        animation = f'<img src="{name}/animation.webp" alt="{item["title"]} 애니메이션">' if (folder/'animation.webp').exists() else '<p>영상 생성 중</p>'
        links = ''.join(f'<a href="{name}/{file}">{label}</a> · ' for file,label in [
            ('animation.gif','GIF'),('sheet.png','PNG 시트'),('frames.json','프레임 시간'),
            ('contact.webp','프레임 비교'),('motion.mp4','정리한 영상'),('raw.mp4','생성 원본 영상'),('settings.json','생성 설정')]
            if (folder/file).exists())
        cards.append(f'<article><h2>{item["title"]}</h2><p>{html.escape(review.get("note","시각 검토 전 시험 결과입니다."))}</p>'
            f'<div class="pair"><figure><img src="{name}/reference.png" alt="오른쪽 동작 입력"><figcaption>방향·자세 조정 입력</figcaption></figure>'
            f'<figure>{animation}<figcaption>영상 생성 → 투명 배경 후처리</figcaption></figure></div><p>{links}</p></article>')
    page = ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        '<title>레퍼런스 치비 동작 시험</title><style>body{margin:24px;background:#171e2b;color:#eef0f6;font:15px/1.6 system-ui}'
        'main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,680px),1fr));gap:20px}'
        'article{background:#263247;border-radius:16px;padding:20px;min-width:0}.pair{display:flex;gap:12px}figure{margin:0;width:50%}'
        'img{width:100%;background:repeating-conic-gradient(#263247 0 25%,#43516a 0 50%) 0/24px 24px}a{color:#c9c0ff}'
        '.source{max-height:360px;width:auto;max-width:100%}body.light img{background:#eee}button{padding:8px 16px}</style>'
        '<h1>레퍼런스 치비 · 달리기와 별봉 공격</h1><p>앞서 비교한 원화 직접 변형·그림체 0.6 후보를 사용했습니다. '
        '동일한 원화 픽셀을 입력해 오른쪽 자세를 조정한 뒤 MiniMax로 동작을 생성했습니다. 별봉과 의상을 유지하며 새 검은 추가하지 않았습니다.</p>'
        '<p>일러스트 치비 시험이며 도트 변환은 하지 않았습니다. 원본 영상과 투명 PNG 시트·GIF를 함께 보관합니다. '
        '자세 조정 단계에서도 얼굴·의상·소품이 재해석될 수 있고 달리기 루프의 이음새는 확인이 필요합니다.</p>'
        '<button onclick="document.body.classList.toggle(\'light\')">밝은 / 어두운 배경</button> '
        '<a href="accepted-source.png">사용한 치비 원화</a><br><img class="source" src="accepted-source.png" alt="선택한 원화"><main>'
        + ''.join(cards) + '</main></html>')
    (OUT/'preview.html').write_text(page, encoding='utf-8')


def check():
    assert digest(SOURCE) == digest(OUT/'accepted-source.png')
    result = {}
    for name in ACTIONS:
        folder = OUT/name
        history = json.loads((folder/'native-v1-history.json').read_text(encoding='utf-8'))
        assert history['status']['status_str'] == 'success'
        meta = json.loads((folder/'frames.json').read_text(encoding='utf-8'))
        saved_settings=json.loads((folder/'settings.json').read_text(encoding='utf-8'))
        graph=json.loads((folder/'native-v1-workflow.json').read_text(encoding='utf-8'))
        saved_settings['actualPrompt']=graph['6']['inputs']['prompt']
        save(folder/'settings.json',saved_settings)
        with av.open(str(folder/'raw.mp4')) as video:
            stream=video.streams.video[0]
            assert (stream.width,stream.height)==(768,768)
            assert sum(1 for _ in video.decode(video=0)) == 73
        sheet=Image.open(folder/'sheet.png').convert('RGBA')
        assert len(meta['sourceIndices'])==24
        for i,index in enumerate(meta['sourceIndices']):
            frame=Image.open(folder/meta.get('frameSourceDir','all-frames')/f'frame-{index:03d}.png').convert('RGBA')
            assert frame.getchannel('A').getextrema()==(0,255)
            assert np.array_equal(np.asarray(frame),np.asarray(sheet.crop((i%4*768,i//4*768,(i%4+1)*768,(i//4+1)*768))))
        with Image.open(folder/'animation.gif') as gif:
            assert gif.size==(512,512) and gif.n_frames==len(meta['previewTimingMs']) and gif.info.get('loop')==0
            duration=0
            for i in range(gif.n_frames):
                gif.seek(i)
                duration+=gif.info['duration']
            assert abs(duration-sum(meta['previewTimingMs']))<=10
        with av.open(str(folder/'motion.mp4')) as video:
            assert float(video.streams.video[0].average_rate)==24
            assert sum(1 for _ in video.decode(video=0))==len(meta['previewTimingMs'])
        result[name]=dict(nativeFrames=73,sheetFrames=24,edgeContact=sum(x['edgeContact'] for x in meta['diagnostics']),
            exportedAnimationFrames=len(meta['previewTimingMs']),exportDurationMs=sum(meta['previewTimingMs']),
            videoSha256=digest(folder/'raw.mp4'),gifBytes=(folder/'animation.gif').stat().st_size)
    from html.parser import HTMLParser
    class Links(HTMLParser):
        def handle_starttag(self,tag,attrs):
            for key,value in attrs:
                if key in ('src','href'):
                    assert (OUT/value).is_file(),value
    Links().feed((OUT/'preview.html').read_text(encoding='utf-8'))
    save(OUT/'validation.json',dict(passed=True,sourceUnchanged=True,published=False,cases=result))
    (OUT/'README.txt').write_text(
        'Reference-based original chibi motion tests\n'
        'run: 73 frames, 3042 ms, 24-cell PNG sheet.\n'
        'attack: first complete strike only, original frames 0..33, 1417 ms, 24-cell PNG sheet.\n'
        'PNG cells: 768 x 768, 4 columns x 6 rows. Use frames.json for cell durations.\n'
        'animation.webp / animation.gif are 512px fixed-crop previews. GIF timing uses 10ms units.\n'
        'motion.mp4 is the selected playback; raw.mp4 preserves the full AI generation.\n'
        'The raw attack contains two strikes; only the first is used in the animation and sheet.\n'
        'Golden sparks are recovered from actual generated video pixels, not drawn afterward.\n'
        'Face/wardrobe/accessory details can drift; attack remains a near-front three-quarter view.\n'
        'Browser playback automation was unavailable because local file URLs were blocked.\n'
        'Source videos, decoded frames, transparency, GIF durations and sheet cells were checked.\n',encoding='utf-8')
    with zipfile.ZipFile(OUT/'chibi-motion-handoff.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ACTIONS:
            for file in ('animation.gif','animation.webp','sheet.png','frames.json','reference.png','motion.mp4','raw.mp4','settings.json','native-v1-workflow.json','pose-v1-workflow.json'):
                z.write(OUT/name/file,name+'/'+file)
        z.write(OUT/'validation.json','validation.json')
        z.write(OUT/'README.txt','README.txt')
        z.write(OUT/'accepted-source.png','accepted-source.png')
    with zipfile.ZipFile(OUT/'chibi-motion-handoff.zip') as z:
        assert z.testzip() is None
    build()
    print('VALIDATED',result,flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser()
    p.add_argument('stage',choices=['references','motion','export','select_attack','build','check','all'])
    args=p.parse_args()
    if args.stage=='all':
        references();motion();export();select_attack();check()
    else:
        globals()[args.stage]()
