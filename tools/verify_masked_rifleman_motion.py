"""Private 40-step masked rifleman idle and suppressed rifle burst."""
import argparse
import html
import json
import math
import shutil
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import av
import numpy as np
from PIL import Image,ImageDraw
from scipy import ndimage
import idle_tool as engine
import image_background
from tools import verify_masked_raider_motion as exporter
from tools import verify_pixel_minimax as executor
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release
from tools.sprite_matte import clean_flat_matte

SOURCE=Path('Z:/Vertex/적/NAI-images_(2026-09-08_16-39-14)_1-of-1/0.2__artist_crimson comics___0.6__artist_dramz__, _0.5__artist_santa (sunflower) s-1239157476.png')
OUT=ROOT/'outputs/masked-rifleman-motion-20261024'
ORIGINAL_REMOVE=image_background.remove_sprite
IDENTITY=(
    'The EXACT SAME single adult masked rifleman from the input illustration, facing SCREEN LEFT in the same '
    'three-quarter side view. Preserve the 2D hand-inked anime/comic contours, flat painted cel shadows and '
    'tan digital-camouflage uniform, dark olive plate carrier, original patches, belt pouches, knee pads, '
    'tan boots and rear radio antenna. Keep the black ballistic helmet with folded twin night-vision tubes, '
    'ear protection and full dark angular face mask with its red lens; the face stays completely concealed. '
    'Keep exactly ONE original black suppressed rifle, stock pressed to the shoulder, muzzle pointing LEFT, '
    'trigger hand on the pistol grip and support hand on the fore-end. Both hands stay attached to these '
    'grip points. Preserve rigid straight suppressor/barrel, weapon length, two original arms and legs. '
    'No new weapon, no exposed face or human eye, no helmet removal, no camera orbit, realistic relighting '
    'or glossy 3D render. The whole character including muzzle and both boots remains visible. ')
ACTIONS={
    'idle':dict(title='조준 대기 · idle',seed=2026102413,padding=30,loop=True,strength='high',frames=24,
        prompt=(
            'An active but controlled combat-ready IDLE LOOP with the existing rifle aimed screen LEFT. '
            'Keep both soles in contact with their original support spots, allowing ankle flexion and '
            'small heel rolls. Animate ONE complete rhythmic whole-body weight-transfer cycle: the '
            'pelvis travels visibly between the two supporting legs; the forward knee bends and the '
            'opposite leg softens, lowering the pelvis, then the opposite weight transfer raises it. '
            'The shoulder line counter-rotates against the hips, the head follows the spine with a '
            'small purposeful tilt, and bent elbows and guard hands follow in smooth rounded paths. '
            'Use VISIBLE 15-25 pixels of combined hip travel and body rise/fall at 768px canvas, '
            'not an almost motionless still with changing textures. Both hands carry the rifle '
            'as a single rigid object following the shoulders; the muzzle stays approximately left '
            'but may trace a small smooth aim correction. Breathing moves the shoulders without inflating '
            'the rigid vest. Small cloth folds and loose straps follow with a delay. The helmet, red lens '
            'and weapon retain their shapes. No walking, foot sliding, shooting, smoke, muzzle flash, '
            'reloading, waving the gun, dramatic head turn or looking at the viewer. '
            'Continuous motion through the loop boundary, matching the opening stance and motion phase.')),
    'attack':dict(title='소총 연사 · 왼쪽',seed=2026102412,padding=30,loop=False,strength='high',frames=24,
        prompt=(
            'Fire ONE short THREE-ROUND BURST from the actual LEFTMOST TIP of the original rifle suppressor '
            'toward SCREEN LEFT. At 0.0-0.5 seconds the knees flex and shoulders lean slightly into the '
            'shouldered rifle. At 0.5-1.2 seconds fire three quick shots with THREE SMALL separate orange '
            'muzzle flashes precisely at the suppressor tip. Each flash exists briefly and vanishes, '
            'no persistent painted fire. Each shot gives a short backward rifle kick into the shoulder '
            'and slight muzzle rise; bent elbows, shoulders and torso visibly absorb the impulse, '
            'then push the rigid rifle back on target. The leading knee bears the forward lean while '
            'the rear boot stays grounded. The body participates naturally rather than only the barrel '
            'shivering. At 1.2-3.0 seconds settle smoothly back into the original aimed ready stance. '
            'Very compact flash, tiny quickly disappearing smoke puff, never a huge fireball, beam or '
            'explosion. Keep the exact two-handed grip and rigid weapon assembly. No reload, magazine '
            'change, running, stepping, victim, new shell casings in front of the face or firing from '
            'the red eye lens. The masked head stays oriented left with no face reveal.'))}



def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')


def generate():
    configure();exporter.prepare()
    assert exporter.digest(SOURCE)==exporter.digest(OUT/'source-original.png')
    save(OUT/'source.json',dict(sourcePath=str(SOURCE),sourceSha256=exporter.digest(SOURCE),
        sourceUnchanged=True,published=False,referenceSha256=exporter.digest(OUT/'reference.png'),
        preparation='Exterior-connected white sticker rim removed in an input copy with 24px transparent border. Original pixels retained elsewhere; original file preserved.'))
    for name,item in ACTIONS.items():
        folder=OUT/name;folder.mkdir(exist_ok=True)
        if (folder/'raw.mp4').exists():continue
        if (folder/'native-v1-pending.json').exists():graph=json.loads((folder/'native-v1-workflow.json').read_text(encoding='utf-8'))
        else:
            ensure_idle();engine.start_comfy();release((8190,8191))
            prepared=engine.prepare_reference_image((OUT/'reference.png').read_bytes(),768,768,item['padding'])
            (folder/'reference-prepared.png').write_bytes(prepared)
            uploaded=engine.upload_image(prepared,'masked-rifleman-'+name+'.png')
            prompt=IDENTITY+item['prompt']+' Fixed camera, constant scale and lighting. Whole rifleman, boots, rifle and compact muzzle flash stay inside the canvas. Flat uniform neutral-grey matte in every arm and leg gap; no floor, ground shadow, scenery, text outside the existing decals or floating decoration.'
            graph=engine.build_workflow(uploaded,prompt,3,768,768,item['seed'],animation_type=name,
                loop=item['loop'],facing='left',flat_background=True,blink_mode='none',motion_strength=item['strength'],
                sampling_mode='quality',workflow_id='standard',subject_type='human')
            graph['10']['inputs']['steps']=40
            if name=='idle':
                graph['6']['inputs']['prompt']=graph['6']['inputs']['prompt'].replace(
                    engine.FACING_PROMPTS['left'],
                    'The nose and gaze stay directed screen LEFT with the same three-quarter side camera. Allow natural shoulder and pelvis counterrotation, spinal movement, head tilt and ankle flexion. Do not freeze the torso or hips into their opening orientation.').replace(
                    'The opening character size, screen placement, head-to-body proportions, costume, equipment, linework and painted shading are retained.',
                    'Retain overall character scale, proportions, costume, equipment and the original ink-and-cel shading. The pelvis, chest, head and hands may translate and rotate naturally within the fixed camera during weight transfer.')
            graph['6']['inputs']['prompt']=graph['6']['inputs']['prompt'].replace(
                'The original subject scale, composition, silhouette, component proportions, linework and painted shading are retained.',
                'Retain the original component designs, solid proportions, linework, painted shading and camera scale. The articulated silhouette and ride height may change naturally as the existing mechanical joints move.')
            graph['15']['inputs'].pop('audio',None);graph.pop('14',None);graph.pop('5',None)
            graph['16']['inputs']['filename_prefix']='masked_rifleman_20261024/'+name
            save(folder/'settings.json',dict(animationType=name,subjectType='human',seed=item['seed'],width=768,height=768,
                duration=3,fps=24,steps=40,loop=item['loop'],motionPadding=item['padding'],motionStrength=item['strength'],
                referenceOffsetX=0,facing='left',workflowId='standard',prompt=prompt,actualPrompt=graph['6']['inputs']['prompt'],
                sourceSha256=exporter.digest(SOURCE),referenceSha256=exporter.digest(OUT/'reference.png'),published=False))
        executor.OUT=folder;history=executor.execute(graph,engine.COMFY_URL,'native-v1')
        shutil.copyfile(engine.find_saved_video(history),folder/'raw.mp4')
        raw_review(name);print('RIFLEMAN_VIDEO_READY',name,flush=True)
    ensure_idle();release((8189,))


def raw_review(name):
    with av.open(str(OUT/name/'raw.mp4')) as v:frames=[f.to_image().convert('RGB') for f in v.decode(video=0)]
    contact=Image.new('RGB',(1600,960));draw=ImageDraw.Draw(contact)
    for n,i in enumerate(np.linspace(0,len(frames)-1,15).round().astype(int)):
        contact.paste(frames[i].resize((320,320)),(n%5*320,n//5*320));draw.text((n%5*320+8,n//5*320+8),str(i),fill='red')
    contact.save(OUT/name/'review-raw.webp',quality=95)


def cut_rifleman(image):
    cut=ORIGINAL_REMOVE(image)
    rgb=np.asarray(image.convert('RGB'),dtype=float);rgba=np.array(cut)
    r,g,b=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2];yy,xx=np.indices(r.shape)
    # Preserve the generated flash around the left-pointing muzzle only.
    # The red mask lens lies outside the recovery region.
    roi=(xx<320)&(yy>80)&(yy<320)
    warm=(r>160)&(g>85)&(r-b>35)&(g-b>12)
    white=(rgb.min(2)>190)&(np.ptp(rgb,axis=2)<55)
    support=ndimage.binary_propagation(warm&roi,mask=(warm|white)&roi)
    border=np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1]));bg=np.median(border,axis=0)
    alpha=np.clip(np.maximum(((rgb-bg)/np.maximum(255-bg,1)).max(2),((bg-rgb)/np.maximum(bg,1)).max(2)),0,1)
    recover=support&(rgba[:,:,3]<220)
    unmix=np.clip((rgb-bg*(1-alpha[:,:,None]))/np.maximum(alpha[:,:,None],.02),0,255)
    rgba[recover,:3]=np.rint(unmix[recover]).astype('uint8')
    rgba[recover,3]=np.maximum(rgba[recover,3],np.rint(alpha[recover]*255).astype('uint8'))
    cleaned,_=clean_flat_matte(Image.fromarray(rgba),tolerance=10,radius=2)
    return cleaned



def configure():
    exporter.OUT=OUT;exporter.SOURCE=SOURCE;exporter.ACTIONS=ACTIONS;exporter.build=build


def export(only=None):
    configure()
    if (OUT/'idle/raw.mp4').exists() and not (OUT/'idle/selection.json').exists():save(OUT/'idle/selection.json',dict(start=0,end=71,note='Repeated last reference omitted.'))
    image_background.remove_sprite=cut_rifleman
    try:exporter.export(only)
    finally:image_background.remove_sprite=ORIGINAL_REMOVE
    if all((OUT/name/'frames.json').exists() for name in ACTIONS):
        exporter.game();full_sheets();matte_review();build()


def full_sheets():
    for name in ACTIONS:
        folder=OUT/name;meta=json.loads((folder/'frames.json').read_text(encoding='utf-8'))
        indices=meta['previewSourceIndices'];cols=8;rows=math.ceil(len(indices)/cols)
        sheet=Image.new('RGBA',(cols*768,rows*768))
        for n,i in enumerate(indices):sheet.paste(Image.open(folder/'all-frames'/f'frame-{i:03d}.png').convert('RGBA'),(n%cols*768,n//cols*768))
        sheet.save(folder/'native-sheet.png')
        save(folder/'native-frames.json',dict(frameWidth=768,frameHeight=768,columns=cols,rows=rows,
            frameCount=len(indices),sourceIndices=indices,durationMs=meta['previewDurationMs'],sourceFPS=24,
            loop=ACTIONS[name]['loop'],anchor=[384,384],note='All forward displayed native frames. No pose stabilisation, reverse playback or frame interpolation.'))


def matte_review():
    for name in ACTIONS:
        meta=json.loads((OUT/name/'frames.json').read_text(encoding='utf-8'));indices=meta['previewSourceIndices']
        samples=[17,31,indices[-1]] if name=='attack' else [indices[0],18,54]
        canvas=Image.new('RGB',(1536,1024));draw=ImageDraw.Draw(canvas)
        for col,i in enumerate(samples):
            im=Image.open(OUT/name/'all-frames'/f'frame-{i:03d}.png').convert('RGBA')
            for row,color in enumerate(['#142436','#fff4dc']):
                bg=Image.new('RGBA',im.size,color);bg.alpha_composite(im)
                canvas.paste(bg.resize((512,512)).convert('RGB'),(col*512,row*512));draw.text((col*512+8,row*512+8),str(i),fill='red')
        canvas.save(OUT/name/'matte-review.jpg',quality=96)


def build():
    OUT.mkdir(exist_ok=True);cards=[]
    for name,item in ACTIONS.items():
        folder=OUT/name
        prefix='game-' if (folder/'game-animation.webp').exists() else ''
        if not (folder/(prefix+'animation.webp')).exists():continue
        review=json.loads((folder/'review.json').read_text(encoding='utf-8')) if (folder/'review.json').exists() else {}
        cards.append(f'<article><h2>{item["title"]}</h2><p>{html.escape(review.get("note","시각 검토 전입니다."))}</p><img src="{name}/{prefix}animation.webp" alt="{item["title"]}"><p><a href="{name}/{prefix}animation.gif">GIF</a> · <a href="{name}/native-sheet.png">전체 프레임 PNG 시트</a> · <a href="{name}/native-frames.json">프레임 시간</a> · <a href="{name}/settings.json">프롬프트·설정</a></p></article>')
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>소총병 · idle / 사격</title><style>:root{--matte:#142436}body{background:#1b2230;color:#eee;font:16px/1.65 system-ui;margin:24px}main{display:flex;gap:20px;flex-wrap:wrap}article{width:512px;max-width:100%}img{width:100%;background:var(--matte)}a{color:#c9c0ff}button{padding:8px 14px;margin-right:8px}</style><h1>소총병 · 조준 대기와 점사</h1><p>원화의 흰 스티커 테두리를 입력용 사본에서 정리한 뒤 MiniMax 영상으로 생성했습니다. 원본 파일은 유지했습니다. 두 동작 모두 768px·24FPS·40스텝입니다.</p><p>왼쪽 조준 대기와 짧은 소총 점사입니다. 장비·위장 무늬·총기 세부는 프레임마다 조금씩 달라질 수 있습니다. 원본 이미지는 그대로 보관했습니다. PNG/WebP는 반투명 경계를 유지하며 GIF는 이진 투명도만 지원합니다.</p><button onclick="document.documentElement.style.setProperty('--matte','#142436')">어둡게</button><button onclick="document.documentElement.style.setProperty('--matte','#fff4dc')">밝게</button><button onclick="document.documentElement.style.setProperty('--matte','#226b54')">초록</button><p><a href="masked-rifleman-handoff.zip">GIF·전체 PNG 시트·원본 영상 ZIP</a></p><main>'''+''.join(cards)+'''</main><p><a href="reference.png">정리한 입력</a> · <a href="idle/matte-review.jpg">idle 배경 비교</a> · <a href="attack/matte-review.jpg">공격 배경 비교</a></p></html>'''
    (OUT/'preview.html').write_text(page,encoding='utf-8')


def check():
    assert exporter.digest(SOURCE)==exporter.digest(OUT/'source-original.png');records={}
    for name in ACTIONS:
        folder=OUT/name;meta=json.loads((folder/'frames.json').read_text(encoding='utf-8'))
        graph=json.loads((folder/'native-v1-workflow.json').read_text(encoding='utf-8'));assert graph['10']['inputs']['steps']==40
        native=json.loads((folder/'native-frames.json').read_text(encoding='utf-8'))
        sheet=Image.open(folder/'native-sheet.png').convert('RGBA');assert max(sheet.size)<=8192
        for n,i in enumerate(native['sourceIndices']):
            original=np.asarray(Image.open(folder/'all-frames'/f'frame-{i:03d}.png').convert('RGBA'))
            cell=np.asarray(sheet.crop((n%8*768,n//8*768,(n%8+1)*768,(n//8+1)*768)))
            assert np.array_equal(original,cell)
        with Image.open(folder/'game-animation.gif') as gif:
            assert gif.n_frames==len(meta['previewSourceIndices']);total=0
            for i in range(gif.n_frames):gif.seek(i);total+=gif.info['duration']
            assert abs(total-sum(meta['previewDurationMs']))<=10
        records[name]=dict(sourceFrames=meta['sourceFrames'],exportedFrames=native['frameCount'],durationMs=total,
            edgeContactFrames=[x['frame'] for x in meta['diagnostics'] if x['edgeContact']],
            review=json.loads((folder/'review.json').read_text(encoding='utf-8')) if (folder/'review.json').exists() else 'pending')
    save(OUT/'validation.json',dict(fileChecksPassed=True,actualSteps=40,sourceUnchanged=True,websiteUnchanged=True,userApproval='pending',cases=records))
    (OUT/'README.txt').write_text('Masked rifleman idle and rifle burst attack\n\nNative MiniMax 40 steps, 768px, 24FPS, original videos preserved.\nIdle closing duplicate is omitted. Attack GIF repeats for preview only.\nThe attack requests a short three-round burst; actual generated shot timing is documented in review.json.\nUse native-sheet.png (8 columns, 768px cells) and native-frames.json for all displayed native frames.\nIndividual PNGs: frames/*.png in each action folder.\nSame drawing scale and common presentation crop for both motions.\nNo frame interpolation or reversed poses.\nInput exterior white sticker rim removed with alpha extraction in a copy. Original image preserved.\nThin barrel, camouflage, hands and gear can change across generated frames; see review.json.\n',encoding='utf-8')
    with zipfile.ZipFile(OUT/'masked-rifleman-handoff.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ['source-original.png','source.json','reference.png','preview.html','validation.json','README.txt','game-registration.json']:z.write(OUT/name,name)
        for action in ACTIONS:
            folder=OUT/action;native=json.loads((folder/'native-frames.json').read_text(encoding='utf-8'))
            for name in ['game-animation.gif','game-animation.webp','native-sheet.png','native-frames.json','settings.json','raw.mp4','reference-prepared.png','review-raw.webp','matte-review.jpg','review.json','shot-diagnostics.json','motion-diagnostics.json']:
                if (folder/name).exists():z.write(folder/name,action+'/'+name)
            for index in native['sourceIndices']:
                p=folder/'all-frames'/f'frame-{index:03d}.png';z.write(p,action+'/frames/'+p.name)
    with zipfile.ZipFile(OUT/'masked-rifleman-handoff.zip') as z:assert z.testzip() is None
    build();print('RIFLEMAN_HANDOFF_VALIDATED',records,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['generate','export','idle-export','build','check','all']);stage=parser.parse_args().stage
    if stage=='all':generate();export();check()
    elif stage=='idle-export':export('idle')
    else:globals()[stage]()
