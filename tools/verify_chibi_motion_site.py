"""Replay reviewed videos through production packing without submitting GPU work."""
import base64
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
from PIL import Image
import idle_tool as engine
OUT=ROOT/'outputs/site-chibi-reference-20261023'
SOURCE=ROOT/'outputs/chibi-reference-motion-20261023'


def main():
    OUT.mkdir(exist_ok=True)
    catalog=json.loads((ROOT/'web/assets/sprite-examples/catalog.json').read_text(encoding='utf-8'))
    reports={}
    for name in ('run','attack'):
        entry=next(x for x in catalog['examples'] if x['id']=='chibi-reference-'+name)
        recipe=entry['recipe']
        payload=dict(recipe,imageData=base64.b64encode((SOURCE/name/'reference.png').read_bytes()).decode(),
            assetSpec=dict(type='side',facing='right',directionCount=1))
        result={}
        post_response=Mock(ok=True)
        post_response.json.return_value={'prompt_id':'replay-'+name}
        history=Mock()
        history.json.return_value={'replay-'+name:{'status':{'completed':True,'status_str':'success'}}}
        with patch.object(engine,'RESULT_ROOT',OUT),patch.object(engine,'upload_image',return_value='reference.png'),\
            patch.object(engine,'update_job',side_effect=lambda jid,**kw:result.update(kw)),\
            patch.object(engine.requests,'post',return_value=post_response) as post,\
            patch.object(engine.requests,'get',return_value=history),\
            patch.object(engine,'find_saved_video',return_value=SOURCE/name/'raw.mp4'):
            engine.run_job(name,payload)
        assert result['state']=='complete',result
        assert result['transparentSheet'] and result['frameCount']==24
        assert result['backgroundRemoval']==recipe['backgroundRemoval']
        submitted=post.call_args.kwargs['json']['prompt']
        assert submitted['10']['inputs']['steps']==20
        assert recipe['prompt'] in submitted['6']['inputs']['prompt']
        assert 'plum-brown' not in submitted['6']['inputs']['prompt']
        with Image.open(OUT/name/'reference_prepared.png') as prepared,Image.open(SOURCE/name/'reference_prepared.png') as original:
            assert np.array_equal(np.asarray(prepared.convert('RGB')),np.asarray(original.convert('RGB')))
        raw=OUT/name/(name+'_raw.mp4')
        assert hashlib.sha256(raw.read_bytes()).digest()==hashlib.sha256((SOURCE/name/'raw.mp4').read_bytes()).digest()
        with Image.open(OUT/name/(name+'_transparent.png')) as im:
            assert im.getchannel('A').getextrema()==(0,255)
        reports[name]=dict(passed=True,gpuJobSubmitted=False,backgroundRemoval=result['backgroundRemoval'],
            originalSourcePreserved=True,preparedReferenceMatches=True,result=result)
        print('PASS production replay',name,flush=True)
    # Compare the deployed effect extractor with the previously reviewed final
    # attack frame. This verifies the actual sparks, beyond a synthetic mask test.
    import av
    with av.open(str(SOURCE/'attack/raw.mp4')) as clip:
        for i,frame in enumerate(clip.decode(video=0)):
            if i==18:
                actual=engine.image_background.remove_sprite_with_sparks(frame.to_image())
                expected=Image.open(SOURCE/'attack/spark-frames/frame-018.png').convert('RGBA')
                assert np.array_equal(np.asarray(actual),np.asarray(expected))
                break
    reports['approvedSparkFrameMatches']=True
    (OUT/'validation.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
