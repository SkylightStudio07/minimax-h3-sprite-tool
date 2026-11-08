"""AI/Lanczos comparison of a cropped real rig layer, isolated from saved rigs."""
import io
import json
from pathlib import Path
import sys
import time
import tempfile
import zipfile
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import rigging_upscale as upscale
import rigging_super_resolution as sr

if __name__=='__main__':
    folder=ROOT/'outputs/rigging/5ed3fddd3383252008ecd0c8e7dce9df'
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    record=next(p for p in manifest['parts'] if p['id']=='face')
    with zipfile.ZipFile(folder/'character-unity-parts.zip') as archive:
        source=Image.open(io.BytesIO(archive.read(record['file']))).convert('RGBA')
    bounds=source.getchannel('A').getbbox()
    if bounds:source=source.crop(bounds)
    source.thumbnail((256,256),Image.Resampling.LANCZOS)
    out=ROOT/'outputs/live2d-quality-smoke-20261018';out.mkdir(exist_ok=True)
    source.save(out/'source.png');source.save(out/'ai.png')
    lanczos=upscale.resize_layer(source,2);lanczos.save(out/'lanczos.png')
    start=time.monotonic();sr.upscale_files([out/'ai.png'],2)
    with Image.open(out/'ai.png') as ai:
        assert ai.size==lanczos.size
        assert np.array_equal(np.asarray(ai.getchannel('A')),np.asarray(lanczos.getchannel('A')))
        difference=float(np.abs(np.asarray(ai.convert('RGB')).astype(float)-np.asarray(lanczos.convert('RGB'))).mean())
        assert difference>0
        comparison=Image.new('RGB',(ai.width*3,ai.height),'#ccc')
        for i,image in enumerate([source.resize(ai.size,Image.Resampling.NEAREST),lanczos,ai]):
            background=Image.new('RGBA',ai.size,'#ddd');background.alpha_composite(image.convert('RGBA'));comparison.paste(background.convert('RGB'),(i*ai.width,0))
        comparison.save(out/'comparison.webp')
    (out/'verification.json').write_text(json.dumps(dict(seconds=round(time.monotonic()-start,2),alphaIdentical=True,outputSize=lanczos.size,rgbMeanDifference=difference,method='RealESRGAN anime6B CPU',order=['source nearest','lanczos','anime-ai']),indent=2),encoding='utf-8')
    print((out/'verification.json').read_text(),flush=True)

    # End-to-end apply on a disposable package, never on the user's saved rig.
    with tempfile.TemporaryDirectory(prefix='rig-quality-apply-') as name:
        scratch=Path(name)
        record=dict(id='face',runtimeName='face',file='layers/face.png',left=20,top=20,width=source.width,height=source.height)
        fixture=dict(canvas=dict(width=256,height=256),parts=[record],expressions=[],editRevision=0,anchors=dict(face=dict(cx=70,cy=80)))
        (scratch/'manifest.json').write_text(json.dumps(fixture),encoding='utf-8')
        with zipfile.ZipFile(scratch/'character-unity-parts.zip','w') as archive:archive.writestr('layers/face.png',(out/'source.png').read_bytes())
        (scratch/'character.psd').write_bytes(b'original-psd')
        composite=Image.new('RGBA',(256,256));composite.alpha_composite(source,(20,20));composite.save(scratch/'composite.png')
        applied=upscale.apply_layers(scratch,2,0,ROOT/'tools/write_psd.js',ROOT/'unity-v2',method='anime-ai')
        assert applied['revision']==1 and applied['manifest']['canvas']['width']==512
        assert applied['manifest']['parts'][0]['left']==40
        assert (scratch/'character.psd').read_bytes()[:4]==b'8BPS'
        assert (scratch/'revisions/0000/character.psd').read_bytes()==b'original-psd'
        with zipfile.ZipFile(scratch/'character-unity-skeleton.zip') as archive:
            assert json.loads(archive.read('rig-v2.json'))['sourceRevision']==1
        verification=json.loads((out/'verification.json').read_text())
        verification.update(realAiApply=True,psd=True,v2=True,previousRevisionPreserved=True)
        (out/'verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
        print('PASS: real AI apply + PSD + V2 + previous revision preservation',flush=True)
