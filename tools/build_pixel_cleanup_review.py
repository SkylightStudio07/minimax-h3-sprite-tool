"""Build a synchronized, local-only pixel cleanup review and asset bundles."""
import html,json,zipfile
from pathlib import Path

SCRIPT=r'''
const configs=JSON.parse(document.getElementById('configs').textContent);
for(const cfg of configs){
 const section=document.getElementById(cfg.id),slider=section.querySelector('[data-action="slider"]'),label=section.querySelector('[data-label]'),toggle=section.querySelector('[data-action="toggle"]');
 let index=0,playing=true,elapsed=0,last=performance.now(),speed=1;
 const pictures=section.querySelectorAll('img[data-method]');
 const url=(method,i)=>`${cfg.id}/${method}/frame-${String(i).padStart(2,'0')}.png`;
 for(const method of ['original','edge','vote','thin'])for(let i=0;i<cfg.indices.length;i++){const preload=new Image();preload.src=url(method,i)}
 function draw(){for(const picture of pictures)picture.src=url(picture.dataset.method,index);slider.value=index;label.textContent=`${index+1} / ${cfg.indices.length} · 원본 ${cfg.indices[index]}번`;toggle.textContent=playing?'일시 정지':'재생'}
 toggle.onclick=()=>{playing=!playing;elapsed=0;last=performance.now();draw()};
 function step(delta){playing=false;elapsed=0;index=(index+delta+cfg.indices.length)%cfg.indices.length;draw()}
 section.querySelector('[data-action="previous"]').onclick=()=>step(-1);
 section.querySelector('[data-action="next"]').onclick=()=>step(1);
 slider.oninput=()=>{playing=false;elapsed=0;index=Number(slider.value);draw()};
 section.querySelector('[data-action="speed"]').onchange=e=>{speed=Number(e.target.value)};
 function tick(now){const dt=Math.max(0,Math.min(now-last,200));last=now;if(playing){elapsed+=dt*speed;let changed=false;while(elapsed>=cfg.duration[index]){elapsed-=cfg.duration[index];index=(index+1)%cfg.indices.length;changed=true}if(changed)draw()}requestAnimationFrame(tick)}
 draw();requestAnimationFrame(tick);
}
'''

def build(out,names):
 cases=[('swordswoman','여검사 · 내려베기'),('musketeer','여총사 · 한 발 사격')]
 if (out/'walking/comparison.png').exists():cases.append(('walking','걷기 · 기존 파츠 분리 캐릭터'))
 configs=[];sections=[];recommended={}
 for key,title in cases:
  meta=json.loads((out/key/'thin/frames.json').read_text(encoding='utf-8'));count=len(meta['sourceIndices'])
  configs.append(dict(id=key,indices=meta['sourceIndices'],duration=meta['durationMs']))
  recommended[key]=dict(method='thin',frameCount=count,frameSize=[128,128],paletteSize=32 if key=='walking' else 36,notes=meta['review'])
  card=lambda method,label:f'<article><h3>{label}</h3><img data-method="{method}" src="{key}/{method}/frame-00.png" alt="{html.escape(title)} {label}"><p><a href="{key}/{method}/sheet-grid.png">PNG 시트</a> · <a href="{key}/{method}/animation.webp">애니메이션</a> · <a href="{key}/{method}/frames.json">표시 시간·원본 프레임</a></p></article>'
  allcards=''.join(card(method,label) for method,label in names.items())
  note=('원본 얼굴·손 레이어와 복원한 검, 같은 추적 위치를 네 방식에 공통 적용했습니다. 걷기는 몸 후처리만 비교하며 무기 추적이 개선됐다는 뜻은 아닙니다.' if key=='walking' else '같은 생성 영상·선택 프레임·재생 시간·팔레트입니다. 생성 단계의 무기 변형과 잘린 효과는 후처리로 복구되지 않습니다.')
  sections.append(f'<section id="{key}"><h2>{title}</h2><p>{note}</p><div class="controls"><button data-action="toggle">일시 정지</button><button data-action="previous" aria-label="이전 프레임">←</button><button data-action="next" aria-label="다음 프레임">→</button><input aria-label="프레임 선택" data-action="slider" type="range" min="0" max="{count-1}" value="0"><span data-label>1 / {count}</span><label>속도 <select data-action="speed"><option value="0.5">0.5배</option><option value="1" selected>1배</option><option value="2">2배</option></select></label></div><div class="pair">{card("original","기존 결과")}{card("thin","현재 우선 후보 · 경계＋색 투표＋가는 부품")}</div><details><summary>비교한 네 방식 모두 보기</summary><div class="methods">{allcards}</div><p>원본 / 경계 보정 / 16픽셀 색 투표 / 가는 밝은 부품 보존. 마지막 방식은 검날을 살리는 대신 밝은 머리칼·소매 끝도 조금 두꺼워질 수 있습니다.</p><a href="{key}/comparison.png">전체 선택 프레임 정지 비교</a></details></section>')
 recommendation=dict(status='experimental candidate; user evaluation pending',method='Known flat-matte edge cleanup -> 16 observed pixels vote in perceptual colour space -> current-frame thin bright-part evidence -> motion-gated temporal cleanup -> nearest display',cases=recommended,limitations=['No new AI generation; cannot restore source weapon deformation or clipped VFX','Bright thin-part protection can thicken legitimate hair/cuff highlights','Manual source masks and cached head/hand/weapon tracks remain character-specific'])
 (out/'recommendation.json').write_text(json.dumps(recommendation,ensure_ascii=False,indent=2),encoding='utf-8')
 page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>픽셀 다듬기 · 같은 프레임 비교</title><style>body{background:#151b26;color:#eee;font:15px/1.6 system-ui;max-width:1280px;margin:28px auto;padding:0 20px}a{color:#c6c3ff}h1{font-size:27px}h2{margin-top:36px}h3{font-size:16px}article{background:#252d3b;border-radius:12px;padding:16px;min-width:0}.pair,.methods{display:grid;grid-template-columns:1fr 1fr;gap:16px}img{display:block;width:100%;image-rendering:pixelated;background:repeating-conic-gradient(#202632 0 25%,#303a4b 0 50%) 0/20px 20px}.controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:14px 0}button,select{background:#323f58;color:white;border:1px solid #64728c;padding:8px 12px;border-radius:6px}input[type=range]{min-width:180px;flex:1;accent-color:#b4a7ff}details{margin:16px 0;background:#1e2634;padding:14px;border-radius:8px}summary{cursor:pointer;margin-bottom:8px}.notice{background:#28384a;padding:14px;border-radius:9px}@media(max-width:700px){.pair,.methods{grid-template-columns:1fr}}</style><h1>픽셀 다듬기 · 같은 프레임 비교</h1><p>기존 영상으로 네 가지 처리를 비교했습니다. 현재 우선 후보를 기존 결과와 나란히 보여줍니다. 같은 프레임으로 함께 재생되며, 멈춘 뒤 좌우 버튼이나 슬라이더로 확인할 수 있습니다.</p><p><a href="recommended-pixel-sprites.zip" download>우선 후보 PNG 시트·프레임 ZIP</a> · <a href="pixel-cleanup-comparison.zip" download>네 방식 전체 비교 ZIP</a></p><p class="notice">검날·총열의 끊김과 경계 잡점은 줄어드는 방향입니다. 원본 영상에서 이미 휘어진 무기, 잘린 발광은 해결되지 않았습니다. 이 결과는 아직 비교용 후보이며 기존 파일을 교체하지 않았습니다.</p>'''+''.join(sections)+'<script id="configs" type="application/json">'+json.dumps(configs,ensure_ascii=False)+'</script><script>'+SCRIPT+'</script></html>'
 if (out.parent/'pixel-outline-repair-20261019/preview.html').exists():
  page=page.replace('<h1>픽셀 다듬기 · 같은 프레임 비교</h1>','<h1>픽셀 다듬기 · 같은 프레임 비교</h1><p class="notice"><a href="../pixel-outline-repair-20261019/preview.html">후속 비교: 남은 흰 테두리 정리＋검날 다시 그리기</a> — 이 페이지의 밝은 부품 보존이 흰 잡점도 살리는 문제를 확인해 추가 보정했습니다.</p>',1)
 (out/'preview.html').write_text(page,encoding='utf-8')
 (out/'preview-script-check.js').write_text(SCRIPT,encoding='utf-8')
 with zipfile.ZipFile(out/'recommended-pixel-sprites.zip','w',zipfile.ZIP_DEFLATED) as z:
  z.write(out/'recommendation.json','recommendation.json')
  for key,_ in cases:
   for p in (out/key/'thin').rglob('*'):
    if p.is_file():z.write(p,Path(key)/p.relative_to(out/key/'thin'))
 with zipfile.ZipFile(out/'pixel-cleanup-comparison.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in out.rglob('*'):
   if p.is_file() and p.suffix in ('.png','.webp','.json','.html'):z.write(p,p.relative_to(out))
 print('PREVIEW',out/'preview.html',flush=True)
