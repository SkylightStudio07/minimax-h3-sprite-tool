"""CPU smoke of existing character footage; no generation or gallery changes."""
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import idle_tool as engine

if __name__=='__main__':
    out=ROOT/'outputs/sprite-background-smoke-20261018';out.mkdir(exist_ok=True)
    source=ROOT/'outputs/results/0286b9aa15555fc56aac3742bfb7155f/idle.mp4'
    before=hashlib.sha256(source.read_bytes()).hexdigest();start=time.monotonic()
    engine.make_sprite_sheet(source,out/'original.png',4,True,out/'transparent.png',24,'ai')
    original=Image.open(out/'original.png').convert('RGBA');cutout=Image.open(out/'transparent.png').convert('RGBA')
    assert original.size==cutout.size
    a=np.asarray(original);b=np.asarray(cutout)
    assert np.array_equal(a[:,:,:3],b[:,:,:3]),'RGB changed'
    alpha=b[:,:,3];assert (alpha<16).any() and (alpha>240).any()
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    (out/'verification.json').write_text(json.dumps(dict(seconds=round(time.monotonic()-start,2),size=cutout.size,rgbPreserved=True,sourceUnchanged=True,transparentFraction=float((alpha<16).mean()),opaqueFraction=float((alpha>240).mean()),method='Anime Segmentation ISNet CPU'),indent=2),encoding='utf-8')
    w,h=cutout.size;checker=Image.new('RGBA',(w,h),'#ddd');draw=ImageDraw.Draw(checker)
    for y in range(0,h,24):
        for x in range(0,w,24):
            if (x//24+y//24)%2:draw.rectangle((x,y,x+23,y+23),fill='#fff')
    checker.alpha_composite(cutout)
    preview=Image.new('RGB',(w,h*2));preview.paste(original.convert('RGB'),(0,0));preview.paste(checker.convert('RGB'),(0,h));preview.thumbnail((1400,1000));preview.save(out/'comparison.webp')
    print((out/'verification.json').read_text(),flush=True)
