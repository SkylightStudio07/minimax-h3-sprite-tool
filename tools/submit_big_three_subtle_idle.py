"""Two restrained breathing idles; keep every previous take and attack intact."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import requests
import idle_tool as engine
from tools.submit_big_three_motion import CASES,OUT as PREVIOUS,INPUT
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release

OUT=ROOT/'outputs/big-three-subtle-idle-20261024'
ORDER=['02-desmond-kilroy','01-etienne-vasseur']
MOTION=(
    'An extremely RESTRAINED combat-ready BREATHING IDLE, already quietly in progress. '
    'The opening pose is the permanent resting pose for this entire shot. Keep the '
    'pelvis, trouser silhouette, knee angles, lower legs and both boot contacts '
    'stationary in their exact opening screen coordinates and at a constant height. '
    'Keep the original head angle and gaze steady. There is NO independent head '
    'gesture, head scan, deliberate nod, tilt or side-to-side head shaking. The '
    'only intended movement is a tiny, smooth breathing relaxation in the shoulders '
    'and soft collar cloth, about ONE to TWO pixels at 768px canvas size. The '
    'solid plate carrier and jacket retain their width, volume and plate spacing; '
    'breathing never inflates the armour or bobs the whole body. The existing gun '
    'follows the holding forearm with an extremely SMALL gentle muzzle drift of '
    'only TWO to FOUR pixels, rather than a visible aim adjustment. The gun stays '
    'rigid and at almost exactly its original angle and height. A single unhurried '
    'small breathing cycle over three seconds, with matching opening and closing '
    'pose, motion phase and speed. At game scale this reads as a composed still '
    'ready stance with a little life, not an action demonstration. No weight '
    'transfer, hip sway, knee flexing, squatting, marching, torso pumping, rocking '
    'back and forth, repeated arm movement, gun raising, aiming gesture, recoil, '
    'firing, flash, smoke, reload or change of grip. Keep scarf and loose clothing '
    'almost still; no wind-driven flapping. Preserve face covering and visor shape. ')
DETAILS={
 '02-desmond-kilroy':(
    'Both gloved hands remain at their ORIGINAL rifle grip points. Keep the '
    'rifle at its exact original diagonal DOWN-LEFT LOW-READY angle, stock in its '
    'opening position, never bringing it up to the shoulder or sights. The '
    'original bent knees stay at exactly those angles. The belt, hip mug and '
    'leg equipment stay stationary; no mug swinging. '),
 '01-etienne-vasseur':(
    'Keep the original pistol arm extended SCREEN LEFT at the opening height, '
    'with the suppressor almost perfectly horizontal. Do not lift, retract or '
    'sweep this arm. The opposite hand keeps the closed silver-grey briefcase '
    'hanging at its EXACT original screen position and angle, without any '
    'pendulum sway, hand lifting or case opening. Retain the original crossed '
    'leg pose, straight support leg and hip height. ')}

def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    OUT.mkdir(exist_ok=True);cases={c['id']:c for c in CASES}
    needed=any(not (OUT/cid/'idle/native-v4-pending.json').exists() for cid in ORDER)
    if needed:ensure_idle();engine.start_comfy();release((8190,8191))
    records=[]
    for cid in ORDER:
        case=cases[cid];root=OUT/cid;root.mkdir(exist_ok=True)
        folder=root/'idle';folder.mkdir(exist_ok=True);pending=folder/'native-v4-pending.json'
        if pending.exists():
            records.append(dict(case=cid,action='idle',**json.loads(pending.read_text(encoding='utf-8'))));continue
        previous=PREVIOUS/cid
        for name in ['source-original.png','reference.png','source.json']:
            if not (root/name).exists():shutil.copy2(previous/name,root/name)
        assert digest(INPUT/(case['label']+'.png'))==digest(root/'source-original.png')
        prepared=(previous/'idle/reference-prepared.png').read_bytes()
        (folder/'reference-prepared.png').write_bytes(prepared)
        uploaded=engine.upload_image(prepared,cid+'-subtle-breathing-idle-v4.png')
        prompt=(case['identity']+MOTION+DETAILS[cid]+' Preserve the exact original 2D '
            'hand-inked illustration, cel-painted shading and colours. No glossy 3D '
            'render or realistic relighting. Fixed camera, framing, magnification '
            'and illumination. Uniform flat medium-GREY matte in every exposed '
            'gap between legs, arms and equipment. No floor, cast shadow, white '
            'sticker rim, scenery or new objects. Keep the full original subject inside the canvas.')
        seed=case['seed']+400
        graph=engine.build_workflow(uploaded,prompt,3,768,768,seed,animation_type='idle',loop=True,
            facing='preserve',flat_background=True,blink_mode='none',motion_strength='low',
            sampling_mode='quality',workflow_id='standard',subject_type='human',image_guided=True)
        graph['6']['inputs']['prompt']=graph['6']['inputs']['prompt'].replace(
            'Allow the described head inclination and natural shoulder/pelvis counterrotation and joint articulation.',
            'Maintain the starting head angle and stationary pelvis; allow only the extremely small breathing and muzzle drift specified below.')
        graph['10']['inputs']['steps']=40
        graph['15']['inputs'].pop('audio',None);graph.pop('14',None);graph.pop('5',None)
        prefix='big_three_subtle_idle_20261024/'+cid+'/idle';graph['16']['inputs']['filename_prefix']=prefix
        save(folder/'native-v4-workflow.json',graph)
        save(folder/'settings.json',dict(animationType='idle',subjectType='human',caseId=cid,label=case['label'],
            seed=seed,width=768,height=768,duration=3,fps=24,steps=40,loop=True,facing='preserve',
            motionPadding=case['padding'],referenceOffsetX=0,motionStrength='low',workflowId='standard',
            samplingMode='quality',motionPromptMode='image-guided',prompt=prompt,
            actualPrompt=graph['6']['inputs']['prompt'],sourceSha256=digest(root/'source-original.png'),
            outputPrefix=prefix,backgroundRemoval='deferred until user requests it',published=False,
            note='Restrained breathing and tiny muzzle drift only; no head gestures, aim raising, hip or leg motion.'))
        signature=hashlib.sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest()
        response=requests.post(engine.COMFY_URL+'/prompt',json=dict(prompt=graph),timeout=60)
        if not response.ok:raise RuntimeError(response.text[:2000])
        info=response.json();record=dict(signature=signature,promptId=info['prompt_id'],queueNumber=info.get('number'))
        save(pending,record);records.append(dict(case=cid,label=case['label'],action='idle',**record))
        save(OUT/'generation-submissions.json',dict(comfyUrl=engine.COMFY_URL,outputRoot=str(ROOT/'outputs/comfy'),
            records=records,steps=40,requestedNativeResolution=[768,768],progressPolling=False,
            backgroundRemovalDeferred=True,scope='Desmond and Etienne idle v4 only: quiet breathing and tiny muzzle drift'))
        print('SUBMITTED_SUBTLE_IDLE',cid,record['promptId'],flush=True)
    assert len(records)==2
    print('BOTH_SUBTLE_BREATHING_IDLES_SUBMITTED',flush=True)

if __name__=='__main__':main()
