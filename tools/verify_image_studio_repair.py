"""Private real generation checks for seed limits and selectable additional styles."""
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import image_engine as image
from tools.verify_rpg_sprite_styles import ensure_idle


def main():
    ensure_idle();out=image.ROOT/'outputs/image-studio-repair-20261018';out.mkdir(exist_ok=False)
    cases=[('default',dict()),('additional',dict(model='flanime-xl',styleId='epic-seven-sprites',styleStrength=.6))]
    records=[]
    for name,settings in cases:
        ensure_idle()
        p=image.validate(dict(prompt='adult female knight, short silver hair, navy coat, black boots, full body, plain white background',width=512,height=768,background='keep',count=1,**settings))
        result={};start=time.monotonic()
        def update(jid,**changes):result.update(changes)
        with patch.object(image,'RESULT_ROOT',out),patch.object(image,'update_job',update):image.run_job(name,p)
        with Image.open(out/name/'image-1.png') as im:
            metadata=json.loads(im.info['sprite_lab']);assert metadata['seed']==p['seed']
            if name=='additional':assert metadata['styleId']=='epic-seven-sprites'
            else:assert metadata['seed']<=2**50
            record=dict(name=name,model=p['model'],style=p.get('styleId'),seed=p['seed'],size=list(im.size),seconds=round(time.monotonic()-start,2))
        records.append(record);(out/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(record),flush=True)


if __name__=='__main__':main()
