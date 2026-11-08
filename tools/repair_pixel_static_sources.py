"""Repair the original STILL references, not any motion or sheet frames.

Semantic mask removes only near-white contamination rejected as background.
Hand-reviewed masks preserve this reference's face, hair, cuffs and weapon.
"""
import sys,json,hashlib,zipfile
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.repair_pixel_sprite_contours import dehalo,line_mask
import image_background
SOURCE=ROOT/'outputs/pixel-female-combat-20261019';OUT=ROOT/'outputs/pixel-static-source-20261019'

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def protection(name,alpha):
 mask=np.zeros((128,128),bool)
 if name=='swordswoman':
  mask[28:39,54:66]=True
  mask|=line_mask((72,61),(99,46),width=4,extension=3)[0]
 else:
  mask[19:40,28:51]=True # Original silver hair/face and hat, not the arm gap.
  mask|=line_mask((50,36),(107,36),width=3,extension=2)[0] # Entire long musket.
  mask[38:46,64:77]=alpha[38:46,64:77]>=180 # Actual supporting cuff/fingers.
 return mask

def main():
 OUT.mkdir(exist_ok=True);records={}
 for name in ['swordswoman','musketeer']:
  source=SOURCE/name;target=OUT/name;target.mkdir(exist_ok=True)
  originals={f:digest(source/f) for f in ['reference-raw.png','reference.png','reference-clean.png','video-input.png','action-raw.mp4','sheet-grid.png']}
  raw=Image.open(source/'reference-raw.png').convert('RGBA');raw.save(target/'generated-original.png')
  original=np.array(Image.open(source/'reference.png').convert('RGBA'));mild=np.array(Image.open(source/'reference-clean.png').convert('RGBA'))
  cached=OUT/f'{name}-ai-highres.png'
  cachemeta=cached.with_suffix('.json');rawhash=digest(source/'reference-raw.png')
  if cached.exists() and cachemeta.exists() and json.loads(cachemeta.read_text(encoding='utf-8')).get('rawSha256')==rawhash:ai=Image.open(cached).convert('RGBA')
  else:
   ai=image_background.remove(raw);ai.save(cached);cachemeta.write_text(json.dumps(dict(rawSha256=rawhash)),encoding='utf-8')
  ai.save(target/'ai-mask-highres.png');alpha=np.array(ai.getchannel('A').resize((128,128),Image.Resampling.NEAREST))
  Image.fromarray(alpha).save(target/'ai-mask-128.png')
  preserve=protection(name,alpha);rgb=mild[:,:,:3].astype(float)
  # AI decides only whether a near-white fragment lies outside the character.
  # Preserve existing dark outlines, thin weapon and all other original colours.
  removable=(mild[:,:,3]>0)&(rgb.min(axis=2)>140)&(np.ptp(rgb,axis=2)<65)&(alpha<128)&~preserve
  prepared=mild.copy();prepared[removable]=0
  corrected,stat=dehalo(prepared,preserve)
  assert np.array_equal(corrected[preserve],mild[preserve])
  # Exact palettes remain fixed; no diffusion, recolouring of interiors or weapon redraw.
  palette={tuple(c) for c in json.loads((source/'reference-settings.json').read_text(encoding='utf-8'))['palette'][:32]}
  assert {tuple(c) for c in np.unique(corrected[:,:,:3][corrected[:,:,3]>0],axis=0)}<=palette
  for filename,a in [('before.png',original),('previous-clean.png',mild),('corrected.png',corrected)]:
   Image.fromarray(a).save(target/filename)
   Image.fromarray(a).resize((512,512),Image.Resampling.NEAREST).save(target/filename.replace('.png','-4x.png'))
  Image.fromarray(preserve.astype(np.uint8)*255).save(target/'protected-materials.png')
  Image.fromarray(corrected).save(source/'reference-static-clean.png');Image.fromarray(corrected).resize((512,512),Image.Resampling.NEAREST).save(source/'reference-static-clean-large.png')
  assert all(digest(source/f)==v for f,v in originals.items())
  stat.update(aiRejectedWhitePixelsRemoved=int(removable.sum()),changedVisiblePixels=int((np.any(original!=corrected,axis=2)&((original[:,:,3]>0)|(corrected[:,:,3]>0))).sum()),originalHashes=originals,source='original reference-raw/reference PNG; no motion frame used',manualMaterialMask=True,motionAndSheetsUnchanged=True)
  records[name]=stat;print(name,stat['changedVisiblePixels'],'visible pixels changed; AI removed',stat['aiRejectedWhitePixelsRemoved'],'white fragments',flush=True)
 comparison=Image.new('RGB',(1536,1024),'#202632');draw=ImageDraw.Draw(comparison)
 for row,name in enumerate(records):
  for col,(file,label) in enumerate([('before.png','INITIAL SPRITE'),('previous-clean.png','PREVIOUS STATIC FIX'),('corrected.png','STATIC OUTLINE CLEANUP')]):
   im=Image.open(OUT/name/file).convert('RGBA').resize((512,512),Image.Resampling.NEAREST);comparison.paste(im,(col*512,row*512),im);draw.text((col*512+10,row*512+10),name+' / '+label,fill='white')
 comparison.save(OUT/'static-comparison.png');(OUT/'results.json').write_text(json.dumps(dict(target='original still sprites only',records=records,limitations='These protected material regions are reference-specific. No animation, blade redraw, new AI generation, model download or production-wide auto fix.'),ensure_ascii=False,indent=2),encoding='utf-8')
 build()

def build():
 cards=[]
 for name,label in [('swordswoman','여검사 · 최초 정지 스프라이트'),('musketeer','여총사 · 최초 정지 스프라이트')]:
  imgs=''.join(f'<article><h3>{title}</h3><img src="{name}/{file}" alt="{label} {title}"><p><a href="{name}/{file}" download>128px 투명 PNG 저장</a></p></article>' for file,title in [('before.png','처음 내보낸 정지 이미지'),('previous-clean.png','이전 약한 경계 보정'),('corrected.png','정지 원본을 다시 정리한 결과')])
  cards.append(f'<section><h2>{label}</h2><div class="cards">{imgs}</div><details><summary>생성 원본과 보호 영역</summary><p><a href="{name}/generated-original.png">배경 포함 생성 원본</a> · <a href="{name}/ai-mask-128.png">AI 전경 마스크</a> · <a href="{name}/protected-materials.png">밝은 재질 보호 영역</a></p></details></section>')
 script="const z=document.getElementById('zoom'),b=document.getElementById('background');z.onchange=()=>document.documentElement.style.setProperty('--zoom',z.value);b.onchange=()=>document.body.dataset.background=b.value;"
 page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>최초 정지 스프라이트 · 흰 점 정리</title><style>:root{--zoom:3}body{background:#151b26;color:#eee;font:15px/1.6 system-ui;max-width:1440px;margin:28px auto;padding:0 20px}a{color:#c8c4ff}h1{font-size:27px}h2{margin-top:32px}h3{font-size:15px}article{background:#252d3b;border-radius:10px;padding:12px;flex:0 0 auto;width:calc(128px * var(--zoom))}.cards{display:flex;gap:16px;flex-wrap:wrap;overflow-x:auto}img{display:block;width:calc(128px * var(--zoom));height:calc(128px * var(--zoom));image-rendering:pixelated;background:#202632}body[data-background=light] img{background:#f0f1f4}body[data-background=checker] img{background:repeating-conic-gradient(#202632 0 25%,#455069 0 50%) 0/24px 24px}.controls{display:flex;gap:20px;align-items:center;flex-wrap:wrap}select{background:#323f58;color:white;border:1px solid #64728c;padding:8px 12px;border-radius:6px}.notice{background:#29394b;padding:14px;border-radius:8px}details{margin:12px 0}</style><h1>최초 정지 스프라이트 · 흰 점 정리</h1><p class="notice">움직이는 프레임이 아니라 처음 생성한 정지 PNG만 비교합니다. 모션 후처리·영상·스프라이트 시트는 그대로 유지했습니다.</p><p>생성 원본을 AI 전경 마스크와 대조하고, 도트 축소 뒤 몸·옷 경계에 남은 밝은 점을 정리했습니다. 실제 흰 머리·옷·무기는 수동 보호 영역으로 구분했습니다. 두 캐릭터에 맞춘 보정이며 범용 자동 해결은 아닙니다.</p><p><a href="static-sprites-cleaned.zip" download>보정 정지 PNG·비교·마스크 ZIP</a></p><div class="controls"><label>배율 <select id="zoom"><option value="1">1배</option><option value="2">2배</option><option value="3" selected>3배</option><option value="4">4배</option><option value="6">6배</option></select></label><label>배경 <select id="background"><option value="dark">어두운색</option><option value="light">밝은색</option><option value="checker">체커보드</option></select></label></div>'''+''.join(cards)+'<script>'+script+'</script></html>'
 (OUT/'preview.html').write_text(page,encoding='utf-8');(OUT/'preview-script-check.js').write_text(script,encoding='utf-8')
 with zipfile.ZipFile(OUT/'static-sprites-cleaned.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in OUT.rglob('*'):
   if p.is_file() and p.suffix in ('.png','.json','.html') and p.parent!=OUT:z.write(p,p.relative_to(OUT))
  for name in ['preview.html','results.json','static-comparison.png','validation.json']:
   if (OUT/name).exists():z.write(OUT/name,name)
 print('PREVIEW',OUT/'preview.html',flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');main()
