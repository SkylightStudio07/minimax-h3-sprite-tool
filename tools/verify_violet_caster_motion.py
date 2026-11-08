"""Private reference-conditioned caster idle and rightward spell release."""
import argparse
import hashlib
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
import image_background
from tools import verify_masked_rifleman_motion as base
from tools import verify_pixel_minimax as executor
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release
from tools.sprite_matte import clean_flat_matte

SOURCE=Path('Z:/Vertex/합류 캐릭터/NAI-images_(2026-10-23_06-18-36)_1-of-1/0.2__artist_crimson comics___0.6__artist_dramz__, _0.5__artist_santa (sunflower) s-1261387617.png')
OUT=ROOT/'outputs/violet-caster-motion-20261024'
ORIGINAL_REMOVE=image_background.remove_sprite
IDENTITY=(
    'The EXACT SAME single adult female spellcaster in the supplied 2D illustration, facing SCREEN RIGHT '
    'in the original three-quarter side view. Preserve the same face and blue eye, long indigo hair '
    'with vivid cyan underside and pink headband, white long sleeves, pale pink long split dress '
    'with royal blue lining, blue gloves, dark ankle boots, black belts and pouches, white respirator '
    'with yellow filter hanging at the waist and small colored vials on the thigh strap. '
    'Her near blue-gloved hand faces right with spread fingers at the original violet circular magic '
    'seal. The opposite arm stays naturally beside the body. Exactly two arms, two hands and two legs. '
    'Keep her fully clothed original design, body proportions and existing equipment. Original '
    'hand-drawn anime contours and flat cel-painted shadows in EVERY frame. No 3D render, realistic '
    'relighting, camera orbit, new weapon or character redesign. All magic is the same violet-blue '
    'swirling energy as the input, and it must actually evolve rather than be a frozen painted decal. ')
ACTIONS={
    'idle':dict(title='마법 유지 대기 · 오른쪽',seed=2026102421,padding=30,loop=True,strength='normal',frames=24,
        prompt=(
            'A restrained magical combat-ready IDLE LOOP. Both boots, pelvis and knees stay in the '
            'same stable stance and at the SAME HEIGHT; no squats, rhythmic body bobbing or repeated '
            'knee bends. She quietly maintains the spell in front of her outstretched right-facing '
            'palm. Give the wrist and fingers one small controlled adjustment, elbow subtly softens '
            'then returns, shoulder follows naturally. Head and gaze stay right. The long indigo '
            'and cyan hair tips and pink-blue skirt tails flow gently to the left in a slow breeze, '
            'with delayed follow-through instead of rigid swaying of the entire picture. The small '
            'violet seal in front of her palm turns slowly and its inner spiral curls circulate '
            'continuously. The larger existing violet ribbons behind her and around the boots '
            'drift softly along their own curves. Keep the effects modest in brightness and size, '
            'not an attack or a screen-filling explosion. The pale cyan oval beneath the boots is '
            'a transparent magical seal, NOT a physical pedestal or scenery. Its outline remains '
            'near its opening position while the violet wisps move. One unhurried maintenance cycle '
            'in three seconds, small movements primarily in hair, cloth, wrist and magical currents. '
            'Return to the supplied pose and effect arrangement at the loop boundary. No steps, '
            'jump, speaking, dramatic face turn or increasing breast/torso volume.')),
    'attack':dict(title='마법 발사 · 오른쪽',seed=2026102422,padding=30,loop=False,strength='high',frames=24,
        prompt=(
            'Perform exactly ONE decisive MAGIC RELEASE toward SCREEN RIGHT, with a readable arm '
            'windup, forceful cast and recovery. At 0.0-0.6 seconds bend the extended elbow to draw '
            'the blue-gloved palm back toward the chest; the violet seal follows the palm and '
            'contracts, gathering its swirling energy. Her shoulders and upper torso turn a little '
            'back as preparation; both boots stay grounded and knees only flex slightly ONCE. '
            'At 0.6-1.2 seconds rotate the shoulders forward and drive the same palm sharply to '
            'SCREEN RIGHT. Release ONE compact violet-blue spiral energy pulse from the palm '
            'seal into the empty space at the right side. A bright brief cyan-violet core and '
            'two curved purple streaks follow its rightward path. Keep the blast smaller than '
            'the character torso and completely inside the 768px canvas; it fades before reaching '
            'the right border. Strong readable arm extension and upper-body follow-through, '
            'not merely a static character with an animated effect. Her free arm counterbalances '
            'near the waist, hair and dress tails flare briefly toward left, then settle. '
            'At 1.2-3.0 seconds the energy pulse disperses and she recovers the original right-facing '
            'guard with the palm seal re-forming. Existing violet wisps around the boots and behind '
            'her visibly stream into the cast then resume a soft swirl; no frozen painted effects. '
            'No second cast, beam held for the whole clip, full spin, running, jump, deep bow, '
            'victim, new object or giant explosion hiding the character. Keep her face, fingers, '
            'hair roots and equipment recognizable throughout.'))}


def save(path,value):base.save(path,value)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def configure():
    base.OUT=OUT;base.SOURCE=SOURCE;base.ACTIONS=ACTIONS;base.build=build
    base.cut_rifleman=cut;base.configure()


def prepare():
    OUT.mkdir(exist_ok=True)
    if not (OUT/'source-original.png').exists():shutil.copy2(SOURCE,OUT/'source-original.png')
    assert digest(SOURCE)==digest(OUT/'source-original.png')
    if not (OUT/'reference.png').exists():
        im=Image.open(SOURCE).convert('RGBA');box=im.getchannel('A').getbbox();assert box
        cropped=im.crop(box);canvas=Image.new('RGBA',(cropped.width+48,cropped.height+48))
        canvas.paste(cropped,(24,24));canvas.save(OUT/'reference.png')
    save(OUT/'source.json',dict(sourcePath=str(SOURCE),sourceSha256=digest(SOURCE),sourceUnchanged=True,
        referenceSha256=digest(OUT/'reference.png'),published=False,
        preparation='Original transparent artwork and original violet effects retained. Alpha bounding-box crop and 24px transparent border only; no repainting or generative reference edit.'))


def generate():
    configure();prepare()
    for name,item in ACTIONS.items():
        folder=OUT/name;folder.mkdir(exist_ok=True)
        if (folder/'raw.mp4').exists():continue
        if (folder/'native-v1-pending.json').exists():graph=json.loads((folder/'native-v1-workflow.json').read_text(encoding='utf-8'))
        else:
            ensure_idle();engine.start_comfy();release((8190,8191))
            prepared=engine.prepare_reference_image((OUT/'reference.png').read_bytes(),768,768,30)
            (folder/'reference-prepared.png').write_bytes(prepared)
            uploaded=engine.upload_image(prepared,'violet-caster-'+name+'.png')
            prompt=IDENTITY+item['prompt']+' Fixed camera and drawing scale. Entire character, boots, hair, magical ribbons and pulse remain visible with empty margins. Uniform flat medium neutral-grey matte in EVERY exposed gap, no floor, scenery or cast shadow. Keep original violet effects distinct from the neutral background.'
            graph=engine.build_workflow(uploaded,prompt,3,768,768,item['seed'],animation_type='custom',
                loop=item['loop'],facing='preserve',flat_background=True,blink_mode='none',
                motion_strength=item['strength'],sampling_mode='quality',workflow_id='standard')
            graph['10']['inputs']['steps']=40
            text=graph['6']['inputs']['prompt'].replace(engine.FACING_PROMPTS['preserve'],
                'The nose and gaze stay SCREEN RIGHT in the same three-quarter view. Allow natural elbow, wrist and shoulder articulation for the spell while keeping the same body orientation. No facing the viewer.')
            if name=='idle':text=text.replace(engine.MOTION_PROMPTS['normal'],
                'Small, smooth, controlled arm and wrist movement with flowing hair, cloth and magical currents. Hips, knees and boots keep their original height without pumping up and down.')
            graph['6']['inputs']['prompt']=text
            graph['15']['inputs'].pop('audio',None);graph.pop('14',None);graph.pop('5',None)
            graph['16']['inputs']['filename_prefix']='violet_caster_20261024/'+name
            save(folder/'settings.json',dict(animationType=name,generationPromptType='custom',seed=item['seed'],
                width=768,height=768,duration=3,fps=24,steps=40,loop=item['loop'],facing='right',motionPadding=30,
                referenceOffsetX=0,motionStrength=item['strength'],workflowId='standard',samplingMode='quality',
                prompt=prompt,actualPrompt=text,sourceSha256=digest(SOURCE),referenceSha256=digest(OUT/'reference.png'),published=False))
        executor.OUT=folder;history=executor.execute(graph,engine.COMFY_URL,'native-v1')
        shutil.copyfile(engine.find_saved_video(history),folder/'raw.mp4')
        base.raw_review(name);print('CASTER_VIDEO_READY',name,flush=True)
    ensure_idle();release((8189,))


def cut(image):
    result=ORIGINAL_REMOVE(image);a=np.array(result);rgb=np.array(image.convert('RGB')).astype(float)
    r,g,b=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2]
    # Keep actually generated violet/cyan magic, including disconnected ribbons.
    # Neutral grey remains governed by the semantic matte, preserving outfit greys.
    violet=(b>90)&(b-g>18)&(b-r>8)
    cyan=(b>140)&(g>120)&(g-r>25)&(b-r>35)
    recover=(violet|cyan)&(a[:,:,3]<220)
    border=np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1]));bg=np.median(border,axis=0)
    alpha=np.clip(np.maximum(((rgb-bg)/np.maximum(255-bg,1)).max(2),((bg-rgb)/np.maximum(bg,1)).max(2)),0,1)
    unmix=np.clip((rgb-bg*(1-alpha[:,:,None]))/np.maximum(alpha[:,:,None],.025),0,255)
    a[recover,:3]=np.rint(unmix[recover]).astype('uint8')
    a[recover,3]=np.maximum(a[recover,3],np.rint(alpha[recover]*255).astype('uint8'))
    return clear_neutral_gaps(Image.fromarray(a),image)


def clear_neutral_gaps(cutout,raw):
    a=np.array(cutout.convert('RGBA'));rgb=np.array(raw.convert('RGB')).astype(float)
    border=np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1]));bg=np.median(border,axis=0)
    # This costume and its effects are chromatic; sizeable neutral patches
    # matching the measured flat background are empty gaps, including enclosed ones.
    near=(np.max(np.abs(rgb-bg),axis=2)<14)&(np.ptp(rgb,axis=2)<9)
    labels,n=ndimage.label(near);sizes=np.bincount(labels.ravel())
    remove=sizes[labels]>=64;remove[labels==0]=False;a[remove,3]=0
    # Supply the real matte colour to the local colour-line unmatting pass.
    a[a[:,:,3]==0,:3]=np.rint(bg).astype('uint8')
    result,_=clean_flat_matte(Image.fromarray(a),tolerance=14,radius=2)
    return result


def export():configure();base.export()


def build():
    OUT.mkdir(exist_ok=True);cards=[]
    for name,item in ACTIONS.items():
        folder=OUT/name
        if not (folder/'game-animation.webp').exists():continue
        review=json.loads((folder/'review.json').read_text(encoding='utf-8')) if (folder/'review.json').exists() else {}
        cards.append(f'<article><h2>{item["title"]}</h2><p>{html.escape(review.get("note","시각 검토 전"))}</p><img src="{name}/game-animation.webp" alt="{item["title"]}"><p><a href="{name}/game-animation.gif">GIF</a> · <a href="{name}/native-sheet.png">전체 PNG 시트</a> · <a href="{name}/native-frames.json">프레임 시간</a> · <a href="{name}/settings.json">설정·프롬프트</a></p></article>')
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>마법사 idle · attack</title><style>:root{--matte:#142436}body{background:#1b2230;color:#eee;font:16px/1.65 system-ui;margin:24px}main{display:flex;gap:24px;flex-wrap:wrap}article{width:512px;max-width:100%}img{width:100%;background:var(--matte)}a{color:#c9c0ff}button{padding:8px 14px}</style><h1>마법사 · 대기 / 발사</h1><p>원본 그림과 보라색 마법 효과를 입력으로 사용했습니다. MiniMax 768px · 24FPS · 40스텝. 원본 파일은 유지했습니다. PNG/WebP는 부드러운 투명 경계를 보존하고 GIF는 이진 투명도를 사용합니다.</p><button onclick="document.documentElement.style.setProperty('--matte','#142436')">어둡게</button> <button onclick="document.documentElement.style.setProperty('--matte','#fff4dc')">밝게</button> <button onclick="document.documentElement.style.setProperty('--matte','#226b54')">초록</button><p><a href="violet-caster-idle-attack.zip">Idle + Attack 전체 ZIP</a></p><main>'''+''.join(cards)+'</main></html>'
    (OUT/'preview.html').write_text(page,encoding='utf-8')


def check():
    configure();assert digest(SOURCE)==digest(OUT/'source-original.png');records={}
    for name in ACTIONS:
        folder=OUT/name;meta=json.loads((folder/'frames.json').read_text(encoding='utf-8'))
        native=json.loads((folder/'native-frames.json').read_text(encoding='utf-8'))
        graph=json.loads((folder/'native-v1-workflow.json').read_text(encoding='utf-8'));assert graph['10']['inputs']['steps']==40
        sheet=Image.open(folder/'native-sheet.png').convert('RGBA');assert max(sheet.size)<=8192
        for n,i in enumerate(native['sourceIndices']):
            original=np.array(Image.open(folder/'all-frames'/f'frame-{i:03d}.png').convert('RGBA'))
            cell=np.array(sheet.crop((n%8*768,n//8*768,(n%8+1)*768,(n//8+1)*768)))
            assert np.array_equal(original,cell)
        with Image.open(folder/'game-animation.gif') as gif:
            assert gif.n_frames==native['frameCount'];total=0
            for i in range(gif.n_frames):gif.seek(i);total+=gif.info['duration']
        assert abs(total-sum(meta['previewDurationMs']))<=10
        records[name]=dict(exportedFrames=native['frameCount'],durationMs=total,
            edgeContactFrames=[x['frame'] for x in meta['diagnostics'] if x['edgeContact']],
            review=json.loads((folder/'review.json').read_text(encoding='utf-8')))
    save(OUT/'validation.json',dict(fileChecksPassed=True,sourceUnchanged=True,websiteUnchanged=True,
        nativeCanvas=[768,768],fps=24,actualSteps=40,cases=records,userApproval='pending'))
    (OUT/'README.txt').write_text('Violet caster idle + attack\n\nMiniMax 40 steps, 768x768 native cells, 24FPS.\nOriginal image and original videos preserved. Same source scale and canvas registration for both actions.\nUse action/native-sheet.png with native-frames.json, or action/frames/*.png.\nIdle duplicate closing reference omitted; attack repeats in previews only.\nPNG/WebP retain soft alpha, GIF uses binary alpha.\nThe magic is generated in the video; no synthetic magic was drawn during export.\nOriginal source effects were retained in the reference. See review.json for actual motion and limitations.\n',encoding='utf-8')
    build();target=OUT/'violet-caster-idle-attack.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for n in ['source-original.png','source.json','reference.png','preview.html','validation.json','README.txt','game-registration.json']:z.write(OUT/n,n)
        for name in ACTIONS:
            folder=OUT/name;native=json.loads((folder/'native-frames.json').read_text(encoding='utf-8'))
            for n in ['game-animation.gif','game-animation.webp','native-sheet.png','native-frames.json','settings.json','raw.mp4','reference-prepared.png','review-raw.webp','matte-review.jpg','review.json']:
                z.write(folder/n,name+'/'+n)
            for n in ['neutral-gap-cleanup.json','cast-matte-review.jpg']:
                if (folder/n).exists():z.write(folder/n,name+'/'+n)
            for i in native['sourceIndices']:
                p=folder/'all-frames'/f'frame-{i:03d}.png';z.write(p,name+'/frames/'+p.name)
    with zipfile.ZipFile(target) as z:assert z.testzip() is None
    print('CASTER_HANDOFF_VALIDATED',records,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['generate','export','check','build','all']);stage=parser.parse_args().stage
    if stage=='all':generate();export();check()
    else:globals()[stage]()
