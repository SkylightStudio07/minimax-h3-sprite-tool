# VERTEX 총격 효과 시안 — 2026-10-17

## 타격감 후속

preview.html을 즉시 감쇠하는 총구 섬광, 탄도선, 55ms 명중, 50ms 효과 히트스톱, 감쇠 화면 흔들림, 비대칭 불티/파편으로 수정했다. 정지 스크린샷이라 실제 캐릭터 본의 반동/이동이나 게임 시뮬레이션 정지는 없다. 생성 총격/금속 타격음은 별도 로컬 오디오 경로에서 준비한다. 음성/음악 추가 없음.

Stable Audio 3 Medium으로 shot-impact-source.wav(3초)를 생성하고 시작 무음 112ms를 제거, 1.2초 페이드아웃 파일 shot-impact.wav를 재생 버튼에 연결했다. 44.1kHz 스테레오, peak 0.85, NaN/무음 검사 통과. 실제 청취 평가는 하지 않았으며 합성 총격/타격음 내부 이벤트의 55ms 동기화는 보장하지 않는다. 느린 화면에서는 오디오 0.5배 재생으로 근사한다. 브라우저 JS 오류 없음/재생 클릭/시각 캡처 확인.

사용자 전투 스크린샷과 Project-Vertex/ArtDirection의 VERTEX_Art_Direction.md, BattleFxMockup/LAYOUT_BRIEF.md를 참고했다. 해당 프로젝트 원본/Unity 파일은 수정하지 않았다. 배너 UI의 색 금지를 물리 총격 전체의 규칙으로 확대하지 않는다.

## 결과

- `outputs/vertex-vfx-20261017/preview.html`: 실제 화면 위 총구 100ms, 탄착 250ms 타이밍 시안. 재생/¼속도/어두운 배경 비교. 원화 스케일·밝기 애니메이션이며 생성 영상 기반 스프라이트가 아니다. Edge headless에서 이미지 로드·버튼·화면 확인.
- `revised/muzzle/image-1.png`, `revised/armor-impact/image-1.png`: Anima Turbo 1024px 원화. 첫 시도는 총 자체 생성/화면 밖으로 뻗는 불티로 제외. 수정 프롬프트는 물체명보다 빛의 형태로 설명.
- 밝은 화면에서 총구가 약하고 탄착은 별 모양 경향이 남는다. 제품 완성 품질 승인 전. Screen 합성만 적용되어 회청색 연기의 불투명한 대조 표현은 아직 구현하지 않았다.
- FastH3 탄착 `outputs/results/fasth3-effects-20261016-impact-vertex-impact/`: 63.88초, 512px, 3초, 단발. 초반 섬광 후 원형 연기가 되며 빠르게 사라짐. 시간 정리와 배경 잔상 처리가 필요해 미리보기에는 원화 기반 타이밍 버전을 사용한다.
- 사이트/Unity 설치 및 자동 활성화 없음.

## LoRA

`smooth-anime-booster`를 `web/assets/image-styles.json`에 enabled=false로 등록했다. Civitai model 1145743/version 3271822, Anima Booster (Anime), 약 139MB, 트리거 Smooth_Anima_Booster. Anima용이며 FastH3 영상 LoRA가 아니다. Anime 전용 버전을 선택했고 Realism은 제외했다. 실제 강도 비교/미리보기 검증 전에는 활성화하지 않는다. API 원본은 `outputs/vertex-vfx-20261017/lora-research/` 보존.

추가 조사한 Anime Style LoRA model 2396251은 preview 시절 버전이라 이번에는 설치하지 않았다.

후속: 총구 빛의 갈라짐, 탄착의 비대칭 불티/짧은 파편을 개선하고 normal-alpha 연기를 분리. 영상 전체를 250ms에 압축하지 말고 초반 유효 프레임을 선정한다.
