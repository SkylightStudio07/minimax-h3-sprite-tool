"""Compare identity-anchor img2img strengths and two-image Qwen pose transfer."""
import base64
import io
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
import requests
import image_engine as engine
import pose_motion as motion
import rigging_engine as rig
from tools.verify_rpg_sprite_styles import ensure_idle

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/pose-consistency-20261018'


def data(im):
    buf=io.BytesIO();im.save(buf,'PNG');return 'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()


def main():
    OUT.mkdir(exist_ok=True)
    doc=json.loads((ROOT/'outputs/pose-walk-smoke-20261018-adjusted/document.json').read_text(encoding='utf-8'))
    anchor=Image.open(ROOT/'outputs/pose-walk-smoke-20261018-adjusted/frames/walk/original-000.png').convert('RGBA')
    pose=doc['motion']['poses'][2]
    engine.update_job=lambda jid,**changes:print(json.dumps(changes,ensure_ascii=True)[:300],flush=True)
    for denoise in (.5,.65):
        name=f'anchor-{round(denoise*100)}';folder=OUT/name
        if (folder/'image-1.png').exists():continue
        ensure_idle();previous=engine.RESULT_ROOT;engine.RESULT_ROOT=OUT
        try:
            p=engine.validate(dict(model='wai-cutscene-counter',preset='illustration',mode='reference',imageData=data(anchor),
                prompt='the exact same woman and identical outfit as the reference, same purple hair, same hood, identical long black coat with red lining, same gloves, identical black trousers and boots, walking in place, taking a walking step, full body, side view, facing right, no outfit changes, no redesign',
                negativePrompt='different clothes, different hairstyle, skirt, dress, shorts, bare legs, extra limbs, text, watermark, halo',width=512,height=768,steps=24,cfg=4.5,count=1,seed=20261018,denoise=denoise,background='transparent',pose=pose))
            engine.run_job(name,p)
        finally:engine.RESULT_ROOT=previous
    ensure_idle()
    for address in [engine.COMFY_URL,engine.image_soya.URL]:
        try:requests.post(address+'/free',json=dict(unload_models=True,free_memory=True),timeout=30).raise_for_status()
        except requests.ConnectionError:pass
    input1=rig.INPUT_ROOT/'pose_consistency_reference.png';input2=rig.INPUT_ROOT/'pose_consistency_target.png'
    base=Image.new('RGB',anchor.size,'white');base.paste(anchor,mask=anchor.getchannel('A'));base.save(input1)
    motion.image_pose.render(pose,anchor.size).save(input2)
    try:
        graph=rig.qwen21_workflow(input1.name,'pose_consistency_qwen',768,20,20261018)
        graph['10']=dict(class_type='LoadImage',inputs=dict(image=input2.name))
        graph['5']['inputs']['images.image_2']=['10',0]
        graph['5']['inputs']['prompt']='Use the exact character in image 1. Change only her body pose to follow the colored skeleton in image 2. Keep the identical face, hairstyle, hood, long black coat with red lining, sleeves, gloves, trousers and boots from image 1. Keep every garment design and all colors unchanged. Render one full-body 2D game sprite on plain white background, the same size and composition as image 1. Do not draw the skeleton. Walking in place, facing right, opposite leg forward from image 1.'
        response=requests.post(rig.COMFY_URL+'/prompt',json=dict(prompt=graph),timeout=60);response.raise_for_status()
        history=rig._wait_for_prompt(response.json()['prompt_id'])
        with Image.open(rig._saved_image(history,'9')) as im:im.save(OUT/'qwen-pose.png')
    finally:input1.unlink(missing_ok=True);input2.unlink(missing_ok=True)
    print('Compare anchor-50, anchor-65 and qwen-pose.png',flush=True)


if __name__=='__main__':main()
