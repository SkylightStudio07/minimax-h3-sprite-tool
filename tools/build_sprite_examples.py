"""Publish small presentation copies of reviewed sprites, never raw jobs/metadata."""
import json
import shutil
import sys
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
OUT=ROOT/'web/assets/sprite-examples'


def build():
    OUT.mkdir(parents=True,exist_ok=True)
    examples=[]
    cases=[
        ('pixel-idle','도트 · 대기','치비 아니메 도트 캐릭터의 작은 호흡과 머리카락 움직임','pixel','idle','chibi-motion-20261020/idle','animation-3x.webp','sheet-grid.png','reference.png'),
        ('pixel-walk','도트 · 걷기','같은 캐릭터가 오른쪽을 보며 제자리에서 걷기','pixel','walk','chibi-motion-20261020/walk','animation-3x.webp','sheet-grid.png','reference.png'),
        ('pixel-attack','도트 · 검 공격','같은 캐릭터로 한 번 베기 → 자세 회복','pixel','attack','chibi-attack-20261020','animation.webp','sheet-grid.png','reference.png'),
        ('pixel-energy','도트 · 푸른 검기','같은 캐릭터의 검 공격에 AI가 검기·타격 효과를 함께 생성','pixel','attack','chibi-ai-effects-20261020','animation.webp','sheet-grid.png','reference.png'),
        ('normal-idle','일반 · 대기','일반 비율 캐릭터의 작은 호흡과 머리카락 움직임','painted','idle','normal-sprite-examples-20261020/idle','animation.webp','sheet.png','../reference.png'),
    ]
    # A completed job is not sufficient for publication. Rejected actions stay
    # absent until the replacement motion and its cutout have been inspected.
    for action,label,description in (
        ('run','뛰기','전진 기울기와 팔·다리 동작이 있는 제자리 달리기'),
        ('attack','빠른 내려찍기','칼을 들어 올린 자세에서 짧고 빠르게 내려찍기'),
    ):
        folder=('normal-run-sheathed-20261020/' if action=='run' else 'normal-action-snap-20261020/')+action
        review=ROOT/'outputs'/folder/'review.json'
        if review.exists() and json.loads(review.read_text(encoding='utf-8')).get('publish') is True:
            cases.append(('normal-'+action,'일반 · '+label,description,'painted',action,folder,'animation.webp','sheet.png','reference.png'))
    for name,label,description in (
        ('slash','작은 검기 · 베기','검을 휘두를 때 짧고 옅은 검기가 따라오는 동작'),
        ('spin','작은 검기 · 회전베기','몸을 돌려 공격하고 옅은 칼날 빛으로 마무리'),
    ):
        folder='normal-sword-vfx-subtle-20261020/'+name
        review=ROOT/'outputs'/folder/'review.json'
        if review.exists() and json.loads(review.read_text(encoding='utf-8')).get('publish') is True:
            cases.append(('normal-subtle-'+name,'일반 · '+label,description,'painted','attack' if name=='slash' else 'custom',folder,'animation.webp','sheet.png','reference.png'))
    for action,label,description in (
        ('idle','대기','큰 머리와 짧은 몸 비율을 유지하는 작은 호흡·머리카락 움직임'),
        ('run','뛰기','검을 수납하고 두 팔과 짧은 다리를 함께 움직이는 제자리 달리기'),
        ('attack','내려베기','칼을 미리 든 치비 캐릭터가 한 번 빠르게 내려베기'),
    ):
        folder='chibi-illustration-20261020/'+('attack-clean' if action=='attack' else action)
        review=ROOT/'outputs'/folder/'review.json'
        if review.exists() and json.loads(review.read_text(encoding='utf-8')).get('publish') is True:
            cases.append(('chibi-'+action,'치비 · '+label,description,'painted',action,folder,'animation.webp','sheet.png','reference.png'))
    pixel_prompts={
        'pixel-idle':'A very small relaxed idle loop in the original orientation. Both boots stay planted, with tiny shoulder and torso sway, no local inflation. Hair tips follow gently. Keep the same chibi head-to-body proportions, pixel face and eyes, costume, colors and original rigid weapon pose. No stepping, turning, sword swings, added effects or camera motion.',
        'pixel-walk':'Walk in place toward screen right with a short even stride and small opposite arm swing. Preserve the exact reference chibi character, large head and compact body, original eyes and face, costume, pixel clusters, palette and one rigid existing sword. No changing proportions, extra weapon, camera motion, scenery or effects.',
        'pixel-attack':'Perform exactly ONE clear sword attack toward SCREEN RIGHT, then recover. At 0.0-0.4 seconds brace the boots, bend the knees and draw the sword hand back and up beside the rear shoulder. At 0.4-0.95 seconds deliver ONE fast decisive diagonal downward cut through the space in front toward screen right. Move the arm, shoulders and hips with one small grounded weight shift. At 0.95-1.35 seconds follow through low and forward, then brake. At 1.35-2.2 seconds recover the opening compact ready stance at the same screen location and hold until the end. Keep the exact reference chibi head and body proportions, pixel face and eyes, costume, colors and square pixel clusters. Keep one rigid sword in the same hand, unchanged in length. No duplicate weapon, second attack, walking, jumping, full body spin, camera motion or scenery. Keep the whole character, sword and effects inside the empty canvas.',
    }
    pixel_prompts['pixel-energy']=pixel_prompts['pixel-attack']
    for id,title,description,style,action,folder,animation,sheet,reference in cases:
        source=ROOT/'outputs'/folder
        chibi=folder.startswith('chibi-illustration-20261020/')
        metadata=None
        if style=='pixel':
            import numpy as np
            metadata=json.loads((source/'frames.json').read_text(encoding='utf-8'))
            frame_folder=source/'selected' if (source/'selected').is_dir() else source
            frames=[Image.open(frame_folder/f'frame-{i:02d}.png').convert('RGBA') for i in range(len(metadata['sourceIndices']))]
            size=frames[0].size
            assert all(frame.size==size for frame in frames)
            for frame in frames:
                a=np.array(frame)
                assert set(np.unique(a[:,:,3])) <= {0,255},id
            # Only exact integer enlargement for animated presentation copies.
            large=[frame.resize((size[0]*3,size[1]*3),Image.Resampling.NEAREST) for frame in frames]
            large[0].save(OUT/(id+'.webp'),save_all=True,append_images=large[1:],duration=metadata['durationMs'],loop=0,lossless=True)
            frames[0].save(OUT/(id+'-poster.png'))
        else:
            shutil.copyfile(source/animation,OUT/(id+'.webp'))
            with Image.open(source/animation) as im:
                im.seek(0);im.convert('RGBA').save(OUT/(id+'-poster.png'))
            if id.startswith('normal-subtle-'):
                with Image.open(source/('frame-02.png' if id.endswith('slash') else 'frame-08.png')) as im:
                    im.save(OUT/(id+'-poster.png'))
            if chibi:
                shutil.copyfile(source/'poster.png',OUT/(id+'-poster.png'))
        for filename,suffix in [(sheet,'-sheet'),(reference,'-source')]:
            with Image.open(source/filename) as im:
                im=im.convert('RGBA')
                if style!='pixel':im.thumbnail((1200,900),Image.Resampling.LANCZOS)
                im.save(OUT/(id+suffix+'.webp'),lossless=True)
        effect='subtle' if id.startswith('normal-subtle-') else 'blue_slash' if id=='pixel-energy' else 'none'
        if chibi:effect=json.loads((source/'settings.json').read_text(encoding='utf-8'))['combatEffect']
        warning=('같은 치비 아니메 도트 캐릭터의 AI 동작·효과 생성 결과입니다. 큰 검기가 가장자리에 닿는 프레임이 있어 여백·강도를 조정해 주세요.' if id=='pixel-energy' else '같은 치비 아니메 도트 캐릭터로 생성 후 도트화·윤곽·시간축을 정리한 실제 샘플입니다. 걷기의 반복 구간은 생성 후 골랐습니다.' if style=='pixel' else '샘플 캐릭터로 생성한 예시입니다. 내 캐릭터의 실시간 미리보기가 아닙니다.')
        recipe=dict(animationType=action,combatEffect=effect,pixelOutput=style=='pixel',pixelColorLock=True,
                    effectStrength='normal',effectDescription='',duration=3,frameCount=30 if action=='attack' else 12,
                    motionPadding=30 if action=='attack' else 10,loop=True,stabilize=False,optimizeLoop=False,
                    workflowId='standard' if style=='pixel' else 'fasth3-sprite',samplingMode='quality',
                    facing='preserve' if action=='idle' else 'right',subjectType='human',motionStrength='low' if style=='pixel' and action!='attack' else 'high' if style=='painted' else 'normal',
                    blinkMode='none',negativeEnabled=False,removeBackground=style=='pixel',backgroundRemoval='flat',
                    width=768 if action=='attack' else 512,height=640 if action=='attack' else 512)
        if metadata:
            recipe.update(width=metadata['frameWidth']*4,height=metadata['frameHeight']*4,frameCount=len(metadata['sourceIndices']),prompt=pixel_prompts[id],loop=True,duration=3)
        normal=style=='painted' and folder.startswith(('normal-sprite-examples-20261020/','normal-sprite-refine-20261020/','normal-sprite-attack-v3-20261020/','normal-action-snap-20261020/','normal-run-sheathed-20261020/','normal-sword-vfx-subtle-20261020/'))
        if normal:
            recipe=json.loads((source/'settings.json').read_text(encoding='utf-8'))
            recipe.pop('characterId',None)
            warning='같은 일반 비율 캐릭터로 만든 실제 동작 예시입니다. 내 캐릭터의 실시간 미리보기가 아닙니다.'
            if action!='idle':
                warning+=' 다리·팔 사이까지 AI로 배경을 제거했습니다.'
                review=json.loads((source/'review.json').read_text(encoding='utf-8'))
                warning+=' '+review.get('note','')
        if chibi:
            recipe=json.loads((source/'settings.json').read_text(encoding='utf-8'))
            recipe.pop('characterId',None)
            warning='도트가 아닌 오리지널 치비 캐릭터의 실제 생성 예시입니다. 내 캐릭터로 생성하면 결과가 달라져요. '+json.loads((source/'review.json').read_text(encoding='utf-8')).get('note','')
        if id.startswith('normal-subtle-'):
            import sprite_combat
            name='slash' if id.endswith('slash') else 'spin'
            actual=json.loads((source/'settings.json').read_text(encoding='utf-8'))
            recipe={key:actual[key] for key in ('width','height','duration','seed','loop','motionSpeed','trimAction','workflowId','pixelOutput','pixelColorLock','removeBackground','backgroundRemoval','motionPadding')}
            recipe.update(animationType=action,prompt=sprite_combat.SUBTLE_MOTIONS[name],combatEffect='subtle',effectStrength='low',effectDescription='',frameCount=24,
                samplingMode='quality',facing='right',subjectType='human',motionStrength='high',blinkMode='none',negativeEnabled=False,stabilize=False,optimizeLoop=False)
            warning='샘플 캐릭터의 실제 생성 결과입니다. 내 이미지를 넣고 이 설정으로 만들 수 있어요. '+json.loads((source/'review.json').read_text(encoding='utf-8')).get('note','')
            shutil.copyfile(source/'animation.gif',OUT/(id+'.gif'))
        if chibi:shutil.copyfile(source/'animation.gif',OUT/(id+'.gif'))
        dimensions=dict(width=metadata['frameWidth'],height=metadata['frameHeight'],frames=len(metadata['sourceIndices'])) if metadata else None
        item=dict(id=id,title=title,description=description,style=style,category='chibi' if chibi else 'pixel' if style=='pixel' else 'normal',action=action,effect=effect,
            animation=f'assets/sprite-examples/{id}.webp',poster=f'assets/sprite-examples/{id}-poster.png',
            sheet=f'assets/sprite-examples/{id}-sheet.webp',source=f'assets/sprite-examples/{id}-source.webp',
                  note=warning,pixelGrid=dimensions,characterId='original-chibi-cartographer-20261020' if chibi else 'chibi-anime-swordswoman-20261020' if style=='pixel' else 'normal-anime-swordswoman-20261020' if normal else None,recipe=recipe)
        if effect=='subtle' or chibi:item['gif']=f'assets/sprite-examples/{id}.gif'
        examples.append(item)
    from tools.publish_chibi_reference_examples import entries
    examples.extend(entries())
    temporary=OUT/'catalog.tmp'
    temporary.write_text(json.dumps(dict(version=12,examples=examples),ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(OUT/'catalog.json')
    print('Published',len(examples),'reviewed sprite examples')


if __name__=='__main__':build()
