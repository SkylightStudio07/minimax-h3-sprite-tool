# Turbo v4 비교 실험

2026-11-08. 사용자 지시로 설치·비교 실행. 완료 여부는 아래 결과 폴더의 실제 기록을 확인한다.

## 설치와 재현

- LoRA: `ComfyUI/models/loras/minimax_h3_turbo_v4_step600_ema.safetensors`, 779849816 bytes.
- Hugging Face revision `43a74557ac3f6539db8e0f2a959d03feb7a81480`.
- SHA256 `5f3a626cd72c93a8b9318d6760c510bc5092d2ab13aaba1f932c5bab07a416d3`, 검증 완료.
- 전용 노드 commit `4274783a23afcfdbea3b4876cb79effd6c510785`.
- 설치: `tools/install_turbo_v4_20261108.py`. 제출: `tools/compare_turbo_v4_20261108.py`.
- 사이트 기본 모델·기존 가중치를 교체하지 않은 별도 실험이다.

## 조건

- 선택된 금발 idle·attack의 기존 workflow와 `reference-prepared.png`를 그대로 사용.
- 768×768·24FPS·73프레임·3초, 동일 seed와 프롬프트, 동일 기본 pruned INT8 모델·텍스트 인코더·VAE.
- v4는 전용 LoRA loader strength1.0/low_vram=false와 전용 sampler, simple 8스텝.
- 새 기본 모델 비교는 기존 res_multistep sampler와 simple 20스텝.
- 기존 40스텝 결과는 과거 영상 복사본으로, 현 환경에서 측정한 속도 기준으로 쓰지 않는다.
- 입력 조건 일치 검사는 `outputs/turbo-v4-comparison-20261108/comparison-validation.json`.
- 같은 seed여도 모델·sampler가 달라 동일 동작이 생성된다는 보장은 없다.
- 생성 순서 v4 idle→v4 attack→기본20 idle→기본20 attack. 캐시·모델 로딩 차이를 고려하며 sampler 시간도 따로 기록한다. 반복 측정한 통계적 벤치마크가 아니다.

## 파일과 측정

- 결과: `outputs/turbo-v4-comparison-20261108/`.
- 각 작업 폴더 `workflow.json`, `recipe.json`, `pending.json`, `result.json`, `raw.mp4`.
- 제출 후 전체 시간과 Comfy tqdm에서 읽은 sampler 시간을 구분한다. 단위는 초이며 tqdm 표시는 초 단위로 반올림된다.
- 원본 영상 비교 페이지: `http://127.0.0.1:8771/preview.html` (로컬 서버 실행 중에만 유효).
- 각 결과의 VRAM·RAM 정보는 해당 모니터 수집 범위 안에서만 해석한다.
- 루나가 순차 작업 감시, 부모 에이전트가 영상·프레임 검수 담당. 누끼·업스케일은 적용하지 않는다.

## 첫 v4 결과의 관찰

- idle: 총 약186.1초, sampler 약135초. 정상 768×768·24FPS·73프레임. 기존40보다 중간 상체 자세·머리카락 움직임이 커졌다. 사용자가 선택한 기존 절제된 동작과 동일하지 않다.
- attack: 총 약164.6초, sampler 약125초. 정상 영상 생성됐지만 원본에 없는 바닥의 칼·피 자국을 만들었고 측면 회전·발 움직임이 커졌다. 이 상태로 운영 기본값을 교체하지 않는다.
- 원본 공통 프롬프트 끝에 쿠나이 캐릭터의 작은 혈흔 웅덩이를 보존하라는 다른 캐릭터용 문장이 포함돼 있다. v4의 새 소품 발생에 영향을 줬을 가능성은 있으나 원인으로 입증되지 않았다.
- 첫 비교는 기존 조건을 유지한다. 프롬프트를 정리한 추가 테스트를 한다면 별도 실험으로 기록하며 동등 조건 비교에 섞지 않는다.
- 입력 원화 자체의 흰 테두리도 모델 출력에 남는다. 이번 가속 실험은 누끼 해결 실험이 아니다.

기본20 결과와 최종 결론은 완료 후 보완한다.
