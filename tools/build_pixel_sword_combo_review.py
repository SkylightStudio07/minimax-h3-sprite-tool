"""Local review/export package for the actual generated pixel combo."""
import json,zipfile,html
from tools.verify_pixel_sword_combo import OUT
SCRIPT=r'''
const cfg=JSON.parse(document.getElementById('cfg').textContent),img=document.getElementById('frame'),slider=document.getElementById('slider'),label=document.getElementById('phase'),play=document.getElementById('play');
let index=0,playing=true,elapsed=0,last=performance.now();
function url(i){return 'frame-'+String(i).padStart(2,'0')+'.png'}
for(let i=0;i<cfg.indices.length;i++){const p=new Image();p.src=url(i)}
function draw(){img.src=url(index);slider.value=index;label.textContent=(index+1)+' / '+cfg.indices.length+' · 원본 '+cfg.indices[index]+'번 · '+(cfg.labels[index]||'');play.textContent=playing?'일시 정지':'재생'}
function step(delta){playing=false;elapsed=0;index=(index+delta+cfg.indices.length)%cfg.indices.length;draw()}
play.onclick=()=>{playing=!playing;elapsed=0;last=performance.now();draw()};
document.getElementById('previous').onclick=()=>step(-1);document.getElementById('next').onclick=()=>step(1);
slider.oninput=()=>{playing=false;elapsed=0;index=Number(slider.value);draw()};
document.getElementById('zoom').onchange=e=>document.documentElement.style.setProperty('--scale',e.target.value);
document.getElementById('background').onchange=e=>document.body.dataset.background=e.target.value;
function tick(now){const dt=Math.max(0,Math.min(now-last,200));last=now;if(playing){elapsed+=dt*Number(document.getElementById('speed').value);let changed=false;while(elapsed>=cfg.durations[index]){elapsed-=cfg.durations[index];index=(index+1)%cfg.indices.length;changed=true}if(changed)draw()}requestAnimationFrame(tick)}
draw();requestAnimationFrame(tick);
'''

def build():
 meta=json.loads((OUT/'frames.json').read_text(encoding='utf-8'));sel=meta['review'];configs=dict(indices=meta['sourceIndices'],durations=meta['durationMs'],labels=sel.get('phaseLabels',['']*len(meta['sourceIndices'])))
 review=OUT/'review.json';review=json.loads(review.read_text(encoding='utf-8')) if review.exists() else dict(summary='생성 결과 검수 중',limitations='최종 판정 전')
 contacts=''.join(f'<p><a href="{p.name}">전체 프레임 {p.stem.split("-")[-1]}번부터</a></p><img class="contact" src="{p.name}">' for p in sorted(OUT.glob('contact-*.png')))
 page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>픽셀 여검사 · 연속 베기</title><style>:root{--scale:3}body{background:#151b26;color:#eee;font:15px/1.6 system-ui;max-width:1400px;margin:28px auto;padding:0 20px}h1{font-size:27px}h2{font-size:19px}a{color:#c8c4ff}.pair{display:flex;gap:18px;flex-wrap:wrap}article{background:#252d3b;padding:14px;border-radius:10px;min-width:0;overflow-x:auto}.sprite{display:block;width:calc(192px * var(--scale));height:calc(128px * var(--scale));image-rendering:pixelated;max-width:none;background:#202632}body[data-background=light] .sprite{background:#f0f1f4}body[data-background=checker] .sprite{background:repeating-conic-gradient(#202632 0 25%,#455069 0 50%) 0/24px 24px}.controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:12px 0}button,select{background:#323f58;color:white;border:1px solid #64728c;padding:8px 12px;border-radius:6px}input[type=range]{min-width:180px;max-width:500px;flex:1;accent-color:#b4a7ff}.notice{background:#29394b;padding:14px;border-radius:8px}details{margin:18px 0}.contact{max-width:100%;image-rendering:pixelated}video{max-width:100%;width:768px}</style><h1>픽셀 여검사 · 연속 베기</h1><p>채택한 정지 보정본 → 가로 여백 추가 → MiniMax 영상 생성 → 고정 팔레트·시간축 도트 후처리. 캐릭터를 줄이지 않고 192×128 캔버스에 배치했습니다.</p><p class="notice">__SUMMARY__<br>__LIMITATIONS__</p><p><a href="pixel-sword-combo.zip" download>투명 시트·프레임·영상·설정 ZIP</a> · <a href="sheet-grid.png">6열 투명 PNG 시트</a> · <a href="frames.json">프레임 표시 시간·동작 단계</a> · <a href="combo-raw.mp4">생성 원본 영상</a></p><div class="controls"><label>배율 <select id="zoom"><option value="2">2배</option><option value="3" selected>3배</option><option value="4">4배</option></select></label><label>배경 <select id="background"><option value="dark">어두운색</option><option value="light">밝은색</option><option value="checker">체커보드</option></select></label></div><div class="pair"><article><h2>보정된 시작 스프라이트</h2><img class="sprite" src="reference.png"></article><article><h2>연속 공격 · 선택 프레임</h2><img class="sprite" id="frame" src="frame-00.png"></article></div><div class="controls"><button id="play">일시 정지</button><button id="previous" aria-label="이전 프레임">←</button><button id="next" aria-label="다음 프레임">→</button><input id="slider" aria-label="프레임 선택" type="range" min="0" max="__MAX__" value="0"><label>속도 <select id="speed"><option value=".5">0.5배</option><option value="1" selected>1배</option><option value="2">2배</option></select></label><span id="phase"></span></div><p>원샷 공격을 미리보기에서 반복합니다. 게임용 표시 시간은 생성 영상의 실제 시간과 별도로 저장합니다. 표기된 타격 시점은 수동 검토 후보이며 충돌 판정 구현이 아닙니다.</p><details><summary>생성 원본 영상 / 전체 도트 애니메이션</summary><video controls src="combo-raw.mp4"></video><p><a href="full-animation.webp">전체 프레임 도트 애니메이션</a></p></details><details><summary>전체 프레임 정지 검토</summary>__CONTACTS__</details><script id="cfg" type="application/json">__CFG__</script><script>__SCRIPT__</script></html>'''
 page=page.replace('__SUMMARY__',html.escape(review['summary'])).replace('__LIMITATIONS__',html.escape(review['limitations'])).replace('__MAX__',str(len(meta['sourceIndices'])-1)).replace('__CONTACTS__',contacts).replace('__CFG__',json.dumps(configs,ensure_ascii=False)).replace('__SCRIPT__',SCRIPT)
 (OUT/'preview.html').write_text(page,encoding='utf-8');(OUT/'preview-script-check.js').write_text(SCRIPT,encoding='utf-8')
 with zipfile.ZipFile(OUT/'pixel-sword-combo.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in OUT.rglob('*'):
   if p.is_file() and p.suffix in ('.png','.webp','.json','.mp4','.html'):z.write(p,p.relative_to(OUT))
 print('PREVIEW',OUT/'preview.html',flush=True)

if __name__=='__main__':build()
