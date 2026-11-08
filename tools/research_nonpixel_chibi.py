"""Read-only model research; publisher samples, no weights or generations."""
import concurrent.futures, html, io, json, re, sys
from pathlib import Path
import requests
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/chibi-nonpixel-research-20261020'
CANDIDATES=[
 (102318,1940306,'A · 데포르메 치비'),
 (1285358,1450219,'B · 게임 SD 캐릭터'),
 (1019525,1143203,'C · 섬세한 치비 일러스트'),
 (1685523,2969270,'D · 무테 채색 치비'),
 (182276,1338501,'E · 표정 중심 치비'),
 (1898143,2148649,'F · 커스텀 치비'),
 (1775629,2009626,'G · 큐트 치비'),
 (1524200,2318164,'H · 단순 선화 치비'),
 (2604230,3175539,'I · 데포르메 게임 일러스트'),
 (2894155,3272415,'J · 중세 판타지 치비'),
 (355566,3327308,'K · 디테일 치비'),
 (1136754,1278136,'L · 미니 캐릭터 선화'),
]

def fetch_card(item):
 mid,vid,label=item
 response=requests.get(f'https://civitai.com/api/v1/models/{mid}',timeout=45);response.raise_for_status();card=response.json()
 (OUT/f'{mid}.json').write_text(json.dumps(card,ensure_ascii=False,indent=2),encoding='utf-8')
 v=next(v for v in card['modelVersions'] if v['id']==vid)
 folder=OUT/str(mid);folder.mkdir(exist_ok=True)
 samples=[]
 for i,sample in enumerate([i for i in v.get('images',[]) if i.get('nsfwLevel',1)==1][:2]):
  url=sample['url'];url=re.sub(r'/original=true/', '/width=640/',url)
  target=folder/f'publisher-{i+1}.jpg'
  if not target.exists():
   response=requests.get(url,timeout=45);response.raise_for_status()
   Image.open(io.BytesIO(response.content)).convert('RGB').save(target,quality=94)
  samples.append(dict(path=str(target.relative_to(OUT)),source=sample['url'],imageId=sample.get('id')))
 files=[dict(name=f['name'],MiB=round(f['sizeKB']/1024,1),sha256=f.get('hashes',{}).get('SHA256'),downloadUrl=f.get('downloadUrl')) for f in v['files'] if f['type']=='Model']
 return dict(modelId=mid,versionId=vid,label=label,name=card['name'],baseModel=v['baseModel'],version=v['name'],
  source=f'https://civitai.com/models/{mid}?modelVersionId={vid}',triggers=v.get('trainedWords',[]),files=files,samples=samples,
  description=re.sub('<[^>]+>',' ',card.get('description','')),permissions={k:card.get(k) for k in ('allowCommercialUse','allowNoCredit','allowDerivatives','allowDifferentLicense')})

def main():
 OUT.mkdir(exist_ok=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(fetch_card,CANDIDATES))
 (OUT/'candidates.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
 panel=Image.new('RGB',(1600,480*((len(rows)+1)//2)),'#253044');draw=ImageDraw.Draw(panel)
 for row,item in enumerate(rows):
  group=row//2;col=(row%2)*800
  for i,sample in enumerate(item['samples']):
   im=Image.open(OUT/sample['path']);im.thumbnail((390,435),Image.Resampling.LANCZOS)
   panel.paste(im,(col+i*400+(400-im.width)//2,group*480+35+(435-im.height)//2))
  draw.text((col+10,group*480+8),f'{chr(65+row)} / model {item["modelId"]} / {item["baseModel"]}',fill='white')
 panel.save(OUT/'publisher-comparison.webp',quality=93)
 notes={
  2604230:('우선 추천','작은 몸에도 눈동자·눈매와 갑옷/옷 디테일이 남습니다. 예전 후보보다 게임 캐릭터 원화에 가깝습니다. Anima Base 1.0용, 제작자 권장 강도 0.8~1.0.'),
  1019525:('우선 추천','부드러운 선에 홍채·동공이 분명한 일러스트형 치비입니다. 전신 원화 비교에 적합합니다. Illustrious 계열용.'),
  1775629:('비교 후보','동공과 머리카락 채색은 풍부하지만 파스텔/광택이 강해 취향 확인이 필요합니다. 제작자 권장 강도 0.5~0.9.'),
  1285358:('비교 후보','게임 SD 비율과 눈 표현은 선명합니다. 샘플은 입체적·인형 같은 채색이 강해 2D 선화 취향과 다를 수 있습니다.'),
  102318:('제외 권장','샘플에서 눈이 막대 모양으로 단순화됩니다. 이번 목표의 눈동자 표현과 맞지 않습니다.'),
  1685523:('제외 권장','무테·각진 평면 채색이 강해 이전에 거절한 방향과 가깝습니다.'),
  182276:('우선순위 낮음','표정과 스티커형 상반신 중심입니다. 검·전신 동작용으로 쓰려면 추가 검증이 필요합니다.'),
  1898143:('우선순위 낮음','진한 외곽선과 강한 색 대비가 두드러집니다.'),
  1524200:('우선순위 낮음','굵은 선과 단순 채색을 유도하며 샘플의 눈·채색 편차도 큽니다.'),
  2894155:('제외 권장','게임 판타지 분위기는 맞지만 굵은 펜선과 단순 채색이 이번 목표와 다릅니다.'),
  355566:('우선순위 낮음','스티커형 얼굴 중심입니다. 몸과 무기를 보존하는 전신 예시가 더 필요합니다.'),
  1136754:('제외 권장','모델명과 달리 대표 샘플은 일반 비율에 가깝습니다.'),
 }
 preferred=[2604230,1019525,1775629,1285358]
 order=sorted(rows,key=lambda x:preferred.index(x['modelId']) if x['modelId'] in preferred else 99)
 cards=[]
 for item in order:
  status,note=notes[item['modelId']]
  samples=''.join(f'<a href="{html.escape(s["source"])}" target="_blank" rel="noopener"><img loading="lazy" src="{s["path"]}" alt="제작자가 게시한 샘플"></a>' for s in item['samples'])
  flags=item['permissions'].get('allowCommercialUse',[])
  permission='게시된 상업 옵션: '+(', '.join(flags) if flags else '명시 없음')
  cards.append(f'<article><h2>{html.escape(item["label"])}</h2><b>{status}</b><p>{html.escape(note)}</p><div class="samples">{samples}</div><p>{item["baseModel"]} · {item["files"][0]["MiB"]} MiB · <a href="{item["source"]}" target="_blank" rel="noopener">제작자 모델 페이지</a></p><small>{html.escape(permission)}</small></article>')
 page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>비도트 치비 LoRA 후보 조사</title><style>body{margin:28px;background:#171e2b;color:#eef0f6;font:15px/1.65 system-ui}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:20px}article{padding:20px;background:#263247;border-radius:16px}h2{font-size:20px}b{color:#b9dbff}.samples{display:flex;gap:10px;align-items:center}.samples a{width:50%}img{display:block;width:100%;height:340px;object-fit:contain;background:#fff;border-radius:8px}a{color:#c5c7ff}small{color:#b4bfd0}</style><h1>비도트 치비 · 제작자 샘플 비교</h1><p>후보 12개, 제작자 샘플 24장을 확인했습니다. 먼저 볼 것은 I와 C입니다. 아래 그림은 모두 제작자가 게시한 샘플이며, 우리 환경에서 새로 생성한 결과가 아닙니다. 기존 작품 캐릭터가 포함된 샘플도 있으나 새 생성에는 오리지널 캐릭터만 사용합니다. 모델 가중치는 아직 다운로드하지 않았고 사이트 예시도 추가하지 않았습니다.</p><p>표시된 기반 모델은 현재 로컬 엔진과 같은 계열이지만 실제 생성 호환성·포즈 보존은 시험 전입니다. 상업 옵션은 모델 페이지 메타데이터를 그대로 기록했으며 서비스 이용 허가로 확정한 뜻은 아닙니다.</p><main>'''+''.join(cards)+'</main></html>'
 (OUT/'preview.html').write_text(page,encoding='utf-8')
 recommended=[next(r for r in rows if r['modelId']==mid) for mid in preferred[:2]]
 selection=Image.new('RGB',(1200,650),'#253044');draw=ImageDraw.Draw(selection)
 for i,item in enumerate(recommended):
  draw.text((600*i+10,12),f'{"I / Anima Base" if i==0 else "C / Illustrious"} / model {item["modelId"]}',fill='white')
  for j,s in enumerate(item['samples']):
   im=Image.open(OUT/s['path']);im.thumbnail((290,590),Image.Resampling.LANCZOS)
   selection.paste(im,(600*i+300*j+(300-im.width)//2,45+(590-im.height)//2))
 selection.save(OUT/'recommended-comparison.webp',quality=95)
 (OUT/'research-review.json').write_text(json.dumps(dict(recommended=preferred[:2],alternatives=preferred[2:],notes=notes,publisherSamplesOnly=True,weightsDownloaded=False,localGenerationsPerformed=False),ensure_ascii=False,indent=2),encoding='utf-8')
 print('RESEARCH_READY',len(rows),'cards',sum(len(x['samples']) for x in rows),'publisher samples',flush=True)

if __name__=='__main__':sys.stdout.reconfigure(encoding='utf-8');main()
