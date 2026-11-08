"""Verify native hard-alpha grids and exact 3x presentation copies."""
import json
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'web'


def main():
    catalog=json.loads((ASSETS/'assets/sprite-examples/catalog.json').read_text(encoding='utf-8'))
    pixels=[x for x in catalog['examples'] if x['category']=='pixel']
    assert {x['id'] for x in pixels}=={'pixel-idle','pixel-walk','pixel-attack','pixel-energy'}
    assert {x['characterId'] for x in pixels}=={'chibi-anime-swordswoman-20261020'}
    records=[]
    for item in pixels:
        grid=item['pixelGrid'];w,h,count=grid['width'],grid['height'],grid['frames']
        assert item['recipe']['pixelOutput'] is True
        assert item['recipe']['width']==w*4 and item['recipe']['height']==h*4
        colors=set()
        with Image.open(ASSETS/item['animation']) as animation:
            assert animation.size==(w*3,h*3)
            assert animation.n_frames==count,(item['id'],animation.n_frames,count)
            for index in range(count):
                animation.seek(index);a=np.array(animation.convert('RGBA'))
                assert set(np.unique(a[:,:,3]))<={0,255}
                native=a[::3,::3]
                assert np.array_equal(np.repeat(np.repeat(native,3,axis=0),3,axis=1),a),item['id']
                colors.update(map(tuple,np.unique(native[:,:,:3][native[:,:,3]>0],axis=0).tolist()))
        assert len(colors)<=64,(item['id'],len(colors))
        with Image.open(ASSETS/item['poster']) as poster:assert poster.size==(w,h)
        with Image.open(ASSETS/item['source']) as reference:
            a=np.array(reference.convert('RGBA'));assert set(np.unique(a[:,:,3]))<={0,255}
            assert len(np.unique(a[:,:,:3][a[:,:,3]>0],axis=0))<=64
        with Image.open(ASSETS/item['sheet']) as sheet:
            a=np.array(sheet.convert('RGBA'));assert set(np.unique(a[:,:,3]))<={0,255}
            assert sheet.width%w==0 and sheet.height%h==0
            assert len(np.unique(a[:,:,:3][a[:,:,3]>0],axis=0))<=64
        records.append(dict(id=item['id'],native=[w,h],frames=count,colors=len(colors),exactIntegerScale=3,binaryAlpha=True))
    output=ROOT/'outputs/site-pixel-examples-20261020';output.mkdir(exist_ok=True)
    (output/'validation.json').write_text(json.dumps(dict(passed=True,records=records,newAIGeneration=False),indent=2),encoding='utf-8')
    print('PASS same chibi anime character in 4 pixel sources, animations, posters and sheets; binary alpha, <=64 colors, exact 3x blocks, recipe dimensions')


if __name__=='__main__':main()
