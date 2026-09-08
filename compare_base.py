"""Compare saved Turbo4/CFG1 against base20/CFG1 without publishing results."""
import copy
import json
import shutil
import time
from pathlib import Path
import compare_cfg as trial

if __name__=='__main__':
    baseline=Path('outputs/experiments/cfg_compare_20260908_035351').resolve()
    trial.ROOT=Path('outputs/experiments')/('base_compare_'+time.strftime('%Y%m%d_%H%M%S'))
    trial.ROOT=trial.ROOT.resolve();trial.ROOT.mkdir(parents=True)
    w=json.loads((baseline/'off/workflow.json').read_text())
    original=copy.deepcopy(w)
    w.pop('7')
    w['10']['inputs']['model']=['2',0]
    w['10']['inputs']['steps']=20
    w['11']['inputs']['model']=['2',0]
    assert w['11']['class_type']=='BasicGuider'
    assert w['6']==original['6'] and w['8']==original['8']
    (trial.ROOT/'comparison_settings.json').write_text(json.dumps({
        'baseline':str(baseline/'off/raw.mp4'),'changed':['remove Turbo LoRA','4 -> 20 steps'],
        'seed':w['8']['inputs']['noise_seed'],'image':w['1']['inputs']['image'],
        'width':w['6']['inputs']['width'],'height':w['6']['inputs']['height'],
        'length':w['6']['inputs']['length'],'guidance':'BasicGuider (both)',
        'note':'Practical mode comparison, not a LoRA-only causal ablation.'},indent=2))
    print('OUTPUT '+str(trial.ROOT),flush=True)
    result=trial.generate(w,'base20')
    folder=trial.ROOT/'turbo4';folder.mkdir()
    shutil.copy2(baseline/'off/raw.mp4',folder/'raw.mp4')
    shutil.copy2(baseline/'reference.png',trial.ROOT/'reference.png')
    trial.summarize({'turbo4':folder/'raw.mp4','base20':result},trial.ROOT/'reference.png')
