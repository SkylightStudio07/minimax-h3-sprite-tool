"""Actual Qwen edit on a disposable frame; never modifies a team job."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image,ImageDraw
import frame_edit
import image_background
from tools.verify_rpg_sprite_styles import ensure_idle

def main():
    ensure_idle()
    root=Path(__file__).resolve().parents[1]/'outputs/frame-edit-smoke-20261018'
    folder=root/'workspace';folder.mkdir(exist_ok=True)
    with Image.open(root/'source.png') as opened:source=image_background.remove(opened.convert('RGBA'))
    source.save(folder/'source.png')
    mask=Image.new('L',source.size);ImageDraw.Draw(mask).ellipse((242,172,298,207),fill=255);mask.save(folder/'mask.png')
    frame_edit.update_job=lambda jid,**changes:print(json.dumps(changes,ensure_ascii=True),flush=True)
    frame_edit.run_job('test',dict(_workspaceRoot=str(root),workspaceId='workspace',sourceFile='source.png',maskFile='mask.png',revision=0,frame=0,prompt='Make the existing small smiling mouth clean and natural. Keep the same cute mascot style and mouth position.'))
    with Image.open(folder/'candidates/test/candidate.png') as opened:edited=np.array(opened)
    original=np.array(source);outside=np.array(mask)==0
    assert np.array_equal(edited[outside],original[outside])
    assert np.array_equal(edited[:,:,3],original[:,:,3])
    changed=int(np.any(edited!=original,axis=2).sum());assert changed>0
    report=dict(outsideMaskExact=True,alphaExact=True,changedPixels=changed,sourceSize=list(source.size),sourceSHA256=hashlib.sha256((folder/'source.png').read_bytes()).hexdigest())
    (root/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)

if __name__=='__main__':main()
