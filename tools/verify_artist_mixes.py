"""Controlled Anima artist-tag study: two subjects, fixed seeds, no LoRA."""
import json,sys
from pathlib import Path
from unittest.mock import patch
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_engine as engine
from verify_fasth3_actions import ensure_idle

CASES=[('tactical',r'@nardack, @ask \(askzy\), restrained cool gray palette, fine controlled linework, two-stage cel shadows, matte fabric, minimal highlights'),('cel','@ciloranko, @jima, clean tapered outlines, restrained saturation, clear cel shading, simple shadow shapes, matte colors'),('soft','@fkey, @nardack, delicate colored linework, soft cool shadows, restrained warm accent colors, subtle paper texture, no glossy skin')]
SUBJECTS=[('operator','1girl, solo, adult woman, short silver hair, teal eyes, black tactical jacket, fully clothed, holding radio, upper body, three-quarter view, plain light gray background'),
          ('swordsman','1boy, solo, adult man, dark hair tied back, navy coat, scarf, holding sheathed sword, full body, boots, standing, plain light gray background')]

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');out=ROOT/'outputs/artist-mixes-20261017';out.mkdir(parents=True,exist_ok=True)
    for name,tags in CASES:
        for i,(subject,description) in enumerate(SUBJECTS):
            ensure_idle();jid=name+'-'+subject
            if (out/jid/'image-1.png').exists():continue
            # Same append position as the production look preset path.
            p=engine.validate(dict(prompt=description+(', '+tags if tags else ''),model='anima-turbo',preset='illustration',background='keep',width=768,height=1024,seed=202610170+i))
            def update(j,**fields):print(j,fields.get('state'),flush=True)
            with patch.object(engine,'RESULT_ROOT',out),patch.object(engine,'update_job',side_effect=update):engine.run_job(jid,p)
    sheet=Image.new('RGB',(3*300,2*420),'#ddd');d=ImageDraw.Draw(sheet)
    for col,(name,tags) in enumerate(CASES):
        for row,(subject,_) in enumerate(SUBJECTS):
            im=Image.open(out/(name+'-'+subject)/'image-1.png');im.thumbnail((300,400));sheet.paste(im,(col*300,row*420+20));d.text((col*300+3,row*420+2),name+' '+subject,fill='black')
    sheet.save(out/'comparison.jpg')
