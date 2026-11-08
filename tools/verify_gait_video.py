"""Private temporal-model walk/run comparison; never unlocks a production profile."""
import base64
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

import av
from PIL import Image,ImageDraw
import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import idle_tool as engine
import sprite_workflows
from tools.verify_rpg_sprite_styles import ensure_idle


def main():
    out=ROOT/'outputs/gait-video-20261018'
    source=ROOT/'outputs/pose-walk-smoke-20261018-fullbody-walk/frames/walk/original-000.png'
    original_status=sprite_workflows.status
    def local_status(root):
        profiles=original_status(root);profiles[1]['ready']=profiles[1]['installed'];return profiles
    engine.RESULT_ROOT=out
    for action in ('walk','run'):
        ensure_idle()
        target=out/action
        if target.exists():raise RuntimeError('Do not overwrite an existing experiment: '+str(target))
        for port in (8190,8191):
            try:requests.post(f'http://127.0.0.1:{port}/free',json=dict(unload_models=True,free_memory=True),timeout=30).raise_for_status()
            except requests.ConnectionError:pass
        payload=dict(workflowId='fasth3-sprite',width=512,height=512,duration=3,seed=20261018,
                     animationType=action,facing='right',prompt=engine.ANIMATION_DEFAULTS[action],loop=True,
                     motionStrength='high',motionPadding=10,frameCount=12,removeBackground=False,
                     stabilize=False,optimizeLoop=False,filename='gait-reference.png',
                     imageData=base64.b64encode(source.read_bytes()).decode())
        engine.JOBS[action]=dict(state='queued')
        print('START temporal '+action,flush=True);started=time.monotonic()
        with patch.object(sprite_workflows,'status',local_status):engine.run_job(action,payload)
        result=dict(engine.JOBS[action],seconds=round(time.monotonic()-started,2),source=str(source),
                    note='Private installed FastH3 test; no production gate change. No per-frame stabilization or loop optimization.')
        target.mkdir(parents=True,exist_ok=True)
        (target/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        if result['state']!='complete':raise RuntimeError(result['message'])
        frames=[f.to_image() for f in av.open(str(target/(action+'_raw.mp4'))).decode(video=0)]
        montage=Image.new('RGB',(4*512,2*512))
        for i in range(8):
            n=round(i*(len(frames)-1)/7);x,y=i%4*512,i//4*512
            montage.paste(frames[n],(x,y));ImageDraw.Draw(montage).text((x+8,y+8),f'{n/24:.2f}s',fill='white')
        montage.save(target/'motion-review.webp')
        print('DONE '+action+' '+str(result['seconds'])+'s',flush=True)
    requests.post(engine.COMFY_URL+'/free',json=dict(unload_models=True,free_memory=True),timeout=30).raise_for_status()


if __name__=='__main__':main()
