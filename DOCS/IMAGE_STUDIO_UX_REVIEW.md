# 이미지 스튜디오 사용성 재검토 · 2026-10-18

## 2026-10-19 · 레퍼런스에서 후속 작업까지 점검

실제 입력 원화를 업로드하고 Qwen-VL 설명을 검토한 뒤, 추가 그림체를 적용해 1024×1536 이미지를 생성했습니다. 같은 결과를 동작 도구와 Live2D 마스킹 화면으로 넘기는 과정까지 실제 HTTP·로컬 분석·GPU로 확인했습니다. 운영 계정·갤러리 대신 임시 SQLite 계정을 사용했습니다. 외부 신규 사용자를 대상으로 한 평가는 아닙니다.

발견하고 수정한 문제:

- 업로드가 오른쪽 미리보기에 떨어져 있었습니다. 이제 왼쪽 첫 단계에서 업로드→분석 초안 검토→설명 작성 순서로 이어집니다. 원본 확인·마스킹 캔버스는 오른쪽에 유지하고 이동 버튼을 제공합니다. 변환 화면의 캐릭터 예시 버튼은 숨겨 업로드한 캐릭터 설명을 실수로 덮어쓰지 않게 했습니다.
- 화면이 낮은 PC에서 생성 버튼이 내부 스크롤 아래로 밀렸습니다. 선택사항과 그림체 열기 버튼을 한 줄에 배치하고 설정·결과 패널 높이를 줄였습니다. 모바일은 단일 열을 유지합니다.
- 동작 도구의 에셋 안내에는 오른쪽으로 표시되지만 실제 방향 select는 이전 값이 남을 수 있었습니다. 이미지와 에셋 방향을 함께 복원합니다. 결과 생성 뒤 입력 폼의 방향을 바꿔도 완료한 결과의 방향으로 전달되는 것을 검증했습니다.
- 동작·Live2D 이미지 로더가 파일 해독 완료 전에 반환했습니다. 해독·크기 검증까지 기다린 뒤 완료 안내를 표시합니다. 깨진 파일로 교체에 실패하면 기존 이미지는 유지합니다.
- 완료 상태 API에는 원화 생성 설정이 없어, 화면의 그림체를 바꾼 뒤 이전 결과를 부분 수정할 때 원래 고정 조합을 알 수 없었습니다. 인증된 이미지 작업 응답에 재사용 설정을 포함하되 입력 이미지·마스크 데이터는 제외합니다.
- 자세 고정을 켠 상태에서 호환되지 않는 기본 그림체 예시를 적용하면 자세가 해제될 수 있었습니다. 현재 자세를 지원하는 예시만 적용 대상으로 제공합니다.
- 실제 Qwen-VL 결과가 쓴 후드를 `hood down`으로 잘못 읽고 원본의 자세까지 설명에 넣었습니다. 후드 상태 판별 지시를 구체화하고, 방향·자세 문구는 외형 초안에서 제거합니다. 같은 원화를 다시 분석한 결과 `hood up`으로 바뀌었으나 정확도를 보장하지 않습니다. 원본과 비교해 초안을 직접 수정하는 안내를 유지합니다.
- 분석이 오래 걸릴 때 경과 시간을 표시합니다. 영어로 반환된 검수 메모는 한국어 확인 안내로 대체합니다. 분석 위치를 사용자의 컴퓨터로 오해하지 않도록 ‘팀 서버에서 처리, 외부 AI 서비스 전송 없음’으로 바로잡았습니다.

검증:

- `python -m unittest test_image_engine test_image_cutscene test_image_caption test_character_studio test_team_server`: 54개 통과.
- `node tools/test_image_studio.cjs`, `node tools/test_character_studio.cjs`: 통과.
- `node tools/test_image_reference_journey.cjs`: 임시 계정의 실제 HTTP + 명시적인 AI 응답 모의 처리로 전체 연결 검증.
- `node tools/test_image_reference_journey.cjs --real-image`: 같은 화면 조작으로 실제 로컬 분석·GPU 생성. 시작 전 운영 대기열과 세 엔진이 비었는지 검사하고, 결과는 `outputs/image-journey-*/journey.json`에 기록합니다. 운영 갤러리에는 등록하지 않습니다.
- 실제 이미지 생성의 방향·의상·얼굴 품질까지 자동 합격시키는 테스트는 아닙니다. 추가 그림체와 높은 변형 정도는 외형을 바꿀 수 있으므로 사용자가 후보를 비교해야 합니다.

최종 실제 브라우저 검증 기록: `outputs/image-journey-4bb7dod1/journey.json`. 후드 지시 수정 후 `hood up`으로 분석했고, 생성한 1024×1536 결과의 방향 설정·이미지 데이터가 동작 도구로 전달됐으며 Live2D 원본 캔버스의 크기도 일치했습니다. 스크린샷은 `outputs/image-journey-real-reference.png`, `image-journey-real-result.png`, `image-journey-real-motion.png`, `image-journey-real-live2d.png`입니다. 모의 처리 검증은 별도 `image-journey-fixture-*` 이름으로 저장합니다. `node tools/test_rigging_masks.cjs`, `node tools/test_sprite_workflows.cjs`도 통과했습니다.

운영 확인: 작업 중 Codex 연결 중단 후 웹·생성 엔진 프로세스도 종료되어 공개 사이트가 502를 반환했습니다. Windows 프로세스 생성 서비스(Win32_Process.Create)에서 숨김 PowerShell을 시작하고 HTTPS 환경변수와 숨김 Start-Process로 서버를 독립 실행해 복구했습니다. 최신 로그는 `outputs/image-journey-independent.stdout.log` / `.stderr.log`. 공개 사이트와 수정된 정적 파일, 8189·8190·8191의 system_stats 응답이 모두 200인 것을 확인했습니다. 기존 `start_team_tool_https.bat`는 변경하지 않았습니다.

관련 파일: `web/image-studio.html`, `web/assets/image-workspace.js`, `web/assets/image-workspace.css`, `web/assets/image-caption.js`, `web/assets/asset-start.js`, `web/index.html`, `web/rigging.html`, `image_caption.py`, `team_server.py`.

## 목적과 검토 방식

대상은 생성 모델·LoRA·Comfy 워크플로를 모르는 일반 게임 개발자입니다. 공개 사이트의 실제 오류 기록과 코드, 새로 만들기→그림체 고르기→생성→실패 복구 시나리오를 검토했습니다. 실제 UI를 로컬 검증 계정으로 직접 조작하고, PC·모바일 자동 브라우저 테스트 및 실제 GPU 생성을 별도로 확인했습니다. 외부 사용자를 모집한 사용성 테스트는 수행하지 않았습니다.

참고한 설계 기준:

- Nielsen Norman Group, [10 Usability Heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/): 현재 상태의 가시성, 오류 예방, 기억보다 인지, 오류 원인과 복구 안내.
- Nielsen Norman Group, [Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/): 기본 작업에 필요한 선택을 먼저 제공하고 드물게 쓰는 기능을 단계적으로 공개.

## 확인한 실제 실패

1. 최근 이미지 작업 `31a4f5bac2f6f8932cb84a238b07a2ae`가 Soya 그래프의 `Seed (rgthree)` 검증에서 거절됐습니다. 자동 seed 범위는 약 2^53인데 해당 노드 상한은 2^50이었습니다. UI 문제가 아니라 생성 시작 전 실패하는 실제 서버 버그였습니다.
2. 추가 그림체는 현재 모델 계열이 다르거나 고정 조합일 때 버튼만 비활성화됐습니다. 설치된 스타일이 있어도 사용자가 어떤 설정을 바꿔야 하는지 알기 어려웠습니다. 비활성 항목과 파일 미설치, 계열 불일치, 모드 미지원이 비슷하게 보였습니다.
3. 기본 그림체·추가 그림체·추천 프리셋의 표시가 따로 갱신되어 실제 요청 설정을 한눈에 알 수 없었습니다. 추가 그림체를 적용했는데 이전 프리셋 표기가 남을 수도 있었습니다.
4. 모바일 첫 화면에 캐릭터 묶음·원화 가져오기 등 선택사항이 크게 보여 핵심 작업과 입력란이 아래로 밀렸습니다.
5. 엔진 준비 정보를 이미지 생성·추가 스타일·이미지 설명 도구가 각각 조회했습니다. 초기 로딩과 상태 갱신이 중복됐습니다.
6. 생성 실패는 긴 Comfy 검증 메시지 위주였고, 입력을 유지한 재시도와 오류 해결 행동의 연결이 약했습니다.

## 이번 변경

| 사용자 문제 | 변경 | 검증 |
|---|---|---|
| 아무 설정도 안 바꿨는데 Comfy 오류 | 모델별 seed 상한 적용. 후보 4장까지 마지막 seed가 상한을 넘지 않도록 자동 범위 계산. 수동 번호는 서버와 UI 양쪽에서 검증 | 상한·배치 경계 단위 테스트, 기본 그림체 실제 생성 |
| 추가 그림체 버튼이 안 눌림 | 설치·준비·현재 모드·포즈 지원을 확인해 적용 가능한 기본 설정을 찾음. 전환 필요 여부와 미지원 이유를 카드에 표시. 전환 후 적용 사실을 안내 | Soya→Illustrious 그림체 전환, 실제 추가 그림체 생성 |
| 설정이 바뀌었는지 모름 | 그림체 선택을 별도 단계로 정리. 기본/추가 그림체를 생성 버튼 옆에 함께 표시. 기본 설정 변경 시 호환되지 않는 추가 그림체 해제 및 안내 | 현재 상태·payload 일치, 프롬프트 보존 테스트 |
| 처음부터 알아야 할 설정이 너무 많음 | 설명→그림체→출력의 세 단계. 그림체 예시/추가 그림체 바로가기. 선택사항인 캐릭터 묶음은 기본 접기, 묶음에서 이어온 작업은 펼치기 | 모바일 직접 검토, 캐릭터 작업실 회귀 테스트 |
| 로딩이 느리고 중복됨 | 준비 상태 요청 promise를 세 도구가 공유 | 브라우저 전체 흐름 검증 |
| 실패 후 뭘 해야 할지 모름 | 재현 번호·GPU 메모리·연결·설정 검증 오류별 해결 안내. 기술 오류는 접힌 상세. 현재 설정으로 재시도, 설명/이미지는 유지 | 모의 오류→복구→완료 브라우저 테스트 |

## 동작 규칙

- 추가 그림체를 명시적으로 적용하면 이전 추천 프리셋의 그림체 지시를 해제합니다. 기본 생성 설정은 호환이 필요할 때만 전환합니다. 캐릭터 설명, 업로드한 이미지·마스크를 초기화하지 않습니다.
- 셀 채색 전투 고정 조합에 다른 스타일을 몰래 덧붙이지 않습니다. 사용자가 추가 그림체를 고르면 선택한 스타일을 지원하는 기본 설정으로 전환하고 이를 표시합니다. 기존 고정 조합의 생성 코드는 변경하지 않았습니다.
- 자세 고정이 필요한 현재 작업에 맞는 기본 설정이 없다면 이유를 표시합니다. 포즈를 몰래 해제하지 않습니다.
- 미설치·검증 대기 파일을 사용 가능하다고 표시하지 않습니다. 4방향 시트의 전용 스타일 제약은 유지합니다.
- 작가 화풍 안내는 유지합니다. 미지원 원인을 저작권 안내로 혼동해서 설명하지 않습니다.
- 서버 장애나 생성 오류를 CSS로 감추지 않습니다. 기술 상세를 확인할 수 있고, 상태 조회 연결이 끊겼을 때 생성 요청을 중복 제출하지 않습니다.

## 실제 생성 확인

`outputs/image-studio-repair-20261018/results.json`:

- 기본 Soya: 자동 seed 736870378430473, 1024×1536 출력, 35.16초. Comfy 검증과 이미지 저장 완료.
- 추가 그림체: Flanime + 판타지 전투 측면 스타일 0.6, 512×768 출력, 16.3초. 저장된 PNG 메타데이터에서 styleId/seed 확인.

생성 속도와 결과 품질을 모든 입력에 일반화하지 않습니다. 두 생성은 운영 사용자나 갤러리에 등록하지 않은 검증용입니다. `tools/verify_image_studio_repair.py`로 재현하며 기존 출력 폴더를 덮어쓰지 않습니다.

## 유지보수

- 서버: `image_engine.py` seed 검증, `image_soya.py` maxSeed.
- 스타일 선택: `web/assets/image-styles.js`의 targetFor/applyStyle/refresh. 준비 상태는 공통 imageModelsRequest를 사용.
- 화면 상태: `web/assets/image-workspace.js`. 현재 표시와 payload는 같은 실제 select 상태에서 계산.
- 오류 복구: `web/assets/image-studio.js` showImageFailure/poll/submit.
- 첫 진입: `web/assets/character-context.js`의 이미지 작업 전용 접기.
- 테스트: `test_image_engine.py`, `test_image_cutscene.py`, `tools/test_image_studio.cjs`, `tools/test_character_studio.cjs`.

후속 UX 검증은 신규 사용자에게 다음 세 가지를 설명 없이 시켜 보는 것으로 진행할 수 있습니다: 원화 1장 생성, 추가 그림체 바꾸기, 입력 원화 일부 수정. 작업 성공률·첫 생성까지 걸린 시간·막힌 항목을 기록한 뒤 다음 변경을 정합니다.


최종 자동 검증: `python -m unittest test_image_engine test_image_cutscene test_image_caption test_character_studio test_team_server` 52개 통과. `node tools/test_image_studio.cjs`, `node tools/test_character_studio.cjs` 통과. 기본 스타일·추가 스타일·계열 전환·수동 모델 변경 시 스타일 해제·입력 원화/설명/포즈 보존·오류 후 재시도를 확인했습니다. 직접 브라우저 조작에서도 추가 그림체 플랫 컬러 선택이 실제 select·강도 0.5·현재 생성 설정 표시에 반영되는 것을 확인했습니다. 새 사용자 모집 평가는 후속 항목입니다.

작업 이름은 선택사항으로 고급 설정에 옮겼습니다. PC의 설명·그림체 설정 열을 410px로 넓혀 선택 문구가 잘리지 않게 하고, 기본 화면에서 캐릭터 설명과 그림체에 먼저 접근하도록 정리했습니다.

이전 실패 작업의 설정을 다시 불러올 때 현재 그림체 범위를 초과한 seed는 비우고 자동 번호로 전환했다는 안내를 반환합니다. 이전 서버에서 잘못 발급한 seed 때문에 같은 실패를 반복하지 않도록 검증했습니다.
