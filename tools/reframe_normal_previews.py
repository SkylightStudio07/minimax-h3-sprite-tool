"""Zoom presentation copies using one union crop; preserve native sheet coordinates."""
import json,math,shutil,sys
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import sprite_gif
def reframe(folder):
 meta=json.loads((folder/'frames.json').read_text(encoding='utf-8'))
 frames=[Image.open(p).convert('RGBA') for p in sorted((folder/'all-frames').glob('frame-*.png'))]
 assert len(frames)==meta['previewFrames']==73
 boxes=[im.getchannel('A').getbbox() for im in frames]
 assert all(boxes)
 bounds=(min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes))
 side=math.ceil(max(bounds[2]-bounds[0],bounds[3]-bounds[1])*1.12)
 x=math.floor((bounds[0]+bounds[2]-side)/2);y=math.floor((bounds[1]+bounds[3]-side)/2)
 crop=(x,y,x+side,y+side)
 for box in boxes:assert box[0]>=crop[0] and box[1]>=crop[1] and box[2]<=crop[2] and box[3]<=crop[3]
 for ext in ('webp','gif'):
  original=folder/('animation-fullcanvas.'+ext)
  if not original.exists():shutil.copyfile(folder/('animation.'+ext),original)
 preview=[im.crop(crop).resize((512,512),Image.Resampling.LANCZOS) for im in frames]
 timing=meta['previewTimingMs']
 preview[0].save(folder/'animation.webp',save_all=True,append_images=preview[1:],duration=timing,loop=0,lossless=True)
 gif,info=sprite_gif.encode(preview,timing);(folder/'animation.gif').write_bytes(gif)
 meta.update(previewCropBounds=list(crop),previewCropMode='fixed union of all native frame alpha bounds + 12 percent margin',gif=info)
 (folder/'frames.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
 print('Presentation crop',str(folder),crop,'native frames/sheet untouched')
if __name__=='__main__':reframe(Path(sys.argv[1]))
