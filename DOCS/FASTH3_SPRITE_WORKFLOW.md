# FastH3 스프라이트 워크플로우

2026-10-15. 운영 저장소 `G:\Minimax`.

## 현재 상태

> **2026-11-08 기준:** 검증 표시 파일이 있어 실험 프로필로 **선택 가능**하다. 아래의 "다시 잠금"은 10월 16일 당시 기록이며, 이후 재활성화 내용은 이 문서의 끝부분을 본다.

이펙트 전용 후속 실험: [게임 이펙트 기록](GAME_EFFECTS.md). 불꽃/참격 실생성과 전용 템플릿 모듈을 추가했으며 사이트 연결 전 프로토타입 단계다.

스프라이트 생성기의 **워크플로우**에서 기존 H3와 FastH3 스프라이트를 구분한다. **2026-10-16 모델 설치·실행 확인 완료, 그러나 가슴 팽창 아티팩트로 선택 다시 잠금**. 생성 성공과 동작 품질 통과는 다르다. 검증 마커는 `pending-motion-revalidation`이며 준비 상태는 false. 기존 quality 20-step / turbo 4-step 동작은 유지한다.

### 실생성 기록 (2026-10-16)

- `tools/verify_fasth3.py`: 운영 갤러리에 등록하지 않는 격리 테스트. 팀/Comfy 큐가 비었을 때만 실행하며 프로세스 내부에서만 준비 상태를 우회한다.
- 입력: 기존 flat-color 테스트 캐릭터. 512×512, 3초, seed 42, idle, 8 steps, 루프/안정화/배경 제거 포함.
- 전체 처리 65.7초. 73프레임 영상, 8프레임 시트, 투명 시트 생성 성공. 경고 없음. 루프 자동 평가 good (경계 오차 0.007204), 별도 구간 변경 없음.
- 결과: `outputs/results/fasth3-validation-20261016/`의 `validation.json`, `idle.mp4`, `idle_sprite_sheet.png`, `idle_transparent.png`.
- 시트 육안 확인에서 뚜렷한 형태 붕괴는 없으나 동작은 매우 미세함. 전신/공격/걷기 품질, 기존 H3 대비 속도·품질 우위는 아직 검증하지 않았다. GPU 사용량은 실행 중 약 14.9GiB 관측(최댓값 측정 아님).
- 최초 검증 마커 기록 후 사용자가 가슴 팽창을 지적하여 활성화를 철회했다. 루프 경계 지표 good은 해부학적 형태 보존을 보장하지 않는다.

### 가슴 팽창 재시험

- 원래 기본 idle에는 `visible rise and fall of the shoulders and chest`와 반복 호흡 지시가 있었다. FastH3 human idle에 한해 호흡 대신 작은 통째 이동, 가슴/복부 부피 및 단추 간격 보존을 지시하도록 수정했다. 기존 H3와 비인간 동작은 변경하지 않는다. 사용자 지정 동작 문장은 유지한다.
- 동일 입력/seed 42/512×512/3초/8스텝 재시험: `fasth3-validation-20261016-rigid-idle`, 62.84초, 출력 성공. 시간별 원본 프레임에서 가슴 윤곽 변형이 여전히 보여 품질 검증 실패. 활성화하지 않았다.
- `tools/verify_fasth3.py --hair-only`로 몸통 고정, 머리끝/소매 끝만 움직이는 추가 실험을 수행한다. 결과 디렉터리에 `-hair-only`가 붙으며 이전 결과를 덮어쓰지 않는다.
- 추가 실험 완료: 59.56초, 출력 정상이나 0.75초 부근에서 가슴 윤곽이 다시 커지고 머리 위치도 변한다. 명시적 몸통 고정 지시만으로 문제를 해결하지 못했다. 선택 잠금 유지. 다음 후보는 기존 H3와 동일 조건 비교 또는 움직임 영역 마스크/원본 합성 제약이며 아직 구현·검증하지 않았다.
- 프롬프트 변경은 소스에 저장했지만 운영 서버 재시작/새 품질 승인 없이 잠금을 풀지 않는다.

## 조사 결과와 적용 범위

- 참조: https://github.com/xiaojiangxj33/h3-sprite-generator
- 조사한 commit: `f630bed9d9e6e69d4444d123933c1244d799ec18`.
- README의 기본 H3 모델 목록과 실제 웹 프론트의 native 그래프가 서로 다르다. `web/h3ui.html`의 `workflowRawOfficial`은 FastH3 8-step 모델이며 단순히 기존 H3를 8스텝으로 실행하면 같은 것이 아니다.
- T8 경로는 별도 커스텀 노드가 필요하므로 이번에는 도입하지 않았다.
- native 경로의 FastH3, res_multistep/simple, 8 steps, sigma shift video 10/audio 3을 우리 큐·입력 전처리·SaveVideo에 맞춰 구성했다. 원본 그래프의 attention backend/BlockSparseAttention 최적화는 포함하지 않는다. 원본 웹 UI의 실시간 키잉/프레임 선택/크롭/Eagle 연동도 이번 추가 범위가 아니다.
- 필요한 노드 클래스는 현재 8189의 object_info에 모두 존재한다. 추가 커스텀 노드나 Comfy 업그레이드는 수행하지 않았다.
- 초기 프로필은 512×512, CFG 1(BasicGuider), 네거티브 CFG 미지원. 3~5초, 기존 동작/루프/프레임 시트/배경 제거/안정화 옵션을 재사용한다. 입력은 기존 비율 유지 패딩 전처리를 사용한다.

## 모델

- 공식 배포: https://huggingface.co/FastVideo/FastVideo-FastH3-Comfy
- revision: `ec1e3aa374a91c57b0b94a1623b7e657c0498cf2`
- 파일: `diffusion_models/fastvideo_fasth3_8step_v2_pruned_int8_convrot.safetensors`
- 크기: 22,128,378,696 bytes (약 22.1GB).
- SHA256: `0922785978dc9bfe1adf27d8b291b0ca763f9f165f882e6cb297c72fbb6deda8`
- 모델 카드: MiniMax H3 Community License. 기존 텍스트 인코더·영상/음성 VAE를 재사용한다.
- 설치: `.venv\Scripts\python.exe tools/download_fasth3_model.py`. 기존 범위 분할/재개/해시 검증/원자적 rename 다운로더를 재사용한다.
- 로그: `logs/fasth3-model-download.log`, `logs/fasth3-model-download-error.log`.
- 사용자 요청: 대용량 다운로드를 시작하면 완료까지 감시하지 않고 응답을 종료한다.

## 다음 이어가기

1. 다운로드 로그·파일 크기·SHA256 확인. safetensors 파일 확정 전에는 사용하지 않는다.
2. 팀/Comfy 큐가 비었을 때 격리된 결과 경로에서 512×512/3초/8스텝 실생성을 수행한다. 첫 실험은 process-local mock으로 sprite_workflows.status만 ready로 간주하고 운영 마커는 아직 만들지 않는다.
3. 영상·시트·루프·배경 및 VRAM 동작을 확인하고 기존 4-step/20-step과 비교한다. 속도·품질 향상을 실측 없이 단정하지 않는다.
4. 통과하면 `data/fasth3-validated.txt`에 위 SHA256을 기록한다. 서버 `/api/status`에 ready가 반영되고 UI 환경 확인 후 활성화된다. 실패하면 마커 없이 기존 H3를 유지한다.

## 구현

### 걷기·공격·이펙트 범위 재시험 (2026-10-16)

`tools/verify_fasth3_actions.py`에서 격리된 테스트를 실행한다. 공통 512×512, 3초(73프레임), seed 42, 8스텝. 안정화/루프 최적화는 끄고 원본 동작을 검토한다. 운영 갤러리와 프로필 활성화 상태는 바꾸지 않는다.

- 걷기: `outputs/results/fasth3-actions-20261016-walk/`, 67.31초. 오른쪽 지향 총병이 양발을 번갈아 움직이는 동작 확인. 장비·의복 디테일 변동은 남는다. 제자리 걷기이며 화면을 실제로 횡단하는 테스트는 아니다.
- 연기: `outputs/results/fasth3-actions-20261016-smoke/`, 60.89초. 단순 청록색 합성 테스트 도형 사용(실제 게임 아트 아님). 인간 신체 제약을 제거한 전용 프롬프트를 테스트 프로세스에서만 주입. 말림/소멸/재형성은 보이나 고정 꼬리 위치가 이동한다. 상용 아트나 모든 VFX 품질로 일반화하지 않는다.
- 최초 공격 예비 실행 `fasth3-actions-20261016-sword`는 입력이 곤봉인데 검으로 지시한 불일치가 있어 정식 평가에서 제외한다. 무기 이름과 여백을 고친 `club` 테스트로 대체한다.
- 곤봉 공격: `outputs/results/fasth3-actions-20261016-club/`, 57.97초. 여백 20%, 반복 루프 해제. 들어올림 → 내리치기 → 대기 복귀가 보이고 무기가 화면 안에 남는다. 무기 길이/손·몸 비율의 변동은 남아 완성 품질로 승인하지 않았다.
- 결론: 이번 입력에서는 걷기·공격·이펙트 모두 의미 있는 동작이 생성되어 idle 실패를 전체 용도 실패로 일반화할 수 없다. 범용 활성화 잠금은 유지하며 결과 영상을 사용자에게 제공했다. 기존 H3와의 동일 조건 비교는 미실시.
- 각 폴더의 `generation_prompt.json`은 실제 프롬프트, `validation.json`은 실행 결과, `motion-review.jpg`는 8시점 원본 프레임이다. 코드의 성공 상태는 생성 파이프라인 성공만 뜻하며 품질 승인과 다르다.

- `sprite_workflows.py`: 허용 ID, 설치/검증 상태, 512×512 및 네거티브 금지 검증.
- `idle_tool.py`: 새 프로필 그래프와 실행 게이트. 감사 JSON에 workflowId/실제 모델/실제 steps 저장.
- `team_server.py`: queue 등록 전 준비 상태 검증, status와 job 응답에 workflow 정보 노출.
- `web/index.html`: workflow 선택·상태·재생성 복원, 전용 설정 잠금, 생성 요청에 workflowId 전달.
- `workflows/fasth3-sprite-api.json`: 우리 호환 구성의 Comfy API 예제. input `reference.png`는 사용자가 넣은 참조 이미지로 교체한다.

검증: `python -m unittest test_sprite_prompts test_team_server`, `node tools/test_sprite_workflows.cjs`. 모델 이름/8-step/시그마/가이더/루프 keyframe, 미설치·미등록 ID·해상도·네거티브 차단, 기존 옵션 회귀, UI 선택·요청·복원을 확인했다. **이 테스트들은 실생성 성공을 의미하지 않는다.**


## 2026-10-18 영상 기반 보행 세팅 채택

- 사용자가 `outputs/gait-fullbody-20261018/preview.html`의 영상 기반 결과를 선택했습니다. 걷기/달리기 각각 3초 실생성은 99.75초/96.75초에 완료했고 팔·몸통·코트 동작을 검토했습니다. 달리기는 시작/끝의 서 있는 장면이 남으므로 프레임 구간 정리가 필요합니다. 모든 동작의 완성 품질 승인으로 일반화하지 않습니다.
- 설치된 파일의 크기와 전체 SHA256을 재검증하고 `data/fasth3-validated.txt`에 기존 지정 해시를 기록했습니다. 기존 실험 프로필이 사이트에서 선택 가능하며 새 다운로드는 없습니다. 기존 모델 이용 조건이 유지됩니다.
- 스프라이트 시트 도구의 세팅 모음에 걷기/달리기를 별도 추가했습니다. 테스트와 동일한 동작 설명·모델·512×512·3초·12프레임·강함·오른쪽·여백 10%·루프 켜짐·정규화/자동 루프 선택 꺼짐을 불러옵니다. 투명 시트·배경 제거 선택은 사용자 설정을 유지합니다. 기존 조준 대기 세팅도 유지합니다.
- 프레임별 Qwen 포즈 생성 기능은 종료했습니다. 모델/Comfy 자체를 제거하는 요청이 아니므로 기존 영상 생성, 이미지 포즈 입력, Live2D 및 부분 수정 기능은 유지합니다. 루프는 [프레임 편집기](FRAME_EDITOR.md)에서 구간 미리보기→잘라내기→새 버전 저장으로 정리합니다.
