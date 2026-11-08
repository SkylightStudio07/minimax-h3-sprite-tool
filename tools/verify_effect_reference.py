"""Generate a detailed VFX reference with the project's installed Anima engine."""
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_engine
from verify_fasth3_actions import ensure_idle

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    ensure_idle()
    folder=ROOT/'outputs/experiments/fasth3-quality/anima'
    folder.mkdir(parents=True,exist_ok=True)
    settings=image_engine.validate(dict(model='anima-turbo',preset='illustration',background='keep',
        width=1024,height=1024,seed=20261016,count=1,
        prompt=('A single isolated magical orange and gold flame, high-end hand-painted 2D action RPG visual effect asset, '
                'solid pure black background, no scenery, no character. Elegant curved tapered flame tongues, '
                'flowing organic silhouette, rich vermilion and amber shading, a luminous ivory core, '
                'smooth translucent gradients, delicate wisps and tiny embers, restrained glow, '
                'crisp beautiful Japanese animation effects art. Centered flame, generous empty margins on every side, '
                'no floor or ground, full flame visible, fine painterly detail.'),
        negativePrompt='person, character, face, landscape, text, watermark, logo, polygon, low poly, flat icon, clipart, hard geometric shapes, thick outlines, cropped, border, blurry'))
    def update(jid,**fields):
        print(fields.get('message'),flush=True)
        if fields.get('state')=='complete':
            (folder/'validation.json').write_text(json.dumps(fields,ensure_ascii=False,indent=2),encoding='utf-8')
    with patch.object(image_engine,'RESULT_ROOT',folder),patch.object(image_engine,'update_job',side_effect=update):
        image_engine.run_job('flame',settings)
