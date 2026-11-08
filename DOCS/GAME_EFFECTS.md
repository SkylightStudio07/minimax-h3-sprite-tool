# 게임 이펙트 생성 실험

2026-10-16, `G:\Minimax`. 사용자가 FastH3 연기 결과를 보고 이펙트 방향 탐색을 승인했다.

## 상태

전용 프롬프트 모듈과 로컬 실생성 프로토타입. 사이트 메뉴/API에는 아직 연결하지 않았고 FastH3의 기존 검증 잠금도 유지한다. 캐릭터 idle의 실패와 이펙트의 유용성을 별도로 판단한다.

- `effect_prompts.py`: 연기/불꽃/오라(루프), 참격/타격 섬광/소멸(단발) 6종. 인간 신체·눈·호흡·기계 제약을 넣지 않는다. 루프에만 마지막 참조 프레임을 연결한다.
- `tools/verify_fasth3_effects.py`: 단순 합성 도형으로 불꽃과 참격을 시험. 팀/Comfy 큐 확인 후 프로세스 내부에서만 준비 상태 우회. 갤러리 등록이나 운영 활성화 없음.
- `test_effect_prompts.py`: 인체 지시 배제, 끝 참조/루프 일치, 사용자 설명 및 미지원 유형 확인. 기존 프롬프트 테스트 포함 14개 통과.

## 실험 결과

공통 512×512, 3초/73프레임, seed 42, FastH3 8스텝. 안정화/루프 최적화 끔. 실제 게임 아트가 아닌 단순 테스트 도형이므로 스타일/입력 전체에 일반화하지 않는다.

| 효과 | 시간 | 관찰 |
|---|---:|---|
| 불꽃 | 60.97초 | 끝이 갈라지고 말리는 변화, 투명 PNG 시트 생성. 밑면·높이도 변하며 루프 연결 완성도는 추가 확인 필요 |
| 참격 | 54.8초 | 약 1.3초 이후 사라짐. 그러나 강한 휘두름보다 축소·소멸에 가까워 참격 속도감은 미달 |

결과는 `outputs/results/fasth3-effects-20261016-flame/` 및 `fasth3-effects-20261016-slash/`. `synthetic-reference.png`, `custom.mp4`, `custom_transparent.png`, `motion-review.jpg`, 실제 프롬프트/실행 메타데이터를 보존한다.

이전 연기 시험과 걷기/공격 비교는 [FastH3 기록](FASTH3_SPRITE_WORKFLOW.md) 참고.

## 원화 품질 개선 / 자료 조사 (2026-10-16)

사용자가 다각형 도형의 낮은 시각 품질을 지적하여 입력 원화부터 재검토했다. 내장 imagegen 시도는 HTTP 503 / no_plan_support_for_model 오류로 실패. 프로젝트에 이미 설치된 로컬 Anima 경로로 원화를 생성했다(OpenAI API/CLI 추가 사용 없음).

- `tools/verify_effect_reference.py`: Anima Turbo 1.1, 1024×1024, seed 20261016. 검정 배경의 단일 금빛 마법 불꽃. 결과 `outputs/experiments/fasth3-quality/anima/flame/image-1.png`. 곡선/그라데이션/작은 불티가 있지만 장식적인 문양 경향도 있다.
- `effect_prompts.py`에서 flat painted style 강제를 제거하고 곡선·명암·발광 그라데이션·가는 잔불 보존으로 변경.
- `tools/verify_fasth3_effects.py --reference ... --kind flame --tag anima-detailed`로 외부 입력 검증을 재사용할 수 있다. 원화 1024px와 영상 512px를 혼동하지 않는다.
- Anima 원화 → FastH3 첫 생성 64.47초. 각진 테스트 도형보다 곡선/색 농도가 개선됐지만 중간 프레임의 잔선 단순화와 위쪽 잘림이 관찰되어 `--tag anima-margin20 --padding 20`으로 재시험했다. 디테일 완전 보존이나 고품질 완료를 주장하지 않는다.
- 2026-10-17 결과 확인: 여백 20% 버전은 61.23초에 완료. `outputs/results/fasth3-effects-20261016-flame-anima-margin20/`. 73프레임 RGB 최대값 >32 영역 기준 가장자리 2px 이내 접촉이 기존 51프레임 → 0프레임, 최소 여백 0px → 5px. 각 폴더 `edge-review.json`에 기록. 이 검사는 희미한 발광까지 포함하는 완전한 잘림 판정이 아니다. 시간별 프레임에서 곡선과 명암은 개선됐으나 잔선 단순화가 남는다. 현재 비교용 권장 결과는 이 버전이며 사이트 활성화는 하지 않았다.
- 공개 자료는 `outputs/experiments/fasth3-quality/` 하위에 원본 ZIP과 provenance.json으로 보존한다. 해상도만으로 품질을 판단하지 않는다.

조사한 자료:

1. [NekotoArts Toon Fire](https://nekotoarts.itch.io/free-toon-fire-animation-loop): 512×512, CC0. 직접 확인했지만 셀 채색이 강해 이번 고급 손그림 목표의 최종 입력으로 채택하지 않음.
2. [Mikodrak Fire FX](https://opengameart.org/content/fire-fx-burning-fire-animation): CC0. 내려받은 프레임이 81×123이라 고해상도 품질 시험에 부적합.
3. [rubberduck magic flame](https://opengameart.org/content/magic-flame): CC0, Blender 시뮬레이션/소스 포함. 프레임이 256×300이며 입자/발광 표현 참고용.
4. [Bomy Games Elemental Magic FX](https://bomy-games.itch.io/elemental-magic-fx): 작성자가 Wan 2.2 생성 후 brightness alpha, 윤곽 정리, 루프, 단발 속도 손질을 했다고 설명. 기술 참고만 했으며 자산은 가져오지 않음. 라이선스가 게임 사용과 자산 재배포를 구분하므로 서비스 템플릿으로 복사하지 않는다.
5. [ParticleFX Fire Pillar](https://particlefx.studio/effects/fire-pillar): 유체/입자 레이어와 가산 합성 사용 사례. 참고만 했고 서비스 설치·계정 생성 없음.

## 제품화 후속

우선 연기·불꽃처럼 지속되는 효과부터 별도 실험 메뉴로 연결하는 것이 타당하다. 참격 등 단발형은 이동 궤적과 짧은 재생 구간 검증이 더 필요하다.

UI에 필요한 구성: 참조 이미지 → 효과 템플릿 → 반복/단발 설명 → 생성 → 프레임 구간/재생 FPS → 검정·흰색·체커 배경 확인 → 투명 시트/프레임 PNG. 프레임 삭제·크롭·속도 조절이 이펙트 제작에서 중요하다. 현재 투명화는 기존 시트 배경 제거 경로이며 부드러운 발광 가장자리/색 번짐은 아직 별도 검증하지 않았다.

운영 연결 시 이펙트 타입/템플릿을 API에서 검증하고 생성 기록에 저장해야 한다. 로컬 검증용 mock이나 readiness 우회를 서버 코드로 옮기지 않는다. 캐릭터 FastH3까지 함께 활성화하지 않는다.
