"""User-facing joint motion/VFX recipes; no procedural effect drawing."""
VERSION = 'joint-vfx-v2-subtle'
EFFECTS = {
    'none': '',
    'blue_slash': ('During anticipation a narrow cyan glint charges along the existing blade. At the actual cut, '
        'ONE bright cyan-blue energy crescent follows the physical sword path, with a narrow near-white core, '
        'turquoise body and cobalt edge. A compact gold-white impact starburst at the blade tip releases a short '
        'fan of golden sparks. The crescent breaks into small blue fragments and fades during recovery.'),
    'fire': 'One orange-red flame trail follows the attacking weapon or emitting hand, with a brief warm impact flash and a few fading embers.',
    'impact': 'One compact gold-white impact starburst appears at the actual contact point, followed by a short fan of small fading sparks.',
    'magic': 'Energy gathers at the existing casting hand or emitter, then releases one cyan-violet pulse forward with a brief impact flash and fading fragments.',
    'custom': '',
    'subtle': ('A fine pale cyan highlight stays on the metal blade. A short translucent forearm-length streak '
        'follows just behind its tip for an instant, with a few tiny gold specks.'),
}
STRENGTHS = {
    'low': 'Keep the effect compact, approximately half the weapon length, with only a few sparks.',
    'normal': 'Use a clearly readable crescent or burst about the weapon length, with a short trail.',
    'high': 'Use a vivid larger crescent or burst with more fragments, while keeping the whole effect inside the canvas.',
}
SUBTLE_MOTIONS = {
    'slash': ('Immediately make one quick downward sword cut to screen right from the raised starting pose. '
        'Plant the forward boot, flex the knees and drive both hands from overhead down to the forward hip. '
        'The cut happens during the first half second. Keep the chest lifted and stop in a stable low finishing stance. '
        'Hold the finish as the hair settles.'),
    'spin': ('Sink onto bent knees, then make one quick full-body turn on two short planted steps. '
        'Show the back of the head and outfit during the turn, then face screen right again. '
        'The hips, shoulders and sword rotate together. Finish by planting the front boot and cutting horizontally to the right. '
        'Stop in a low balanced lunge and hold the finish.'),
}


def options(p):
    kind = p.get('combatEffect', 'none')
    strength = p.get('effectStrength', 'normal')
    detail = p.get('effectDescription', '')
    if not isinstance(kind, str) or kind not in EFFECTS:
        raise ValueError('이펙트 종류를 다시 선택하세요.')
    if not isinstance(strength, str) or strength not in STRENGTHS:
        raise ValueError('이펙트 강도를 다시 선택하세요.')
    if not isinstance(detail, str) or len(detail) > 1800:
        raise ValueError('이펙트 설명은 1800자 이내로 입력하세요.')
    if kind == 'custom' and not detail.strip():
        raise ValueError('직접 만들 이펙트의 색·모양·등장 시점을 적어 주세요.')
    if any(type(p.get(k, default)) is not bool for k, default in [('pixelOutput', False), ('pixelColorLock', True)]):
        raise ValueError('도트 출력과 색상 안정화는 체크박스로 선택하세요.')
    if (kind != 'none' or p.get('pixelOutput')) and p.get('removeBackground') and p.get('backgroundRemoval', 'flat') in ('ai','ai-sparks','ai-smooth','ai-soft','green'):
        raise ValueError('공격 이펙트를 보존하려면 배경 제거를 ‘단색 배경’으로 바꿔 주세요. 단순한 배경의 입력 이미지를 권장합니다.')
    return dict(combatEffect=kind, effectStrength=strength, effectDescription=detail.strip(),
                pixelOutput=p.get('pixelOutput', False), pixelColorLock=p.get('pixelColorLock', True))


def prompt(p):
    setting = options(p)
    if setting['combatEffect'] == 'none':
        return ''
    if setting['combatEffect'] == 'subtle':
        return ' '+EFFECTS['subtle']+' '+setting['effectDescription']+' '
    return (' Generate the attack and its visual effects TOGETHER in this same shot. '
        + EFFECTS[setting['combatEffect']] + ' ' + setting['effectDescription'] + ' '
        + STRENGTHS[setting['effectStrength']] + ' '
        'Time the effect to the actual strike or release, after anticipation; dissipate it completely before the final recovery. '
        'No repeated attack, continuous beam or persistent ring. Keep the face, torso and weapon readable. '
        'New bright colors belong to the effect only; preserve the reference costume, hair and skin colors. '
        'Match the reference art style, including sharp square pixel clusters for pixel-art inputs. '
        'Keep the camera fixed and all effects within the empty margins, at least 8 percent away from every canvas edge. '
        'Do not enlarge the character or add scenery, floor, cast shadow, text, cinematic bloom or motion blur. ')


def subtle_animation_prompt(detail, p, *, loop=False, seconds=3, flat_background=True, facing='right', motion_strength='normal', blink_mode='none'):
    """Concise positive conditioning; generic energy/side-facing wrappers defeated the small-trail test."""
    setting=options(p)
    alignment='<Picture 1> is the opening reference.'
    if loop:alignment+=f' <Picture 2> is the matching closing reference at {seconds:.2f} seconds.'
    background=('The camera and character scale stay constant on a uniform flat medium-grey background. '
                if flat_background else 'The camera, character scale and opening background stay unchanged. ')
    motion=detail.strip() or 'Perform one quick physical sword cut, then hold a balanced finishing stance.'
    if facing=='left':motion=motion.replace('screen right','screen left').replace('screen RIGHT','screen LEFT')
    strength={'low':'', 'normal':'Make the local blade highlight a little brighter. ',
              'high':'Make the local highlight brighter and add a few more tiny specks. '}[setting['effectStrength']]
    body={'low':'Keep physical body movement restrained. ','normal':'','high':'Use decisive foot placement and shoulder motion. '}[motion_strength]
    eyes='Allow one brief blink. ' if blink_mode=='once' else 'Retain the opening eye and mouth shapes. '
    end='The short highlight fades completely as the hands stop. '
    if loop:end+='Return smoothly to the closing reference pose. '
    return (alignment+'\n\nintegrated_multimodal_description: [Shot 1] '
        'A fixed full-body game-sprite view of the reference character. '
        'Retain the exact reference face, hair, outfit, proportions and illustration style. '
        +background+'The sword remains a straight rigid silver metal blade in the original hand grip. '
        +motion+' '+body+eyes+EFFECTS['subtle']+' '+strength+setting['effectDescription']+' '
        +'Most of the picture stays unchanged. This is a regular physical sword attack with a subtle local blade highlight. '
        +end+'\n\noverall_soundscape: N/A\n\nnon_diegetic_music: N/A')
