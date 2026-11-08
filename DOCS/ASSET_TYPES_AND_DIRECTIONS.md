# 에셋 유형 진입 및 다방향 스프라이트 조사

2026-10-18. 원화 생성과 Sprite Motion Lab 첫 진입에서 에셋 용도를 선택한다. 시점과 최종 방향 수는 독립된 설정이다.

## 현재 구현

1. 일러스트 / Live2D 정면 / 측면 전투(JRPG·플랫포머) / 탑다운 / 아이소메트릭 선택.
2. 이미지 도구는 새 원화 또는 원화 변형. 모션 도구는 준비된 원화 또는 원화 생성 화면으로 이동.
3. 단일·4·8방향 제작 계획과 이번 기준 방향 선택. **현재 출력은 한 방향**이다. 4/8방향을 선택해도 여러 번의 독립 생성이나 다방향 시트로 위장하지 않는다. 화면에 이 제약을 표시한다.

스튜디오 진입 후 상단 요약의 **에셋 유형 변경**으로 재선택한다. 작성한 캐릭터·동작 프롬프트는 덮어쓰지 않고, 별도 시점 프롬프트를 서버에서 결합한다. 측면 새 원화/변환은 Flanime+카사0.6/1024×1536/32steps·CFG5, 변환 denoise0.3. 일반 새 원화는 기존 Soya, 일반 원화 변형은 Anima Turbo. 탑다운·아이소메트릭은 현재 프롬프트 유도이며 전용 LoRA로 검증된 기능이 아니다.

`assetSpec={type,directionCount,facing,version,outputMode}`를 이미지/모션 큐, 갤러리 설정 및 다시 만들기에 보존한다. `outputMode=single-direction`, `version=game-asset-intent-v1`. `directionCount`는 이미지 장수나 실행 횟수로 변환하지 않는다. 입력 없는 기존 요청은 기존 동작을 유지한다.

이미지 결과를 모션으로 보낼 때 같은 선택을 전달하고 진입 화면을 중복 표시하지 않는다. 이전 결과의 다시 만들기에도 선택을 복원한다. 모션에서 원화 생성으로 이동할 때 sessionStorage의 일회성 선택을 전달하며, 이미 열린 원화 iframe에도 적용한다. 준비된 이미지와 마스크는 기존 정책대로 재업로드한다.

## 구현 파일과 검증

- `web/assets/asset-start.js`, `asset-start.css`: 두 도구 공통 진입 화면·요약·설정 전달. `web/image-studio.html`, `web/index.html`에서 로드.
- `asset_types.py`: 허용된 에셋 유형, 정수 1/4/8, 8개 기준 방향 검증. Live2D는 정면 단일 방향. 시점·방향 프롬프트는 고정 서버 목록에서 구성한다.
- `image_engine.py`: 에셋 시점 사용 시 기존 sprite의 three-quarter 고정 구도를 대체. 사용자 설명은 유지하고 PNG/generation.json에 선택 기록.
- `team_server.py`, `idle_tool.py`: 모션 입력 검증 및 카메라·방향 프롬프트 적용, 로컬 generation_prompt.json 기록. 작업 조회의 assetSpec 및 갤러리 settings에 보존.
- `web/team.html`: 도구 간 이미지 전달에 assetSpec 포함. 목적지 진입 스크립트가 준비된 후 원화를 전달.
- 임베디드 원화 도구는 요약 높이만큼 두 스크롤 패널 높이를 줄인다. iframe 높이가 내용 변화에 따라 계속 커지는 것을 피하도록 summary ResizeObserver로 높이 변수를 갱신한다.
- `test_asset_types.py`: 8방향 계획이 count=8 생성으로 바뀌지 않음, 구도 충돌 방지, 불량 입력 및 기존 요청 호환 확인.
- `test_team_server.py`: 모션 API 검증/저장, `tools/test_image_studio.cjs`: 첫 진입, 8방향 계획 안내·요청·복원, 원화→모션 및 모션→원화 재진입, `tools/test_sprite_workflows.cjs`: 모션 진입과 설정 요청.
- 육안 확인: `outputs/asset-entry-preview.png`. 이번 작업은 화면/설정 연결이며 새로운 탑다운·8방향 모델 생성 품질을 실험하지 않았다.

## 찾아낸 모델·워크플로 후보

공식 설명과 공개 API를 읽었다. 아래 후보는 **다운로드·설치·실생성하지 않았다**. 현재 카사 LoRA에 바로 덧씌워 쓸 수 있는 것으로 설명하지 말 것.

### RPG Character Sprite — Anima / Illustrious

[공식 Civitai](https://civitai.com/models/1397312). RPG Maker용 시트. Anima Base1.0 버전은 512×1024, `rpgchara`와 front/side/back를 포함한 3×4 grid 프롬프트를 안내한다. Illustrious0.1 버전은 768×1280와 multiple views/chibi/reference sheet 트리거. **앞·옆·뒤 시트이지 정확한 8방향 일관성을 보증하는 모델은 아니다.**

- Anima version2964160/file2843556, 약91.9MB. Illustrious version1579416/file1479164, 약228.5MB.
- 기존 Flanime 경로에서는 Illustrious 버전이 구조상 가장 가까운 실험 후보. Anima Base용을 Turbo/Soya에 적용했을 때의 품질은 미검증.
- 2026-10-18 API permissions: allowCommercialUse는 RentCivit/Rent, Image 항목은 없음. 이미지 상업 사용을 허용한다고 단정하지 않는다.
- 일반 원화 파이프라인의 `reference sheet`, `multiple views`, `chibi` 네거티브와 충돌할 수 있다. 추가할 때 전용 sheet 모드와 영역 분리·정렬·누끼 검증이 필요하다.

### Posable Game Sprites — Spritely

[공식 Civitai](https://civitai.com/models/2982439), [제작자 라이선스](https://spritely.studio/model-license). 원화+뼈대 이미지를 Qwen-Image-Edit-2509에 넣어 캐릭터 포즈를 생성한다. 제작자 설명에 측면/탑다운/아이소메트릭 및 8방향, 무기 포함 동작을 명시한다.

- Pose v5: 1024×1024 단일 포즈. Sheet v5: 1536×1024 3×2의 6개 동작 프레임. 6프레임이라는 사실과 8방향이라는 조건은 별개다.
- 각각 약590.2MB LoRA. Skeleton chart가 첫 이미지, 흰 배경 원화가 두 번째. 강도1. Lightning 사용 시 4steps/CFG1, 미사용25steps/CFG4 안내. 무료 workflow ZIP 및846개 skeleton chart 제공.
- 라이선스는 출력물 상업 사용을 허용하되 크레딧을 요구한다. **무료·유료 생성 플랫폼의 hosted feature/API 제공을 금지**한다(§2). 기본 Qwen의 Apache 표기와 구분한다. 우리 공유 생성 사이트에 그대로 연결할 후보로 채택하지 않는다. 로컬 개인 실험과 서비스 제공은 구분한다.

### FLUX.2 Klein 4B 2×2 Sprite Sheet LoRA

[제작자 HF](https://huggingface.co/fal/flux-2-klein-4b-spritesheet-lora). 단일 오브젝트 이미지 → 대각 두 시점·측면·탑뷰가 섞인 2×2. **동일 카메라의 캐릭터 4/8방향 회전 모델은 아니다.** 학습 데이터는 차량·선박·기계 등48개 짝을 안내한다. 출력은 빨간 배경. Apache2.0 표기, 강도1.1, ComfyUI 변환 가중치 제공. 별도 Klein 기반 모델이 필요하며 현재 Anima/Flanime과 직접 호환하지 않는다. 기계/아이템 다중 시점 후보에 더 적합하다.

### Sprute — 8방향 전체 워크플로

[공식 GitHub](https://github.com/sprited-ai/sprute). 원화/텍스트에서 8방향 strip과 idle/walk/run을 만드는 공개 도구. 단일 LoRA가 아니다. 순서는 S,SE,E,NE,N,NW,W,SW, 기본 cell256×256. 모델 목록은 FLUX.1 Fill, AniSoraV3.2 high/low14B, Wan 구성요소 등을 사용하며 동작 생성에는 Kimodo/LLM2Vec도 포함한다. MIT 코드는 각 모델의 이용 조건과 별개. RTX5090 32GB 시험을 명시하므로 5060Ti16GB에서의 실행·오프로딩·시간은 미검증이다. 기존 환경에 setup을 실행하거나 의존성을 변경하지 않았다.

원문/API 스냅샷은 `data/research/directional-sprites-20261018/`에 보관했다. 차후 방향 생성 파이프라인은 원화 외형 보존, 방향 정확도, 발 기준점·캐릭터 크기 정렬, 프레임 일관성을 따로 검사해야 한다.


## 다운로드 시작 — 2026-10-18 사용자 승인

- RPG Character Sprite Anima/Illustrious 2개, 합계 약320.3MB. `data/directional-rpg-import.json`, 상태 `data/directional-rpg-import-status.json`, 로그 `logs/directional-rpg-download.log` 및 `-error.log`. 백그라운드 downloader PID48012. 다운로드 시작 후 완료까지 감시하지 않았다.
- Sprute 소스·워크플로는 `workflows/sprute-source/`에 shallow git clone 시작. 이 제3자 checkout은 루트 `.gitignore`에서 제외한다. setup이나 패키지 설치 스크립트는 실행하지 않았다.
- Sprute의 **기존 원화 입력 → 8방향 turntable → 애니메이션**에 사용할 core weights10개, 약59.06GB 다운로드 시작. AniSora high/low 각15.0GB, SCAIL2 약17.69GB, UMT5 약6.74GB와 shared VAE/CLIP/DPO/Lightx2v/ToonOut. 고정 upstream revision + LFS SHA256/size를 inventory에 기록해 기존 검증 downloader 사용. 기존 같은 경로의 불일치 파일은 덮어쓰지 않는다.
- 목록 `data/sprute-core-import.json`, 상태 `data/sprute-core-import-status.json`, 로그 `logs/sprute-core-download.log` 및 `-error.log`. 전체가 다운로드 완료/설치 완료/실행 가능하다고 표시하지 않는다. 다음 턴에서 상태와 실제 파일 검증 후 연결·실생성할 것.
- 텍스트 원화 단계의 FLUX Fill과 Kimodo/LLM2Vec 동작 합성 가중치는 이번 목록에 없음. 기존 원화를 입력하고 준비된 동작을 사용하는 경로부터 검증하기 위함. 추가 노드/환경 구축도 아직 미수행.
- Spritely는 서비스 제공 제한 때문에 다운로드 목록에서 제외. RPG/FLUX 계열과 각 개별 구성요소의 서비스/생성물 이용 조건은 활성화 전 별도 확인. HF repo-level license 스냅샷은 `data/research/directional-sprites-20261018/sprute-hf-metadata.json`; 일부 repo의 license가 null인 상태를 허용으로 해석하지 않는다.
- 운영 기본값, 사이트 LoRA 활성 목록, Comfy 실행 환경, GPU 작업, 서버는 이번 다운로드로 바꾸지 않았다. 완료 감시·자동 알림은 설정하지 않았다.


### Sprute 취소 — 사용자 후속 지시

용량이 너무 크다는 사용자 지시로 Sprute downloader 및 자식 프로세스를 중단했다. 상태는 cancelled_by_user. 미완성 BiRefNet_toonout.download(약440MB)는 제거했다. 이미 존재하는 완성 shared VAE/Lightx2v 파일은 기존 사용 여부가 불분명하므로 보존했다. Sprute 자동 재개·설치·연결을 하지 말 것. RPG Character Sprite 두 LoRA는 모두 SHA256 검증 완료(약320MB)이며 다음 실험 후보로 유지한다.


## RPG Character Sprite 실생성 검증 — 2026-10-18

사용자가 테스트를 요청했다. `tools/verify_rpgchara.py`로 4건 실행, 출력 `outputs/rpgchara-test-20261018/preview.html`, `comparison.webp`, 원본 PNG·그래프·settings·history·`visual-review.json` 보관. 다운로드된 두 LoRA SHA256을 재확인하고 큐가 빈 상태에서 실행했다. Sprute는 사용/재개하지 않았다.

- 동일 자체 캐릭터 설명(짧은 파란 머리, 흰 목도리, 금색 테두리 남색 코트, 갈색 부츠), seed20261018. 다른 캐릭터 원화의 외형 보존 실험이 아닌 텍스트 신규 생성이다.
- Anima LoRA는 **학습 대상 Anima Base1.0**(`anima_baseV10.safetensors`)에 연결. production anima-turbo graph를 바탕으로 UNET만 실험에서 바꾼 것이며 실제 Turbo로 실행한 것이 아니다. 512×1024,28steps/CFG4,Euler/simple, model-only LoRA0.7/1.0. 16.08초/13.05초.
- Illustrious LoRA는 현재 양호한 Flanimev3로 실행.768×1280,32steps/CFG5,Euler ancestral/normal, MODEL+CLIP강도0.7/1.0. 17.08초/15.06초. 원제작자의 Illustrious0.1 체크포인트와 같다고 표현하지 않는다.
- 제작자별 rpgchara·multiple views/reference sheet/chibi 및 Anima3×4 prompt를 사용. 일반 sprite 프리셋은 single character/reference sheet 네거티브와 충돌하므로 사용하지 않음. 품질 네거티브만 사용.
- 4건 모두 정면/좌측/우측/후면의3열×4행 배치를 육안 확인. Anima는 도트풍, Flanime은 부드러운 SD풍. Anima1.0의 걸음 차이가0.7보다 크지만 장식·목도리·손 모양 변화가 남는다. Flanime1.0은 원문에 없는 머리띠를 추가한다.
- **정확한8방향은 아니며 완성된 RPG Maker 걷기 시트로 보장하지 않는다.** 발 기준선·캐릭터 크기·시트 정렬·프레임별 의상 일관성이 불완전하다. 각 열을 잘라 재생하는 Anima1.0 GIF는 균등 분할 진단용(정렬 보정 없음), 게임용 최종 export가 아니다.
- 배경은 불투명 흰색이다. transparent background 트리거만으로 alpha가 생기지 않는다. 이번에는 배경 제거/얼굴 보정/확대를 사용하지 않았다.
- 4건 Comfy history success와 원본 해상도 확인, 코드 syntax 검사 완료. 운영 카탈로그/기본값/갤러리/서버는 수정하지 않았다. 사이트 연결은 별도 요청 시 sheet 전용 모드·분리·정렬·이용 조건 확인과 함께 수행할 것.


## 사이트 등록 완료 — RPG 4방향 시트

사용자 요청으로 두 LoRA를 라이브러리/그림체 프리셋에 enabled·experimental로 등록했다. 원화 화면의 **RPG 4방향 · 도트풍 / SD풍** 버튼이 가장 빠른 진입이다. 첫 에셋 유형 선택 후 사용할 수 있다. 도트풍은 Anima Base1.0/512×1024/28steps/CFG4/LoRA1.0, SD풍은 Flanime/768×1280/32steps/CFG5/LoRA0.7로 검토 조합을 적용한다. 기존 Soya·카사 기본값은 유지한다.

- `preset=rpg-sheet` 전용 구도. API는 해당 모델+LoRA 조합과 text 모드만 허용하고 얼굴/포즈/Hires 조합은 거부. 일반 single-character 및 multiple-views 네거티브를 자동으로 추가하지 않는다. 임의 프롬프트에 사용자가 쓴 충돌 태그까지 제거하지는 않는다.
- `sheetLayout`에3열4행/정면좌우후면/정렬미검증 버전 기록. 선택 정보는4방향·four-direction-sheet로 저장한다. 사이트의 기존4/8방향 제작 계획과 구별되는 실제4방향 시트 초안 기능이다. 이미지 장수(count)는 시트 장수다.
- Anima Base 신규 프로필은 기존 엔진 graph의 Anima model-only LoRA 경로를 사용한다. Turbo를 Base로 오표기하지 않는다. 그림체 프리셋 및 LoRA 카드 클릭 시 전용 시트 설정으로 전환한다.
- `image_background.remove_sheet`는 각 칸별 ISNet 추론을 수행하며 RGB/캔버스/셀 좌표를 유지한다. 도트풍은 alpha128기준 이진화, SD풍은 soft alpha. 원본 PNG 보존과 실패 시 원본 반환은 기존 정책 그대로.
- 실제 테스트 생성물 Anima1.0/Flanime0.7 두 시트에 적용, CPU 각각 약10초. `outputs/rpgchara-test-20261018/*-transparent.png`, `*-matte-check.webp`. RGB와 해상도 불변 확인. 흰 목도리 유지 및 주요 캐릭터 분리 육안 확인. 일부 밝은 테두리가 남고 이미 잘린 발끝을 복구하지는 않는다.
- 결과 화면은 시트 초안임을 표시하고 한 캐릭터용 Live2D/영상 전달 버튼은 숨긴다. PNG를 내려받아 셀 분리·발 기준점·의상 검수 후 사용한다. 부분 수정은 기존 inpaint 지원 모델로 전환된다. 8방향/정밀 정렬/완성 걷기 보장은 없다.
- 관련 코드: `image_engine.py`, `image_background.py`, `web/assets/image-studio.js`, `image-styles.js`, `image-looks.js`, catalog JSON, `web/image-studio.html`. 단위 검사 `test_rpg_sheet.py`와 브라우저 시트버튼/모델/크기/강도/payload 검사 추가.
