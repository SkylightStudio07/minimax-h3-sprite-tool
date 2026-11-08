"""Write visual acceptance samples. This does not enable the production feature."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_background


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('images',nargs='*')
    args=parser.parse_args()
    files=[Path(p) for p in args.images] or sorted((ROOT/'outputs/style-validation-20261015').glob('*-0.5.png'))
    if not files:raise RuntimeError('Supply character PNGs to compare')
    with image_background.MODEL.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==image_background.SHA256
    folder=ROOT/'outputs/background-validation-20261015';folder.mkdir(exist_ok=True)
    sheet=Image.new('RGB',(900,470*len(files)),'#ffffff')
    records=[]
    for i,p in enumerate(files):
        im=Image.open(p).convert('RGBA');started=time.monotonic()
        cut=image_background.remove(im)
        assert cut.size==im.size
        assert np.array_equal(np.asarray(cut)[:,:,:3],np.asarray(im)[:,:,:3]), 'RGB was modified'
        cut.save(folder/(p.stem+'-transparent.png'))
        a=np.asarray(cut.getchannel('A'))
        records.append(dict(file=str(p),seconds=round(time.monotonic()-started,2),transparentFraction=float((a<10).mean()),opaqueFraction=float((a>245).mean())))
        for col,bg in enumerate((None,'#ffffff','#405060')):
            preview=Image.new('RGBA',im.size,bg or 'white');preview.alpha_composite(im if col==0 else cut)
            preview.thumbnail((300,438))
            sheet.paste(preview.convert('RGB'),(col*300,i*470+26))
            ImageDraw.Draw(sheet).text((col*300+5,i*470+6),p.stem+' / '+('original' if col==0 else bg),fill='black')
        print(records[-1],flush=True)
    sheet.save(folder/'anime-model-comparison.jpg')
    (folder/'results.json').write_text(json.dumps(records,indent=2),encoding='utf-8')


if __name__=='__main__':main()
