"""Experimental VFX templates, independent of character anatomy instructions."""

TEMPLATES = {
    'smoke': dict(name='마법 연기', loop=True, motion='A ribbon of smoke curls slowly upward, with small wisps separating and fading. The emission point at the bottom stays fixed.'),
    'flame': dict(name='불꽃', loop=True, motion='A small flame flickers continuously upward from a fixed base. Its tips split, curl and fade while new flame tongues rise from the same base. Keep its overall height and footprint stable.'),
    'aura': dict(name='오라', loop=True, motion='An aura shimmers gently around its fixed center, with light ripples traveling along its existing contours. Retain a stable overall footprint.'),
    'slash': dict(name='참격', loop=False, motion='The existing curved slash sweeps once along its arc, leaving a short trailing streak that quickly fades. The whole effect dissipates into the empty background by the end. No new weapon or character appears.'),
    'impact': dict(name='타격 섬광', loop=False, motion='The existing impact flash expands briefly from its fixed center, releases a few short radial sparks, then completely fades into the empty background.'),
    'dissolve': dict(name='소멸', loop=False, motion='The existing effect breaks into a few small wisps and particles that drift a short distance and disappear. End with only the empty background.'),
}


def prompt(template, seconds, detail=''):
    config = TEMPLATES[template]
    text = f'<Picture 1> supplies the opening effect image at 0.00 seconds.'
    if config['loop']:
        text += f' <Picture 2> supplies the matching closing image at {seconds:.2f} seconds.'
    text += ('\n\nintegrated_multimodal_description: [Shot 1] An isolated 2D game visual effect. '
             'Preserve the reference palette, smooth curved contours, painted shading, luminous gradients and fine wisps. '
             'Retain the original level of visual detail instead of simplifying it into flat geometric shapes. '
             'Keep the camera, framing and magnification completely fixed. '
             'The surrounding background stays exactly the same uniform color as the reference in every frame. '
             'No scenery, text, characters or physical ground plane. '
             'Keep all moving parts inside the canvas with a clear margin. '
             + (detail.strip() or config['motion']))
    if config['loop']:
        text += ' Continuous flowing motion with matching phase and direction across the loop boundary.'
    else:
        text += ' Perform the effect once; do not restart or reappear at the end.'
    return text+'\n\noverall_soundscape: N/A\n\nnon_diegetic_music: N/A'


def apply(graph, template, detail=''):
    """Adapt a freshly built I2V graph; no production readiness bypass here."""
    config = TEMPLATES[template]
    inputs = graph['6']['inputs']
    if config['loop']:
        inputs['last_frame'] = inputs['first_frame']
    else:
        inputs.pop('last_frame', None)
    inputs['prompt'] = prompt(template, inputs['length']/24, detail)
    return graph
