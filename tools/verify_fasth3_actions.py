"""Manual isolated GPU action tests. Does not unlock the production profile."""
import base64
import json
from pathlib import Path
import sqlite3
import sys
import time
from unittest.mock import patch

import av
import requests
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import idle_tool as engine
import sprite_workflows


def ensure_idle():
    with sqlite3.connect(f'file:{ROOT / "data/team.sqlite3"}?mode=ro', uri=True) as con:
        active = con.execute("SELECT count(*) FROM jobs WHERE state NOT IN ('complete','error','cancelled')").fetchone()[0]
    queue = requests.get(engine.COMFY_URL+'/queue', timeout=10).json()
    if active or queue['queue_running'] or queue['queue_pending']:
        raise RuntimeError('Queue busy; retry when idle')


def smoke_fixture(path):
    # Synthetic diagnostic graphic, not a generated or production art asset.
    im = Image.new('RGB', (512, 512), 'black')
    d = ImageDraw.Draw(im)
    d.polygon([(125,418),(144,349),(188,306),(177,264),(199,213),(259,194),
               (268,145),(310,98),(359,80),(391,113),(389,159),(358,198),
               (312,227),(303,270),(272,310),(228,327),(196,366),(170,400)], fill='#087e9b')
    d.polygon([(138,401),(169,340),(211,307),(206,261),(228,223),(278,212),
               (300,158),(341,121),(368,116),(356,158),(321,199),
               (283,240),(270,283),(222,312),(188,354)], fill='#35d9ce')
    d.polygon([(162,370),(190,326),(239,293),(240,249),(272,226),
               (301,200),(279,250),(271,281),(236,313),(201,331)], fill='#c4fff0')
    im.save(path)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    out = ROOT/'outputs/experiments/fasth3-actions'
    out.mkdir(parents=True, exist_ok=True)
    smoke_fixture(out/'synthetic-smoke.png')
    cases = [
        ('walk', ROOT/'ComfyUI/input/h3_idle_8f31946848_reference.png', dict(
            animationType='walk', facing='right', loop=True,
            prompt='A full-body soldier walks in place facing screen right. Complete two alternating steps: lift the near foot, swing it forward, plant it, then repeat with the far foot. Knees bend naturally. Keep the rifle held steady in both hands, keep the character centered, preserve the costume and weapon.')),
        ('club', ROOT/'ComfyUI/input/h3_idle_ebca14cb14_reference.png', dict(
            animationType='attack', facing='preserve', loop=False,
            prompt='The fighter performs one clear strike with the existing spiked wooden club: raise the club-bearing arm for anticipation, swing the club forward in one broad downward arc, follow through, then settle into a ready stance. Keep one wooden club, the same armor and both feet visible. The club remains rigid and connected to the hand.')),
        ('smoke', out/'synthetic-smoke.png', dict(animationType='custom', loop=True,
            prompt='A flat hand-painted cyan magical smoke effect on a pure black background. Anchor its narrow lower-left tail in place. The cyan ribbon curls and flows slowly upward and to the right, with gentle continuous deformation and a few fading wisps near its tip. Preserve the cyan and turquoise palette and flat illustration style. The entire effect stays within the canvas. Static camera, no zoom. A seamless three-second loop.')),
    ]
    original_status = sprite_workflows.status
    original_build = engine.build_workflow
    def local_status(root):
        profiles = original_status(root)
        profiles[1]['ready'] = profiles[1]['installed']
        return profiles
    for name, source, settings in cases:
        ensure_idle()
        job = 'fasth3-actions-20261016-'+name
        if (engine.RESULT_ROOT/job/'validation.json').exists():
            print('Already tested: '+job, flush=True)
            continue
        payload = dict(workflowId='fasth3-sprite',width=512,height=512,duration=3,seed=42,
                       frameCount=12,removeBackground=True,stabilize=False,optimizeLoop=False,
                       motionPadding=20 if name=='club' else 0,filename=source.name,
                       imageData=base64.b64encode(source.read_bytes()).decode(),**settings)
        def build(*args, **kwargs):
            graph = original_build(*args, **kwargs)
            if name == 'smoke':
                alignment = graph['6']['inputs']['prompt'].split('\n\n')[0]
                graph['6']['inputs']['prompt'] = (alignment+'\n\nintegrated_multimodal_description: [Shot 1] '
                    +settings['prompt']+'\n\noverall_soundscape: N/A\n\nnon_diegetic_music: N/A')
            return graph
        engine.JOBS[job] = dict(state='queued')
        print('START '+name, flush=True)
        started = time.monotonic()
        with patch.object(sprite_workflows,'status',local_status), patch.object(engine,'build_workflow',build):
            engine.run_job(job,payload)
        result = dict(engine.JOBS[job],elapsedSeconds=round(time.monotonic()-started,2),source=str(source),
                      note='Raw motion test: stabilization and loop optimization disabled; synthetic fixture for smoke.')
        folder=engine.RESULT_ROOT/job
        folder.mkdir(parents=True,exist_ok=True)
        (folder/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False),flush=True)
        if result['state'] != 'complete':
            raise RuntimeError(result['message'])
        frames=[f.to_image() for f in av.open(str(folder/(settings['animationType']+'_raw.mp4'))).decode(video=0)]
        montage=Image.new('RGB',(512*4,512*2))
        for i in range(8):
            n=round(i*(len(frames)-1)/7)
            x,y=i%4*512,i//4*512
            montage.paste(frames[n],(x,y))
            ImageDraw.Draw(montage).text((x+8,y+8),f'{n/24:.2f}s',fill='white')
        montage.save(folder/'motion-review.jpg')


if __name__=='__main__':
    main()
