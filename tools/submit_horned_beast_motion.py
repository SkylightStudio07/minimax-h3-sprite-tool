"""Submit horned harness-beast idle and leftward body lunge; no polling."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import requests
from PIL import Image
import numpy as np
from scipy import ndimage
import idle_tool as engine
from tools.verify_rpg_sprite_styles import ensure_idle
from tools.verify_pixel_female_combat import release

SOURCE=Path('Z:/Vertex/적/NAI-images_(2026-09-08_16-39-14)_1-of-1/0.2__artist_crimson comics___0.6__artist_dramz__, _0.5__artist_santa (sunflower) s-3108080225.png')
OUT=ROOT/'outputs/horned-beast-motion-20261024'
IDENTITY=(
    'Animate the EXACT SAME single enormous non-human quadruped beast from the input 2D '
    'illustration. Preserve its wolf-like head, thick hunched shoulder mane, charcoal and '
    'dark violet fur, visible pink scar lines, ONE original long angular black forehead horn '
    'pointing upper-left, pointed ears, glowing red eye, original curved tail behind the body '
    'and FOUR original muscular legs ending in large clawed paws. The heavy forelegs stay '
    'the dominant supports; do not turn the forelegs into human arms. Preserve the olive '
    'military body harness, its buckles and exact original strap routes. Keep the original '
    'gold-metal cage muzzle secured to the snout by the olive head straps. The metal muzzle '
    'has fixed rigid bars and the same form, remains attached throughout, never opens as a '
    'hinged mouth or disappears. The real teeth and small saliva strands behind/below it '
    'remain recognizable. The dark scars and harness move WITH the underlying anatomy '
    'instead of staying frozen in screen space. Same screen-LEFT-facing three-quarter '
    'view, red eye and snout left throughout. Original 2D hand-inked contours, fur clusters '
    'and flat painted cel shadows in every frame; no 3D render, realistic relighting or '
    'new anatomy, armour, extra horns, legs, heads or tails. ')
ACTIONS={
    'idle':dict(seed=2026102451,loop=True,strength='normal',prompt=(
        'A grounded menacing BEAST IDLE LOOP in the supplied stance. The original paw '
        'placements and hunched spine height stay nearly fixed; no repeated squats, '
        'bouncing, marching or walking. One slow subtle breathing cycle moves the shoulder '
        'mass and ribcage coherently, without inflating the harness or swelling isolated '
        'fur patches. The wolf head dips and turns a few degrees toward screen LEFT as '
        'it quietly snarls through the existing muzzle, then returns. One ear flicks '
        'once, the heavy mane tips bristle and settle, and the existing tail tip behind '
        'the body sways a small distance. Let only a few saliva strands below the mouth '
        'stretch and sway slightly; do not leave frozen painted drips. Small shoulder '
        'and wrist/paw pressure adjustments make the animal feel alive without changing '
        'the planted stance. The mouth can make a small snarl adjustment BEHIND the rigid '
        'cage muzzle, with the same teeth, never an enormous jaw yawn or biting through '
        'metal bars. Red eye stays aimed left and keeps its original shape. One unhurried '
        'cycle, smoothly returning to the original pose and phase in three seconds. '
        'No attack, leap, new effects, smoke, moving scenery or new objects.')),
    'attack':dict(seed=2026102452,loop=False,strength='high',prompt=(
        'Perform exactly ONE short powerful LEFTWARD SHOULDER-AND-HORN RAM followed by '
        'recovery. At 0.0-0.6 seconds brace the two original front paws, load the bent '
        'hind legs and draw the massive shoulder line slightly back. Head dips a little '
        'so the same forehead horn and muzzled snout aim diagonally forward-left, without '
        'hiding the red eye. At 0.6-1.2 seconds drive off the hind paws into ONE explosive '
        'short low body lunge toward SCREEN LEFT. Forelegs reach a short distance and '
        'plant to catch the heavy impact; the shoulders, spine, head and hindquarters '
        'all participate in the forceful motion. Keep forward body travel only about '
        '45-65 pixels on the 768px canvas, no long charge or offscreen jump. Attack with '
        'the existing heavy shoulder and forehead horn, not a human punch. The rigid '
        'gold-metal muzzle remains secured to the snout, following the head as one '
        'solid assembly. No biting through the muzzle, detaching straps or stretching '
        'horn/legs. The mane flares with the acceleration and the body scars and olive '
        'harness follow the moving torso. At 1.2-3.0 seconds the front paws absorb the '
        'impact, body rises only enough to regain support, then the beast takes compact '
        'recovery steps back to the original left-facing ready stance. Tail follows '
        'the impulse and settles. ONE attack only, no repeated lunges, full spin, rear '
        'view, standing on two legs, tumbling, victim, blood, beam, explosion or camera '
        'shake. Every paw, claw, horn tip, muzzle, fur tuft and tail stays inside the '
        'canvas with empty margins throughout.'))}




def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=True)
    if not (OUT/'source-original.png').exists():shutil.copy2(SOURCE,OUT/'source-original.png')
    assert digest(SOURCE)==digest(OUT/'source-original.png')
    if not (OUT/'reference.png').exists():
        im=Image.open(SOURCE).convert('RGBA');box=im.getchannel('A').getbbox();assert box
        a=np.array(im);rgb=a[:,:,:3].astype(float);alpha=a[:,:,3].copy()
        white=(rgb.min(2)>205)&(np.ptp(rgb,axis=2)<30);transparent=alpha<16
        allowed=white|transparent;seeds=transparent.copy()
        seeds[0]|=allowed[0];seeds[-1]|=allowed[-1];seeds[:,0]|=allowed[:,0];seeds[:,-1]|=allowed[:,-1]
        exterior=ndimage.binary_propagation(seeds,mask=allowed)
        # Preserve the saliva/teeth region while stripping exterior sticker white.
        yy,xx=np.indices(alpha.shape);mouth=(xx<im.width*.25)&(yy>im.height*.36)&(yy<im.height*.55)
        alpha[exterior&white&~mouth]=0;alpha[alpha<16]=0;a[:,:,3]=alpha;a[alpha==0,:3]=0
        im=Image.fromarray(a);box=im.getchannel('A').getbbox();assert box
        im=im.crop(box);canvas=Image.new('RGBA',(im.width+64,im.height+64));canvas.paste(im,(32,32));canvas.save(OUT/'reference.png')
    save(OUT/'source.json',dict(sourcePath=str(SOURCE),sourceSha256=digest(SOURCE),sourceUnchanged=True,
        referenceSha256=digest(OUT/'reference.png'),preparation='Exterior-connected white sticker rim stripped except teeth/saliva region; alpha crop and 32px border; no repainting.',published=False))
    pending_all=all((OUT/name/'native-v1-pending.json').exists() for name in ACTIONS)
    if not pending_all:ensure_idle();engine.start_comfy();release((8190,8191))
    records=[]
    for name,item in ACTIONS.items():
        folder=OUT/name;folder.mkdir(exist_ok=True);pending=folder/'native-v1-pending.json'
        if pending.exists():
            records.append(dict(action=name,**json.loads(pending.read_text(encoding='utf-8'))));continue
        prepared=engine.prepare_reference_image((OUT/'reference.png').read_bytes(),768,768,40)
        (folder/'reference-prepared.png').write_bytes(prepared)
        uploaded=engine.upload_image(prepared,'horned-beast-'+name+'.png')
        prompt=IDENTITY+item['prompt']+' Fixed camera, constant scale and lighting. Uniform flat neutral medium-grey matte in every empty gap; no floor, cast shadow, scenery, text or additional people. Entire quadruped, horn tip, muzzle, paws and tail stay within the canvas.'
        graph=engine.build_workflow(uploaded,prompt,3,768,768,item['seed'],animation_type='custom',
            loop=item['loop'],facing='left',flat_background=True,blink_mode='none',motion_strength=item['strength'],
            sampling_mode='quality',workflow_id='standard',subject_type='creature')
        graph['10']['inputs']['steps']=40
        text=graph['6']['inputs']['prompt'].replace(
            'The original subject scale, composition, silhouette, component proportions, linework and painted shading are retained.',
            'Retain the original overall scale, non-human body proportions, anatomy, harness, muzzle and ink-and-cel shading. The articulated silhouette can change naturally as the existing four legs, shoulder girdle, neck and tail move within the fixed camera.')
        graph['6']['inputs']['prompt']=text
        graph['15']['inputs'].pop('audio',None);graph.pop('14',None);graph.pop('5',None)
        prefix='horned_beast_20261024/'+name;graph['16']['inputs']['filename_prefix']=prefix
        save(folder/'native-v1-workflow.json',graph)
        save(folder/'settings.json',dict(animationType=name,subjectType='creature',generationPromptType='custom',seed=item['seed'],
            width=768,height=768,duration=3,fps=24,steps=40,loop=item['loop'],facing='left',motionPadding=40,
            referenceOffsetX=0,motionStrength=item['strength'],workflowId='standard',samplingMode='quality',
            prompt=prompt,actualPrompt=text,sourceSha256=digest(SOURCE),referenceSha256=digest(OUT/'reference.png'),
            outputPrefix=prefix,backgroundRemoval='deferred until user requests it',published=False))
        signature=hashlib.sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest()
        response=requests.post(engine.COMFY_URL+'/prompt',json=dict(prompt=graph),timeout=60)
        if not response.ok:raise RuntimeError(response.text[:2000])
        info=response.json();record=dict(signature=signature,promptId=info['prompt_id'],queueNumber=info.get('number'))
        save(pending,record);records.append(dict(action=name,**record));print('SUBMITTED',name,record['promptId'],flush=True)
    save(OUT/'generation-submissions.json',dict(comfyUrl=engine.COMFY_URL,outputRoot=str(ROOT/'outputs/comfy'),
        records=records,progressPolling=False,backgroundRemovalDeferred=True))
    print('BOTH_MOTIONS_SUBMITTED_NO_POLLING',flush=True)


if __name__=='__main__':main()
