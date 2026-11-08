"""Package existing experiment outputs for visual review; does not run inference."""
from pathlib import Path
import json
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/pose-consistency-20261018'
BEFORE=ROOT/'outputs/pose-walk-smoke-20261018-adjusted'
AFTER=ROOT/'outputs/pose-walk-smoke-20261018-identity'


def main():
    for label,folder in [('before',BEFORE),('after',AFTER)]:
        doc=json.loads((folder/'document.json').read_text(encoding='utf-8'))
        frames=[]
        for f in doc['frames']:
            with Image.open(folder/'frames/walk'/f['file']) as opened:
                im=opened.convert('RGBA')
                bg=Image.new('RGB',im.size,(70,73,80));bg.paste(im,mask=im.getchannel('A'));bg.thumbnail((384,576))
                frames.append(bg)
        frames[0].save(OUT/(label+'-walk.webp'),save_all=True,append_images=frames[1:],duration=180,loop=0,quality=88)
    (OUT/'preview.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>걷기 외형 일관성 비교</title>
<style>body{margin:0;padding:24px;background:#151821;color:#eee;font:15px system-ui}main{max-width:1200px;margin:auto}h1{font-size:24px}p{color:#bfc5d2;line-height:1.7}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}article{padding:18px;background:#222734;border-radius:16px}h2{font-size:18px}img{display:block;width:100%;height:65vh;object-fit:contain;background:#464950;border-radius:8px}.sheet{width:100%;height:auto;margin:16px 0}@media(max-width:650px){.pair{grid-template-columns:1fr}img{height:50vh}}</style>
<main><h1>걷기 프레임 · 외형 일관성 비교</h1><p>동일한 원화·관절 템플릿·재현 번호의 4프레임 비교입니다. 새 방식은 원화를 편집하여 첫 프레임을 만들고, 그 프레임을 이후 포즈의 공통 외형 기준으로 사용합니다. 별도 그림체 LoRA는 사용하지 않습니다. 백엔드와 생성 모델이 달라 동일 비용 비교는 아닙니다.</p>
<div class="pair"><article><h2>기존 · 매 프레임 다시 생성</h2><img src="before-walk.webp" alt="기존 4프레임 재생"><p>코트 형태·바지 길이·장갑과 얼굴이 프레임마다 달라집니다.</p></article><article><h2>개선 · 공통 외형 기준으로 편집</h2><img src="after-walk.webp" alt="원화 보존 편집 4프레임 재생"><p>후드·긴 코트·바지·기계 장갑을 공통 기준에서 편집합니다. 다리 교차·팔 동작·발 접지·가장자리와 반복 연결은 여전히 검토가 필요합니다.</p></article></div>
<h2>새 결과 전체 프레임</h2><img class="sheet" src="../pose-walk-smoke-20261018-identity/frames.webp" alt="개선한 4프레임 전체 비교"><p>운영 캐릭터와 기존 결과는 덮어쓰지 않은 실험 출력입니다.</p></main></html>''',encoding='utf-8')
    print(OUT/'preview.html')


if __name__=='__main__':main()
