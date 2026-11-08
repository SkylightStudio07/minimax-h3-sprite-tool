"""Compare actual walk/run outputs in sync with their intended skeletons; no inference."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import image_pose
OUT=ROOT/'outputs/gait-fullbody-20261018'


def main():
    OUT.mkdir(exist_ok=True)
    cases=[]
    for key,label,folder,action in [
        ('before','이전 걷기','pose-walk-smoke-20261018-identity','walk'),
        ('walk','새 걷기','pose-walk-smoke-20261018-fullbody-walk','walk'),
        ('run','새 달리기','pose-walk-smoke-20261018-fullbody-run','run')]:
        root=ROOT/'outputs'/folder
        doc=json.loads((root/'document.json').read_text(encoding='utf-8'))
        frames=['../'+folder+'/frames/'+action+'/'+f['file'] for f in doc['frames']]
        pose=[]
        if key!='before':
            for i,p in enumerate(doc['motion']['poses']):
                image_pose.render(p,(512,768)).save(OUT/f'{key}-pose-{i}.png')
                pose.append(f'{key}-pose-{i}.png')
        cases.append(dict(key=key,label=label,frames=frames,poses=pose))
    (OUT/'results.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8')
    template='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>걷기·달리기 전신 동작 검토</title>
<style>body{background:#141821;color:#eee;font:15px system-ui;margin:0;padding:24px}main{max-width:1500px;margin:auto}h1{font-size:24px}p{line-height:1.6;color:#c4cad7}.controls{display:flex;gap:20px;align-items:center;flex-wrap:wrap;margin:20px 0}button,input{font:inherit}button{padding:8px 16px}section{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}article{background:#242a36;padding:14px;border-radius:12px}h2{font-size:18px}canvas{display:block;width:100%;height:auto;background:#363d49}article img{width:100%;max-height:220px;object-fit:contain;background:#10141c;margin-top:10px}@media(max-width:800px){section{grid-template-columns:1fr}}</style>
<main><h1>걷기 / 달리기 · 실제 4프레임 비교</h1><p>같은 원화로 생성한 검토용 결과입니다. 포즈를 개선해도 모델이 그대로 따르는 것은 아닙니다. 팔의 반대 스윙·어깨/골반 변화·발 중복·몸 크기 흔들림을 확인하세요. 각 프레임을 따로 편집한 결과이며 시간축을 함께 생성한 영상은 아닙니다. 운영 결과는 변경하지 않았습니다.</p>
<div class="controls"><button id="play">정지</button><label>프레임 <input id="frame" type="range" min="0" max="3" value="0"></label><output id="number">1 / 4</output><label>검토 속도 <input id="fps" type="number" min="1" max="12" value="4" style="width:60px"> FPS</label></div><section id="cases"></section><p>아래 뼈대는 생성 모델에 전달한 목표 포즈입니다. 실제 이미지와 나란히 비교하세요. 4장은 동작 확인용이며 부드러운 루프를 검증하는 샘플 수는 아닙니다.</p></main>
<script>const cases=__DATA__;let index=0,playing=true,last=0;const views=[];for(const c of cases){const a=document.createElement('article'),h=document.createElement('h2'),canvas=document.createElement('canvas'),pose=document.createElement('img');h.textContent=c.label;canvas.width=512;canvas.height=768;a.append(h,canvas);if(c.poses.length){pose.alt='목표 뼈대';a.append(pose)}document.querySelector('#cases').append(a);views.push({canvas,pose,frames:c.frames.map(src=>{const im=new Image();im.src=src;im.onload=draw;return im}),poses:c.poses})}function draw(){for(const v of views){const ctx=v.canvas.getContext('2d');ctx.fillStyle='#363d49';ctx.fillRect(0,0,512,768);ctx.strokeStyle='#6d788c';ctx.beginPath();ctx.moveTo(0,730);ctx.lineTo(512,730);ctx.stroke();const im=v.frames[index];if(im.complete&&im.naturalWidth)ctx.drawImage(im,0,0,512,768);if(v.poses.length)v.pose.src=v.poses[index]}document.querySelector('#number').textContent=(index+1)+' / 4';document.querySelector('#frame').value=index}document.querySelector('#play').onclick=()=>{playing=!playing;document.querySelector('#play').textContent=playing?'정지':'재생'};document.querySelector('#frame').oninput=e=>{playing=false;document.querySelector('#play').textContent='재생';index=Number(e.target.value);draw()};function tick(t){const fps=Math.max(1,Math.min(12,Number(document.querySelector('#fps').value)||4));if(playing&&t-last>1000/fps){last=t;index=(index+1)%4;draw()}requestAnimationFrame(tick)}requestAnimationFrame(tick);draw();</script></html>'''
    video=ROOT/'outputs/gait-video-20261018'
    if all((video/action/(action+'_raw.mp4')).is_file() for action in ('walk','run')):
        cards=''.join('<article><h2>영상 기반 · '+label+'</h2><video src="../gait-video-20261018/'+action+'/'+action+'_raw.mp4" controls autoplay loop muted playsinline style="width:100%"></video></article>' for action,label in [('walk','걷기'),('run','달리기')])
        template=template.replace('</main>','<h2>연속 동작 비교</h2><p>기존에 설치된 영상 모델로 시간축을 함께 생성한 별도 실험입니다. 위 새 걷기의 첫 프레임을 공통 원화로 사용했습니다. 512×512·3초·24FPS 원본이며 안정화·루프 보정은 껐습니다. 프레임별 이미지 편집과 비용·해상도·프레임 수가 다른 비교입니다. 영상에서도 상체 움직임·무기와 의상 보존·방향·발 미끄러짐을 확인하세요.</p><section>'+cards+'</section></main>')
    (OUT/'preview.html').write_text(template.replace('__DATA__',json.dumps(cases,ensure_ascii=False)),encoding='utf-8')
    print(OUT/'preview.html')


if __name__=='__main__':main()
