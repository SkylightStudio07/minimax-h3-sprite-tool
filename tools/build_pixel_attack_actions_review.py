"""Review UI and bundles for independent pixel attack prompt experiments."""
import json,html,zipfile
from tools.verify_pixel_attack_actions import OUT,WIDTH,HEIGHT
from pixel_attack_prompts import TEMPLATES
SCRIPT=r'''
const configs=JSON.parse(document.getElementById('configs').textContent);
for(const cfg of configs){
 const section=document.getElementById(cfg.id),img=section.querySelector('[data-frame]'),slider=section.querySelector('[data-action="slider"]'),label=section.querySelector('[data-phase]'),play=section.querySelector('[data-action="play"]');
 let index=0,playing=true,elapsed=0,last=performance.now();
 function url(i){return cfg.id+'/frame-'+String(i).padStart(2,'0')+'.png'}
 for(let i=0;i<cfg.indices.length;i++){const preload=new Image();preload.src=url(i)}
 function draw(){img.src=url(index);slider.value=index;label.textContent=(index+1)+' / '+cfg.indices.length+' · 원본 '+cfg.indices[index]+'번 · '+(cfg.labels[index]||'');play.textContent=playing?'일시 정지':'재생'}
 function step(delta){playing=false;elapsed=0;index=(index+delta+cfg.indices.length)%cfg.indices.length;draw()}
 play.onclick=()=>{playing=!playing;elapsed=0;last=performance.now();draw()};
 section.querySelector('[data-action="previous"]').onclick=()=>step(-1);
 section.querySelector('[data-action="next"]').onclick=()=>step(1);
 slider.oninput=()=>{playing=false;elapsed=0;index=Number(slider.value);draw()};
 function tick(now){const dt=Math.max(0,Math.min(now-last,200));last=now;if(playing){elapsed+=dt*Number(section.querySelector('[data-action="speed"]').value);let changed=false;while(elapsed>=cfg.durations[index]){elapsed-=cfg.durations[index];index=(index+1)%cfg.indices.length;changed=true}if(changed)draw()}requestAnimationFrame(tick)}
 draw();requestAnimationFrame(tick);
}
document.getElementById('zoom').onchange=e=>document.documentElement.style.setProperty('--scale',e.target.value);
document.getElementById('background').onchange=e=>document.body.dataset.background=e.target.value;
'''
def build():
 cases=[key for key in TEMPLATES if (OUT/key/'frames.json').exists()]
 configs=[];sections=[]
 for key in cases:
  folder=OUT/key;meta=json.loads((folder/'frames.json').read_text(encoding='utf-8'));review=json.loads((folder/'review.json').read_text(encoding='utf-8'));n=len(meta['sourceIndices'])
  configs.append(dict(id=key,indices=meta['sourceIndices'],durations=meta['durationMs'],labels=meta['review'].get('phaseLabels',['']*n)))
  cards=f'<div class="pair"><article><h3>보정된 시작 스프라이트</h3><img class="sprite" src="{key}/reference.png"></article><article><h3>선택 {n}프레임</h3><img class="sprite" data-frame src="{key}/frame-00.png"></article></div>'
  controls=f'<div class="controls"><button data-action="play">일시 정지</button><button data-action="previous" aria-label="이전 프레임">←</button><button data-action="next" aria-label="다음 프레임">→</button><input data-action="slider" type="range" min="0" max="{n-1}" value="0" aria-label="프레임 선택"><label>속도 <select data-action="speed"><option value=".5">0.5배</option><option value="1" selected>1배</option><option value="2">2배</option></select></label><span data-phase></span></div>'
  contacts=''.join(f'<a href="{key}/{p.name}"><img class="contact" src="{key}/{p.name}"></a>' for p in sorted(folder.glob('contact-*.png')))
  sections.append(f'<section id="{key}"><h2>{TEMPLATES[key]["label"]}</h2><p class="notice">{html.escape(review["summary"])}<br>{html.escape(review["limitations"])}</p><p><a href="{key}/sheet-grid.png">6열 투명 PNG 시트</a> · <a href="{key}/animation.webp">애니메이션</a> · <a href="{key}/frames.json">프레임 시간·단계</a> · <a href="{key}/action-raw.mp4">생성 원본 영상</a></p>{cards}{controls}<details><summary>사용한 프롬프트 / 실제 평가</summary><p><a href="{key}/video-settings.json">전체 생성 프롬프트·설정</a> · <a href="{key}/review.json">동작 평가 기록</a></p><pre>{html.escape(TEMPLATES[key]["motion"])}</pre></details><details><summary>전체 프레임 검토 / 원본 영상</summary><video controls src="{key}/action-raw.mp4"></video><p><a href="{key}/full-animation.webp">전체 프레임 도트 애니메이션</a></p>{contacts}</details></section>')
 page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>픽셀 공격 테스트 · 돌려베기 / 점프 내려찍기</title><style>:root{--scale:2}body{background:#151b26;color:#eee;font:15px/1.6 system-ui;max-width:1400px;margin:28px auto;padding:0 20px}h1{font-size:27px}h2{margin-top:34px}h3{font-size:17px}a{color:#c8c4ff}.pair{display:flex;gap:18px;flex-wrap:wrap}article{background:#252d3b;padding:14px;border-radius:10px;min-width:0;overflow-x:auto}.sprite{display:block;width:calc(192px * var(--scale));height:calc(192px * var(--scale));image-rendering:pixelated;max-width:none;background:#202632}body[data-background=light] .sprite{background:#f0f1f4}body[data-background=checker] .sprite{background:repeating-conic-gradient(#202632 0 25%,#455069 0 50%) 0/24px 24px}.controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:12px 0}button,select{background:#323f58;color:white;border:1px solid #64728c;padding:8px 12px;border-radius:6px}input[type=range]{min-width:180px;max-width:500px;flex:1;accent-color:#b4a7ff}.notice{background:#29394b;padding:14px;border-radius:8px}details{margin:18px 0}.contact{max-width:100%;image-rendering:pixelated}video{max-width:100%;width:576px}pre{white-space:pre-wrap}</style><h1>픽셀 공격 테스트 · 돌려베기 / 점프 내려찍기</h1><p>같은 보정 정지 여검사로 행동을 각각 따로 생성했습니다. 입력 정지 PNG의 픽셀을 그대로 192×192 캔버스에 배치해 여백을 추가했습니다. 생성된 동작에서는 체형과 무기 형태가 달라질 수 있습니다. 요청 프롬프트와 실제 평가를 함께 남겨 후속 템플릿 검토에 사용합니다.</p><p><a href="pixel-attack-actions.zip" download>두 동작 시트·전체 프레임·영상·프롬프트 ZIP</a> · <a href="templates.json">실험 템플릿·평가 JSON</a></p><div class="controls"><label>배율 <select id="zoom"><option value="1">1배</option><option value="2" selected>2배</option><option value="3">3배</option></select></label><label>배경 <select id="background"><option value="dark">어두운색</option><option value="light">밝은색</option><option value="checker">체커보드</option></select></label></div>'''+''.join(sections)+'<script id="configs" type="application/json">'+json.dumps(configs,ensure_ascii=False)+'</script><script>'+SCRIPT+'</script></html>'
 (OUT/'preview.html').write_text(page,encoding='utf-8');(OUT/'preview-script-check.js').write_text(SCRIPT,encoding='utf-8')
 with zipfile.ZipFile(OUT/'pixel-attack-actions.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in OUT.rglob('*'):
   if p.is_file() and p.suffix in ('.png','.webp','.json','.mp4','.html'):z.write(p,p.relative_to(OUT))
 print('PREVIEW',OUT/'preview.html',flush=True)

if __name__=='__main__':build()
