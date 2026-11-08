"""Production reference and masked-correction smoke without gallery records."""
import base64
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch
from PIL import Image, ImageDraw, ImageChops

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_engine as engine
from verify_rpg_sprite_styles import ensure_idle

OUT=ROOT/'outputs/reference-site-smoke-20261018'

def data(im):
    buf=io.BytesIO();im.save(buf,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()

def main():
    sys.stdout.reconfigure(encoding='utf-8');OUT.mkdir(exist_ok=True)
    original=Image.open(ROOT/'outputs/rigging/5ed3fddd3383252008ecd0c8e7dce9df/source-original.png').convert('RGBA')
    previous=json.loads((ROOT/'outputs/reference-battle-adjust-20261018/outfit-080.json').read_text())
    pose=json.loads((ROOT/'outputs/reference-battle-adjust-20261018/battle-080.json').read_text())['pose']
    request=dict(model='wai-cutscene-counter',mode='reference',prompt=previous['graph']['4']['inputs']['text'],negativePrompt=previous['graph']['5']['inputs']['text'],imageData=data(original),width=832,height=1216,steps=28,cfg=4.5,denoise=.8,seed=20261018,count=1,background='keep',pose=pose)
    events=[]
    with patch.object(engine,'RESULT_ROOT',OUT),patch.object(engine,'update_job',side_effect=lambda *a,**kw:events.append(kw)):
        ensure_idle();engine.run_job('reference',engine.validate(request))
        source=Image.open(OUT/'reference/image-1.png').convert('RGBA')
        mask=Image.new('RGB',source.size,'black');ImageDraw.Draw(mask).rectangle((0,560,260,1120),fill='white');mask.save(OUT/'mask.png')
        request.update(mode='inpaint',imageData=data(source),maskData=data(mask),pose=None,denoise=.3,prompt='long black coat, red lining, clean silhouette, grey background',seed=20261019)
        ensure_idle();engine.run_job('correction',engine.validate(request))
    after=Image.open(OUT/'correction/image-1.png').convert('RGBA')
    diff=ImageChops.difference(source.convert('RGB'),after.convert('RGB'))
    outside=Image.composite(diff,Image.new('RGB',diff.size),Image.eval(mask.convert('L'),lambda v:255-v))
    assert outside.getbbox() is None,'Unmasked pixels changed'
    assert diff.getbbox() is not None,'No correction generated'
    (OUT/'verification.json').write_text(json.dumps(dict(reference=True,maskedCorrection=True,unmaskedPixelsUnchanged=True,changedBox=diff.getbbox(),events=events),ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS: production reference + correction; unmasked pixels unchanged',flush=True)

if __name__=='__main__':main()
