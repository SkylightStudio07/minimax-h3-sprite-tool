"""Manual VFX study with synthetic fixtures, no production activation."""
import base64
import argparse
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch
import av
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import effect_prompts
import idle_tool as engine
import sprite_workflows
from verify_fasth3_actions import ensure_idle


def fixture(kind, path):
    im=Image.new('RGB',(512,512),'black')
    d=ImageDraw.Draw(im)
    if kind=='flame':
        d.polygon([(173,413),(147,360),(162,300),(200,333),(188,251),(232,176),(258,94),(283,183),(330,247),(348,318),(325,393),(291,418)],fill='#e94a26')
        d.polygon([(197,410),(178,354),(212,283),(216,328),(259,186),(290,266),(319,336),(298,408)],fill='#ffae32')
        d.polygon([(225,411),(210,368),(245,313),(256,264),(280,342),(278,405)],fill='#fff2a0')
    else:
        d.polygon([(99,379),(129,274),(198,171),(302,106),(407,83),(325,127),(249,187),(183,269),(140,354)],fill='#177bd3')
        d.polygon([(110,367),(151,275),(219,189),(315,125),(397,89),(309,141),(240,208),(177,289)],fill='#55ecff')
        d.polygon([(117,355),(171,268),(232,200),(307,147),(242,216),(185,289)],fill='#f1ffff')
    im.save(path)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser()
    parser.add_argument('--reference',type=Path)
    parser.add_argument('--kind',choices=tuple(effect_prompts.TEMPLATES),default='flame')
    parser.add_argument('--tag',default='painted')
    parser.add_argument('--padding',type=int,choices=(0,10,20,30),default=0)
    args=parser.parse_args()
    if not args.tag.replace('-','').isalnum():
        parser.error('tag must be alphanumeric or hyphenated')
    if args.reference and not args.reference.is_file():
        parser.error('reference file missing')
    old_status=sprite_workflows.status
    old_build=engine.build_workflow
    def status(root):
        profiles=old_status(root)
        profiles[1]['ready']=profiles[1]['installed']
        return profiles
    for kind in ((args.kind,) if args.reference else ('flame','slash')):
        ensure_idle()
        job='fasth3-effects-20261016-'+kind
        if args.reference:
            job+='-'+args.tag
        folder=engine.RESULT_ROOT/job
        folder.mkdir(parents=True,exist_ok=True)
        if (folder/'validation.json').exists():
            continue
        source=args.reference or folder/'synthetic-reference.png'
        if not args.reference:
            fixture(kind,source)
        payload=dict(workflowId='fasth3-sprite',width=512,height=512,duration=3,seed=42,
                     animationType='custom',loop=effect_prompts.TEMPLATES[kind]['loop'],
                     frameCount=12,removeBackground=True,stabilize=False,optimizeLoop=False,
                     motionPadding=args.padding,filename=source.name,imageData=base64.b64encode(source.read_bytes()).decode())
        def build(*args,**kwargs):
            return effect_prompts.apply(old_build(*args,**kwargs),kind)
        engine.JOBS[job]={'state':'queued'}
        started=time.monotonic()
        print('START '+kind,flush=True)
        with patch.object(sprite_workflows,'status',status),patch.object(engine,'build_workflow',build):
            engine.run_job(job,payload)
        result=dict(engine.JOBS[job],elapsedSeconds=round(time.monotonic()-started,2),effectTemplate=kind,syntheticFixture=not bool(args.reference),reference=str(source))
        (folder/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False),flush=True)
        if result['state']!='complete':
            raise RuntimeError(result['message'])
        frames=[f.to_image() for f in av.open(str(folder/'custom_raw.mp4')).decode(video=0)]
        sheet=Image.new('RGB',(2048,1024))
        for i in range(8):
            n=round(i*(len(frames)-1)/7);x=i%4*512;y=i//4*512
            sheet.paste(frames[n],(x,y));ImageDraw.Draw(sheet).text((x+8,y+8),f'{n/24:.2f}s',fill='white')
        sheet.save(folder/'motion-review.jpg')


if __name__=='__main__':
    main()
