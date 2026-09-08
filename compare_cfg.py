"""Private fixed-seed comparison. Reuses the exact prepared image and CFG 1.5 result."""
import json
import shutil
import sqlite3
import time
from pathlib import Path
import av
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_dilation
import idle_tool as engine

SOURCE='c55a23dba52cbc8fa6408984df9143da'
ROOT=engine.OUTPUT_ROOT/'experiments'/('cfg_compare_'+time.strftime('%Y%m%d_%H%M%S'))


def wait_for_idle():
    deadline=time.monotonic()+3600
    while time.monotonic()<deadline:
        con=sqlite3.connect('file:data/team.sqlite3?mode=ro',uri=True)
        n=con.execute("SELECT count(*) FROM jobs WHERE state NOT IN ('complete','error','cancelled')").fetchone()[0]
        con.close()
        q=engine.requests.get(engine.COMFY_URL+'/queue',timeout=15).json()
        if not n and not q.get('queue_running') and not q.get('queue_pending'):
            return
        print('Waiting for team GPU queue',flush=True)
        time.sleep(20)
    raise TimeoutError('Team queue remained busy; no jobs interrupted')


def generate(w,label):
    folder=ROOT/label;folder.mkdir()
    w['16']['inputs']['filename_prefix']='private_cfg_comparison/'+label
    (folder/'workflow.json').write_text(json.dumps(w,indent=2),encoding='utf-8')
    wait_for_idle()
    r=engine.requests.post(engine.COMFY_URL+'/prompt',json={'prompt':w},timeout=60)
    r.raise_for_status()
    pid=r.json()['prompt_id']
    (folder/'prompt_id.txt').write_text(pid)
    print(label+' submitted '+pid,flush=True)
    start=time.monotonic();last=start
    while time.monotonic()-start<2400:
        h=engine.requests.get(engine.COMFY_URL+'/history/'+pid,timeout=30).json().get(pid)
        if h:
            if h.get('status',{}).get('status_str')=='error':
                raise RuntimeError(json.dumps(h['status']))
            shutil.copy2(engine.find_saved_video(h),folder/'raw.mp4')
            print(label+' complete in '+str(round(time.monotonic()-start))+' seconds',flush=True)
            return folder/'raw.mp4'
        if time.monotonic()-last>=45:
            print(label+' running '+str(round(time.monotonic()-start))+' seconds',flush=True);last=time.monotonic()
        time.sleep(5)
    raise TimeoutError('Sampling still unfinished; consult saved prompt_id, do not resubmit blindly')


def summarize(paths,reference):
    original=np.array(Image.open(reference).convert('RGB'))
    foreground=np.max(np.abs(original.astype(float)-128),axis=2)>16
    # A conservative excluded region: do not score expected hair/limb motion as background drift.
    mask=~binary_dilation(foreground,iterations=48)
    panels=Image.new('RGB',(5*224,3*360),(25,28,34));draw=ImageDraw.Draw(panels)
    metrics={}
    for row,(label,path) in enumerate(paths.items()):
        with av.open(str(path)) as c:
            count=c.streams.video[0].frames
        indices=[round((count-1)*v) for v in (0,.25,.5,.75,1)]
        measurements=[]
        with av.open(str(path)) as c:
            for i,f in enumerate(c.decode(video=0)):
                if i not in indices:continue
                im=f.to_image().convert('RGB');a=np.array(im).astype(float)
                delta=np.max(np.abs(a-128),axis=2)
                if 0<i<count-1 and mask.any():
                    measurements.append(float(np.mean(delta[mask]>30)))
                thumb=im.copy();thumb.thumbnail((216,320))
                col=indices.index(i);panels.paste(thumb,(col*224+(224-thumb.width)//2,row*360+32))
                draw.text((col*224+6,row*360+8),f'{label} frame {i}',fill='white')
        metrics[label]={'mean_changed_background_fraction':float(np.mean(measurements)),
                        'sampled_changed_background_fractions':measurements,'raw_video':str(path)}
        engine.make_sprite_sheet(path,path.parent/'raw_sheet.png',8,True)
    panels.save(ROOT/'comparison.png')
    (ROOT/'metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    print(json.dumps(metrics),flush=True)
    print('COMPARISON '+str(ROOT/'comparison.png'),flush=True)


if __name__=='__main__':
    source=engine.RESULT_ROOT/SOURCE
    audit=json.loads((source/'generation_prompt.json').read_text(encoding='utf-8'))
    con=sqlite3.connect('file:data/team.sqlite3?mode=ro',uri=True)
    p=json.loads(con.execute('SELECT payload FROM jobs WHERE id=?',(SOURCE,)).fetchone()[0]);con.close()
    assert audit['negativeEnabled'] and audit['cfgScale']==1.5
    ROOT.mkdir(parents=True)
    print('OUTPUT '+str(ROOT),flush=True)
    reference=source/'reference_prepared.png'
    shutil.copy2(reference,ROOT/'reference.png')
    image_name=engine.upload_image(reference.read_bytes(),'cfg_comparison.png')
    paths={}
    for label,cfg in [('off',1.0),('cfg1.2',1.2)]:
        w=engine.build_workflow(image_name,p['prompt'],p['duration'],p['width'],p['height'],audit['seed'],
            p['animationType'],p['loop'],p['facing'],flat_background=audit['flatBackground'],
            blink_mode=p['blinkMode'],negative_enabled=cfg>1,negative_prompt=p['negativePrompt'],cfg_scale=cfg,sampling_mode='turbo')
        assert w['6']['inputs']['prompt']==audit['prompt'], 'Positive prompt changed: abort invalid comparison'
        if cfg>1:assert w['17']['inputs']['prompt']==audit['negativePrompt']
        paths[label]=generate(w,label)
    folder=ROOT/'cfg1.5';folder.mkdir()
    shutil.copy2(source/'idle_raw.mp4',folder/'raw.mp4')
    paths['cfg1.5']=folder/'raw.mp4'
    (ROOT/'source.json').write_text(json.dumps({'sourceJob':SOURCE,'audit':audit,'reusedCFG':1.5},indent=2),encoding='utf-8')
    summarize(paths,reference)
