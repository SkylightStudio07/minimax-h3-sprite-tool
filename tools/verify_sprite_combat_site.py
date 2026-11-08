"""Replay the accepted AI clip through the production runner. No new GPU job."""
import base64
import io
import json
from pathlib import Path
import sys
from unittest.mock import Mock, patch
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import idle_tool as engine
import sprite_gif


def main():
    source=ROOT/'outputs/chibi-ai-effects-20261020'
    out=ROOT/'outputs/site-combat-check-20261020'
    p=dict(imageData=base64.b64encode((source/'reference.png').read_bytes()).decode(),width=768,height=640,
           seed=2026102031,animationType='attack',loop=True,duration=3,frameCount=30,motionPadding=0,
           facing='right',samplingMode='quality',workflowId='standard',stabilize=False,optimizeLoop=False,
           combatEffect='blue_slash',effectStrength='normal',effectDescription='',pixelOutput=True,
           pixelColorLock=True,removeBackground=True,backgroundRemoval='flat',prompt='one sword attack and recovery')
    result={}
    def update(jid,**changes):result.update(changes)
    response=Mock(ok=True);response.json.return_value={'prompt_id':'existing-accepted-clip'}
    history=Mock();history.json.return_value={'existing-accepted-clip':{'status':{'completed':True}}}
    with patch.object(engine,'RESULT_ROOT',out),patch.object(engine,'upload_image',return_value='ref.png'),\
         patch.object(engine,'update_job',side_effect=update),patch.object(engine.requests,'post',return_value=response) as post,\
         patch.object(engine.requests,'get',return_value=history),patch.object(engine,'find_saved_video',return_value=source/'attack-raw.mp4'):
        engine.run_job('ai-effects',p)
    assert result['state']=='complete',result
    graph=post.call_args.kwargs['json']['prompt']
    assert 'cyan-blue energy crescent' in graph['6']['inputs']['prompt']
    assert graph['10']['inputs']['steps']==20
    report=result['pixelExport'];assert (report['width'],report['height'],report['frameCount'])==(192,160,30)
    assert report['colors']<=48 and report['separateEffectLayers'] is False
    folder=out/'ai-effects'
    with Image.open(folder/'attack_transparent.png') as sheet:
        a=np.array(sheet);assert set(np.unique(a[:,:,3]))<={0,255}
        assert np.any((a[:,:,0]<100)&(a[:,:,1]>140)&(a[:,:,2]>180)&(a[:,:,3]>0))
        frames=sprite_gif.split_sheet(sheet,8,4,30)
    data,info=sprite_gif.encode(frames,report['durationMs']);(folder/'animation.gif').write_bytes(data)
    assert abs(info['totalMs']-3042)<=10
    validation=dict(passed=True,source='existing accepted MiniMax joint AI effects clip; no new GPU generation',
                    actualBrowserVerified=False,runnerResult=result,gif=info)
    (out/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS production runner, audited workflow, actual 73-frame AI clip, 192x160/30-frame pixel sheet, new effect colors, binary alpha, GIF timing, edge warning',flush=True)


if __name__=='__main__':main()
