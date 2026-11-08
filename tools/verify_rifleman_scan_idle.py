"""Rifleman idle revision: stationary stance, a small purposeful aim check."""
import argparse
import html
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
from PIL import Image
from scipy import ndimage
import idle_tool as engine
from tools import verify_masked_rifleman_motion as base
from tools import verify_pixel_minimax as executor
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release

OUT=ROOT/'outputs/rifleman-scan-idle-20261024'
PREVIOUS=ROOT/'outputs/masked-rifleman-motion-20261024'
ACTION=dict(title='경계 대기 · 작은 조준 탐색',seed=2026102414,padding=30,loop=True,strength='normal',frames=24)
ORIGINAL_CUT=base.cut_rifleman
PROMPT=(
    'A quiet tactical SENTRY IDLE of the exact same masked rifleman in the supplied 2D illustration. '
    'He stays in the original LEFT-facing aimed stance and makes ONE small purposeful AIM CHECK. '
    'Both boots, hips and knees remain at their original positions and height throughout. '
    'No repeated knee bends, squats, body bobbing, stepping or exercise. The helmet stays at nearly '
    'the same height. Make the life come from the arms and aim, not from lifting the body. '
    'The stock stays seated against the shoulder while the elbows smoothly articulate to tilt '
    'the same rigid rifle a FEW DEGREES down-left, then a little up-left, then return to its '
    'original line of aim. Muzzle travel only about 10-18 pixels on this 768px canvas. '
    'Both hands remain on their original grips; barrel and suppressor stay straight and constant '
    'length. A tiny accompanying head inclination follows the sights; the red mask lens stays '
    'a fixed lens, never a human eye or a weapon. The torso stays almost still with shallow '
    'breathing visible only as a small shoulder adjustment, no chest inflation. '
    'During the middle aim check the existing rifle-mounted rail aiming device emits a very '
    'THIN, DIM RED laser sight toward screen LEFT, aligned with the rifle direction. '
    'A delicate hairline aiming ray with a small red tip, never a thick beam, projectile, flame, '
    'muzzle flash or glowing sword. It originates at the RIFLE rail device near the fore-end, '
    'never at the red mask lens. Keep the whole short visible aiming ray inside the canvas. '
    'The laser is off at the opening and closing reference poses and briefly on during the '
    'small scan. No laser impact surface, target, wall or new scenery. '
    'One unhurried check in three seconds, not rapid gun waving or repeated up/down pumping. '
    'Return smoothly to the original aim and stance to close the loop. '
    'Keep the original black helmet, folded twin night-vision tubes, full black mask and red lens, '
    'tan digital camouflage, olive plate carrier, original patches and pouches, knee pads, boots '
    'and rear radio antenna. Exactly one original suppressed rifle with its original two-handed '
    'grip. Original hand-inked contours and painted cel shadows; no 3D render or photoreal relighting. '
    'Fixed side-view camera and character scale. Uniform neutral medium-grey matte in every '
    'empty gap. No floor shadow, floor, text, smoke, shooting, reload or additional people.')


def save(path,value):base.save(path,value)


def configure():
    base.OUT=OUT; base.ACTIONS={'idle':ACTION};base.build=build;base.cut_rifleman=cut
    base.configure()


def generate():
    configure();OUT.mkdir(exist_ok=True);folder=OUT/'idle';folder.mkdir(exist_ok=True)
    for name in ['source-original.png','reference.png']:
        if not (OUT/name).exists():shutil.copy2(PREVIOUS/name,OUT/name)
    assert base.exporter.digest(base.SOURCE)==base.exporter.digest(OUT/'source-original.png')
    save(OUT/'source.json',dict(sourcePath=str(base.SOURCE),sourceSha256=base.exporter.digest(base.SOURCE),
        sourceUnchanged=True,referenceSha256=base.exporter.digest(OUT/'reference.png'),
        preparation='Same cleaned input pixels as previous rifleman. No new image edit.',published=False))
    if (folder/'raw.mp4').exists():return
    if (folder/'native-v1-pending.json').exists():
        graph=json.loads((folder/'native-v1-workflow.json').read_text(encoding='utf-8'))
    else:
        ensure_idle();engine.start_comfy();release((8190,8191))
        prepared=(PREVIOUS/'idle/reference-prepared.png').read_bytes()
        (folder/'reference-prepared.png').write_bytes(prepared)
        uploaded=engine.upload_image(prepared,'rifleman-small-aim-check.png')
        # Custom action avoids the generic idle's mandatory even breathing rhythm.
        graph=engine.build_workflow(uploaded,PROMPT,3,768,768,ACTION['seed'],animation_type='custom',
            loop=True,facing='preserve',flat_background=True,blink_mode='none',
            motion_strength='normal',sampling_mode='quality',workflow_id='standard')
        graph['10']['inputs']['steps']=40
        text=graph['6']['inputs']['prompt'].replace(engine.FACING_PROMPTS['preserve'],
            'Keep the same LEFT-facing three-quarter view. The head and arms may make small aiming adjustments while hips, knees and feet stay in the same stance. Do not turn toward the viewer.').replace(
            engine.MOTION_PROMPTS['normal'],
            'Restrained, smooth, deliberate elbow and shoulder motion. The lower body stays steady; no body-height oscillation.').replace(
            'The opening character size, screen placement, head-to-body proportions, costume, equipment, linework and painted shading are retained.',
            'Retain overall scale, leg stance, body height, proportions, costume, weapon construction and original drawn shading. Arms may articulate and the rifle may tilt slightly as one rigid object during the aim check.')
        graph['6']['inputs']['prompt']=text
        graph['15']['inputs'].pop('audio',None);graph.pop('14',None);graph.pop('5',None)
        graph['16']['inputs']['filename_prefix']='rifleman_scan_idle_20261024/idle'
        save(folder/'settings.json',dict(animationType='idle',generationPromptType='custom',seed=ACTION['seed'],
            width=768,height=768,duration=3,fps=24,steps=40,loop=True,facing='left',
            motionPadding=30,motionStrength='normal',referenceOffsetX=0,workflowId='standard',
            samplingMode='quality',prompt=PROMPT,actualPrompt=text,
            sourceSha256=base.exporter.digest(base.SOURCE),referenceSha256=base.exporter.digest(OUT/'reference.png'),
            published=False))
    executor.OUT=folder;history=executor.execute(graph,engine.COMFY_URL,'native-v1')
    shutil.copyfile(engine.find_saved_video(history),folder/'raw.mp4')
    base.raw_review('idle');ensure_idle();release((8189,))
    print('SCAN_IDLE_VIDEO_READY',flush=True)


def cut(image):
    rgba=np.array(ORIGINAL_CUT(image));rgb=np.array(image.convert('RGB')).astype(float)
    r,g,b=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2];yy,xx=np.indices(r.shape)
    # Recover only actually generated thin red components left of the rifle.
    red=(r>120)&(r-g>45)&(r-b>40)&(xx<320)&(yy>130)&(yy<330)
    labels,n=ndimage.label(red,structure=np.ones((3,3)))
    recover=np.zeros(red.shape,bool)
    for i in range(1,n+1):
        ys,xs=np.where(labels==i)
        if len(xs)>=4 and len(xs)<2400 and xs.max()-xs.min()>2*(ys.max()-ys.min()+1):recover|=labels==i
    border=np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1]));bg=np.median(border,axis=0)
    alpha=np.clip(np.maximum(((rgb-bg)/np.maximum(255-bg,1)).max(2),((bg-rgb)/np.maximum(bg,1)).max(2)),0,1)
    recover&=rgba[:,:,3]<220
    unmix=np.clip((rgb-bg*(1-alpha[:,:,None]))/np.maximum(alpha[:,:,None],.02),0,255)
    rgba[recover,:3]=np.rint(unmix[recover]).astype('uint8')
    rgba[recover,3]=np.maximum(rgba[recover,3],np.rint(alpha[recover]*255).astype('uint8'))
    return Image.fromarray(rgba)


def export():configure();base.export()


def build():
    OUT.mkdir(exist_ok=True);folder=OUT/'idle'
    note=json.loads((folder/'review.json').read_text(encoding='utf-8')).get('note','') if (folder/'review.json').exists() else '시각 검토 전'
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>소총병 · 경계 대기</title><style>body{background:#1b2230;color:#eee;font:16px/1.65 system-ui;margin:24px}img{width:512px;max-width:100%;background:#142436}a{color:#c9c0ff}</style><h1>소총병 · 작은 조준 탐색</h1><p>하체의 반복적인 높이 변화를 줄이고, 팔·총구 중심의 경계 동작으로 다시 생성했습니다. MiniMax 768px · 24FPS · 40스텝.</p>'''
    page+=f'<p>{html.escape(note)}</p><img src="idle/game-animation.webp" alt="경계 대기"><p><a href="idle/game-animation.gif">GIF</a> · <a href="idle/native-sheet.png">전체 PNG 시트</a> · <a href="idle/native-frames.json">프레임 시간</a> · <a href="rifleman-scan-idle.zip">전체 ZIP</a></p><p><a href="idle/raw.mp4">원본 영상</a> · <a href="idle/matte-review.jpg">배경 비교</a> · <a href="idle/settings.json">설정과 프롬프트</a></p></html>'
    (OUT/'preview.html').write_text(page,encoding='utf-8')


def check():
    configure();base.check()
    source=OUT/'masked-rifleman-handoff.zip';target=OUT/'rifleman-scan-idle.zip'
    (OUT/'README.txt').write_text('Rifleman sentry idle revision\n\nSame source reference and 768px input scale. 40 steps, 24FPS.\n72 forward display frames; duplicate closing anchor omitted.\nGenerated aim-check animation; any laser is generated in the video, not drawn afterwards.\nSee idle/review.json for the observed motion and limits.\nUse idle/native-sheet.png and native-frames.json for all native frames.\nGIF has binary alpha; PNG and WebP preserve soft alpha. Original image and video preserved.\n',encoding='utf-8')
    with zipfile.ZipFile(source) as z,zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as dest:
        for info in z.infolist():dest.writestr(info.filename,(OUT/'README.txt').read_bytes() if info.filename=='README.txt' else z.read(info.filename))
    with zipfile.ZipFile(target) as z:assert z.testzip() is None
    print('SCAN_IDLE_HANDOFF_VALIDATED',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['generate','export','build','check','all']);stage=parser.parse_args().stage
    if stage=='all':generate();export();check()
    else:globals()[stage]()
