"""Synchronized integer-scale review of selected contour / blade corrections."""
import json,zipfile
from tools.build_pixel_cleanup_review import SCRIPT as OLD_SCRIPT
SCRIPT=OLD_SCRIPT.replace("for(const method of ['original','edge','vote','thin'])","for(const method of cfg.methods)")
SCRIPT+='''
const zoom=document.getElementById('zoom'),background=document.getElementById('background');
zoom.onchange=()=>document.documentElement.style.setProperty('--zoom',zoom.value);
background.onchange=()=>{document.body.dataset.background=background.value};
'''

def build(out):
 configs=[];sections=[]
 for char,title in [('swordswoman','여검사 · 내려베기'),('musketeer','여총사 · 사격'),('walking','파츠 분리 캐릭터 · 걷기')]:
  methods=['before','contour']+(['blade'] if char!='musketeer' else [])
  meta=json.loads((out/char/'before/frames.json').read_text(encoding='utf-8'))
  configs.append(dict(id=char,indices=meta['sourceIndices'],duration=meta['durationMs'],methods=methods))
  cards=[]
  for method in methods:
   label={'before':'이전 후보','contour':'몸·옷의 흰 테두리 정리','blade':'테두리 정리＋검날 다시 그리기'}[method]
   cards.append(f'<article><h3>{label}</h3><img data-method="{method}" src="{char}/{method}/frame-00.png" alt="{title} · {label}"><p><a href="{char}/{method}/sheet-grid.png">투명 PNG 시트</a> · <a href="{char}/{method}/animation.webp">애니메이션</a> · <a href="{char}/{method}/frames.json">표시 시간</a></p></article>')
  note={'swordswoman':'검날이 곧게 보이는 9개 선택 포즈는 손잡이·검끝을 수동 지정해 도트로 다시 그렸습니다. 검이 가늘고 곧은 인상으로 달라집니다. 넓은 베기 잔상 3포즈는 그대로 남겼습니다.','musketeer':'흰 머리·얼굴·소매·총열·발광은 보호하고 몸/옷 경계만 정리했습니다. 총 자체를 새로 그리거나 자동 파츠 분리한 결과는 아닙니다.','walking':'원본 얼굴·스카프·앞쪽 손을 보호했습니다. 검날 다시 그리기는 기존 추적 위치와 회전만 사용하며 새 추적은 하지 않았습니다.'}[char]
  controls=f'<div class="controls"><button data-action="toggle">일시 정지</button><button data-action="previous" aria-label="이전 프레임">←</button><button data-action="next" aria-label="다음 프레임">→</button><input data-action="slider" type="range" min="0" max="{len(meta["sourceIndices"])-1}" value="0" aria-label="프레임 선택"><span data-label></span><label>속도 <select data-action="speed"><option value="0.5">0.5배</option><option value="1" selected>1배</option><option value="2">2배</option></select></label></div>'
  sections.append(f'<section id="{char}"><h2>{title}</h2><p>{note}</p>{controls}<div class="cards">'+''.join(cards)+f'</div><details><summary>전체 선택 프레임 / 보호 영역</summary><p><a href="{char}/comparison.png">정지 비교 이미지</a> · <a href="{char}/review.json">프레임별 수정 내역</a></p><p>보호 영역 PNG는 ZIP의 protected-materials 폴더에 들어 있습니다.</p></details></section>')
 page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>흰 테두리 정리 / 검날 보정</title><style>:root{--zoom:3}body{background:#151b26;color:#eee;font:15px/1.6 system-ui;max-width:1440px;margin:28px auto;padding:0 20px}a{color:#c8c4ff}h1{font-size:27px}h2{margin-top:36px}h3{font-size:15px}article{background:#252d3b;border-radius:10px;padding:12px;flex:0 0 auto;width:calc(128px * var(--zoom));max-width:none}.cards{display:flex;gap:16px;flex-wrap:wrap;overflow-x:auto}img{display:block;width:calc(128px * var(--zoom));height:calc(128px * var(--zoom));image-rendering:pixelated;background:#202632}body[data-background=light] img{background:#f0f1f4}body[data-background=checker] img{background:repeating-conic-gradient(#202632 0 25%,#455069 0 50%) 0/24px 24px}.controls,.display{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:12px 0}button,select{background:#323f58;color:white;border:1px solid #64728c;padding:8px 12px;border-radius:6px}input[type=range]{min-width:140px;max-width:420px;flex:1;accent-color:#b4a7ff}.notice{background:#29394b;padding:14px;border-radius:8px}details{margin:16px 0}summary{cursor:pointer}</style><h1>흰 테두리 정리 / 검날 보정</h1><p>이전 후보와 같은 선택 프레임·재생 시간입니다. 부츠/코트의 불투명한 흰 점은 주변 재질색으로 정리했습니다. 실제 머리칼·얼굴·옷·무기의 밝은 부분은 수동 보호 영역으로 구분합니다.</p><p class="notice">이번 결과는 선택 32장에 맞춘 보정 실험입니다. 자동 범용 해결이나 전체 영상 수정은 아닙니다. 검날을 다시 그린 버전은 형태가 달라지고, 넓은 베기 잔상은 여전히 남습니다. 기존 생성 영상과 결과는 보존했습니다.</p><p><a href="pixel-outline-repair.zip" download>투명 시트·프레임·보호 영역·수정 내역 ZIP</a></p><div class="display"><label>픽셀 배율 <select id="zoom"><option value="1">1배</option><option value="2">2배</option><option value="3" selected>3배</option><option value="4">4배</option><option value="6">6배</option></select></label><label>확인용 배경 <select id="background"><option value="dark">어두운색</option><option value="light">밝은색</option><option value="checker">체커보드</option></select></label><span>정수 배율로 표시해 화면 확대 때문에 픽셀 폭이 들쭉날쭉해지는 것을 피합니다.</span></div>'''+''.join(sections)+'<script id="configs" type="application/json">'+json.dumps(configs,ensure_ascii=False)+'</script><script>'+SCRIPT+'</script></html>'
 if (out.parent/'pixel-static-source-20261019/preview.html').exists():
  page=page.replace('<h1>흰 테두리 정리 / 검날 보정</h1>','<h1>흰 테두리 정리 / 검날 보정</h1><p class="notice"><a href="../pixel-static-source-20261019/preview.html">최초 정지 스프라이트의 흰 점 보정 비교</a> — 이 페이지는 모션 프레임 비교입니다. 처음 생성한 정지 PNG 보정은 별도 비교로 분리했습니다.</p>',1)
 (out/'preview.html').write_text(page,encoding='utf-8');(out/'preview-script-check.js').write_text(SCRIPT,encoding='utf-8')
 with zipfile.ZipFile(out/'pixel-outline-repair.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in out.rglob('*'):
   if p.is_file() and p.suffix in ('.json','.png','.webp','.html'):z.write(p,p.relative_to(out))
 print('PREVIEW',out/'preview.html',flush=True)
