"""Only rerun Desmond and Van Rieden idle; keep the original takes intact."""
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

OUT=ROOT/'outputs/big-three-idle-retry-20261024'
MOTIONS={
 '02-desmond-kilroy':(
    'A quiet WATCHFUL LOW-READY IDLE, with a STATIONARY LOWER BODY. From the belt '
    'through the pelvis, thighs, knees, shins and both boots, hold the opening drawing '
    'in exactly the SAME screen position, height, silhouette and joint angles for the '
    'whole shot. The initially bent knees simply stay bent at the same angle. The '
    'pelvis remains at one constant height; each boot stays planted on the exact '
    'opening contact pixel. All intentional movement is ABOVE THE BELT. The helmet '
    'and masked head make one slow tiny purposeful inclination while checking the '
    'screen-left sector, then ease back. The chest and shoulders make a very small '
    'aim correction with the existing rifle, at most 5-8 pixels at the suppressor '
    'tip, keeping it near the original diagonal DOWN-LEFT low-ready angle. Both '
    'hands retain their original grip points and the barrel stays rigid. Very slight '
    'scarf and loose strap follow-through only. The red mask lens stays an intact '
    'lens and the face never becomes exposed. Keep the hip mug, belt and leg '
    'equipment stationary with the lower body. Quiet composed observation, no '
    'whole-body vertical rhythm, knee flexing, squat, weight-transfer cycle, bouncing, '
    'marching, dancing or pumping. No firing, smoke, gun raise to shoulder, reload '
    'or foot sliding. One tiny upper-body adjustment over three seconds, matching '
    'the opening pose and motion phase at the end.'),
 '03-van-rieden':(
    'A composed veteran hunter IDLE with a STATIONARY LOWER BODY. From the belt '
    'through pelvis, both thighs, knees, shins and boot soles, keep the exact opening '
    'drawing in the SAME screen coordinates and at a constant height throughout '
    'the shot. Pants creases, knee angles and both planted boot contacts remain '
    'unchanged. This character is standing still, calmly observing SCREEN LEFT. '
    'Only animate the small upper details: the head makes a slow slight downward '
    'inclination of about 2 degrees and returns, the cigar follows the mouth, a '
    'thin small smoke curl continuously rises from the actual cigar tip and fades. '
    'One tiny finger-pressure adjustment on the cane handle is allowed, but the '
    'cane remains straight and its tip stays FIXED at the opening ground contact. '
    'A small gentle air current moves the free lower edge of the leopard cape '
    'behind the legs by about 5-10 pixels, with delayed cloth follow-through; the '
    'legs themselves remain still. The holster-side hand stays beside the holstered '
    'revolver and the back rifle remains slung. Keep the hat, face, beard and body '
    'scale unchanged. No vertical body rhythm, alternating knee bends, hip dipping, '
    'squatting, springing, marching, dancing, cane lifting, gun draw or shooting. '
    'No large chest inflation or whole-body breathing sway. A quiet upper-detail '
    'loop over three seconds, matching opening pose and cape motion phase at the end.')}

def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    OUT.mkdir(exist_ok=True);cases=[c for c in CASES if c['id'] in MOTIONS]
    needed=any(not (OUT/c['id']/'idle/native-v2-pending.json').exists() for c in cases)
    if needed:ensure_idle();engine.start_comfy();release((8190,8191))
    records=[]
    for case in cases:
        root=OUT/case['id'];root.mkdir(exist_ok=True);folder=root/'idle';folder.mkdir(exist_ok=True)
        pending=folder/'native-v2-pending.json'
        if pending.exists():
            records.append(dict(case=case['id'],action='idle',**json.loads(pending.read_text(encoding='utf-8'))));continue
        original=PREVIOUS/case['id']
        for name in ['source-original.png','reference.png','source.json']:
            if not (root/name).exists():shutil.copy2(original/name,root/name)
        assert digest(INPUT/(case['label']+'.png'))==digest(root/'source-original.png')
        prepared=(original/'idle/reference-prepared.png').read_bytes()
        (folder/'reference-prepared.png').write_bytes(prepared)
        uploaded=engine.upload_image(prepared,case['id']+'-stationary-legs-idle-v2.png')
        prompt=(case['identity']+MOTIONS[case['id']]+' Retain the exact original 2D hand-inked '
            'illustration and painted cel shadows. No glossy 3D transformation or photorealistic '
            'relighting. Fixed camera, constant scale and light. The whole subject stays inside '
            'the frame. Uniform flat medium-GREY matte in every exposed gap, including between '
            'legs, arm and cane; no floor, ground shadow, white sticker rim, scene or extra props.')
        seed=case['seed']+100
        graph=engine.build_workflow(uploaded,prompt,3,768,768,seed,animation_type='custom',loop=True,
            facing='preserve',flat_background=True,blink_mode='none',motion_strength='low',
            sampling_mode='quality',workflow_id='standard',subject_type='human',image_guided=True)
        graph['10']['inputs']['steps']=40
        graph['15']['inputs'].pop('audio',None);graph.pop('14',None);graph.pop('5',None)
        prefix='big_three_idle_retry_20261024/'+case['id']+'/idle';graph['16']['inputs']['filename_prefix']=prefix
        save(folder/'native-v2-workflow.json',graph)
        save(folder/'settings.json',dict(animationType='idle',generationPromptType='custom',subjectType='human',
            caseId=case['id'],label=case['label'],seed=seed,width=768,height=768,duration=3,fps=24,steps=40,
            loop=True,facing='preserve',motionPadding=case['padding'],referenceOffsetX=0,motionStrength='low',
            workflowId='standard',samplingMode='quality',motionPromptMode='image-guided',prompt=prompt,
            actualPrompt=graph['6']['inputs']['prompt'],outputPrefix=prefix,sourceSha256=digest(root/'source-original.png'),
            previousTake=str(original/'idle/raw.mp4'),backgroundRemoval='deferred until user requests it',
            note='New idle only: stationary pelvis/knees/boots, tiny upper-body/equipment details. Previous take and all attacks preserved.',published=False))
        signature=hashlib.sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest()
        response=requests.post(engine.COMFY_URL+'/prompt',json=dict(prompt=graph),timeout=60)
        if not response.ok:raise RuntimeError(response.text[:2000])
        info=response.json();record=dict(signature=signature,promptId=info['prompt_id'],queueNumber=info.get('number'))
        save(pending,record);records.append(dict(case=case['id'],label=case['label'],action='idle',**record))
        save(OUT/'generation-submissions.json',dict(comfyUrl=engine.COMFY_URL,outputRoot=str(ROOT/'outputs/comfy'),
            records=records,steps=40,requestedNativeResolution=[768,768],progressPolling=False,
            backgroundRemovalDeferred=True,scope='Desmond and Van Rieden idle v2 only; attacks unchanged'))
        print('SUBMITTED_IDLE_V2',case['id'],record['promptId'],flush=True)
    assert len(records)==2
    print('BOTH_STATIONARY_LEG_IDLES_SUBMITTED',flush=True)

if __name__=='__main__':main()
