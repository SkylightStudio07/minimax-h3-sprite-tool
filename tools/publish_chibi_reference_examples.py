"""Publish the approved reference-chibi motions without rebuilding other samples."""
import json
import shutil
import sys
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
SOURCE=ROOT/'outputs/chibi-reference-motion-20261023'
DEST=ROOT/'web/assets/sprite-examples'


def entries():
    from tools.verify_chibi_reference_motion import ACTIONS
    validation=json.loads((SOURCE/'validation.json').read_text(encoding='utf-8'))
    assert validation['passed'] and validation['sourceUnchanged']
    result=[]
    for action,title,description in (
        ('run','치비 · 달리기','짧은 다리·팔과 망토가 함께 움직이는 오른쪽 달리기'),
        ('attack','치비 · 별봉 공격','앞으로 찌르는 한 번의 공격과 작은 금빛 불꽃'),
    ):
        folder=SOURCE/action
        item_id='chibi-reference-'+action
        actual=json.loads((folder/'settings.json').read_text(encoding='utf-8'))
        if action=='attack':assert actual['selectedSourceRange']==[0,33]
        shutil.copyfile(folder/'animation.webp',DEST/(item_id+'.webp'))
        shutil.copyfile(folder/'animation.gif',DEST/(item_id+'.gif'))
        with Image.open(folder/'animation.webp') as animation:
            animation.seek(18 if action=='attack' else 15)
            animation.convert('RGBA').save(DEST/(item_id+'-poster.png'))
        for file,suffix in [('reference.png','source'),('sheet.png','sheet')]:
            with Image.open(folder/file) as im:
                im=im.convert('RGBA')
                im.thumbnail((1200,900),Image.Resampling.LANCZOS)
                im.save(DEST/(item_id+'-'+suffix+'.webp'),lossless=True)
        # Applying the motion must not replace a user's hair/clothes with the
        # sample cartographer's identity description.
        identity=('Preserve the EXACT supplied chibi character, original face, eyes, hairstyle, '
            'costume colors, accessories, large head and compact short body, anime linework and painted texture. ')
        motion=ACTIONS[action]['prompt']
        if action=='run':motion=motion.replace('wand hand','hand holding the original prop')
        recipe={key:actual[key] for key in ('animationType','width','height','duration','frameCount','seed','loop',
            'motionSpeed','trimAction','motionStrength','motionPadding','workflowId','samplingMode','facing',
            'pixelOutput','combatEffect','effectStrength','effectDescription','removeBackground','backgroundRemoval',
            'optimizeLoop','stabilize','subjectType','blinkMode','negativeEnabled')}
        recipe['prompt']=identity+motion+' Fixed camera, full body and existing equipment inside the canvas. Uniform grey background, no floor, scenery or text.'
        if action=='attack':recipe['backgroundRemoval']='ai-sparks'
        note='오리지널 치비 캐릭터의 실제 생성 예시입니다. 내 캐릭터로 생성하면 결과가 달라져요. '
        note+=('별봉·가방에 작은 변형과 색 변화가 남으며 반복 경계는 확인이 필요해요.' if action=='run' else
            '이 샘플은 생성 영상에서 첫 공격만 약 1.42초로 골랐어요. 새 결과도 필요한 공격 구간을 선택해 주세요. 얼굴은 정면에 가까운 3/4 시점이며 손·별봉에 작은 변형이 남아요.')
        result.append(dict(id=item_id,title=title,description=description,style='painted',category='chibi',
            action=action,effect='impact' if action=='attack' else 'none',
            animation=f'assets/sprite-examples/{item_id}.webp',gif=f'assets/sprite-examples/{item_id}.gif',
            poster=f'assets/sprite-examples/{item_id}-poster.png',sheet=f'assets/sprite-examples/{item_id}-sheet.webp',
            source=f'assets/sprite-examples/{item_id}-source.webp',note=note,pixelGrid=None,
            characterId='original-reference-chibi-cartographer-20261023',recipe=recipe))
    return result


def publish():
    path=DEST/'catalog.json'
    catalog=json.loads(path.read_text(encoding='utf-8'))
    previous=[x for x in catalog['examples'] if not x['id'].startswith('chibi-reference-')]
    new=entries()
    catalog.update(version=max(12,catalog['version']),examples=previous+new)
    temporary=DEST/'catalog.tmp'
    temporary.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temporary.replace(path)
    (SOURCE/'site-publication.json').write_text(json.dumps(dict(published=True,date='2026-10-23',
        authorization='User requested site integration after reviewing motion tests.',
        examples=[x['id'] for x in new],otherExamplesUnchanged=True),ensure_ascii=False,indent=2),encoding='utf-8')
    print('Published',len(new),'chibi samples; preserved',len(previous),'existing samples.')


if __name__=='__main__':publish()
