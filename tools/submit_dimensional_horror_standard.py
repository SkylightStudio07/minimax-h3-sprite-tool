"""Standard 768-square boss generation after the high-resolution run was stopped.

Submit idle and attack only; generation monitoring and matte export are separate.
"""
import hashlib
import io
import json
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import requests
from PIL import Image
import idle_tool as engine
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release

SOURCE=Path('C:/Users/SKYLIGHT/Documents/Graduation/Project-Vertex/Assets/Art/Characters/Enemy/Boss/Dimensional Horror/Dimensional Horror.png')
OUT=ROOT/'outputs/dimensional-horror-standard-20261024'
WIDTH=768;HEIGHT=768;STEPS=40;FPS=24
IDENTITY=(
    'Animate the EXACT SAME single enormous dark armored dimensional creature from the '
    'reference illustration. It is a stationary boss emerging LEFTWARD from the narrow '
    'VERTICAL violet-black rift on the RIGHT edge of the image. Preserve the exact original '
    'side view, pointed downward-left head with its long backward sweeping jagged horn '
    'crest, layered charcoal stone-like armor plates, violet fissures and dark purple '
    'under-neck tissue. Keep the original enormous long articulated forelimb extending '
    'down-left into a single huge curved SCYTHE-LIKE terminal claw, the original thinner '
    'hooked digits near the center-right and the existing segmented torso disappearing '
    'into the right-side rift. No human anatomy, face, new eyes, teeth, legs, wings, tails '
    'or new limbs. Preserve each existing part and connection. The rift is a fixed map '
    'boundary, NOT a handheld weapon or a rotating staff. Its tall black slit and violet '
    'rim stay vertical at the EXACT SAME screen coordinates, about x=735 on this '
    '768-pixel-wide frame. The rear torso attachment at the rift stays at the original '
    'coordinates and scale. Only the existing head, neck and articulated limbs move '
    'out into the empty LEFT side; no entire-body floating or sliding across the frame. '
    'Retain the original hand-inked 2D contours, painted plate textures and flat cel-shadow '
    'shapes in every frame, no glossy 3D render, new realistic relighting, redesign or '
    'camera orbit. Black plates stay solid and keep their cracks; articulation occurs '
    'at existing neck and forelimb joints, never a rubber armor expansion. ')
ACTIONS={
    'idle':dict(seed=2026102471,loop=True,strength='normal',prompt=(
        'A restrained threatening BOSS IDLE LOOP while anchored in the right-side rift. '
        'The head makes ONE slow small downward-left inclination then returns, with '
        'coordinated slight neck articulation. The giant low scythe-like claw hangs '
        'in the original broad curve; its existing elbow makes a very small pressure '
        'adjustment, moving the terminal hook about 10-18 pixels without changing '
        'its shape or length. The thinner hooked digits near the torso gently flex '
        'once and relax, maintaining the same count. Soft violet currents move '
        'through the existing armor fissures and along the fixed portal rim, '
        'small brightness variation only, never a giant glow covering the armor. '
        'The motion reads as a huge creature quietly watching from its anchored '
        'rift. Keep the torso root and vertical rift completely steady. No global '
        'up/down pumping, chest inflation, bobbing of the entire silhouette, attack, '
        'walking, stepping, portal drift, opening new jaws, added teeth or new '
        'particles. The horn tips and giant hook remain completely inside the '
        'canvas. One unhurried three-second cycle returning to the original '
        'pose, effect arrangement and motion phase.')),
    'attack':dict(seed=2026102472,loop=False,strength='high',prompt=(
        'Perform exactly ONE powerful SCYTHE-FORELIMB SWEEP into SCREEN LEFT and '
        'recover, with the boss torso and portal anchored on the RIGHT. At '
        '0.0-0.7 seconds flex the EXISTING long forelimb elbow to draw the huge '
        'curved terminal claw inward toward the body and upward a little, '
        'loading the strike. The head and neck pull back slightly toward the '
        'rift as anticipation, but the rear torso attachment and the rift '
        'itself remain stationary. At 0.7-1.4 seconds extend that SAME forelimb '
        'in ONE fast diagonal DOWN-LEFT sweeping cut through the empty space '
        'in front of the boss. Drive the motion through the existing shoulder '
        'and elbow, with a readable neck follow-through, rather than only '
        'twitching the claw tip. The original giant curved blade stays one '
        'continuous solid hook of constant size; never turns into a new sword '
        'or a chain. Keep its LEFTMOST point at least 30 pixels INSIDE the '
        'canvas and its lowest curve above the lower frame edge. Only about '
        '40-60 pixels of leftward extension beyond its original reach is '
        'needed, because the boss is already enormous. Keep every original '
        'long horn and thin digit visible. A narrow brief violet trace may '
        'follow the actual hook edge during the fast cut, never a giant '
        'screen-filling beam or explosion hiding the plate detail. The thinner '
        'claw near the torso remains a guard and may flex for balance. At '
        '1.4-3.0 seconds flex the elbow to retract the giant forelimb and '
        'return to the original hanging scythe pose and left-facing ready '
        'head angle. One strike only, no second slash, spin, giant forward '
        'body lunge, teleport, rift movement, full-view turn, victim or blood. '
        'The body must remain attached to the SAME fixed portal throughout.'))}


def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    OUT.mkdir(exist_ok=True)
    if not (OUT/'source-original.png').exists():shutil.copy2(SOURCE,OUT/'source-original.png')
    assert digest(SOURCE)==digest(OUT/'source-original.png')
    source=Image.open(SOURCE).convert('RGBA');box=source.getchannel('A').getbbox();assert box
    reference=source.crop(box)
    if not (OUT/'reference.png').exists():reference.save(OUT/'reference.png')
    # Fill most of the native height, with fixed right-rift alignment and
    # an explicit margin for the original long leftmost hook.
    scale=min(HEIGHT*.90/reference.height,(WIDTH-100)/reference.width)
    size=(round(reference.width*scale),round(reference.height*scale))
    resized=reference.resize(size,Image.Resampling.LANCZOS)
    offset=((WIDTH-size[0])-7,(HEIGHT-size[1])//2)
    alpha=Image.new('RGBA',(WIDTH,HEIGHT));alpha.paste(resized,offset)
    assert alpha.getchannel('A').getbbox()[0]>=30
    alpha.save(OUT/'reference-native-alpha.png')
    canvas=Image.new('RGBA',alpha.size,(128,128,128,255));canvas.alpha_composite(alpha)
    buf=io.BytesIO();canvas.convert('RGB').save(buf,format='PNG')
    save(OUT/'source.json',dict(sourcePath=str(SOURCE),sourceSha256=digest(SOURCE),sourceUnchanged=True,
        sourceSize=list(source.size),cropBounds=list(box),referenceSize=list(reference.size),
        preparedSize=[WIDTH,HEIGHT],inputScale=scale,inputOffset=list(offset),
        visibleInputHeight=size[1],riftAnchorX=735,targetGameResolution=[1920,1080],
        preparation='Original pixels, alpha crop, one Lanczos scale and fixed placement; no generative source edit.',published=False))
    return buf.getvalue()


def main():
    prepared=prepare()
    pending_all=all((OUT/n/'native-v1-pending.json').exists() for n in ACTIONS)
    if not pending_all:ensure_idle();engine.start_comfy();release((8190,8191))
    records=[]
    for name,item in ACTIONS.items():
        folder=OUT/name;folder.mkdir(exist_ok=True);pending=folder/'native-v1-pending.json'
        if pending.exists():
            records.append(dict(action=name,**json.loads(pending.read_text(encoding='utf-8'))));continue
        (folder/'reference-prepared.png').write_bytes(prepared)
        uploaded=engine.upload_image(prepared,'dimensional-horror-standard-'+name+'.png')
        prompt=IDENTITY+item['prompt']+(
            ' Fixed camera and scale. Uniform flat neutral medium-GREY matte in every '
            'empty gap between the horns, forelimbs, digits, torso and rift. The grey '
            'is an extraction background, not a wall, floor, sky or scenery. No cast '
            'shadow, white sticker outline, text, new objects or extra creatures.')
        graph=engine.build_workflow(uploaded,prompt,3,WIDTH,HEIGHT,item['seed'],animation_type='custom',
            loop=item['loop'],facing='left',flat_background=True,blink_mode='none',motion_strength=item['strength'],
            sampling_mode='quality',workflow_id='standard',subject_type='creature')
        graph['10']['inputs']['steps']=STEPS
        graph['6']['inputs']['prompt']=graph['6']['inputs']['prompt'].replace(
            'The original subject scale, composition, silhouette, component proportions, linework and painted shading are retained.',
            'Retain original scale, part proportions, layered ink-and-cel armor and anchored right-side torso and portal. Existing head, neck and forelimb joints may articulate inside the fixed canvas. The portal and torso attachment never translate or rotate.')
        graph['15']['inputs'].pop('audio',None);graph.pop('14',None);graph.pop('5',None)
        prefix='dimensional_horror_standard_20261024/'+name;graph['16']['inputs']['filename_prefix']=prefix
        save(folder/'native-v1-workflow.json',graph)
        save(folder/'settings.json',dict(animationType=name,generationPromptType='custom',subjectType='creature',
            seed=item['seed'],width=WIDTH,height=HEIGHT,duration=3,fps=FPS,steps=STEPS,loop=item['loop'],
            facing='left',targetGameResolution=[1920,1080],riftAnchorX=735,workflowId='standard',
            samplingMode='quality',motionStrength=item['strength'],prompt=prompt,
            actualPrompt=graph['6']['inputs']['prompt'],sourceSha256=digest(SOURCE),
            outputPrefix=prefix,backgroundRemoval='deferred until user requests it',published=False,
            note='Standard 768x768, 40 steps, approximately 3 seconds at 24FPS. Separate new jobs; cancelled high-resolution prompts are not resumed.'))
        signature=hashlib.sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest()
        response=requests.post(engine.COMFY_URL+'/prompt',json=dict(prompt=graph),timeout=60)
        if not response.ok:raise RuntimeError(response.text[:2000])
        info=response.json();record=dict(signature=signature,promptId=info['prompt_id'],queueNumber=info.get('number'))
        save(pending,record);records.append(dict(action=name,**record));print('SUBMITTED',name,record['promptId'],flush=True)
        save(OUT/'generation-submissions.json',dict(comfyUrl=engine.COMFY_URL,outputRoot=str(ROOT/'outputs/comfy'),
            records=records,requestedNativeResolution=[WIDTH,HEIGHT],steps=STEPS,targetGameResolution=[1920,1080],
            progressPolling=False,backgroundRemovalDeferred=True))
    print('STANDARD_BOSS_IDLE_ATTACK_SUBMITTED',flush=True)


if __name__=='__main__':main()
