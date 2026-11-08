"""Generate comparable varied subjects for installed style library; no auto activation."""
import hashlib,json,sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_engine as engine
import image_styles
from verify_fasth3_actions import ensure_idle
from PIL import Image

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    out=ROOT/'outputs/style-diversity-20261017';out.mkdir(parents=True,exist_ok=True)
    catalog=[dict(s,enabled=True) for s in image_styles.catalog()]
    subjects=[('operator','Adult woman with short silver bob hair, teal eyes, fully covered black tactical jacket, holding a radio, waist-up three-quarter portrait, pale gray background, Japanese anime illustration.'),
              ('swordsman','Adult man with dark hair tied back, dark blue coat and scarf, full body with boots, holding a sheathed sword, confident stance, plain pale gray background, Japanese anime game character.'),
              ('mage','Adult woman with long auburn hair, round glasses, fully covered ivory scholar robe, holding an open book, side view waist-up, pale gray background, Japanese anime illustration.')]
    records=[]
    for s in catalog:
        with (ROOT/'ComfyUI/models/loras'/s['filename']).open('rb') as f:
            assert hashlib.file_digest(f,'sha256').hexdigest()==s['sha256']
        for i,(subject,prompt) in enumerate(subjects):
            ensure_idle()
            jid=s['id']+'-'+subject
            with patch.object(image_styles,'catalog',return_value=catalog):
                p=engine.validate(dict(prompt=prompt,model='anima-turbo',width=768,height=1024,seed=202610170+i,styleId=s['id'],styleStrength=s['strength']))
            def update(j,**fields):
                print(j,fields.get('state'),flush=True)
                if fields.get('state')=='complete': records.append(dict(id=j,style=s['id'],subject=subject))
            if not (out/jid/'image-1.png').exists():
                with patch.object(image_styles,'catalog',return_value=catalog),patch.object(engine,'RESULT_ROOT',out),patch.object(engine,'update_job',side_effect=update): engine.run_job(jid,p)
            dest=ROOT/'web/assets/style-diversity';dest.mkdir(parents=True,exist_ok=True)
            im=Image.open(out/jid/'image-1.png');im.thumbnail((384,512));im.save(dest/(jid+'.webp'),quality=88)
    (out/'results.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
