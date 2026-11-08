# 세션 인계 시작점

갱신: 2026-11-08 (Asia/Seoul). 이 대화에서 확인한 구현·결과물·사용자 선택 기록이다. 최신 사용자 지시가 우선한다.

## 프로젝트와 기존 문서

- 실제 영상 생성·사이트 운영: `G:/Minimax`. 현재 채팅 cwd인 `G:/111`과 혼동하지 않는다.
- 기능별 개발·운영 문서: `G:/Minimax/DOCS/`, 전체 안내: [README](../README.md).
- 별도 리깅 개발 공간: `G:/111/service-prototype`, 런타임·모델: `G:/111/runtime`, `G:/111/models`.
- 리깅 전체 인계: [LIVE2D_TOOL_HANDOFF.md](G:/111/docs/LIVE2D_TOOL_HANDOFF.md).
- 리깅 연혁: [04-status-and-next.md](G:/111/docs/rigging-v1/04-status-and-next.md).
- 두 프로젝트 전체를 서로 덮어쓰지 않는다. 기존 수정·미추적 파일이 많다. 문서가 로컬에 있다는 것이 커밋·원격 백업 완료를 뜻하지 않는다.

| 작업 | 읽을 문서 |
|---|---|
| 이미지 스튜디오 | [IMAGE_STUDIO.md](IMAGE_STUDIO.md), [IMAGE_STUDIO_UX_REVIEW.md](IMAGE_STUDIO_UX_REVIEW.md) |
| 그림체·LoRA·원화 변환 | [IMAGE_STYLES.md](IMAGE_STYLES.md), [IMAGE_LOOKS.md](IMAGE_LOOKS.md), [SPRITE_STUDIO_CONVERSION.md](SPRITE_STUDIO_CONVERSION.md) |
| 스프라이트 프레임·루프 | [FRAME_EDITOR.md](FRAME_EDITOR.md) |
| 배경 제거 | [IMAGE_BACKGROUND.md](IMAGE_BACKGROUND.md) + 아래 최신 실패·수정 기록 |
| FastH3 기존 구현·실측 | [FASTH3_SPRITE_WORKFLOW.md](FASTH3_SPRITE_WORKFLOW.md) |
| 픽셀·전투 이펙트 | [PIXEL_ART.md](PIXEL_ART.md), [VERTEX_COMBAT_VFX.md](VERTEX_COMBAT_VFX.md), [GAME_EFFECTS.md](GAME_EFFECTS.md) |
| 캐릭터 작업실·방향 | [CHARACTER_WORKSPACE.md](CHARACTER_WORKSPACE.md), [ASSET_TYPES_AND_DIRECTIONS.md](ASSET_TYPES_AND_DIRECTIONS.md) |
| Live2D 본·타임라인 | [LIVE2D_BONE_EDITOR.md](LIVE2D_BONE_EDITOR.md), [LIVE2D_TIMELINE.md](LIVE2D_TIMELINE.md) |
| Live2D 편집·재생성 | [LIVE2D_LIVE_PREVIEW.md](LIVE2D_LIVE_PREVIEW.md), [LIVE2D_MASKING.md](LIVE2D_MASKING.md), [LIVE2D_REGENERATION.md](LIVE2D_REGENERATION.md), [LIVE2D_UPSCALE.md](LIVE2D_UPSCALE.md) |
| Unity | [UNITY_IMPORTER.md](UNITY_IMPORTER.md) |
| BGM | [YUE2_BGM_HANDOFF.md](YUE2_BGM_HANDOFF.md), [BGM_SETUP.md](../BGM_SETUP.md) |

기능별 문서 상당수는 10월 기록이다. 11월 작업은 아래 내용을 함께 읽는다. Live2D풍 기능은 Cubism `.moc3` 생성기가 아니라 파츠와 자체 Web/Unity 런타임을 사용한다.

## 최근 선택 결과와 전달한 파일

### 금발 캐릭터

- 사용자는 11/2 자연 호흡·스텝 사격 버전을 거절하고, 11/1 그립 확인 idle·사격 버전을 선택했다.
- 선택한 원본 영상: `outputs/comfy/blonde_grip_retry_20261101/01-blonde-idle-grip_00001_.mp4`, `02-blonde-fire-v2_00001_.mp4`.
- 최종 선택 누끼: [outputs/blonde-from-raw-20261102/](../outputs/blonde-from-raw-20261102/), `approval.json` 기록 있음.
- 최종 ZIP: [blonde-from-raw-handoff.zip](../outputs/blonde-from-raw-20261102/blonde-from-raw-handoff.zip), 약 50MiB.
- 미리보기: `http://127.0.0.1:8770/preview.html`. 로컬 서버 실행 중에만 유효하다.
- 생성 스크립트: `tools/submit_blonde_grip_retry_20261101.py`. 이미 완료했으므로 다시 제출하지 않는다.
- 최종 누끼·내보내기: `tools/rebuild_blonde_from_raw_20261102.py`.
- 거절된 새 모션: `outputs/blonde-natural-step-20261102/`, 원본은 `outputs/comfy/blonde_natural_step_20261102/`. 선택 버전과 바꾸지 않는다.

### 하얀머리 주인공·권총 3종

- 원래 9개 배치: `outputs/character-variations-20261101/`.
- idle A/B/C와 사격 A/B/C 총 6개 생성 완료. 원본 영상: `outputs/comfy/character_variations_20261101/03-...`부터 `08-...`.
- 마지막 전달한 공격 전용 ZIP: [protagonist-pistol-attacks-3.zip](../outputs/pistol-attacks-only-20261102/protagonist-pistol-attacks-3.zip), 약 62.8MiB.
- 묶음 원본: `outputs/character-variations-cutout-v2-20261102/pistol-{a,b,c}/attack/`.
- 사용자가 공격 3개만 요청했다. 이 ZIP에 idle·금발·쿠나이는 넣지 않았다.
- 사용자에게 전달했다는 것이 품질 전체 승인을 뜻하지 않는다. 거의 모든 스프라이트의 자글거림을 지적했고 수작업용 원본을 요청했다.

### 누끼 전 원본 통짜 시트

- 원본 영상은 보존되어 있으며 누끼 결과로 덮어쓰지 않았다.
- 추가 전달: [original-raw-sprite-sheets.zip](../outputs/raw-sprite-sheets-20261103/original-raw-sprite-sheets.zip), 약 46.1MiB.
- 금발 선택본 2개 + 권총 6개 + 쿠나이 횡베기 1개. 회색 배경의 RGB PNG 시트, 시간 JSON, 원본 MP4 포함.
- 768×768 셀, 8열, 원본 73프레임 모두 포함. 끝의 앵커 프레임도 보존하며 마지막 행의 빈 셀은 프레임이 아니다.
- PNG는 원본 MP4의 디코딩 결과다. 생성 이전 무압축 마스터는 아니므로 생성·영상 압축 흔들림은 남는다.
- 투명 결과는 idle 72프레임(끝 중복 제외), attack 73프레임. 시간은 각 `native-frames.json` 참조.

## 누끼 실패와 최종 처리 주의점

1. `tools/export_character_variations_20261102.py` → `outputs/character-variations-cutout-20261102/`: 금발 2개·권총 6개 첫 CPU 누끼. 사용자 지시로 쿠나이는 제외했다.
2. `tools/refine_variations_edges_20261102.py` → `outputs/character-variations-cutout-v2-20261102/`: 금발 흰 경계 추가 제거, 전체 768px 미리보기. 사용자에게 윤곽 자글거림을 다시 지적받았다.
3. 금발만 `tools/rebuild_blonde_from_raw_20261102.py`로 원본 영상부터 다시 처리한 것이 최종 선택본이다. 앞선 누끼를 입력으로 사용하지 않았다.

- 흰색을 기준으로 경계를 지우면 흰 셔츠·피부·머리카락·그려진 윤곽선을 손상하고 점처럼 끊어진다. 보정을 반복 누적하지 않는다.
- 최종 방식은 원본 색 차이 마스크 + 내부 보호 + GrabCut 경계 + 부드러운 알파. 내부 core의 RGB·불투명도를 총 146프레임에서 검사했다. 이 검사는 윤곽 품질의 완전 보장이 아니다.
- 눈의 붉은 기운, 총구의 흰 섬광 중심, 연기, 팔과 무기·다리 사이 빈틈을 밝고 어두운 배경에서 확인한다.
- 최종 금발도 머리카락 끝에 잔흔이 남는다. 사용자는 일단 이 버전을 선택했다. 완벽하게 제거했다고 기록하지 않는다.
- 첫 미리보기는 512px. v2 이후는 768px 무손실 WebP. PNG 시트의 셀은 원래부터 768px였다. GIF는 256색·이진 투명도여서 PNG/WebP와 함께 비교한다.
- 원본 영상·원화 및 이전 버전을 유지한다. 사용자는 원본 윤곽선을 보존하는 방향을 선호한다.

## 11/8 가속 모델 조사: 조사만 완료, 신규 설치·실측 없음

사용자 링크: https://gall.dcinside.com/mgallery/board/view/?id=ai_utilize&no=173414

- 실제 확인한 PC: RTX 5060 Ti 16GB, RAM 약 32GB.
- 최근 캐릭터 배치는 `sampling_mode=quality`에서 기본 H3를 40스텝으로 실행했다.
- `idle_tool.py` 기본 quality는 20스텝. 기존 Turbo 4스텝 경로와 FastH3 V2 8스텝 경로도 구현되어 있다.
- 기존 모델: `ComfyUI/models/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors`, 약 19.5GiB.
- 기존 FastH3: `fastvideo_fasth3_8step_v2_pruned_int8_convrot.safetensors`, 약 20.6GiB. 최신 Omni와는 다르다.
- 기존 Turbo: `minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors`, 약 1.82GiB. 아래 Larry 최신 v4와 다른 파일이다.
- `sprite_workflows.py`의 FastH3는 512×512 제한, 8스텝, video shift10/audio shift3. 검증 표시는 `data/fasth3-validated.txt`.
- 과거 FastH3 실측은 `outputs/results/fasth3-actions-20261016-*/validation.json`. 512×512·3초에서 약 58~67초. 최근 768px 배치와 동등 조건의 비교가 아니다.
- 제안한 비교: 기본 H3 20스텝 / 최신 Larry Turbo v4 8스텝 / 기존 FastH3 V2 8스텝. 원화·프롬프트·해상도·길이를 맞춰 누끼 전 결과와 시간·VRAM·RAM을 비교한다. 같은 seed라도 모델 사이 동작이 같다는 보장은 없다.
- 최신 Larry v4 step600 EMA는 약 744MB. 제작자가 정적·미세 동작 개선을 설명한다. 격한 동작의 4스텝은 잔상 위험이 있어 6~8스텝 권장. 전용 노드·샘플러 및 pruned INT8 지원을 설명한다. 아직 설치하지 않았다.
- Pika Flex는 Comfy LoRA가 공개됐지만 배포자가 해당 변환본의 Comfy 실생성 미검증을 명시한다. 전용 6-NFE 노이즈 일정이 필요하며 단순 6스텝 설정과 다르다. 현재 pruned 모델과 호환 미확인.
- HyperFlow Flash는 약 14B·4~8스텝. 공식 16GB GPU 실측은 미확인이다. 시스템 RAM 16GB와 VRAM 16GB를 혼동하지 않는다.
- VDN 대표 속도는 8×B200 기준. 현 PC의 우선 후보로 보지 않는다.
- `MINIMAX_H3_LICENSE_APPROVED.txt`에는 기존 사용자 별도 인가 확인 기록이 있다. 새 파생 모델의 조건까지 자동 확인된 것으로 확대 해석하지 않는다.
- 가속은 누끼 자글거림을 해결하지 않는다. 스텝 비율을 전체 시간 단축 비율로 약속하지 않는다.

일차 자료:
- https://huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora
- https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo
- https://huggingface.co/Pika-Labs/Pika-H3-Flex/blob/main/comfy/README.md
- https://github.com/Pika-Labs/Pika-H3-Flex
- https://huggingface.co/FastVideo/FastH3-Omni-Comfy
- https://huggingface.co/VideoRebirthAI/hyperflow-h3-flash
- https://huggingface.co/OpenVDN/vdn-minimax-h3

## 환경·사용자 작업 선호

- Python: `G:/Minimax/.venv/Scripts/python.exe`. 명령마다 작업 폴더를 명시한다.
- 영상 Comfy: `http://127.0.0.1:8189`. 웹 앱: `http://127.0.0.1:7866`. 공개 사이트: `https://bcsd-nai.mywire.org:18444/`.
- 진단용 8192/8193은 건드리지 않는다. 사이트 표시만을 위해 GPU 엔진을 켜지 않는다.
- GPU 생성은 한 번에 하나씩. 과거 고화질 작업으로 PC가 불안정해졌다. 보통 768×768·24FPS 기준.
- RAM 여유 2GB 미만이면 다음 생성을 시작하지 않는다. 활성 작업을 임의 취소·재시작하지 않는다. 완료 후 queue가 빈 경우에만 필요한 캐시 해제를 한다.
- 완료 MP4·pending 기록을 확인해 중복 생성을 막는다. Comfy 이력 소실만으로 재생성하지 않는다.
- 사용자는 생성 시작 시 알리고, 스텝 감시와 다음 작업 시작은 Luna에게 맡기라고 명시했다. 누끼 구현과 직접 검수는 부모 에이전트 담당. 이전 Luna 생존을 가정하지 않는다.
- idle은 절제된 살아 있는 움직임. 가슴 팽창만 반복하거나 스쿼트 같은 하체 동작은 불호. 공격은 실제 무기와 전신 체중 이동이 연결되어야 한다.
- 쿠나이 캐릭터는 혈계 능력자. 피 효과를 누끼 오류로 제거하지 않는다. 권총 주인공은 긴 총열의 리볼버로 장비 구조를 유지한다.
- 원작 있는 캐릭터를 새로 생성하지 말라는 기존 요청이 있다. 원화의 외형과 그림체 보존을 중시한다.
- 11월 배치를 공개 갤러리에 자동 게시하지 않는다. ZIP 전달은 공개 게시 승인이 아니다.
- localhost 미리보기 주소는 서버 실행 중에만 유효하다. 파일 실체를 우선 확인하고 필요한 경우 해당 폴더만 127.0.0.1에 제한해 서비스한다.

## 11/8 후속 실행: Turbo v4 설치·비교 시작

- 사용자 지시로 최신 v4 설치와 기존 모델 비교를 시작했다. 위의 '신규 설치·실측 없음'은 조사 당시 상태다.
- LoRA: `ComfyUI/models/loras/minimax_h3_turbo_v4_step600_ema.safetensors`, 779849816 bytes.
- HF revision: `43a74557ac3f6539db8e0f2a959d03feb7a81480`, SHA256: `5f3a626cd72c93a8b9318d6760c510bc5092d2ab13aaba1f932c5bab07a416d3`. 전체 해시 검증 완료.
- 노드: `ComfyUI/custom_nodes/ComfyUI-MiniMax-H3-Turbo`, commit `4274783a23afcfdbea3b4876cb79effd6c510785`. 추가 패키지 요구 없음. 기존 Comfy 코드·사이트 기본값 유지.
- 설치 스크립트: `tools/install_turbo_v4_20261108.py`.
- 비교 제출: `tools/compare_turbo_v4_20261108.py`. 결과·재개 기록: `outputs/turbo-v4-comparison-20261108/`.
- v4 8스텝 idle → v4 8스텝 attack → 기본 H3 20스텝 idle → 기본 H3 20스텝 attack 순차. 원화·프롬프트·seed·768×768·24FPS·73프레임을 기존 선택한 금발과 맞췄다. 누끼 없음.
- 40스텝 기존 영상도 별도 복사했다. 과거 영상은 현재 생성 속도 실측 대상이 아니다.
- 첫 제출: `turbo-v4-idle`, promptId `256b0bb5-0c6b-4a72-8fc7-40e3d56f54df`. 중복 제출 전에 pending/result와 실제 MP4를 확인한다.
- 루나가 감시·후속 제출을 맡음. 완료 여부는 결과 폴더 `progress.json` 및 각 작업 `result.json`을 확인한다. 시작했다고 완료로 기록하지 않는다.
- 비교 미리보기: `http://127.0.0.1:8771/preview.html`. 기존 결과는 보존했다.
- 초기 RAM 1.4GB여서 대기했으며, 사용자가 앱 종료 후 4.4GB 확인하고 시작했다.

## 다음 세션 시작

이 문서와 해당 기능별 DOCS를 읽고, 진행 중인 Turbo 비교의 실제 상태를 먼저 확인한다. 기존 전달 결과물을 덮어쓰거나 누끼를 임의로 추가 보정하지 않는다.
