"""Isolated Vertex gunshot VFX reference generation using installed Anima."""
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
    out=ROOT/'outputs/vertex-vfx-20261017/revised'
    out.mkdir(parents=True,exist_ok=True)
    cases={
        'muzzle': 'One isolated horizontal burst of white-hot light. A tiny narrow emission point on the left expands into three short tapered ivory and pale gold flame petals pointing right. The whole burst occupies only the middle third of the image. Smooth luminous curves, compact silhouette, no object attached.',
        'armor-impact': 'One tiny isolated asymmetrical starburst of ivory light surrounded by five short tapered pale gold sparks and a small soft blue-gray puff. The entire cluster occupies only the middle third of the image, surrounded by wide empty black margins. All spark tips terminate inside that cluster. Fine elegant curved light strokes, translucent wisps.'
    }
    for i,(name,prompt) in enumerate(cases.items()):
        ensure_idle()
        settings=image_engine.validate(dict(model='anima-turbo',preset='illustration',background='keep',width=1024,height=1024,seed=20261027+i,count=1,
            prompt=prompt+' Isolated 2D hand-painted Japanese tactical anime game VFX asset on pure black background. Elegant smooth tapered contours, crisp core, subtle shaded wisps. Entire effect centered with generous empty margins. No gun, no person, no target, no environment. One effect only.',
            negativePrompt='person, girl, weapon, gun, robot, landscape, text, logo, watermark, polygon, low poly, icon, fireball, huge explosion, magic circle, decorative swirls, border, cropped'))
        def update(jid,**fields):
            print(jid,fields.get('message'),flush=True)
            if fields.get('state')=='complete':
                (out/(jid+'-result.json')).write_text(json.dumps(fields,ensure_ascii=False,indent=2),encoding='utf-8')
        with patch.object(image_engine,'RESULT_ROOT',out),patch.object(image_engine,'update_job',side_effect=update):
            image_engine.run_job(name,settings)
