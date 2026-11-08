"""Finish a visual experiment whose history poll timed out; never submits inference again."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
import motion_identity
import pose_motion as motion

ROOT=Path(__file__).resolve().parents[1]


def main():
    out=ROOT/'outputs/pose-walk-smoke-20261018-identity'
    source=out/'motions/walk-test'
    prompt=json.loads((ROOT/'outputs/pose-consistency-20261018/recovery-prompt.json').read_text())['promptId']
    print('Waiting for the existing fourth-frame prompt; no new request submitted.',flush=True)
    record=motion_identity.wait_for_prompt(prompt,timeout=1200)
    with Image.open(motion_identity.rig._saved_image(record,'9')) as opened:
        raw=opened.convert('RGBA').resize((512,768),Image.Resampling.LANCZOS)
    raw.save(source/'edit-raw-003.png')
    folder=out/'frames/walk';folder.mkdir(parents=True,exist_ok=True)
    poses=motion.walking()
    frames=[]
    for i in range(4):
        with Image.open(source/f'edit-raw-{i:03d}.png') as opened:image=motion.image_background.remove(opened.convert('RGBA'))
        aligned,alignment=motion.align_frame(image,(512,768));name=f'original-{i:03d}.png';aligned.save(folder/name)
        frames.append(dict(file=name,locked=False,alignment=alignment))
    doc=dict(revision=0,width=512,height=768,columns=4,rows=1,fps=8,frames=frames,
        motion=dict(consistency='reference-edit',appearanceAnchorFrame=0,identityVersion='fixed-anchor-v1',poses=poses,seed=20261018,facing='right',model='qwen-image-2.1-edit'),
        validation=dict(historyTimeoutRecovered=True,inferenceResubmitted=False))
    (out/'document.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
    montage=Image.new('RGB',(4*512,768),(90,90,90))
    for i,f in enumerate(frames):
        with Image.open(folder/f['file']) as im:montage.paste(im,(i*512,0),im.getchannel('A'))
    montage.save(out/'frames.webp')
    print('Recovered four-frame experiment successfully.',flush=True)


if __name__=='__main__':main()
