"""One requested alternate video with painted-in reference VFX removed first."""
import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import idle_tool as engine
from tools import verify_cp01_dynamic_slash as run
from tools import verify_pixel_minimax as executor
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release

run.OUT=ROOT/'outputs/cp01-clean-sweep-20261023'
run.PREVIOUS=ROOT/'outputs/cp01-dynamic-sweep-20261023'
run.ACTION=dict(run.ACTION,seed=2026102335,title='발밑 자국 없는 횡베기 · 새 변형')
EDITED=Path('C:/Users/SKYLIGHT/.codex/generated_images/01a0943f-e4b7-7e11-af05-20d776c93f13/exec-152fb242-fc5b-466b-b99f-d4731659fcdb.png')
previous=json.loads((run.PREVIOUS/'attack/settings.json').read_text(encoding='utf-8'))
run.PROMPT=previous['prompt'].replace(
    'A single red crescent traces the actual horizontal knife sweep without obscuring the face. ',
    'The opening reference has NO decorative visual effects. Only DURING the fast blade sweep, '
    'one small narrow crimson crescent flashes close to the moving blade, CHANGES SHAPE as the '
    'blade travels, and disappears completely immediately after impact. The floor and space '
    'beneath the boots stay empty grey throughout. No puddle, circular floor decal, blood stain '
    'or stationary floating ribbon. All red visual effects are gone in the final ready stance. ')
run.PROMPT=run.PROMPT.replace('After the cut, settle into a balanced combat guard ',
    'After the cut, draw the knife forward again and settle into a balanced combat guard ')
run.PROMPT+=' This is one alternate take: make the weight transfer snappy, front knee receive the lunge, and finish the recovery instead of freezing in the extreme follow-through pose.'
BASE_BUILD=run.build


def build():
    BASE_BUILD()
    p=run.OUT/'preview.html'
    text=p.read_text(encoding='utf-8')
    text=text.replace('이전 · 팔 위주','이전 · 고정 붉은 자국 포함').replace('새 시험 · 전신 동작','새 변형 · 입력 이펙트 제거')
    text=text.replace('<h1>전신 횡베기 시험</h1>','<h1>원화의 고정 이펙트를 뺀 횡베기</h1><p>입력용 사본에서 발밑 원형 자국과 공중 리본을 이미지 편집으로 제거했습니다. 붉은 장갑과 머리 장식은 유지했습니다. 새 단발 영상 1회 생성입니다.</p>')
    text=text.replace('href="cp01-dynamic-slash.zip"','href="cp01-clean-sweep.zip"')
    text=text.replace('</main>','</main><p><a href="reference.png">이펙트 제거 입력 이미지</a> · <a href="reference-edit-prompt.txt">입력 이미지 편집 프롬프트</a></p>')
    text=text.replace('</main>','</main><p><a href="attack/settings.json">영상 생성 설정·프롬프트</a> · <a href="attack/effect-validation.json">발밑 잔여물 확인 기록</a></p>')
    p.write_text(text,encoding='utf-8')


run.build=build


def check():
    run.check()
    readme=run.OUT/'README.txt'
    readme.write_text(readme.read_text(encoding='utf-8')+'\nReference image edited with built-in image generation to remove painted-in crimson floor/ribbon VFX. See reference-edit-prompt.txt. Original user image unchanged.\n',encoding='utf-8')
    with zipfile.ZipFile(run.OUT/'cp01-dynamic-slash.zip') as source, zipfile.ZipFile(run.OUT/'cp01-clean-sweep.zip','w',zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            if info.filename=='README.txt':target.writestr(info.filename,readme.read_bytes())
            else:target.writestr(info.filename,source.read(info.filename))
        for name in ['reference.png','reference-edit-prompt.txt','reference-validation.json']:
            target.write(run.OUT/name,name)
        target.write(run.OUT/'attack/effect-validation.json','attack/effect-validation.json')
    with zipfile.ZipFile(run.OUT/'cp01-clean-sweep.zip') as z:assert z.testzip() is None
    print('CLEAN_SWEEP_PACKAGE_READY',flush=True)


def generate():
    run.configure()
    folder=run.OUT/'attack';folder.mkdir(parents=True,exist_ok=True)
    original=run.OUT/'source-original.png'
    if not original.exists():shutil.copy2(run.cp.SOURCE,original)
    assert run.cp.digest(original)==run.cp.digest(run.cp.SOURCE)
    reference=run.OUT/'reference.png'
    if not reference.exists():shutil.copy2(EDITED,reference)
    run.cp.save(run.OUT/'source.json',dict(sourcePath=str(run.cp.SOURCE),sha256=run.cp.digest(original),
        sourceUnchanged=True,sourceSize=[1024,1536],motionPadding=30,published=False,
        referencePath=str(reference),referenceSha256=run.cp.digest(reference),
        preparation='Built-in image edit removed original floor swirl and floating VFX; original character artwork retained as reference but not pixel-identical. Reference includes neutral grey matte.'))
    if (folder/'raw.mp4').exists():return
    if (folder/'native-v1-pending.json').exists():
        graph=json.loads((folder/'native-v1-workflow.json').read_text(encoding='utf-8'))
    else:
        ensure_idle();engine.start_comfy();release((8190,8191))
        prepared=engine.prepare_reference_image(reference.read_bytes(),768,768,30)
        (folder/'reference-prepared.png').write_bytes(prepared)
        uploaded=engine.upload_image(prepared,'cp01-clean-sweep.png')
        graph=engine.build_workflow(uploaded,run.PROMPT,3,768,768,run.ACTION['seed'],
            animation_type='attack',loop=False,facing='right',flat_background=True,blink_mode='none',
            motion_strength='high',sampling_mode='quality',workflow_id='standard')
        text=graph['6']['inputs']['prompt'].replace(
            'The opening character size, screen placement, head-to-body proportions, costume, equipment, linework and painted shading are retained.',
            'Retain the drawing scale, proportions, costume, equipment and painted 2D linework. Allow natural forward and downward body translation during the knee bend and step; do not pin the body or feet to their opening positions.')
        graph['6']['inputs']['prompt']=text
        graph['15']['inputs'].pop('audio',None);graph.pop('14',None);graph.pop('5',None)
        graph['16']['inputs']['filename_prefix']='cp01_clean_sweep_20261023/attack'
        run.cp.save(folder/'settings.json',dict(animationType='attack',seed=run.ACTION['seed'],width=768,
            height=768,duration=3,fps=24,steps=20,loop=False,facing='right',motionPadding=30,motionStrength='high',
            referenceOffsetX=0,workflowId='standard',samplingMode='quality',prompt=run.PROMPT,actualPrompt=text,
            sourceSha256=run.cp.digest(original),referenceSha256=run.cp.digest(reference),
            sourceVFXRemoved=True,oneRequestedAlternate=True,published=False))
    executor.OUT=folder
    history=executor.execute(graph,engine.COMFY_URL,'native-v1')
    shutil.copyfile(engine.find_saved_video(history),folder/'raw.mp4')
    ensure_idle();release((8189,))
    run.raw_review()
    print('CLEAN_SWEEP_VIDEO_READY',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['generate','export','compare','build','check'])
    stage=parser.parse_args().stage
    if stage=='generate':generate()
    elif stage=='check':check()
    else:getattr(run,stage)()
