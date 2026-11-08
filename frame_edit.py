"""Queued local image edits on one frame. Outside-mask RGB and original alpha are exact."""
import io
import json
from pathlib import Path
import secrets
import requests
from PIL import Image, ImageOps
import rigging_engine as rigging


def run_job(jid, p):
    root=Path(p['_workspaceRoot'])
    folder=root/p['workspaceId']
    source=folder/p['sourceFile']
    target=folder/'candidates'/jid
    target.mkdir(parents=True,exist_ok=True)
    input_path=rigging.INPUT_ROOT/('frame_edit_'+jid+'.png')
    try:
        with Image.open(source) as opened: original=opened.convert('RGBA')
        with Image.open(folder/p['maskFile']) as opened: mask=opened.convert('L')
        # Crop around the requested area to spend model resolution on a face or hand.
        box=mask.getbbox()
        if not box:raise ValueError('수정할 영역을 칠해 주세요.')
        pad=max(32,box[2]-box[0],box[3]-box[1])
        crop=(max(0,box[0]-pad),max(0,box[1]-pad),min(original.width,box[2]+pad),min(original.height,box[3]+pad))
        reference=original.crop(crop)
        background=Image.new('RGB',reference.size,'white');background.paste(reference,mask=reference.getchannel('A'))
        rigging.INPUT_ROOT.mkdir(parents=True,exist_ok=True);background.save(input_path)
        seed=secrets.randbelow(2**32)
        graph=rigging.qwen21_workflow(input_path.name,'frame_edit_'+jid,768,20,seed)
        graph['5']['inputs']['prompt']=('Edit this exact 2D game character image. '+p['prompt']+
            ' Preserve the identity, original drawing style, face angle, outfit, colors, pose and composition. '
            'Keep feature locations and the existing character silhouette. No text, no new background.')
        update_job(jid,state='generating',message='선택 프레임의 칠한 영역 수정 중 · 다른 프레임은 유지됩니다.')
        response=requests.post(rigging.COMFY_URL+'/prompt',json={'prompt':graph},timeout=60)
        if not response.ok:raise RuntimeError('프레임 수정 워크플로 오류: '+response.text[:400])
        record=rigging._wait_for_prompt(response.json()['prompt_id'])
        with Image.open(rigging._saved_image(record,'9')) as opened:
            generated=opened.convert('RGBA').resize(reference.size,Image.Resampling.LANCZOS)
        full=original.copy();full.paste(generated,crop[:2])
        edited=Image.composite(full,original,mask)
        edited.putalpha(original.getchannel('A'))
        edited.save(target/'candidate.png')
        meta=dict(revision=p['revision'],frame=p['frame'],workspaceId=p['workspaceId'],seed=seed)
        (target/'candidate.json').write_text(json.dumps(meta),encoding='utf-8')
        update_job(jid,state='complete',message='수정 후보 완료 · 비교 후 적용하세요.',candidate=meta)
    finally:
        input_path.unlink(missing_ok=True)


def update_job(jid,**changes):pass  # replaced by the FIFO worker
