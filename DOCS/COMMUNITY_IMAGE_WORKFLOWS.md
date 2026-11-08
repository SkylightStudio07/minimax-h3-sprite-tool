# 커뮤니티 원화 워크플로 설치 — 2026-10-17

사용자가 설치를 승인하여 Legendaer V9, Soya 공유용 JSON, Anima AiO 샘플과
관련 노드를 가져왔다. 기존 음악/이미지 런타임의 패키지를 바꾸지 않도록 독립 overlay를 쓴다.
현재 설치 완료 여부는 `data/community-workflows-status.json`을 읽어 확인해야 한다.
사이트에서 사용할 수 있다고 판단하려면 서버 노드 등록과 실생성 검증이 추가로 필요하다.

## 파일

- 설치기: `tools/install_community_workflows.py` (고정 커밋 10개 노드 팩)
- 설치 상태: `data/community-workflows-status.json`
- 설치 로그: `data/community-workflows-install.log`, `data/community-workflows-install-error.log`
- 별도 Python: `.venv-workflows/Scripts/python.exe`
- 별도 Comfy base: `ComfyUI-workflows/`
- 커스텀 노드: `ComfyUI-workflows/custom_nodes/`
- 원본 워크플로: `ComfyUI/user/default/workflows/SpriteLab-Community/`
- 별도 실행 환경의 워크플로 복사본: `ComfyUI-workflows/user/default/workflows/SpriteLab-Community/`
- 모델은 기존 `ComfyUI/models/`를 `extra_model_paths.yaml`로 공유한다.

현재 overlay는 기존 `.venv/Lib/site-packages`를 읽기 전용으로 참조한다.
추가 패키지는 overlay에 설치하며, 기존 버전 목록을 constraints로 고정하여 업그레이드를 금지했다.
의존성 충돌 시 설치 상태에 `needs_attention`이 남는다. 조용히 버전 제약을 풀지 말고
해당 노드 요구와 기존 도구의 요구를 비교해 overlay 안에서만 해결해야 한다.
기존 환경이 변하면 overlay 참조 버전도 변할 수 있다. 완전히 독립된 복제 환경은 아니다.

## 워크플로 원본

Legendaer: https://civitai.com/models/2426853
V9.0 version 3326453 / file 3212228.
ZIP SHA256 `3a1e078243bfb489882d4729c75ed15f60240078ea5c4a732a3b255d91108737` 확인 후 추출.
Basic, Standard, Advanced, Advanced TIPO, Detailer가 들어 있다.
설치 대상 의존성은 주로 Standard에 맞췄다. Advanced의 TIPO, RTX, 추가 ControlNet까지
모두 준비됐다는 뜻은 아니다. 모델·LoRA·검출기 선택은 로컬 파일명에 맞춰야 한다.

Anima AiO: https://github.com/n0va39/ComfyUI-EasyUseAnima
commit `be9f4b34f3269ff503199b2f76c345366e6935c5`.
AiO v6 전체 샘플 외에 `ANIMA_Easy_Use_workflow_v1_release_ko.json` 간소화 샘플과
작가 혼합 샘플을 저장했다. 처음 검증할 때는 간소화 샘플의 base 생성만 사용하고
Highres/Detailer/미설치 LoRA를 끈다. 전체 v6와 작가 혼합 예제의 모든 선택 의존성은
기본 경로의 필수 노드와 다르므로 누락을 별도로 확인해야 한다.

Soya: https://github.com/lbh848/comfyui_hooking_server
`frontend/index.html`의 `share-workflow-data`를 파싱한 API JSON.
`Soya-source-api.json`은 미수정 참고 사본이며 `{{risu_prompt}}` 같은 placeholder 및
로컬에 없는 `Detailed anime style.safetensors` 등의 경로를 포함한다.
참조 노드 ID가 모두 존재하는 것은 확인했지만, 실행 가능한 준비 완료 프리셋은 아니다.
세부 조합은 `SOYA_STYLE_IMPORT.md` 참고. 정확한 누락 LoRA 출처 확인 전 동명 모델로 대체하지 않는다.

사용자 추가 요청으로 `workflows/soya/`에 별도의 추적 가능한 원본을 저장했다.
출처 고정 커밋 `7a6cb680827df92fe1e238ab210988f7006b2c93`, 40노드.
`anima-flanime.original.api.json`과 로컬 모델 경로 3개만 바꾼
`anima-flanime.local-paths.api.json`을 함께 제공한다. 양쪽 실행 환경의
`SpriteLab-Community/Soya/`에도 복사했다. `source.json`, `dependencies.json`,
`local-path-changes.json`, 한국어 README가 함께 있다.
모든 노드 참조 ID 연결과 JSON 구문은 확인했지만 모델 누락 때문에 생성 검증 전이다.
설치 로그의 LoRA Manager `UnicodeDecodeError`는 설치기의 requirements.txt 읽기를
명시적 UTF-8로 수정했다. 기존 설치 상태는 재실행/검증 전까지 완료로 변경하지 않는다.

## 실행/이어가기

설치/재시도: `.venv/Scripts/python.exe -u tools/install_community_workflows.py`

설치가 끝난 뒤 실험 서버를 별도 콘솔 또는 숨긴 프로세스로 실행:
`.venv/Scripts/python.exe tools/install_community_workflows.py --serve`

실험 서버는 `http://127.0.0.1:8191`이다. 기존 8189/8190 및 팀 웹서버는 재시작하지 않는다.
자동으로 GPU 작업을 넣지 않는다. 기존 팀 큐가 비었을 때만 비교 생성을 수행한다.
실행 후 `/object_info`에서 노드별 등록을 확인하고 로그의 import 실패를 해결한다.
진행 중 다운로드/설치를 실시간 감시하지 말라는 사용자 선호를 유지한다.

다음 검증 순서: Legendaer Standard → Soya 조합 재현 → Anima AiO.
먼저 모델 선택과 의존성을 해결하고 768~1024 기본 해상도에서 생성한다.
5060 Ti 16GB에서 여러 모델을 동시에 점유하지 않도록 8189 작업과 동시 실행하지 않는다.
Soya 흐름은 사용자 지시로 사이트 기본 생성 경로에 연결했다. `DOCS/IMAGE_STUDIO.md`의
2026-10-17 기본값 변경 절 참고. Legendaer/AiO의 사이트 선택 기능은 아직 연결하지 않았다.

## 실험 서버 및 Soya 생성 검증

`tools/verify_soya_workflow.py`로 8191에서 3종 실제 생성 완료.
상세 설정과 결과는 `workflows/soya/README.md`의 실생성 절 참고.
Soya 경로만 검증했으며 Legendaer/AiO의 모든 옵션을 검증한 것은 아니다.

- WD14 노드를 고정 커밋 `9e0a6e700299182fc05c58b62e7ad9f72182a78b`로 추가했다.
  첫 실행 시 wd-vit-tagger-v3 모델(약 379MB)과 태그 CSV를 노드가 다운로드했다.
- LoRA Manager 요구 패키지 설치를 overlay에서 재실행해 import 문제를 해결했다.
- rgthree 기본값 `patch_recursive_execution=true`는 현재 Comfy 0.34에서
  `execution.recursive_output_delete_if_changed`가 없어 import 실패하므로 사용자 config에서 false로 설정했다.
- 서버 실행기에 `--user-directory`와 별도 SQLite URL을 명시했다. base-directory만으로는
  DB가 기존 Comfy 경로를 참조해 파일 잠금 오류가 발생할 수 있었다.
- Soya에 필요한 모든 노드 유형과 AiO Generator, LoRA Manager 로딩을 `/object_info`로 확인했다.
- 실험 종료 후 `/free`로 8191 모델 캐시를 해제했다. 기존 8189는 idle 상태를 확인한 뒤
  `/free`로 모델 캐시만 비웠으며 기존 서비스 프로세스는 재시작하지 않았다.
- 사이트에 실험 워크플로를 자동 노출하지 않았다. 정확한 원본과 후보 LoRA의 차이를 표시한 상태다.
