# Live2D 레이어 화질 개선

리깅 스튜디오 상단 **화질 개선** 또는 갤러리 상세 **화질 개선** 카드로 연다. 일반 결과와 내부 공유 링크에서 사용할 수 있다. 수정 중인 레이어는 먼저 저장한다. 기존 결과를 자동으로 바꾸지 않으며 사용자 적용이 필요하다.

## 사용 흐름

1. 개선 방식 **AI · 애니메이션 선·채색 개선** (모델 준비 시 기본 선택) 또는 **일반 확대**를 고른다.
2. **2배**(기본) 또는 4배를 선택한다. 현재/결과 크기를 표시한다.
3. **화질 개선본 적용 · 새 버전 저장**: 확대 레이어·표정·PSD·Unity V2를 함께 만들고 새 작업 버전을 저장한다. 갤러리와 내부 공유는 새 버전을 사용한다.
4. **확대 파일만 다운로드**: 현재 작업을 변경하지 않고 확대 PSD/PNG ZIP만 받는다.

이전 버전 선택·복원이 가능하다. 반복 적용하면 배율이 누적된다. 4배는 면적이 16배이므로 출력 캔버스는 3,200만 픽셀까지 허용한다. 관리자가 복제해 게시한 공개 Live2D는 갤러리 **공개본 갱신**으로 반영한다.

## 두 방식의 차이

- 일반 확대: premultiplied-alpha Lanczos. 원래 형태를 보간하며 사라진 선을 새로 복원하지 않는다.
- AI 개선: 공식 Real-ESRGAN `RealESRGAN_x4plus_anime_6B.pth` (17,938,799 bytes, BSD-3-Clause). RGB는 애니메이션용 신경망으로 다듬고 알파는 위 일반 확대의 마스크를 그대로 사용한다. 투명 영역의 RGB를 가까운 불투명 픽셀의 색으로 확장해 검은 테두리를 방지한다. 4배 모델 출력을 요청한 2배/4배로 맞춘다. 생성형 재작화가 아니지만 선/채색이 달라질 수 있으며 원본에 없는 눈·입 디테일의 정확한 복원을 보장하지 않는다.

전체 캔버스/레이어 크기·위치·픽셀 앵커·수동 본·타임라인 이동값을 같은 배율로 확대한다. `unityPixelsPerUnit`도 배율에 맞춰 올려 Unity 크기는 유지한다. 최신 Unity 임포터가 필요하다. ZIP에는 character.psd, layers/, expressions/, composite.png, manifest.json, Unity 소스가 포함된다.

## 구현 및 실행

- `rigging_upscale.py`: 기존 내보내기/버전 백업/적용/V2 사전 생성에 `method=lanczos|anime-ai` 추가. 파라미터가 없는 과거 API 호출은 lanczos. 임시 작업 폴더에서 모든 결과를 만든 뒤 적용하여 처리 실패 시 원본 유지.
- `rigging_super_resolution.py`, `tools/run_live2d_upscale.py`: AI는 별도 CPU 프로세스(4threads), 128px tile +16px 여유. 모든 레이어에 같은 모델을 한 번 로드해 사용하고 종료 시 메모리 반환. CUDA 비활성, 동작/음악 생성 모델 변경 없음. 900초 제한.
- `tools/download_live2d_upscale.py`: 공식 xinntao/Real-ESRGAN v0.2.2.4 URL 사용. 모델은 models/live2d-upscale/ (Git 제외). 설치 기록에 출처/크기/실측 SHA256 저장. 모델 준비 전 AI 옵션 비활성. 공개 릴리스 API에 digest가 없으므로 실측 해시를 upstream 일치 검증으로 표현하지 말 것.
- API: `/api/jobs/<jid>/rig-edit/upscale`, `/share/rig/<token>/rig-edit/upscale`에서 method 추가. 저장과 동일한 잠금/리비전 검사 사용. 편집 payload의 upscale.aiReady로 상태 제공.
- UI: `web/rigging-editor.html` qualityTool/qualityPanel/upscaleMethod, `?mode=quality` 진입. 갤러리 `web/assets/results.js` 화질 개선 카드/다운로드 부근 바로가기.

## 검증 (2026-10-18)

- `tools/verify_live2d_upscale.py`: 실제 사용자 결과의 face 레이어를 복사해 AI 비교. 106×139 → 212×278 CPU 약3.55초(전체 작업 속도 아님). 일반 확대와 alpha 배열 완전 일치. 비교 `outputs/live2d-quality-smoke-20261018/comparison.webp` 순서 원본 최근접 / Lanczos / AI.
- 같은 도구로 임시 패키지에 실제 AI apply 실행, PSD 시그니처/V2 sourceRevision/좌표2배/원본 버전 백업 검증. 사용자 실제 저장 작업에는 적용하지 않음.
- `test_rigging_upscale.py`: 투명 경계, parts/expressions 일괄 확대, 앵커/좌표, PSD/V2, 실패 시 원본 보존, 이전 버전 복원.
- `tools/test_rigging_quality.cjs`: 상단 진입/AI 기본/리비전 갱신/미저장 가드/모바일/읽기 전용. 기존 표정 편집 브라우저 검사 통과.
