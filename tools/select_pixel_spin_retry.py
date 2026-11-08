"""Reviewed selections for the two low travelling spin retries."""
import argparse,json
from tools import verify_pixel_spin_retry as run

def select_brake():
 indices=[0,3,8,12,15,16,18,19,20,21,22,23,24,25,26,27,28,30,39,49,51,54,60,72]
 durations=[100,50,60,50,50,50,40,40,40,40,40,40,40,40,40,40,55,80,80,60,70,70,90,150]
 labels=['전진 준비' if i<=15 else '검 당기기' if i<=19 else '오른쪽 베기' if i<=27 else '낮은 마무리' if i<=49 else '새 위치에서 대기 복귀' for i in indices]
 review=dict(summary='오른쪽으로 전진해 한 번 베고 낮은 자세로 멈춥니다. 반복 피겨 회전은 사라졌지만, 몸이 완전히 돌아 등으로 전환하는 동작도 빠졌습니다.',limitations='단발 전진 베기 비교 후보이며 돌려베기 성공으로 분류하지 않습니다. 원본 24~27번 검기/검끝이 오른쪽 끝에 닿습니다. 무기 형태·두 발의 지면 접촉은 수동 정리가 필요합니다.',observedPhases=['2~18 짧은 전진·검 당기기','20~27 한 번 베기','28~49 낮은 마무리 유지','50~60 새 위치에서 대기 복귀'],status='tested: forward lunge slash; full body turn missing',bodyBackEvidence=[],hitSourceFrame=24)
 return indices,durations,labels,review

def select_turn():
 indices=[0,4,8,12,16]+list(range(18,39))+[40,44,50,54,55,56,58,60,64,72]
 durations=[100,50,55,55,65]+[42]*21+[70,70,65,60,45,50,60,70,90,160]
 labels=['준비' if i<8 else '낮게 전진' if i<20 else '한 바퀴 몸 회전' if i<32 else '마무리 공격·제동' if i<39 else '낮은 자세 유지' if i<=55 else '새 위치에서 대기 복귀' for i in indices]
 review=dict(summary='짧게 전진한 뒤 옆·등·정면을 거치는 한 번의 몸 회전이 나오고, 오른쪽 낮은 마무리에서 멈춥니다. 이전의 긴 연속 회전은 사라졌습니다.',limitations='회전 중 무릎이 다시 펴져 피겨 느낌이 일부 남습니다. 짧은 칼끝 잔상 대신 수평 고리 효과가 생성됐고, 마지막은 베기보다 찌르기에 가깝습니다. 긴 검끝/효과의 오른쪽 잘림과 손·검 형태 보정이 필요합니다. 완성된 낮은 돌려베기 템플릿으로 확정하지 않습니다.',observedPhases=['8~19 준비·낮은 전진','20~31 옆·등·정면을 거치는 단발 몸 회전','32~38 수평 고리·오른쪽 마무리','39~55 낮은 자세에서 제동 유지','56~64 대기 복귀'],status='tested: single body turn then braked lunge; upright midpoint, ring and thrust-like finish remain',bodyBackEvidence=[24,25,26,27,28],hitSourceFrame=36)
 return indices,durations,labels,review

def save_selection(root,values):
 indices,durations,labels,review=values;folder=root/'spin_slash'
 post=json.loads((folder/'postprocess.json').read_text(encoding='utf-8'))
 review.update(edgeContactFrames=[d['frame'] for d in post['diagnostic'] if d['edgeContact']],selectedFrames=len(indices),playbackMs=sum(durations),manualVisualReview='All processed contact-sheet frames reviewed; no automatic action quality score.')
 run.base.save(folder,'selection.json',dict(indices=indices,durationMs=durations,phaseLabels=labels,hitEventCandidates=[dict(sourceFrame=review['hitSourceFrame'],selectedFrame=indices.index(review['hitSourceFrame']),kind='시각적 타격 후보; 실제 충돌 검증 아님')],notes='시간순 실제 프레임만 사용. 역재생/새 보간 이미지 없음. '+review['limitations']))
 run.base.save(folder,'review.json',review)
 templates=json.loads((root/'templates.json').read_text(encoding='utf-8'));templates['spin_slash'].update(status=review['status'],observedPhases=review['observedPhases'],limitations=review['limitations'],selectedFrames=len(indices),playbackMs=sum(durations),fullPrompt='spin_slash/video-settings.json',review='spin_slash/review.json')
 run.base.save(root,'templates.json',templates)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--variant',choices=['brake','step-turn'],default='brake');a=p.parse_args()
 if a.variant=='step-turn':save_selection(run.ROOT/'outputs/pixel-spin-step-turn-20261019',select_turn())
 else:save_selection(run.OUT,select_brake())
