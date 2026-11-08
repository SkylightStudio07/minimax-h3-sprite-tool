"""Side-by-side playable review of the two generated actions; no painted VFX."""
import json,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import sprite_gif
OUT=ROOT/'outputs/normal-sword-vfx-contained-20261020'

def build(notice_text=None,notes=None,labels=None):
 actions=[];labels=labels or ['검기 내려베기','회전베기']
 for name in ('slash','spin'):
  folder=OUT/name;meta=json.loads((folder/'frames.json').read_text(encoding='utf-8'))
  frames=[Image.open(folder/'all-frames'/f'frame-{i:03d}.png').convert('RGBA') for i in meta['previewSourceIndices']]
  ticks=np.cumsum(meta['previewTimingMs']);actions.append((frames,ticks))
 font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',24)
 ticks=list(range(0,3000,40));preview=[]
 for elapsed in ticks:
  out=Image.new('RGB',(1024,560),'#171f2e');draw=ImageDraw.Draw(out)
  for side,(frames,bounds) in enumerate(actions):
   for y in range(48,560,24):
    for x in range(side*512,(side+1)*512,24):
     draw.rectangle((x,y,x+23,y+23),fill=('#293548' if ((x-side*512)//24+(y-48)//24)%2 else '#222d3e'))
   draw.text((side*512+18,8),labels[side],font=font,fill='white')
   index=min(len(frames)-1,int(np.searchsorted(bounds,elapsed,side='right')))
   small=frames[index].resize((512,512),Image.Resampling.LANCZOS);out.paste(small,(side*512,48),small)
  preview.append(out)
 data,_=sprite_gif.encode(preview,[40]*len(preview));(OUT/'comparison.gif').write_bytes(data)
 page=OUT/'preview.html';s=page.read_text(encoding='utf-8')
 if notice_text is None:notice_text='검기와 섬광의 끝 일부가 화면 경계에 닿습니다. 회전베기는 추가 회전과 발이 뜨는 구간이 있습니다.'
 notice=('<p id="review-notice"><a href="sword-vfx-handoff.zip" download>GIF·PNG 시트·원본 영상 묶음</a> · '
  '<a href="comparison.gif">나란히 비교 GIF</a><br>'+notice_text+'</p>')
 if 'id="review-notice"' not in s:page.write_text(s.replace('<main>',notice+'<main>'),encoding='utf-8')
 if notes is None:notes=('검기 강화 시험\n768x768, 원본 73프레임, 동작+효과 AI 공동 생성. 수작업 이펙트 없음.\n'
  '내려베기: 1.5배속, 약 2.03초. 회전베기: 1.25배속, 약 2.43초.\n'
  '각 PNG 시트는 24장, 칸 크기 768x768. frames.json의 프레임 시간을 사용하세요.\n'
  '단색 제거와 에너지 가장자리 배경색 분리를 적용하고, AI 캐릭터 마스크로 옷 그림자를 보호했습니다.\n'
  '일부 섬광과 검기 끝이 프레임 경계에 닿습니다. 회전베기는 추가 회전과 발이 뜨는 구간이 남습니다.\n'
  '원본 영상은 보존했으며 사이트 예시는 교체하지 않았습니다.\n')
 (OUT/'README.txt').write_text(notes,encoding='utf-8')
 package=OUT/'sword-vfx-handoff.zip'
 if package.exists():
  with zipfile.ZipFile(package,'a',zipfile.ZIP_DEFLATED) as archive:
   for name in ('README.txt','validation.json','slash/review.json','spin/review.json'):
    if name not in archive.namelist():archive.write(OUT/name,name)
  with zipfile.ZipFile(package) as archive:assert archive.testzip() is None
 for name in ('slash','spin'):
  im=Image.open(OUT/name/'all-frames/frame-025.png').convert('RGBA')
  out=Image.new('RGB',(1536,768),'#111722');out.paste(im,(0,0),im)
  light=Image.new('RGB',im.size,'#f5f5f5');light.paste(im,(0,0),im);out.paste(light,(768,0));out.save(OUT/name/'matte-review.webp')
 print('REVIEW',OUT/'comparison.gif')
if __name__=='__main__':build()
