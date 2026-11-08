"""Reference + text -> AI-generated attack and effects, with no procedural VFX overlay."""
import argparse,hashlib,json,sys,zipfile
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import verify_chibi_attack as attack
OUT=ROOT/'outputs/chibi-ai-effects-20261020'
ORIGINAL=ROOT/'outputs/chibi-attack-20261020'
EFFECT_DESCRIPTION=(
 'A spectacular stylized BLUE ENERGY SWORD SLASH. During the wind-up a narrow cyan glint charges along the existing blade. '
 'At the actual downward cut, generate ONE LARGE BRIGHT CYAN-BLUE ENERGY CRESCENT following the sword swing in the empty space in front of her, '
 'with a narrow near-white core, saturated turquoise body and cobalt-blue outer edge. '
 'At the end of the cut, a compact GOLD-WHITE IMPACT STARBURST erupts at the blade tip toward screen right and throws a short fan of small golden sparks. '
 'The crescent follows the physical sword path, not an unrelated floating ring or projectile. '
 'The energy is vivid and larger than the blade but stays within the generous empty canvas; keep the face and torso clearly visible. '
 'The crescent breaks into a few small blue fragments and the warm sparks dissipate completely before she finishes recovering. '
 'Exactly one energy pulse with the single attack, no continuous beam, no repeated explosions, no flames covering the body. '
 'Draw the effects in the same sharp square-pixel game style, distinct color clusters, no realistic fire, cinematic bloom or motion blur. '
 'The bright cyan and gold belong to the effects ONLY: do not recolor her cream jacket, teal skirt, brown hair or boots. '
 'The surrounding background remains uniform medium grey, no scenery, floor or cast shadow.')

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def configure():
 attack.OUT=OUT
 attack.PROMPT=attack.PROMPT.replace('A clean physical sword cut with NO magical effects, no slash trail, sparkles, smoke, glow, ground shadow or motion blur hiding the blade. ',EFFECT_DESCRIPTION+' ')
 return attack

def video():
 parent=configure();OUT.mkdir(parents=True,exist_ok=True)
 hashes={str(p.relative_to(ROOT)):sha(p) for folder in [ORIGINAL,ROOT/'outputs/chibi-attack-vfx-20261020'] for p in folder.rglob('*') if p.is_file() and p.suffix in ('.png','.gif','.mp4','.json')}
 if (OUT/'comparison-source-hashes.json').exists():assert read(OUT/'comparison-source-hashes.json')==hashes
 else:save(OUT/'comparison-source-hashes.json',hashes)
 save(OUT/'generation-method.json',dict(method='AI joint attack and visual-effects generation',effectDescription=EFFECT_DESCRIPTION,model='same installed MiniMax H3 20 steps',sameInputAndSeedAsOriginal=True,proceduralEffectOverlay=False,manualEffectCoordinates=False,separateEffectLayers=False,scope='local test; no production preset changes'))
 parent.video()

def learn_palette():
 """Keep original source colors and learn up to 16 extra colors from the AI video."""
 import av
 settings=read(OUT/'source-settings.json');original=np.array(read(attack.SOURCE/'palette.json')['colors'],np.int32);samples=[];counts=[]
 with av.open(str(OUT/'attack-raw.mp4')) as clip:
  for i,frame in enumerate(clip.decode(video=0)):
   rgb=np.array(frame.to_image().convert('RGB'))
   bg=np.median(np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1])),axis=0)
   candidate=rgb[2::8,2::8].reshape(-1,3).astype(np.int32)
   colorful=(np.ptp(candidate,axis=1)>35)&(np.max(np.abs(candidate-bg),axis=1)>32)
   candidate=candidate[colorful]
   distances=((candidate[:,None,:]-original[None,:,:])**2).sum(axis=2).min(axis=1) if len(candidate) else np.array([])
   candidate=candidate[distances>22**2];counts.append(dict(frame=i,extraColorSamples=len(candidate)))
   if len(candidate)>512:candidate=candidate[np.linspace(0,len(candidate)-1,512).round().astype(int)]
   if len(candidate):samples.append(candidate.astype(np.uint8))
 extra=[]
 if samples:
  pixels=np.concatenate(samples);im=Image.fromarray(pixels.reshape(-1,1,3));q=im.quantize(colors=16,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
  for row in np.unique(np.array(q.convert('RGB')).reshape(-1,3),axis=0).tolist():
   if row not in original.tolist():extra.append(row)
 palette=original.tolist()+extra;assert len(palette)<=48
 settings.update(palette=palette,paletteMethod='original reference colors + up to 16 shared colors automatically learned from generated video',originalCharacterPalette=original.tolist(),learnedVideoColors=extra,proceduralEffectOverlay=False)
 save(OUT/'source-settings.json',settings);save(OUT/'palette-analysis.json',dict(extraColors=extra,frameSamples=counts,globalAcrossFrames=True,colorsPaintedByHand=False))
 print('PALETTE',len(original),'reference +',len(extra),'learned video colors',flush=True)

def process():
 configure();learn_palette();attack.process();build()

def selected():configure();attack.selected();build()

def build():
 configure();attack.build()
 path=OUT/'preview.html';page=path.read_text(encoding='utf-8')
 page=page.replace('<title>치비 · 검 공격</title>','<title>치비 · AI 검기 생성</title>').replace('<h1>치비 · 오른쪽 검 공격</h1>','<h1>치비 · 공격과 이펙트 AI 생성</h1>')
 page=page.replace('영상 생성 → 기존 팔레트/윤곽/시간축 후처리 도트입니다.','검기·섬광·불꽃을 MiniMax가 공격과 함께 생성한 결과입니다. 코드로 이펙트 모양/위치를 그려 넣지 않았습니다. 후처리는 배경 제거·도트화·공통 팔레트·시간축 정리입니다. 새 효과색이 사라지지 않도록 원본 색에 영상에서 학습한 공통 색을 추가했습니다.')
 page=page.replace('chibi-attack.zip','chibi-ai-effects.zip').replace('PNG·GIF·전체 프레임 ZIP','AI 결과 PNG·GIF·전체 프레임 ZIP')
 page=page.replace('<article id="attack">','<p>이번 결과는 캐릭터와 효과가 함께 생성되어 분리된 이펙트 레이어는 없습니다. 입력 캐릭터와 시드는 기존 공격과 같지만, 생성된 동작과 얼굴이 완전히 같다는 뜻은 아닙니다.</p><article id="attack">')
 path.write_text(page,encoding='utf-8')
 with zipfile.ZipFile(OUT/'chibi-ai-effects.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in OUT.rglob('*'):
   if p.is_file() and p.suffix in ('.png','.webp','.gif','.mp4','.json','.html','.js'):z.write(p,p.relative_to(OUT))
 print('AI_EFFECTS_PREVIEW',path,flush=True)

def check():
 configure();attack.check()
 for p,h in read(OUT/'comparison-source-hashes.json').items():assert sha(ROOT/p)==h
 assert sha(OUT/'video-input.png')==sha(ORIGINAL/'video-input.png')
 assert read(OUT/'generation-method.json')['proceduralEffectOverlay'] is False
 assert read(OUT/'video-settings.json')['seed']==read(ORIGINAL/'video-settings.json')['seed']
 assert len(read(OUT/'source-settings.json')['palette'])<=48
 validation=read(OUT/'validation.json');validation.update(sameInputAndSeedAsOriginal=True,previousAttackAndManualVfxUnchanged=True,proceduralEffectOverlay=False,manualEffectCoordinates=False,separateEffectLayers=False,paletteLearnedFromVideo=True);save(OUT/'validation.json',validation);build()
 edges=[v['frame'] for v in read(OUT/'postprocess.json')['diagnostic'] if v['edgeContact']]
 validation.update(effectEdgeContactFrames=edges,productionReady=False);save(OUT/'validation.json',validation);build()
 with zipfile.ZipFile(OUT/'chibi-ai-effects.zip') as z:assert z.testzip() is None and z.read('validation.json')==(OUT/'validation.json').read_bytes()
 print('PASS AI provenance, unchanged earlier results, same input/seed, learned palette and ZIP',flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['video','process','selected','build','check']);a=p.parse_args();globals()[a.stage]()
