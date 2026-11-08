"""Reference-conditioned edits for walking frames; no style LoRA is added here."""
from pathlib import Path
import secrets
import time
import requests
from PIL import Image

import image_background
import image_pose
import rigging_engine as rig


def ready():
    return all(p.is_file() for p in rig.QWEN_MODEL_PATHS) and image_background.status()['ready']


def workflow(reference_name,pose_name,prefix,seed,resolution=768):
    graph=rig.qwen21_workflow(reference_name,prefix,resolution,20,seed)
    graph['10']=dict(class_type='LoadImage',inputs=dict(image=pose_name))
    graph['5']['inputs']['images.image_2']=['10',0]
    graph['6']['inputs'].update(device='cpu',dtype='default')
    return graph


def wait_for_prompt(prompt_id,timeout=1800):
    """Polling can time out while the GPU backend holds its event loop; never resubmit."""
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        try:
            response=requests.get(rig.COMFY_URL+'/history/'+prompt_id,timeout=15)
            response.raise_for_status()
            record=response.json().get(prompt_id)
        except (requests.Timeout,requests.ConnectionError):
            time.sleep(4)
            continue
        if record:
            if record.get('status',{}).get('status_str')=='error':
                raise RuntimeError('원화 보존 편집 실패: '+str(record.get('status',{}).get('messages',[]))[-800:])
            return record
        time.sleep(4)
    raise TimeoutError('원화 보존 편집 상태 확인이 30분을 초과했습니다. 원본과 이전 결과는 유지됩니다.')


def edit_frame(reference,pose,size,seed,prompt,folder,index):
    """Use one fixed appearance reference, rather than recursively editing previous frames."""
    token=secrets.token_hex(12)
    source=rig.INPUT_ROOT/('motion_identity_'+token+'.png')
    target=rig.INPUT_ROOT/('motion_pose_'+token+'.png')
    rig.INPUT_ROOT.mkdir(parents=True,exist_ok=True)
    completed=False
    try:
        reference.save(source)
        image_pose.render(pose,size).save(target)
        graph=workflow(source.name,target.name,'motion_identity_'+token,seed)
        graph['5']['inputs']['prompt']=prompt
        response=requests.post(rig.COMFY_URL+'/prompt',json=dict(prompt=graph),timeout=60)
        if not response.ok:raise RuntimeError('원화 보존 편집 워크플로 실패: '+response.text[:400])
        record=wait_for_prompt(response.json()['prompt_id'])
        with Image.open(rig._saved_image(record,'9')) as image:
            raw=image.convert('RGBA').resize(size,Image.Resampling.LANCZOS)
        raw.save(Path(folder)/f'edit-raw-{index:03d}.png')
        edited=image_background.remove(raw)
        if not edited.getchannel('A').getbbox():raise RuntimeError('원화 보존 편집의 배경 제거 결과가 비어 있습니다.')
        completed=True
        return edited
    finally:
        source.unlink(missing_ok=True);target.unlink(missing_ok=True)
        if completed:
            # Do not retain several large reference-prefix caches across a long batch
            # on a 16GB GPU. The PNG appearance anchor remains fixed on disk.
            try:
                requests.post(rig.COMFY_URL+'/free',json=dict(unload_models=True,free_memory=True),timeout=30)
            except requests.RequestException:pass
