"""Resume/export the saved second whole-body sweep experiment without changing its graph."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import verify_cp01_dynamic_slash as run
from PIL import Image
import sprite_gif

run.OUT=ROOT/'outputs/cp01-dynamic-sweep-20261023'
settings=json.loads((run.OUT/'attack/settings.json').read_text(encoding='utf-8'))
run.ACTION=dict(run.ACTION,seed=settings['seed'],title='전진 스텝 + 앞에서 뒤로 횡베기')
run.PROMPT=settings['prompt']


def retime():
    folder=run.OUT/'attack'
    meta=json.loads((folder/'frames.json').read_text(encoding='utf-8'))
    indices=meta['previewSourceIndices']
    assert indices==list(range(6,40)), 'Use the reviewed interval for phase timing'
    durations=[]
    for index in indices:
        durations.append(100 if index==39 else 1000/(24 if index<20 else 40 if index<32 else 30))
    ticks=[0];total=0.
    for value in durations:
        total+=value;ticks.append(round(total))
    times=[b-a for a,b in zip(ticks,ticks[1:])]
    positions=[indices.index(i) for i in meta['sourceIndices']]
    bounds=[ticks[i] for i in positions]+[ticks[-1]]
    selected_times=[b-a for a,b in zip(bounds,bounds[1:])]
    images=[Image.open(folder/'all-frames'/f'frame-{i:03d}.png').convert('RGBA').crop(meta['previewCropBounds']).resize((512,512),Image.Resampling.LANCZOS) for i in indices]
    images[0].save(folder/'animation.webp',save_all=True,append_images=images[1:],duration=times,loop=0,lossless=True)
    data,gif=sprite_gif.encode(images,times);(folder/'animation.gif').write_bytes(data)
    timing=dict(method='Forward native frames only, phase-specific playback; no new or reversed poses',
        anticipationSourceFrames=[6,19],anticipationFPS=24,strikeSourceFrames=[20,31],strikeFPS=40,
        followThroughSourceFrames=[32,38],followThroughFPS=30,finalHoldMs=100,totalMs=ticks[-1])
    meta.update(previewDurationMs=times,durationMs=selected_times,gif=gif,phaseTiming=timing)
    (folder/'frames.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    game=json.loads((folder/'game-frames.json').read_text(encoding='utf-8'))
    game.update(previewDurationMs=times,durationMs=selected_times,phaseTiming=timing)
    (folder/'game-frames.json').write_text(json.dumps(game,ensure_ascii=False,indent=2),encoding='utf-8')
    run.compare();run.build()
    print('PHASE_TIMING_READY',timing,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['all','generate','export','build','check','compare','retime'])
    stage=parser.parse_args().stage
    if stage=='all':run.generate();run.export();retime();run.check()
    elif stage=='retime':retime()
    else:getattr(run,stage)()
