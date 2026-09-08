"""Non-human sprite templates; never assume parts absent from the reference."""
SUBJECT_DEFAULTS = {
    'creature': {
        'idle': 'continuous subtle body expansion and contraction, small balance adjustments and delayed motion of existing appendages throughout the clip',
        'walk': 'a steady locomotion cycle in place using only the existing limbs or body structure, preserving the original anatomy',
        'run': 'a fast locomotion cycle in place using only the existing limbs or body structure, with a clear repeating rhythm',
        'attack': 'one forward attack using an existing attacking appendage or the body, followed by recovery',
        'cast': 'one energy release from an existing visible feature, retaining the original anatomy',
        'hit': 'one brief body recoil opposite the impact followed by recovery',
        'death': 'the body loses support and settles into a defeated pose appropriate to its existing anatomy',
        'jump': 'the body compresses, rises slightly, and returns to its starting location using existing anatomy',
        'custom': 'one readable action using only the anatomy visible in the reference',
    },
    'hover_machine': {
        'idle': 'continuous small rhythmic vertical hovering with subtle corrections at existing articulated mounts throughout the clip, rigid hull and barrels',
        'walk': 'a slow hovering travel cycle in place with small vertical oscillation, fixed viewing direction',
        'run': 'a brisk hovering travel cycle in place with controlled vertical oscillation, fixed viewing direction',
        'attack': 'one firing action along the original axis of an existing weapon, localized mechanical recoil of its mount and return',
        'cast': 'one energy discharge from an existing emitter or weapon opening, with localized mechanical recoil',
        'hit': 'one brief rigid-body displacement opposite the impact, then recover hovering position',
        'death': 'the rigid vehicle loses hover support and descends into a disabled position within the canvas',
        'jump': 'one short vertical hover boost and return to the starting altitude',
        'custom': 'one readable mechanical action using only existing components',
    },
    'ground_machine': {
        'idle': 'continuous small mechanical suspension or existing joint adjustments throughout the clip, stable chassis and ground contact',
        'walk': 'a slow in-place travel cycle using existing wheels, tracks or articulated supports, stable rigid chassis',
        'run': 'a fast in-place travel cycle using existing wheels, tracks or articulated supports, controlled chassis vibration',
        'attack': 'one firing action along the original axis of an existing weapon, localized recoil and recovery, ground contact maintained',
        'cast': 'one energy discharge from an existing emitter or weapon opening, chassis remains supported',
        'hit': 'one brief mechanical recoil through existing suspension or joints, then recover stable support',
        'death': 'existing supports settle into a disabled position, the rigid chassis comes to rest',
        'jump': 'one small chassis lift and landing only if the visible supports permit it; otherwise a suspension compression and recovery',
        'custom': 'one readable mechanical action using only existing components with stable ground contact',
    },
}


def subject_constraints(subject, facing, strength, blink, action):
    direction = {
        'preserve': 'Preserve the exact camera-relative orientation from <Picture 1>.',
        'right': 'Maintain a screen-right-facing orientation.',
        'left': 'Maintain a screen-left-facing orientation.',
        'front': 'Maintain a front-facing orientation.',
        'back': 'Maintain a rear-facing orientation.',
    }.get(facing, 'Preserve the exact camera-relative orientation from <Picture 1>.')
    common = (direction + ' Keep the viewing angle fixed throughout; existing weapons act along their original axes. '
              'Preserve the number, shape, proportions and connections of all existing parts; animate only structures visible in the reference. ')
    amplitude = {'low': 'small restrained', 'normal': 'clearly visible moderate', 'high': 'pronounced but controlled'}[strength]
    motion = f'Use {amplitude} motion amplitude, keeping the entire subject inside the canvas. '
    if subject == 'creature':
        eyes = ('If eyes are present, keep their original shape and gaze. ' if blink == 'none' else
                'Only if eyelids are present, allow at most one brief blink; otherwise preserve the existing eyes. ')
        return common + 'Preserve the original non-human anatomy and surface markings. ' + eyes, motion
    support = ('Maintain hovering support during active motion. ' if subject == 'hover_machine' else
               'Use only the original ground-contact mechanisms. ')
    if action == 'death':
        support = ''
    return (common + 'Treat the subject as a rigid mechanical assembly: armor plates and barrels retain their straight edges and dimensions. '
            'Articulation occurs only at existing mechanical joints. Keep sensor lenses and surface markings unchanged. ' + support,
            motion + 'Secondary movement is limited to existing articulated components. ')
