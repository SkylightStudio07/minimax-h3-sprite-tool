"""Replace just the two approved v4 idles in a new complete handoff."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import av
import numpy as np
from PIL import Image,ImageDraw
from tools import export_big_three_final as final

PREVIOUS=ROOT/'outputs/big-three-final-20261024'
GENERATED=ROOT/'outputs/big-three-subtle-idle-20261024'
OUT=ROOT/'outputs/big-three-subtle-final-20261024'
REPLACEMENTS={'01-etienne-vasseur','02-desmond-kilroy'}
final.OUT=OUT
final.batch.OUT=OUT
final.batch.NOTES['01-etienne-vasseur']['idle']='원래 권총 조준 자세를 유지하며 어깨의 작은 호흡과 총구의 미세한 움직임만 보이는 잔잔한 대기입니다.'
final.batch.NOTES['02-desmond-kilroy']['idle']='소총을 낮게 든 원래 자세를 유지하며 작은 호흡과 총구 미세 움직임만 보입니다. 총을 들어 조준하는 동작은 제외했습니다.'

def save(path,obj):final.save(path,obj)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def prepare():
    OUT.mkdir(exist_ok=True)
    previous_selection=json.loads((PREVIOUS/'take-selection.json').read_text(encoding='utf-8'))
    records=[]
    for case in final.batch.CASES:
        cid=case['id'];root=OUT/cid;root.mkdir(exist_ok=True)
        for name in ['source-original.png','source.json','reference.png']:
            if not (root/name).exists():shutil.copy2(PREVIOUS/cid/name,root/name)
        prepared=[]
        for action in ['idle','attack']:
            replaced=cid in REPLACEMENTS and action=='idle'
            source=(GENERATED if replaced else PREVIOUS)/cid/action
            folder=root/action
            if not folder.exists():shutil.copytree(source,folder)
            if replaced:
                raw=ROOT/'outputs/comfy/big_three_subtle_idle_20261024'/cid/'idle_00001_.mp4'
                if not (folder/'raw.mp4').exists():shutil.copy2(raw,folder/'raw.mp4')
                assert digest(raw)==digest(folder/'raw.mp4')
                shutil.copy2(folder/'native-v4-workflow.json',folder/'native-v1-workflow.json')
                save(folder/'selected-take.json',dict(originalFolder=str(source),generationVersion=4,
                    rawSource=str(raw),workflowAlias='native-v1-workflow.json is an exact copy of native-v4-workflow.json',
                    userSelected=True,selection='Quiet breathing and tiny muzzle drift; no aim-raising gesture.'))
                version=4
            else:
                assert digest(source/'raw.mp4')==digest(folder/'raw.mp4')
                version=next(r['selectedVersion'] for r in previous_selection['selectedTakes'] if r['character']==cid and r['action']==action)
            with av.open(str(folder/'raw.mp4')) as video:
                assert float(video.streams.video[0].average_rate)==24
                frames=[f.to_image() for f in video.decode(video=0)]
            assert len(frames)==73 and all(f.size==(768,768) for f in frames)
            if not (folder/'review-raw.webp').exists():
                contact=Image.new('RGB',(1600,960));draw=ImageDraw.Draw(contact)
                for n,i in enumerate(np.linspace(0,72,15).round().astype(int)):
                    contact.paste(frames[i].resize((320,320)),(n%5*320,n//5*320));draw.text((n%5*320+8,n//5*320+8),str(i),fill='red')
                contact.save(folder/'review-raw.webp',quality=95)
            prepared.append(digest(folder/'reference-prepared.png'))
            records.append(dict(character=cid,action=action,selectedVersion=version,rawPreserved=True))
        assert len(set(prepared))==1
    save(OUT/'take-selection.json',dict(selectedTakes=records,matchingPreparedCanvasPerCharacter=True,
        earlierTakesPreserved=True,previousHandoff=str(PREVIOUS),replacementScope='Desmond and Etienne idle only'))
    print('SUBTLE_HANDOFF_INPUTS_READY',flush=True)

def process():
    prepare();final.process()

def samples():
    prepare();final.review_samples()

def package():
    # Native RGBA cells for the retained four actions must remain identical.
    for case in final.batch.CASES:
        cid=case['id']
        for action in ['idle','attack']:
            if cid in REPLACEMENTS and action=='idle':continue
            old=PREVIOUS/cid/action;new=OUT/cid/action
            assert digest(old/'raw.mp4')==digest(new/'raw.mp4')
            assert digest(old/'native-sheet.png')==digest(new/'native-sheet.png')
    final.package()
    report=dict(replacedIdles=sorted(REPLACEMENTS),retainedNativeSheetsUnchanged=True,
        earlierHandoffPreserved=True,newHandoff=str(OUT),newIdlesApprovedByUser=True)
    save(OUT/'replacement-validation.json',report)
    plan_path=ROOT/'outputs/big-three-motion-20261024/handoff-plan.json'
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    plan.update(status='handoff-complete',finalOutput=str(OUT),remainingHandoff=None,
        mattePausedDuringGeneration=False,selectedIdleVersion=4)
    save(plan_path,plan)
    print('SUBTLE_IDLE_REPLACEMENT_COMPLETE',flush=True)

if __name__=='__main__':globals()[sys.argv[1] if len(sys.argv)>1 else 'samples']()
