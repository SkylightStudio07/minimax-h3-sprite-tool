"""User-requested roughly one-third VFX size; regenerate jointly, never scale the character."""
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import verify_normal_sword_vfx_contained
from tools import verify_normal_sword_vfx as base
base.OUT=ROOT/'outputs/normal-sword-vfx-small-20261020'
base.EFFECT_STRENGTH='low'
base.MIN_EFFECT_PIXELS=64
base.COMMON=base.COMMON.replace('Use the generous empty space for the effects.','Most of the surrounding canvas stays empty grey throughout the shot.')
base.EFFECT=(
 'A SMALL LOCAL CYAN SWORD TRAIL, not a special-attack screen effect. '
 'Draw one SHORT THIN curved cyan-white ribbon attached directly to the moving blade tip ONLY during the actual cut. '
 'Keep the entire trail about ONE THIRD the height and width of an oversized character-height energy wave: '
 'a small blade-length accent, never taller than the physical sword and never surrounding the body. '
 'Its thin white highlight and cyan edge make it readable without a large luminous mass. '
 'The trail follows just the most recent short segment of the blade motion and vanishes immediately behind it. '
 'No complete circle, body halo, giant crescent, projectile or lingering energy wall. '
 'At the final cut release only three to six tiny gold sparks near the blade tip, no starburst. '
 'NO long horizontal or vertical light rays, NO cross-shaped flash, NO explosion, NO broad glow, NO secondary ribbons. '
 'Leave the face, hands, torso, knees and foot placement plainly visible. '
 'The trail exists for a brief instant at the cut, then disappears fully well before recovery. '
 'The background remains flat medium grey and the original character colors stay unchanged.')
for name,item in base.CASES.items():
 item['label']='작은 검기 · '+('내려베기' if name=='slash' else '회전베기')
 if name=='slash':
  item['motion']=item['motion'].replace('A blade-length cyan crescent follows this fast sword sweep directly beside her, in exact sync.',
   'A short narrow cyan blade-tip trail briefly accents the fast cut; it stays small and fades immediately.')
 else:
  item['motion']=item['motion'].replace(
   'its cyan energy crescent wraps around that physical path as a wide transient sweeping arc, not a static floating ring.',
   'only a short narrow cyan streak stays attached to the blade tip; do not draw the entire circular sword path or a ring around her.')
  item['motion']=item['motion'].replace('with a gold-white impact burst.','with a few tiny gold sparks and no impact flash.')

def review():
 from tools import build_normal_sword_vfx_review as builder
 builder.OUT=base.OUT
 notes=('검기 크기 축소 시험\n같은 원화/시드로 동작과 작은 칼끝 검기를 함께 새로 생성했습니다.\n'
  '이전 검격의 약 1/3 크기를 요청한 결과이며, 기존 효과 이미지를 잘라서 축소한 작업이 아닙니다.\n'
  '768x768 원본 73프레임. 검 휘두르기 1.5배속, 회전베기 1.25배속. 각 시트는 24장입니다.\n'
  'frames.json의 재생 시간을 사용하세요. 검기는 단색 제거와 색상 역산으로 보존하고 의상은 AI 마스크로 보호했습니다.\n'
  '자세한 시각 검토와 남은 한계는 각 review.json을 확인하세요. 사이트 예시는 교체하지 않았습니다.\n')
 builder.build(notice_text='이전보다 작은 칼끝 검기로 다시 생성했습니다. 정확한 축소 비율과 남은 동작 한계는 생성 결과와 검토 기록을 확인하세요.',notes=notes,labels=['검 휘두르기','회전베기'])
 page=base.OUT/'preview.html';text=page.read_text(encoding='utf-8').replace('검격 이펙트 강화 시험','검기 크기 축소 시험').replace('검기 · 내려베기와 회전베기','작은 검기 · 검 휘두르기와 회전베기').replace('단색 배경 제거와 재생 속도 조정만 적용했습니다.','배경 제거·의상 보호·검기 가장자리 정리와 재생 속도 조정을 적용했습니다.')
 page.write_text(text,encoding='utf-8')
 from tools.measure_sword_vfx_size import measure
 measure(base.OUT)
 text=page.read_text(encoding='utf-8')
 text=text.replace('</main>','</main><details><summary>이전 효과와 같은 배율로 비교</summary><img src="size-comparison.webp"><p>푸른 효과색 기준의 대략적인 비교이며, 흰색 중심과 금빛 불꽃은 수치에서 제외됩니다.</p></details>')
 page.write_text(text,encoding='utf-8')
 import zipfile
 package=base.OUT/'sword-vfx-handoff.zip';temporary=package.with_suffix('.zip.tmp')
 with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
  for name in ('slash','spin'):
   for filename in ('animation.gif','animation.webp','sheet.png','frames.json','settings.json','raw.mp4','review.json'):
    archive.write(base.OUT/name/filename,f'{name}/{filename}')
  for filename in ('README.txt','validation.json','comparison.gif','size-comparison.webp','size-comparison.json'):
   archive.write(base.OUT/filename,filename)
 with zipfile.ZipFile(temporary) as archive:assert archive.testzip() is None
 temporary.replace(package)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('stage',choices=['video','export','build','check','review']);p.add_argument('--case',choices=['slash','spin']);a=p.parse_args()
 if a.case:base.CASES={a.case:base.CASES[a.case]}
 if a.stage=='export':
  for name in base.CASES:
   if (base.OUT/name/'raw.mp4').exists():base.export_case(name)
  base.build()
 elif a.stage=='review':review()
 else:getattr(base,a.stage)()
