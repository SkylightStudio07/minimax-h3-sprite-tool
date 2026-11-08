"""Actual four-frame walk/run experiment, private disposable outputs only."""
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image,ImageDraw
import pose_motion as motion
from tools.verify_rpg_sprite_styles import ensure_idle

def main():
    ensure_idle()
    root=Path(__file__).resolve().parents[1]/'outputs'/('pose-walk-smoke-20261018'+('-'+sys.argv[1] if len(sys.argv)>1 else ''))
    action=sys.argv[2] if len(sys.argv)>2 else 'walk'
    task=action+'-test';folder=root/'motions'/task;folder.mkdir(parents=True,exist_ok=False)
    source=Path('outputs/rigging/5ed3fddd3383252008ecd0c8e7dce9df/source-original.png')
    shutil.copyfile(source,folder/'reference.png')
    p=motion.validate(dict(action=action,fps=6 if action=='run' else 4,poses=motion.gait(action),prompt='adult woman, purple bob hair, black hood, black long coat with red lining, black fitted trousers, black boots, mechanical glove, preserve the outfit',size='512x768',seed=20261018))
    p.update(_motionRoot=str(root/'motions'),_frameRoot=str(root/'frames'),workspaceId=action)
    events=[]
    def update(jid,**changes):
        if not events or events[-1].get('message')!=changes.get('message'):print(json.dumps(changes,ensure_ascii=True),flush=True)
        events.append(changes)
    motion.update_job=update
    doc=motion.run_job(task,p)
    (root/'document.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
    montage=Image.new('RGB',(4*512,768),(90,90,90))
    for i in range(4):
        with Image.open(root/'frames'/action/doc['frames'][i]['file']) as im:montage.paste(im,(i*512,0),im.getchannel('A'))
    montage.save(root/'frames.webp')
    poses=Image.new('RGB',(4*256,384))
    for i,pose in enumerate(p['poses']):poses.paste(motion.image_pose.render(pose,(256,384)),(i*256,0))
    poses.save(root/'poses.png')
    frames=[]
    for item in doc['frames']:
        with Image.open(root/'frames'/action/item['file']) as im:
            bg=Image.new('RGB',im.size,(50,55,65));bg.paste(im,mask=im.getchannel('A'));frames.append(bg)
    frames[0].save(root/'animation.webp',save_all=True,append_images=frames[1:],duration=round(1000/doc['fps']),loop=0)
    print('Completed 4 pose-conditioned frames; inspect frames.webp for temporal quality.',flush=True)

if __name__=='__main__':main()
