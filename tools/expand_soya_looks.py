"""Curated Soya refinement recipes, separate from subjects and artist identities."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
COMMON_NEG='photorealistic, 3d render, plastic skin, oily skin, excessive bloom, heavy lens flare'
# id, name, prompt, negative, detail LoRA, denoise, vibrance, saturation
GROUPS={
'soya-cel':('Soya · 셀 채색',[
('clean','깔끔한 2단 셀','clean tapered anime lineart, two-tone cel shading, crisp shadow boundaries, matte colors, restrained highlights','painterly texture, soft gradient shadows',.2,.25,5,0),
('soft','부드러운 셀','delicate colored outlines, soft low-contrast cel shadows, gentle midtones, matte anime coloring','thick black outlines, harsh contrast',.2,.25,-5,-5),
('vivid','선명한 셀','clean fine outlines, vivid controlled anime colors, clear two-tone shadows, sharp graphic color separation','muddy colors, oversaturated skin',.25,.28,15,10),
('muted','저채도 셀','fine clean linework, muted sophisticated colors, flat cel shadows, restrained cool highlights','neon colors, glossy skin',.15,.25,-15,-20),
('pastel','파스텔 셀','light pastel palette, pale colored outlines, lavender and peach cel shadows, airy matte colors','dense black shadows, gritty texture',.2,.3,-5,-10),
('retro','레트로 TV 애니','1990s anime cel rendering, confident ink contours, simple flat shadows, restrained analog colors','3d lighting, glossy digital finish',.15,.32,-10,-5),
('modern','현대 TV 애니','modern TV anime frame, precise thin lineart, consistent two-step cel shading, clean matte surfaces','sketch lines, photoreal textures',.25,.25,5,0),
('highcontrast','강한 명암 셀','bold graphic anime shading, deep flat cast shadows, clear light-dark separation, minimal gradients','soft airbrush, heavy glow',.25,.3,5,0),
('coloredline','색선 셀','colored lineart matched to local colors, clean anime contours, matte cel shading, softly tinted shadows','heavy black outlines, grainy paint',.2,.3,0,-5),
]),
'soya-line':('Soya · 선화·원화',[
('ink','정돈된 잉크 선화','monochrome anime ink drawing, precise tapered black lines, fine controlled contour variation, sparse flat shadows','colorful shading, gray wash',.15,.32,-100,-100),
('pencil','연필 러프','graphite anime pencil sketch, visible construction strokes, delicate hatching, light graphite texture, white paper','polished digital painting, colored skin',.1,.35,-100,-100),
('keyframe','애니 원화 느낌','anime key animation drawing, clean expressive pencil contours, minimal shading, sparse light gray shadow guides','finished glossy illustration, full color rendering',.1,.35,-100,-100),
('thin','가는 펜 선화','very fine precise monochrome pen linework, delicate outer contours, sparse detail, minimal shadow masses','bold outlines, thick hatching',.15,.3,-100,-100),
('bold','굵은 잉크 외곽선','confident thick outer contours and thin interior details, monochrome anime ink drawing, clean graphic black shapes','messy scribbles, painterly gradients',.2,.3,-100,-100),
('hatch','해칭 선화','monochrome anime pen illustration, disciplined crosshatching shadows, varied line weight, clean white spaces','soft airbrush shading, color fill',.2,.35,-100,-100),
('bluepencil','청색 연필 느낌','blue pencil anime drawing on white paper, loose clean strokes, pale blue shadows, minimal color','full color painting, black heavy shading',.1,.38,-20,-45),
('sepia','세피아 잉크','sepia monochrome anime ink illustration, warm brown contours, light cream paper, restrained crosshatching','vivid saturated colors, realistic skin',.15,.35,-20,-65),
('celguide','명암 가이드 선화','anime production drawing, clear fine contours, sparse geometric shadow guide lines, pale flat shadow annotations','text labels, dense painterly rendering',.1,.32,-40,-65),
]),
'soya-game':('Soya · 게임 일러스트',[
('tactical','차가운 전술 일러스트','refined tactical anime game illustration, cool gray color design, crisp linework, matte fabric, disciplined cel shadows','oily skin, dramatic neon bloom',.3,.28,-5,-15),
('rpg','담백한 RPG 원화','Japanese RPG character illustration, elegant clean contours, subtle watercolor-like color edges, restrained material highlights','photoreal rendering, heavy oil paint',.25,.32,0,-5),
('vn','비주얼 노벨 채색','visual novel character art, polished thin lineart, smooth restrained cel shading, clear facial features, soft matte colors','3d skin lighting, harsh noisy texture',.25,.28,5,0),
('card','카드 일러스트 채색','refined anime character card illustration, precise layered shading, luminous controlled edge highlights, rich balanced colors','extreme bloom, cluttered composition',.35,.32,15,5),
('sprite','전투 스프라이트 채색','readable anime game sprite rendering, decisive outer contours, simplified interior shadow shapes, crisp material boundaries','tiny noisy texture, smeared edges',.2,.28,5,0),
('scifi','SF 콘셉트 채색','anime science fiction concept art rendering, cool graphite shadows, precise clean contours, restrained cyan edge accents, matte materials','cyberpunk neon fog, metallic skin',.3,.3,5,-10),
('fantasy','부드러운 판타지 채색','anime fantasy character illustration, elegant tapered outlines, warm subdued highlights, delicate cool shadows, matte fabric','photoreal skin, dense oily texture',.3,.3,0,-5),
('muted','무광 콘셉트 아트','anime character concept rendering, desaturated sophisticated palette, clear graphic shadow planes, matte surfaces, restrained highlights','shiny plastic materials, heavy gradients',.2,.3,-20,-20),
('graphic','그래픽 게임 아트','graphic anime game character art, bold outer silhouettes, flat angular shadow planes, limited balanced palette, crisp edges','photographic textures, soft blurry gradients',.2,.32,5,-5),
]),
'soya-paint':('Soya · 일러스트·질감',[
('softwash','담백한 수채 채색','anime watercolor illustration, transparent light color washes, clean delicate contours, subtle paper grain, gentle shadow edges','thick impasto, oily skin, realistic portrait',.2,.35,-10,-10),
('gouache','과슈 색면','anime gouache illustration, opaque matte color planes, softly broken paint edges, restrained brush texture, clean facial drawing','thick oil impasto, 3d shading',.2,.35,0,-5),
('paper','종이 질감 채색','clean anime illustration on subtly textured paper, fine colored outlines, matte muted colors, gentle grain','dirty noise, gritty damaged paper',.2,.3,-10,-10),
('colorpencil','색연필 채색','anime colored pencil illustration, delicate layered colored strokes, light paper texture, crisp expressive contours','glossy digital skin, heavy black shading',.15,.35,-5,-10),
('editorial','담백한 표지 일러스트','refined anime editorial illustration, elegant sparse linework, flat color design, subtle dimensional shading, sophisticated muted palette','magazine text, typography, heavy glossy rendering',.25,.3,-10,-10),
('softlight','부드러운 확산광','clean anime illustration, soft diffused ambient lighting, fine contours, restrained smooth shadow transitions, matte highlights','overexposed glow, lens flare, realistic skin',.3,.28,0,-5),
('twilight','차가운 보랏빛 채색','anime illustration with cool lavender shadow colors, subdued warm highlights, fine clean lines, balanced muted colors','neon purple saturation, heavy bloom',.25,.3,-5,-10),
('warm','따뜻한 크림색 채색','anime illustration with soft cream highlights, warm muted midtones, delicate brown contours, matte color finish','orange color cast, glossy skin',.25,.3,-5,-5),
('crisp','정교한 선·담백한 채색','precise refined anime linework, finely separated material shadows, understated color gradients, controlled detail density, matte finish','excessive tiny details, plastic skin, heavy black outlines',.3,.25,0,0),
])}


def main():
    path=ROOT/'web/assets/image-looks.json'
    data=json.loads(path.read_text(encoding='utf-8'))
    additions=[]
    for group,(title,rows) in GROUPS.items():
        for suffix,name,prompt,negative,detail,denoise,vibrance,saturation in rows:
            additions.append(dict(id=group+'-'+suffix,group=group,name=name,model='soya-anima-flanime',
                styleId=None,styleStrength=.3,steps=16,cfg=2,prompt=prompt,negative=negative+', '+COMMON_NEG,
                workflow=dict(kieedStrength=.3,detailStrength=detail,refineDenoise=denoise,vibrance=vibrance,saturation=saturation),
                verification='실제 예시 생성 대기 · 실험적',note='Soya 기본 조합의 재처리 채색 설정. 캐릭터·의상·소품이 달라질 수 있어요.',listed=True))
            if group=='soya-line':
                additions[-1].update(basePrompt='monochrome anime pencil line drawing on white paper, uncolored, clean fine contours, minimal hatching, unshaded white spaces',baseNegative='full color, painted skin, colorful illustration, heavy shading, realistic photograph')
                additions[-1]['workflow']['kieedStrength']=.1
                if suffix!='celguide':additions[-1]['finalTone']={'bluepencil':'blue','sepia':'sepia'}.get(suffix,'grayscale')
            if group=='soya-paint':
                additions[-1].update(basePrompt='anime watercolor illustration, pencil-like fine line texture, translucent matte color washes, subtle paper grain, isolated character only',baseNegative='glossy digital painting, plastic skin, 3d render, photograph, art supplies, marker pens, pencils, brushes, paint tubes, artist palette, stationery, art tools beside the character')
                additions[-1]['workflow']['kieedStrength']=.1
    ids={s['id'] for s in additions}
    previous={s['id']:s for s in data['looks']}
    for item in additions:
        old=previous.get(item['id'])
        if old and all(old.get(k)==item.get(k) for k in ('model','prompt','negative','workflow','steps','cfg','styleId','basePrompt','baseNegative','finalTone')):
            for key in ('preview','previews','verification','note'):
                if key in old:item[key]=old[key]
    data['looks']=[s for s in data['looks'] if s['id'] not in ids]+additions
    gids={'soya',*GROUPS}
    data['groups']=[dict(id='soya',name='Soya 전체 · 기본 워크플로')]+[dict(id=k,name=v[0]) for k,v in GROUPS.items()]+[g for g in data['groups'] if g['id'] not in gids]
    data['version']=4
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Added',len(additions),'Soya presets')


if __name__=='__main__':main()
