# 원화 포즈 제어 호환성 조사


> **2026-10-18 현재:** Flanime + Illustrious 전용 OpenPose는 설치·실생성 확인 및 사이트 관절 편집 연결 완료. 우측 관절 포즈 탭에서 편집하고 적용한다. text/reference 지원, Anima/Animagine 포즈 미지원. 아래 과거 계획의 Animagine 우선 순서·가중치 미설치 문구는 당시 기록이다. 최신 상태·해시·구현/검증은 [SPRITE_STUDIO_CONVERSION.md](SPRITE_STUDIO_CONVERSION.md)의 사이트 연결 절 참고.

## 진행 기록 — 2026-10-15

사용자가 포즈 편집·연결 구현을 승인했다. 우선 `tools/download_pose_model.py`로 xinsir 기본 가중치(2,502,139,104 bytes)를 백그라운드 다운로드한다. 고정 revision과 SHA256 검증을 사용하며, 완료 파일은 `ComfyUI/models/controlnet/xinsir-openpose-sdxl/diffusion_pytorch_model.safetensors`다. 로그: `logs/pose-model-download.log`, 오류: `logs/pose-model-download-error.log`.

사용자 선호에 따라 다운로드를 기다리지 않고 이번 턴을 종료한다. 다음 이어가기에서는 파일 해시/설치 여부를 확인한 뒤, **브라우저 관절 편집 및 포즈 프리셋 → 모델별 골격 PNG 렌더링 → Animagine ControlNet 연결 → 입력 검증/저장/실생성 비교** 순서로 구현한다. Anima 포즈 제어와 사진 포즈 추출은 아직 미구현이다. 아래는 이전 조사 결과다.

2026-10-15. **문서·로컬 노드 수준 확인**이며 제어 가중치 다운로드/실생성/포즈 편집기 구현은 이번 범위에 포함하지 않았다.

## 권장 순서

1. Animagine XL 4.0 + xinsir SDXL OpenPose를 먼저 실험한다. 동일 SDXL 구조의 연결 경로이며, 현재 체크포인트에서의 품질은 비교 테스트가 필요하다.
2. 브라우저에서 관절을 움직여 OpenPose 색상·연결 규칙으로 PNG를 만든다. 직접 지정하는 포즈는 검출기 없이도 가능하다. 이미지에서 포즈 추출은 별도로 DWPose 등을 설치해야 한다.
3. Anima Turbo 1.1은 별도 실험 옵션으로 검증한다. 기본 모델과 아키텍처가 같다는 사실만으로 포즈 정확도를 보장하지 않는다.

| 후보 | 추가 가중치 | 연결 | 확인 범위 / 제약 |
|---|---:|---|---|
| xinsir/controlnet-openpose-sdxl-1.0 | 기본 파일 약 2.50 GB | ControlNetLoader → ControlNetApplyAdvanced → 기존 KSampler | SDXL용. 모델 카드 Apache-2.0. Animagine 실생성 미검증 |
| Comfy-Org/Anima-LLLite pose-1 | 약 23.3 MB | ModelPatchLoader → AnimaLLLiteApply → KSampler MODEL | 로컬 Comfy 소스에 노드 존재. Preview3 학습 가중치. Base v1.0에서도 품질 저하를 동반해 사용 가능하다는 원저자 설명. Turbo 1.1 보장 없음 |
| Claquasse/Anima-Control-Pose Preview-2 | 약 75.1 MB | 전용 AnimaControlApply / AnimaPoseControl 커스텀 노드 | Anima v1.0 대상 실험 어댑터. 현재 미설치. 검출까지 쓰면 ONNX 약 316 MB와 rtmlib 등 추가 |

현재 `G:\Minimax\ComfyUI\models\controlnet`, `model_patches`에는 제어 가중치가 없다. SDXL ControlNet을 Anima에 그대로 연결할 수 없다. Anima 계열 파생 가중치는 CircleStone 비상업 모델 라이선스 조건을 확인한다.

## 중요한 입력 차이

- xinsir는 학습 때 굵은 골격선을 사용해 기본 OpenPose 선 두께와 다르면 성능이 불안정할 수 있다고 설명한다. 웹 렌더러도 이 규칙을 맞춰야 한다.
- Claquasse는 얇은 검은 배경 골격이 학습 기본값이라고 설명한다. xinsir용 렌더링을 그대로 공유하면 안 된다.
- 사진 기반 검출기는 애니 원화의 손·관절 위치를 틀릴 수 있다. 추출 후 사람이 수정할 수 있는 화면이 필요하다.
- 포즈는 인체 관절 제어이며 카메라 시점, 옷 주름, 소품, 손가락과 캐릭터 정체성을 모두 고정하지 않는다.

## 근거

- https://huggingface.co/xinsir/controlnet-openpose-sdxl-1.0 — revision `23f966cd5cfdd3f7729c903e243d87152162d2b7`
- https://huggingface.co/Comfy-Org/Anima-LLLite — revision `57973aa5c824df58d9f8217b031f96a148f9b349`
- https://huggingface.co/kohya-ss/Anima-LLLite — 현재 README의 Preview3 가중치 관련 설명, 상세는 `PREVIEW3.md`
- https://huggingface.co/Claquasse/Anima-Control-Pose — revision `8f559771d5a49a02fa03f7df2a05ccb7eecb3a2a`
- 로컬 `ComfyUI/comfy_extras/nodes_model_patch.py`: ModelPatchLoader / AnimaLLLiteApply, `ComfyUI/nodes.py`: ControlNetLoader / ControlNetApplyAdvanced.

후속 다운로드가 필요하면 시작 상태와 크기만 알려주고 답변을 끝낸다. 사용자가 이어가자고 하면 설치 확인과 실생성 검증을 진행한다.
