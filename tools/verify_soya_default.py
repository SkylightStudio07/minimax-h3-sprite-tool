"""Authenticated isolated queue smoke test using the real default GPU runner."""
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_engine
import team_server
from verify_fasth3_actions import ensure_idle


def main():
    ensure_idle()
    out=ROOT/'outputs/soya-default-smoke-20261017'
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temp,patch.object(image_engine,'RESULT_ROOT',out):
        root=Path(temp)
        app=team_server.create_app(root,image_runner=image_engine.run_job)
        client=app.test_client()
        def post(path,payload):
            return client.post('/api/'+path,json=payload,headers={'X-Sprite-Request':'1'})
        response=post('register',dict(username='smoke',name='local smoke',password='local-smoke-password',setupCode=(root/'admin-setup-code.txt').read_text()))
        assert response.status_code in (200,201),response.status_code
        assert post('login',dict(username='smoke',password='local-smoke-password')).status_code==200
        # No model specified: exercise the server's new default, not a test override.
        response=post('images/generate',dict(prompt='Adult woman, short silver bob hair, teal eyes, fully covered black tactical jacket, holding a radio, upper body, gray background',seed=202610170,background='transparent'))
        assert response.status_code==202,response.json
        jid=response.json['jobId']
        start=time.monotonic()
        app.start_worker()
        try:
            while time.monotonic()-start<600:
                job=client.get('/api/jobs/'+jid).json
                if job['state']=='complete':break
                if job['state'] in ('error','cancelled'):raise RuntimeError(job)
                time.sleep(2)
            else:raise TimeoutError('Queue smoke test did not finish')
            folder=out/jid
            with Image.open(folder/'image-1.png') as im:
                assert im.size==(1536,1536),im.size
                assert im.mode=='RGBA',im.mode
                assert im.getchannel('A').getextrema()[0]<255
                metadata=json.loads(im.info['sprite_lab'])
                assert metadata['model']=='soya-anima-flanime'
                assert metadata['outputWidth']==1536
            assert (folder/'image-1-original.png').exists()
            gallery=client.get('/api/gallery?type=image').json
            assert gallery['total']==1,gallery
            result=dict(state='passed',jobId=jid,seconds=round(time.monotonic()-start,2),model=metadata['model'],outputSize=[1536,1536],background='transparent',gallery=True)
            (out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            print(json.dumps(result),flush=True)
        finally:
            app.stop_worker()
            time.sleep(1)


if __name__=='__main__':main()
