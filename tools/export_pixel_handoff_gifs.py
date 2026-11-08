"""Export existing reviewed pixel animation sheets to handoff GIFs; no generation."""
import hashlib,html,json,sys,zipfile
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import sprite_gif
OUT=ROOT/'outputs/pixel-gif-handoff-20261019'

def main():
 OUT.mkdir(exist_ok=True);items=[];candidates=[]
 for root in sorted((ROOT/'outputs').glob('pixel-*20261019')):
  if root==OUT:continue
  for p in sorted(root.rglob('*.png')):
   if 'all-frames' in p.parts:continue
   with Image.open(p) as image:
    if getattr(image,'n_frames',1)>1:candidates.append(p)
  for p in sorted(root.rglob('animation*.webp')):
   if not p.with_suffix('.png').exists() and Image.open(p).n_frames>1:candidates.append(p)
 for p in candidates:
  with Image.open(p) as source:
   frames=[];times=[]
   for i in range(source.n_frames):
    source.seek(i);frames.append(source.convert('RGBA'));times.append(source.info.get('duration',100))
  metadata=p.parent/'frames.json'
  if metadata.exists():
   info=json.loads(metadata.read_text(encoding='utf-8'))
   if len(info.get('durationMs',[]))==len(frames):times=info['durationMs']
  # Extra head-lock preview is enlarged; match its sibling native APNG size.
  sibling=p.parent/'animation.png'
  if p.suffix=='.webp' and sibling.exists():
   native=Image.open(sibling).size
   if frames[0].width%native[0]==0 and frames[0].height%native[1]==0:frames=[f.resize(native,Image.Resampling.NEAREST) for f in frames]
  relative=p.relative_to(ROOT/'outputs');folder=OUT/relative.parent;folder.mkdir(parents=True,exist_ok=True)
  data,record=sprite_gif.encode(frames,times);target=folder/(p.stem+'.gif');target.write_bytes(data)
  preview,large=sprite_gif.encode(frames,times,scale=3);largepath=folder/(p.stem+'-3x.gif');largepath.write_bytes(preview)
  with Image.open(target) as check:
   actual=sum((check.seek(i) or check.info.get('duration',0)) for i in range(check.n_frames));assert actual==record['totalMs']
  item=dict(source=str(p),sourceSha256=hashlib.sha256(p.read_bytes()).hexdigest(),gif=target.relative_to(OUT).as_posix(),preview=largepath.relative_to(OUT).as_posix(),originalDurationMs=times,**record)
  (folder/(p.stem+'-gif.json')).write_text(json.dumps(item,ensure_ascii=False,indent=2),encoding='utf-8');items.append(item)
 featured=['pixel-color-lock-20261019/','pixel-spin-step-turn-20261019/','pixel-spin-retry-20261019/','pixel-sword-combo-20261019/','pixel-attack-actions-20261019/jump_slam/','pixel-outline-repair-20261019/swordswoman/blade/','pixel-outline-repair-20261019/musketeer/contour/','pixel-weapon-layers-20261019/composite-preview/']
 selected=[i for i in items if any(i['gif'].startswith(prefix) for prefix in featured)]
 for name,entries in [('pixel-gifs-all.zip',items),('pixel-gifs-latest.zip',selected)]:
  with zipfile.ZipFile(OUT/name,'w',zipfile.ZIP_DEFLATED) as z:
   for i in entries:
    for key in ['gif','preview']:z.write(OUT/i[key],i[key])
   z.writestr('manifest.json',json.dumps(entries,ensure_ascii=False,indent=2))
   z.writestr('README.txt','인계용 GIF: 기본 크기와 최근접 3배 미리보기입니다. 프레임 순서/시간은 manifest.json 참고. GIF는 10ms 단위로 시간을 반올림하며 연속 동일 프레임은 저장 시 합쳐질 수 있습니다. 반복은 확인용이며 원샷 공격의 처음/끝 연결을 보장하지 않습니다. 색 255개+투명 1개, 알파 0/255입니다. 게임용 원본 PNG 시트를 함께 보관하세요.\n')
  with zipfile.ZipFile(OUT/name) as z:assert z.testzip() is None
 def cards(entries):return ''.join('<article><h3>'+html.escape(i['gif'].replace('/animation.gif',''))+'</h3><img loading="lazy" src="'+i['preview']+'"><p><a download href="'+i['gif']+'">원래 크기 GIF</a> · <a download href="'+i['preview']+'">3배 GIF</a></p></article>' for i in entries)
 page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>픽셀 스프라이트 GIF 인계 묶음</title><style>body{background:#151b26;color:#eee;font:15px/1.6 system-ui;margin:24px}a{color:#c6c3ff}.cards{display:flex;gap:18px;flex-wrap:wrap}article{background:#252d3b;padding:14px;max-width:620px;overflow:auto;border-radius:10px}h3{font-size:14px;overflow-wrap:anywhere}img{image-rendering:pixelated;background:#202632;max-width:none}summary{cursor:pointer}</style><h1>픽셀 스프라이트 GIF · 인계용</h1><p>기존 시트의 프레임 순서와 표시 시간을 사용했습니다. 원래 크기와 정수 3배 GIF를 함께 제공합니다.</p><p><a href="pixel-gifs-latest.zip" download>최근 결과 묶음 ZIP</a> · <a href="pixel-gifs-all.zip" download>이전 비교본까지 전체 ZIP</a> · <a href="manifest.json">원본·프레임·시간 기록</a></p><h2>최근 결과</h2><div class="cards">'''+cards(selected)+'</div><details><summary>이전 시험·비교본 포함 전체 '+str(len(items))+'개 보기</summary><div class="cards">'+cards([i for i in items if i not in selected])+'</div></details></html>'
 (OUT/'preview.html').write_text(page,encoding='utf-8');(OUT/'manifest.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
 print('EXPORTED',len(items),'animations / latest',len(selected),'both native and 3x',flush=True)

if __name__=='__main__':main()
