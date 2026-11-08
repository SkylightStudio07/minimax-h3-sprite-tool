"""Manual forward-time selections after reviewing every action contact sheet."""
import json
from tools.verify_pixel_attack_actions import OUT
from pixel_attack_prompts import TEMPLATES

def save(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
 templates=json.loads((OUT/'templates.json').read_text(encoding='utf-8'))
 for key in TEMPLATES:
  folder=OUT/key
  if key=='spin_slash':
   indices=[0]+list(range(30,94))+[106]
   duration=[100]+[42]*64+[140]
   labels=['대기' if i==0 or i>=93 else '준비·체중 이동' if i<=37 else '연속 몸 회전·베기' if i<90 else '회전 제동·복귀' for i in indices]
   review=dict(summary='등과 정면이 번갈아 보이는 실제 몸 회전·검기·대기 복귀가 생성됐습니다. 이번 결과는 단발 한 바퀴가 아닌 연속 회전 공격입니다.',limitations='한 바퀴/수평 베기 지시는 정확히 따르지 않았습니다. 큰 검기가 몸과 칼날을 일부 가리고, 무기 형태·회전 중 체격도 흔들립니다. 단발 회전 템플릿은 추가 시험이 필요합니다.',observedPhases=['30~37 준비','38~89 정면/측면/등을 반복하는 몸 회전과 검기','90~93 제동·복귀'],bodyBackEvidence=[38,44,45,50,51,58,65,73,80,87,88],status='tested: repeated full-body spinning slash; single-turn instruction not met')
   events=[dict(selectedFrame=indices.index(40),sourceFrame=40,kind='회전 베기 타격 후보; 실제 충돌 검증 아님')]
  else:
   indices=[0,4,8,16,20,21,22,23,24,26,32,46,48,49,50,51,52,53,54,55,57,60,64,69,74,80,84,88,94,106]
   duration=[100,65,65,75,60,45,40,40,45,60,75,50,35,35,35,35,35,45,65,60,50,60,55,60,60,60,65,65,80,160]
   labels=['준비' if i<=4 else '웅크리기' if i<=20 else '도약' if i<=24 else '공중 준비' if i<=48 else '낙하 베기' if i<=52 else '착지·타격' if i<=60 else '잔광 소멸' if i<=80 else '대기 복귀' for i in indices]
   review=dict(summary='양발 도약 → 검을 든 공중 자세 → 낙하 베기 → 금색 착지 효과 → 오른쪽 대기 복귀가 한 번 생성됐습니다.',limitations='원본 26~46번의 공중 정지가 길어 선택본에서 줄였습니다. 비행 궤적의 물리적 정확성, 손/검날 형태, 착지 때 발 모양은 수동 정리가 필요합니다. 원샷이며 완벽한 연속 루프를 보증하지 않습니다.',observedPhases=['8~20 웅크리기','22~24 양발이 원래 바닥선에서 떨어지는 도약','26~46 긴 공중 준비','49~52 낙하 베기','53 착지와 첫 금색 효과','54~80 효과·잔광','81~94 대기 복귀'],airborneEvidence=[22,24,32,46],landingFrame=53,status='tested: jumping overhead slam, long airborne hold shortened in selection')
   events=[dict(selectedFrame=indices.index(53),sourceFrame=53,kind='착지·첫 타격광 후보; 실제 충돌 검증 아님')]
  post=json.loads((folder/'postprocess.json').read_text(encoding='utf-8'))
  review.update(edgeContactFrames=[d['frame'] for d in post['diagnostic'] if d['edgeContact']],manualVisualReview='All 107 processed frames reviewed in three labelled contact sheets; no automatic action-quality score.',playbackMs=sum(duration),selectedFrames=len(indices))
  save(folder/'selection.json',dict(indices=indices,durationMs=duration,phaseLabels=labels,hitEventCandidates=events,notes='시간순 실제 프레임만 선택. 역재생·새 보간 프레임 없음. 원본의 긴 대기/공중 유지 구간을 단축. '+review['limitations']))
  save(folder/'review.json',review)
  templates[key].update(status=review['status'],observedPhases=review['observedPhases'],limitations=review['limitations'],output=key,selectedFrames=len(indices),playbackMs=sum(duration),fullPrompt=key+'/video-settings.json',review=key+'/review.json',parameters=dict(pixelCanvas=[192,192],videoCanvas=[576,576],fps=24,frames=107,steps=20,seed=TEMPLATES[key]['seed']))
 save(OUT/'templates.json',templates)

if __name__=='__main__':main()
