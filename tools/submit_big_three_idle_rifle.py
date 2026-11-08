"""Two more active upper-body idles and Van Rieden's original back-rifle attack."""
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

OUT=ROOT/'outputs/big-three-idle-rifle-20261024'
JOBS=[
 ('02-desmond-kilroy','idle','normal',2026102783,(
    'An alert soldier IDLE with a meaningful RIFLE HANDLING action, not just a nodding '
    'head. The original bent-leg stance, pelvis height, knee angles and both boot '
    'contacts remain stationary throughout. Animate the upper body and existing '
    'rifle only. From 0.0-0.6 seconds he holds the original rifle at diagonal '
    'DOWN-LEFT low ready, making a small natural 10-15 pixel forearm and muzzle '
    'sway while the head quietly checks the left sector. At 0.6-1.3 seconds BOTH '
    'HANDS smoothly LIFT THE SAME RIFLE to his shoulder; the muzzle rises visibly '
    'from diagonal down-left to near-horizontal LEFT and the stock seats at the '
    'shoulder. The shoulders, upper chest, elbows and masked head coordinate this '
    'movement. He brings the optic to the masked sight line, rather than moving '
    'only his neck. At 1.3-2.2 seconds briefly AIM screen LEFT with a little living '
    'muzzle drift, held steady but not a frozen cutout. At 2.2-3.0 seconds smoothly '
    'LOWER the rifle back to the original diagonal low-ready angle and opening '
    'motion phase. The support hand stays on the fore-end and trigger hand on the '
    'grip throughout; the barrel, stock, optic and suppressor remain ONE rigid '
    'weapon assembly. Small scarf and clothing follow-through. Keep waist, hips '
    'and legs quiet: no squat, alternating knee bends, marching or rhythmic '
    'whole-body pumping. Exactly one occasional aim check, no continuous repetitive '
    'up-down gun exercise. No shot, muzzle flash, smoke, reload or face reveal.')),
 ('03-van-rieden','idle','normal',2026102785,(
    'A calm cigar-smoking veteran hunter IDLE with noticeably animated CIGAR SMOKE '
    'and free cape edges. Keep the pelvis, original trouser silhouette, knee angles '
    'and both boot contacts at their opening coordinates and constant height. '
    'The planted cane tip remains fixed and its shaft stays straight. The head '
    'makes one small slow natural inclination, with a slight coordinated shoulder '
    'settling above the belt, then returns. The mouth keeps the cigar in its '
    'original corner. Produce CLEARLY VISIBLE medium-density pale grey-white '
    'SMOKE from the ACTUAL LIT CIGAR TIP: two small curling strands continuously '
    'rise about 40-70 pixels, stretch and curl irregularly in a gentle air current, '
    'then thin and dissipate. Smoke flows and changes shape instead of being '
    'a fixed painted wisp. It is stronger than a barely visible tiny thread but '
    'does not cover the face, hat or entire character. No smoke from the gun, '
    'boots or cane. The leopard cape hem and long free panel behind the legs '
    'sway gently about 10-18 pixels with delayed cloth movement. One small '
    'gloved finger adjustment on the cane handle is allowed, without lifting '
    'the cane or changing body support. The other hand remains beside the '
    'holstered revolver; the back rifle stays slung for this IDLE. Keep the '
    'hat and white beard intact. No knee flexing, hip dip, torso pumping, '
    'marching, dancing, gun draw or shooting. Smooth three-second loop returning '
    'to the opening upper-body pose and cloth phase, smoke still flowing.')),
 ('03-van-rieden','attack','high',2026102786,(
    'Use the ORIGINAL LONG WOOD-STOCK RIFLE SLUNG ON HIS BACK for ONE shot toward '
    'SCREEN LEFT, then return it to the back. The holstered silver revolver stays '
    'in its holster and is NEVER drawn or fired. Keep the cane held in its original '
    'screen-left hand, tip planted; this powerful hunter fires the rifle one-handed '
    'with its stock firmly BRACED AGAINST HIS SHOULDER. At 0.0-0.7 seconds the '
    'holster-side gloved hand reaches back over the shoulder, grasps the ORIGINAL '
    'back rifle and brings that SAME weapon forward. Its long brown wooden '
    'stock and straight silver-dark metal barrel maintain their original shape '
    'and length. The back position becomes EMPTY as the rifle comes forward: '
    'there is exactly ONE long rifle, never a copy still left on the back. '
    'At 0.7-1.2 seconds seat its butt against the shoulder, aiming the long '
    'barrel approximately horizontally SCREEN LEFT, supported by the bent '
    'firing arm and shoulder. The head follows the rifle sights, hat and cigar '
    'remain attached. At 1.2-1.5 seconds fire ONE brief shot from the actual '
    'LEFTMOST TIP OF THIS LONG RIFLE BARREL. A compact orange-white muzzle '
    'flash, tiny quickly fading smoke puff, short rifle recoil into the shoulder, '
    'and coordinated upper-torso recoil. The lower body stays grounded, no '
    'squat or vertical pumping. At 1.5-3.0 seconds lower and swing that SAME '
    'rifle back onto its original sling behind the shoulder, then return the '
    'firing hand beside the holstered revolver. The back rifle reappears only '
    'when the same held rifle has been put back. Cane remains in the opposite '
    'hand throughout. No added gun, revolver shot, firing cane, new helper arm, '
    'barrel bending, screen-filling blast, environment relighting or camera '
    'movement. Keep the entire long muzzle and compact flash inside the canvas.')),
]

def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    OUT.mkdir(exist_ok=True);cases={c['id']:c for c in CASES}
    needed=any(not (OUT/c/a/'native-v3-pending.json').exists() for c,a,*_ in JOBS)
    if needed:ensure_idle();engine.start_comfy();release((8190,8191))
    records=[]
    for cid,action,strength,seed,motion in JOBS:
        case=cases[cid];root=OUT/cid;root.mkdir(exist_ok=True)
        folder=root/action;folder.mkdir(exist_ok=True);pending=folder/'native-v3-pending.json'
        if pending.exists():
            records.append(dict(case=cid,action=action,**json.loads(pending.read_text(encoding='utf-8'))));continue
        original=PREVIOUS/cid
        for name in ['source-original.png','reference.png','source.json']:
            if not (root/name).exists():shutil.copy2(original/name,root/name)
        assert digest(INPUT/(case['label']+'.png'))==digest(root/'source-original.png')
        prepared=(original/action/'reference-prepared.png').read_bytes()
        (folder/'reference-prepared.png').write_bytes(prepared)
        uploaded=engine.upload_image(prepared,cid+'-'+action+'-active-upper-v3.png')
        identity=case['identity']
        if cid=='03-van-rieden' and action=='attack':
            old='The original wood-stock long rifle remains SLUNG ON THE BACK throughout; do not draw it.'
            assert old in identity
            identity=identity.replace(old,'There is exactly ONE original wood-stock long rifle, initially slung on the back; use this existing rifle for the requested shot and return it to its sling.')
        prompt=(identity+motion+' Preserve the exact original 2D hand-inked illustration, cel-painted '
            'shadows, colours, face and equipment. No glossy 3D render or photorealistic relighting. '
            'Fixed camera and scale. Flat uniform medium-GREY matte in all exposed gaps, including '
            'between legs and held items. No floor, cast shadow, white sticker rim, scenery or extra '
            'subject. All original equipment, boots, hat, cane and compact effects stay inside the frame.')
        graph=engine.build_workflow(uploaded,prompt,3,768,768,seed,animation_type='custom',loop=action=='idle',
            facing='preserve',flat_background=True,blink_mode='none',motion_strength=strength,
            sampling_mode='quality',workflow_id='standard',subject_type='human',image_guided=True)
        graph['10']['inputs']['steps']=40
        graph['15']['inputs'].pop('audio',None);graph.pop('14',None);graph.pop('5',None)
        prefix='big_three_idle_rifle_20261024/'+cid+'/'+action;graph['16']['inputs']['filename_prefix']=prefix
        save(folder/'native-v3-workflow.json',graph)
        save(folder/'settings.json',dict(animationType=action,generationPromptType='custom',subjectType='human',
            caseId=cid,label=case['label'],seed=seed,width=768,height=768,duration=3,fps=24,steps=40,
            loop=action=='idle',facing='preserve',motionPadding=case['padding'],referenceOffsetX=0,
            motionStrength=strength,workflowId='standard',samplingMode='quality',motionPromptMode='image-guided',
            prompt=prompt,actualPrompt=graph['6']['inputs']['prompt'],sourceSha256=digest(root/'source-original.png'),
            outputPrefix=prefix,backgroundRemoval='deferred until user requests it',published=False))
        signature=hashlib.sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest()
        response=requests.post(engine.COMFY_URL+'/prompt',json=dict(prompt=graph),timeout=60)
        if not response.ok:raise RuntimeError(response.text[:2000])
        info=response.json();record=dict(signature=signature,promptId=info['prompt_id'],queueNumber=info.get('number'))
        save(pending,record);records.append(dict(case=cid,label=case['label'],action=action,**record))
        save(OUT/'generation-submissions.json',dict(comfyUrl=engine.COMFY_URL,outputRoot=str(ROOT/'outputs/comfy'),
            records=records,steps=40,requestedNativeResolution=[768,768],progressPolling=False,
            backgroundRemovalDeferred=True,scope='Desmond active rifle idle, Van Rieden stronger cigar idle and back-rifle attack'))
        print('SUBMITTED_V3',cid,action,record['promptId'],flush=True)
    assert len(records)==3
    print('ALL_THREE_ACTIVE_UPPER_BODY_MOTIONS_SUBMITTED',flush=True)

if __name__=='__main__':main()
