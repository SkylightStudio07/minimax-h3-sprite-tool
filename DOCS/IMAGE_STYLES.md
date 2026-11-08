# 그림체 LoRA 및 예시 갤러리

## 공개 워크플로 후보 조사 (2026-10-17)

검색 결과의 소개 문구만으로 유명하다고 판단하지 않고 GitHub/Civitai API의 현재 지표와
공개 파일을 확인했다. 다운로드/스타는 인기도 참고이며 품질·호환성 검증이 아니다.
아래 후보를 설치하거나 실행하지 않았다. Soya 공유 JSON 조사와 기존 LoRA 검증은
`SOYA_STYLE_IMPORT.md` 참고.

| 후보 | 확인한 지표/파일 | 용도 및 판단 |
|---|---|---|
| [Legendaer Anima Workflows](https://civitai.com/models/2426853) | 모델 전체 다운로드 36,292 / 좋아요 982, 최신 V9.0 ZIP 배포 | 가장 우선 비교할 공개 Anima 종합 워크플로. Basic/Standard/Advanced, detailer/upscale/ControlNet/inpaint. 제작자 기본 권장 30–50 steps, CFG 4–5이므로 현재 Turbo 10steps/CFG1과 구별. |
| [EasyUse Anima AiO](https://github.com/n0va39/ComfyUI-EasyUseAnima) | GitHub 35 stars, docs/example_workflows/Anima_AiO_v6.0_release_ko.json | 한국어 가이드 및 작가 혼합 예제, HighRes/부분수정/얼굴·눈 보정. 유명세보다는 사이트 기능 적합성으로 추천. |
| [ComfyUI 공식 템플릿](https://github.com/Comfy-Org/workflow_templates) | 공식 저장소, blueprints/text_to_image_anima_base_1_0.json | 표준 기준선. 화풍을 완성하는 LoRA 조합 프리셋과는 별개. |
| [EasyIllustrious](https://github.com/regiellis/ComfyUI-EasyIllustrious) | GitHub 90 stars, example_workflows/Multi Pass.json | Illustrious 구조 생성/디테일 재샘플링을 나누는 참고 후보. 작은 프로젝트이므로 유명 워크플로로 과장하지 않음. |
| [Impact Pack FaceDetailer](https://github.com/ltdrdata/ComfyUI-Impact-Pack) | GitHub 3,339 stars, example_workflows/1-FaceDetailer.json | 널리 쓰이는 보정 부품 및 예제. 얼굴 재그리기로 눈/작화가 변할 수 있어 optional로 설계. |
| [Ultimate SD Upscale](https://github.com/ssitu/ComfyUI_UltimateSDUpscale) | GitHub 1,574 stars, example_workflows/basic-usdu.json | 타일 단위 확대·재그리기 부품. 별도 화풍이 아니고 원본 세부를 바꿀 수 있음. |
| [IPAdapter Plus](https://github.com/cubiq/ComfyUI_IPAdapter_plus) | GitHub 6,146 stars, examples/ipadapter_precise_composition.json 등 | 참고 이미지의 캐릭터/화풍 조건 제어. Anima에 바로 연결할 수 있다고 가정 금지. 제작자 README상 maintenance-only. |

보류: AnimeFix-Workflow는 기능상 적합하지만 GitHub 1 star, ghostmmmm pixel-art-workflow는 8 stars라
'유명 후보'로 분류하지 않았다. 후자는 현재 README상 GPT Image 2 API를 사용하므로 기존 로컬
Anima/SDXL 워크플로처럼 소개하지 않는다. Civitai 741620 Not so simple Illustrious는 검색상
다수 언급이 있으나 원본 API 404여서 현재 배포/버전을 검증하지 못했다.

우선순위 제안: Legendaer Standard → 기존 Soya Anima/Kieed→Flanime 경로 → Anima AiO.
동일 프롬프트/시드 여러 개로 원화 품질과 의상 보존, 시간, 5060 Ti 16GB 메모리를 비교해야 한다.

## 2026-10-17 라이브러리 탐색 개선

LoRA·그림체 프리셋 모두 페이지당 9개, 넓은 화면에서 3열로 표시한다.
좁은 패널에서는 2열/1열로 줄이되 페이지당 9개를 유지한다. 위·아래에 이전/다음 및 페이지 번호,
전체 검색 결과 수와 표시 범위를 제공한다. 탭별 페이지를 유지하고 검색·계열 변경 시 첫 페이지로 돌아간다.
LoRA 검색은 이름·작가·제작자·설명·모델 계열·트리거를 대상으로 한다.
그림체 검색은 이름·프롬프트·설명·연결 LoRA를 대상으로 한다.
`image-library-pager.js`는 `image-styles.js` 및 `image-looks.js`보다 먼저 로드해야 한다.
브라우저 검사에서 9개 제한, 페이지 이동, 검색 초기화, 검색 결과 없음, 기존 작가 안내 및 생성 흐름을 확인했다.

2026-10-15. 운영 코드: `G:\Minimax`.

## 현재 상태

원화 생성기 오른쪽 첫 탭 **LoRA 라이브러리**에 등록 LoRA 전체 3종과 자체 생성 예시 4장씩 총 12장을 표시한다. 사용자 요청에 따라 애니메이션·게임 일러스트 예시로 선별했다. 과거 제작자 예시는 catalog의 publisherPreviews에 참고용으로 보관하고 현재 UI에서는 표시하지 않는다. 프리셋/프롬프트 템플릿과 별도 탭이며 `image-library.js`가 탐색을 담당한다.

회화풍 LoRA 자체도 낮은 강도에서 애니메이션풍 결과가 있어 유지했지만, 기본 강도를 0.3으로 낮췄다. 서양 카툰/반실사 결과가 강한 프리셋 6종은 추천에서 제외했다. 신규 LoRA는 이번 정리에서 다운로드하지 않았다. 중국어 스프라이트 워크플로우 조사: [SPRITE_WORKFLOW_RESEARCH.md](SPRITE_WORKFLOW_RESEARCH.md).

- 플랫 컬러 — motimalu, Civitai model 1132089 / version 2947255
- 부드러운 선화 — VelvetS, model 599757 / version 3226360
- 회화풍 — motimalu, model 1478417 / version 2955844

선택 가중치 총 426,228,547 bytes. 각 제작자 공개 조건의 Image 및 Rent 허용과 Anima 기반 모델 조건을 확인했다. 전체 조건은 출처와 카탈로그 permissions 필드 참고. Flat Color 설명은 Preview3 학습이라고 명시하므로 파일명만 보고 Base 1 학습으로 단정하지 않는다.

**세 LoRA 설치·SHA256 확인·Turbo 1.1 실생성 비교 완료, `enabled: true`다.** 동일 캐릭터 설명·시드 20261015·832×1216·10 steps로 각 스타일의 강도 0/0.5/0.7을 비교했다(9장, 장당 약 6~9초). 각 행은 해당 스타일 트리거를 동일하게 유지하고 강도만 변경한다. 육안으로 스타일 변화가 확인됐으며 기본 강도는 0.5다. 한 프롬프트의 제한된 검증이므로 실험적 표시를 유지한다. 부드러운 선화는 얼굴과 의상을 어둡게 만드는 경향이 있어 UI 설명에 반영했다.

검증 도구: `tools/verify_image_styles.py`. 결과·워크플로 이력·설정·비교표: `outputs/style-validation-20261015/`. 운영 카탈로그를 임시 활성화하지 않고 테스트 프로세스 안에서만 검증한다. 팀/Comfy 큐가 비어 있을 때 수동 실행한다. Windows Comfy가 하위 폴더 구분자를 역슬래시로 요구하는 오류를 수정했으며 워크플로는 `str(Path(filename))`을 사용한다.

LoRA 선택·0~1.2 강도·트리거 자동 적용·생성 메타데이터 저장·Comfy 모델 패치가 연결돼 있다. 기존 프롬프트 그림체 템플릿과는 별개다.

## 유지보수

- `web/assets/image-styles.json`: 출처·버전·가중치 SHA256·예시·트리거·강도·검증 상태의 관리 카탈로그. 일반 사용자에게 임의 모델 경로를 받지 않는다.
- `image_styles.py`: allowlist와 설치/활성화/모델 계열/강도 검증.
- `image_engine.py`: Anima용 `LoraLoaderModelOnly`; 모델 패치 후 KSampler 연결. 트리거는 resolvedPrompt, ID/버전/강도/SHA는 DB·JSON·PNG 메타데이터에 보관된다.
- `web/assets/image-styles.js`: 카드·출처·선택 UI. 모델 전환 시 비호환 선택을 해제한다.
- `tools/download_style_models.py`: 백그라운드 다운로드 및 SHA256 확인. 완료 파일만 `.safetensors`로 확정. 다운로드 오류나 인증 요구는 로그에서 확인하고 우회하지 않는다.
- 로그: `logs/style-model-download.log`, `logs/style-model-download-error.log`.

## 다음 이어가기

초기 다운로드는 401로 실패했지만, 사용자가 Windows 사용자 환경변수 CIVITAI_API_KEY를 등록한 뒤 인증 다운로드에 성공했다. 다운로더는 Bearer 인증을 지원한다. 키를 채팅·로그·저장소에 기록하지 말 것. 사용자 선호상 새 대용량 다운로드를 시작하면 실시간 감시하지 않고 턴을 종료한다.

1. 다른 캐릭터·구도에서도 검증 범위를 넓히고, 새 스타일은 개별 검증 후 활성화한다. 제작자 예시와 로컬 검증 예시를 구분한다.
2. 기존 승인 작업인 **Animagine OpenPose 관절 편집기/연결** 구현도 남아 있다. OpenPose 2.5GB 가중치는 설치 로그상 완료. `IMAGE_POSE_COMPATIBILITY.md`를 이어서 참고한다.

테스트 통과: `python -m unittest test_image_engine` (4건), `node tools/test_image_studio.cjs`. LoRA allowlist·모델 불일치·NaN 강도 거부·Windows 모델 경로·트리거·SHA 저장, 3개 카드/12개 예시/설치된 스타일 선택/미설치 차단/비호환 모델 전환 시 선택 해제, 기존 생성·전달 흐름 확인.
# 2026-10-17 추가 검증

- Smooth Anima Booster Anime (model 1145743/version 3271822) 설치·SHA256 확인. Turbo 1.1 강도 0.4에서 전술요원/남성 검사/학자 3종 생성 확인 후 실험적으로 활성화. FastH3 영상용 LoRA가 아니며 모든 강도·대상에 대한 품질 보장은 아님.
- 라이브러리 총 4종. 전체 폭으로 이동, 4/3/2/1열 반응형 카드. 그림체 프리셋도 동일 격자 적용.
- 기존 3종+신규 1종으로 같은 3개 프롬프트/시드를 생성해 비교. `tools/verify_style_diversity.py`, `outputs/style-diversity-20261017/`. 유화의 새 결과는 실사 경향이 강해 공개 예시에 반영하지 않았고 기존 예시 유지. 나머지 3종은 서로 다른 인물·구도로 교체.
- `web/assets/style-diversity/`의 카드 예시는 캐릭터 고정 설정이 아니며 생성 프롬프트에 자동 삽입되지 않음.
- `tools/test_image_studio.cjs`: 실제 선택/요청/화면 전환 및 1440/1000/700/390px에서 4/3/2/1열 검증.

## 2026-10-17 FSThicc / Silvermoon 추가 요청

- [FSThicc](https://civitai.com/models/2061456/fsthicc-style-lora): Anima v1.0, Anima B-side, Illustrious v4.0 3종을 고정 버전으로 등록했다. 라이브러리 카드는 다운로드·실생성 검증 대기로 비활성화했다. 굵은 선과 곡선 체형을 함께 강조하는 모델이라 신체 비율 과장 여부를 비교해야 한다. `thick black outline`은 선택적 트리거다. 제작자 공통 권장값은 CFG 5–7, 25 steps, Euler A 또는 DPM++ 2M Karras이며 Turbo/Soya 권장값으로 오인하지 말 것. 기본 강도 0.3은 로컬 시험 시작값이다.
- FSThicc의 Civitai 표시 조건: `allowNoCredit=false`, `allowCommercialUse=[RentCivit]`, `allowDerivatives=false`. 크레딧을 요구하며 게임 결과물 상업 이용 허용을 확인한 상태가 아니다. 모델 파생 금지와 생성 이미지 이용 조건을 동일시하지 말고 제작자 원문을 확인할 것. 업로더 이름을 작가 이름으로 간주하지 않는다.
- [SilvermoonMix-Anima-Evolved](https://civitai.com/models/2639339/silvermoonmix-anima-evolved-29b2b): 기존 Anima용 2B v2.3 BF16과 실험용 2.9B v2.3 Turbo BF16만 선택했다. 모델 가중치는 `models/diffusion_models`에 설치하며 SDXL 체크포인트 로더로 읽지 않는다. 운영 선택 목록에는 아직 활성화하지 않는다. 현재 Soya 기본값을 유지한다.
- 제작자 설명상 손·다인 구성·작가 태그 대응이 개선 목표이며 실제 성능 검증 전이다. 2B 일반판은 Euler a, CFG 4, 20–28 steps. 2.9B Turbo는 ER SDE, CFG 1, 8–12 steps. **네거티브 프롬프트 없이 시작**하고 작가 태그 앞에 **`@`**를 붙이는 것이 제작자 권장이다. v2.3 일반판은 증류 과정 과노출 수정이라고 설명한다.
- 2.9B는 최신 ComfyUI/Forge Neo와 재시작을 요구한다. 기존 2B LoRA는 블록 재매핑이 필요할 수 있으므로 기존 Soya의 RDBT/Kieed 연결에 자동 대체하면 안 된다. 제작자 링크: [Remap](https://github.com/shin131002/ComfyUI-Anima-Remap), [loraPatch](https://github.com/sparklingcoffee777/ComfyUI-Anima-2.9B-loraPatch), [LoRA/ControlNet Patch](https://github.com/INuBq8/ComfyUI-Anima-LoRA-ControlNet-Patch). 운영 Comfy를 무조건 업데이트하지 말고 분리 환경에서 검증한다.
- 두 Silvermoon 버전이 제공하는 텍스트 인코더/VAE는 SHA256이 서로 같고 기존 `qwen_3_06b_base.safetensors`, `qwen_image_vae.safetensors`와도 일치했다. 중복 다운로드하지 않고 다운로더에서 재검증해 재사용한다. 신규 가중치 5개 합계 **10,531,216,634 bytes (약 10.53 GB)**. Silvermoon Civitai 표시 조건은 Image 포함 상업 이용 허용이나 기반 Anima 조건은 별도다.

인계 파일:

- `data/research/civitai-2061456.json`, `civitai-2639339.json`: 설명·버전·권한 API 스냅샷.
- `tools/prepare_fsthicc_silvermoon.py`: 스냅샷으로 카드·다운로드 목록 재생성. 같은 SHA의 기존 검증 상태 보존.
- `data/fsthicc-silvermoon-import.json`: 다운로드 고정 목록, 파일별 bytes/SHA256/출처.
- `data/silvermoon-model-candidates.json`: 비활성 기반 모델 후보 및 버전별 권장 설정. 운영 모델 목록과 분리.
- `data/fsthicc-silvermoon-import-status.json`: 백그라운드 다운로드 상태. `verified`만 완료로 판단.
- `data/fsthicc-silvermoon-download.log`, `data/fsthicc-silvermoon-download-error.log`: 다운로드 로그.

다음 세션: 다운로드 확인 → 2B 단독/네거티브 없음 기준 생성 → FSThicc 강도 0/0.3/0.5 비교 → 2.9B 분리 환경 및 LoRA 재매핑 검증 → 통과한 조합만 UI 활성화. 다운로드 시작 후 완료까지 실시간 감시하지 않는다.

## 2026-10-17 RPG 스프라이트 LoRA

- [Counter Side Sprites](https://civitai.com/models/1942132/counter-side-sprites) / version 2198107 / file 2091877: Illustrious용, 제작자 설명은 카운터사이드 스프라이트 학습이라고만 명시. API에 트리거·강도 권장값이 없어 임의 트리거를 만들지 않았다. 파일 크기 228,481,396 bytes는 일치하지만 API SHA256 `d5224d243d68bef339f09b728d315a4fb7d796a0d9fe21652a69dbb241a972f2`와 받은 파일 SHA256 `9f3a0f44bea6c093c178700521a22576f4e10ae5a8ffe30a2c1c6680f02030d8`가 다르다. 별도 새 다운로드도 검증에 실패해 카드 비활성화. `.download` 파일을 운영 safetensors로 승격하지 말 것. 원본 제공자 해시/파일 상태 확인 필요.
- [Epic Seven Sprites](https://civitai.com/models/1747637/epic-seven-sprites) / version 1977902: Illustrious용, 트리거 `e7sprites`, 제작자 권장 896×1152. 여성 측면 전신 대기 자세 중심이며 남성·몬스터는 미검증. 회색 단순 배경과 facefix를 권장하지만 첫 비교에서는 추가 얼굴 보정 없이 LoRA 효과를 비교한다. SHA256 검증 완료. 강도 0.6은 로컬 시험값으로 제작자 권장값이 아니다.
- 두 모델의 Civitai 표시 조건에는 Image 상업 이용이 포함된다. 기반 Illustrious 조건과 다른 게임 캐릭터의 권리는 별도다. 업로더 이름을 작가 이름으로 취급하지 않는다.
- 캐릭터 태그는 외형 조건, LoRA는 스프라이트 표현 조건으로 함께 사용 가능하다. 학습하지 않은 다른 게임 캐릭터의 정확한 외형·무기 재현은 보장하지 않는다. 동작 프레임/투명 파츠/리깅을 출력하는 모델은 아니다.
- `image_engine.py`의 `illustrious-xl`: 기존 검증 다운로드 Illustrious XL 1.0과 별도 VAE 사용. LoRA는 MODEL과 CLIP을 함께 패치한다. Anima의 모델 전용 로더와 구분하고 계열 혼용을 서버에서 거부한다. Soya 기본값은 유지한다.
- UI에 896×1152와 RPG 전투 스프라이트 프리셋 그룹 추가. 모델 계열에 맞춰 LoRA·템플릿 선택을 전환한다. 검증 대기 카드는 선택 불가. 캐릭터는 프리셋에 고정하지 않는다.
- 다운로드 목록/상태: `data/rpg-sprite-styles.json`, `data/rpg-sprite-styles-status.json`. 재다운로드: `data/rpg-sprite-counter-retry.json`, `data/rpg-sprite-counter-retry-status.json`. 설명 스냅샷은 `data/research/civitai-1942132.json`, `civitai-1747637.json`.
- 수동 GPU 검사: `tools/verify_rpg_sprite_styles.py`. 검증된 파일만 대상으로 임시 프로세스 안에서 활성화, 다른 게임의 라피/엔터프라이즈 태그로 같은 시드 비교. 카탈로그 자동 활성화는 하지 않는다. 결과 `outputs/rpg-sprite-styles-20261017/preview.html`, 설정·전체 PNG·Comfy 이력 포함. 태그는 동일 캐릭터 재현 보증이 아니며 웹 카드 예시는 육안 검토 후 별도 게시한다.


RPG 검증 결과: Epic Seven 3장 생성 성공(라피 강도 0/0.6, 엔터프라이즈 0.6), 각 약 18–21초. 육안으로 게임 전투 원화 형태와 캐릭터 특징을 일부 유지하되 얼굴·의상·무기 세부가 단순화됨을 확인했다. Epic Seven 카드·프리셋을 실험적으로 활성화하고 로컬 실생성 예시 2장을 게시했다. Counter Side는 새 다운로드에서도 SHA 검증 실패하여 비활성화 유지. API 설명/해시 검증을 우회하지 않았다. 백엔드 단위 검사 9건 및 브라우저 통합 검사 통과. 웹 서버가 7866에서 꺼져 있어 GPU 엔진 자동 시작을 생략하고 웹 워커만 기동했으며 `/api/me` HTTP 200 확인.
## 2026-10-17 RPG 얼굴 보정 / FaceDetailer

원화 생성 화면에 선택형 **얼굴 보정 · 실험적** 체크박스를 추가했다. Illustrious XL / Animagine의 새로 생성에서만 지원하며 기본값은 꺼짐이다. Anima 및 Soya, 참고 이미지·부분 수정에서는 비활성화한다. 현재 지원 범위 밖의 요청은 서버에서도 거부한다.

구현은 기존 분리 환경(8191)의 Impact Pack `FaceDetailer`와 Impact Subpack `UltralyticsDetectorProvider`를 사용한다. 얼굴 검출 → 전체 캔버스 가로·세로 2배 확대 → 얼굴 크롭을 높은 해상도로 약하게 재생성 → feather 합성 순서다. 실제 그래프에서는 확대 후 검출해 작은 얼굴의 검출도 돕는다. 신경망 전신 업스케일이 아닌 Lanczos 확대이며 얼굴 외 디테일이 새로 복원되는 것은 아니다. 예: 기본 생성 896×1152 → 결과 1792×2304.

- `image_face_detail.py`: 그래프 추가/설치 상태, 고정 파라미터. guide size 384, max 768, 20 steps, CFG 5, denoise 0.35, crop factor 2.5, feather 8. 얼굴 패스의 스프라이트 LoRA 강도는 최대 0.25로 낮춘다. 전신/무기 배치 태그를 얼굴 프롬프트에서 제외한다. 원래 체크포인트·CLIP에서 새 패치를 만들어 LoRA 중복 적용을 피한다.
- `image_engine.py`: 엄격한 bool 옵션·지원 계열/모드 검증, 8191 라우팅, 8189 GPU 캐시 정리, 출력 크기 메타데이터. Soya 기본값은 유지한다. 팀 FIFO 워커는 기존 8191 기동 및 세 GPU 큐 검사 경로를 재사용한다.
- 결과마다 `beforeFaceUrl`의 단순 확대 비교본을 저장하고 결과 화면에 **보정 전 보기** 링크를 제공한다. API는 기존 인증/결과 파일 allowlist에 이 키만 추가한다. 얼굴 미검출이면 `faceDetailApplied=false`와 경고를 반환하고 확대 원본을 유지한다. 인페인트·자동 부분 수정에는 적용하지 않는다.
- 검출 가중치: [deepghs/anime_face_detection](https://huggingface.co/deepghs/anime_face_detection), commit `784dc4c0bb692351ddcdbe6131a050b17d3025d5`, `face_detect_v1.4_n/model.pt`, 6,229,496 bytes. 모델 카드상 MIT. 정확한 SHA/출처는 `data/anime-face-detector.json`. 공유 모델과 워크플로 환경의 `models/ultralytics/bbox/anime-face-v1.4-n.pt`에 같은 검증 파일을 둔다. Subpack의 bbox 검색 경로가 공유 ultralytics 경로와 별도여서 환경 폴더에도 복사했다. 기존 Python 패키지를 변경하지 않았다.
- [Impact Pack](https://github.com/ltdrdata/ComfyUI-Impact-Pack) / [Impact Subpack](https://github.com/ltdrdata/ComfyUI-Impact-Subpack)은 기존 설치를 사용한다. `ready()`가 파일 존재만 확인하므로 노드 import 실패 시 Comfy 로그를 확인한다. 부분 출력만 성공하고 FaceDetailer가 실패할 수 있어 최종 이미지·비교본·마스크 출력 존재를 필수 확인한다.
- `tools/verify_rpg_face_detail.py`: 동일 라피·엔터프라이즈 PNG에 denoise 0.25/0.4 비교, 2배 출력과 얼굴 검출 마스크 확인. 결과와 그래프/설정/Comfy 이력은 `outputs/rpg-face-detail-20261017/`. `--full-smoke`는 실제 전체 생성 → 얼굴 보정 → 원본 비교 파일 및 PNG 메타데이터 저장 경로를 별도로 검사한다. 테스트 결과는 팀 갤러리에 등록하지 않는다.

눈 구조는 개선되지만 캐릭터의 눈 모양·머리카락 경계·인상이 달라질 수 있다. 보정은 원본 픽셀 복구가 아니라 부분 재생성이며, 확대 비교에서 여전히 남는 흐림과 원작 일치 여부를 확인할 것. 선택한 캐릭터 2종·시드 1개 검증을 다른 캐릭터에 대한 품질 보장으로 확대하지 않는다.

검증 기록: 라피·엔터프라이즈 각 denoise 0.25/0.4 총 4장 실제 생성 및 1792×2304 출력 확인. `pixel-audit.json`에서 단순 확대 비교본 대비 변경 픽셀이 얼굴 주변에만 있음을 검사했다. 별도 `--full-smoke`에서 전체 생성·기본 denoise 0.35 보정·비교본·PNG 메타데이터 저장까지 성공했다. 백엔드/서버 34개 테스트, 브라우저 통합 검사(지원 모델 선택·모델 전환 시 해제·비교본 링크 포함) 통과. 운영 웹 워커만 재기동 후 HTTP 200 확인했으며 GPU 서버는 유지했다.

## 2026-10-17 고해상도 2차 생성 (Hires fix)

Illustrious XL / Animagine의 새로 생성에 **고해상도 2차 생성 · 실험적** 옵션을 추가했다. 기본값 꺼짐. `2x-AnimeSharpV4_Fast_RCAN_PU`로 2배 확대하고 전체 이미지를 latent 입력으로 재생성한다. 사이트 고정값은 16 steps / CFG 5 / Euler ancestral / normal / denoise 0.2. 사용자 요청의 임의 `hiresDenoise`는 채택하지 않는다. 의상·총·머리카락 디테일을 추가할 수 있으나 기존 모양도 달라질 수 있다.

- `image_hires.py`: 공유 업스케일러 및 표준 Comfy 노드 사용. VAE encode/decode만 512 tile / overlap 64로 메모리 사용을 줄이고 샘플러는 전체 화면에서 실행한다. 타일별 샘플링은 아니므로 해상도가 높으면 VRAM·시간 부담이 크다.
- 전신 생성 → AnimeSharp 2배 → VAEEncodeTiled → KSampler 저강도 2차 생성 → VAEDecodeTiled → 선택형 FaceDetailer 순서. Hires와 얼굴 보정을 같이 켜면 얼굴 모듈의 별도 확대를 생략해 출력이 4배가 되지 않게 한다. 기본 896×1152 입력은 두 옵션 조합에서도 1792×2304 출력이다.
- 백엔드는 8191 분리 환경을 재사용하며 요청 bool/계열/모드를 서버에서 검증한다. Soya·Anima, 참고 이미지·부분 수정에는 지원하지 않는다. 모델 전환 시 UI에서 지원하지 않는 체크를 해제한다. 기본 Soya 경로는 변경하지 않는다.
- `hiresFix`, `hiresFixVersion`, `hiresDenoise`, `outputWidth/Height`를 설정/PNG 메타데이터에 기록한다. 결과 `beforeHiresUrl`은 2차 재생성 전 AnimeSharp 확대본이며 **전체 보정 전 보기**로 제공한다. `beforeFaceUrl`은 Hires 완료 후 얼굴 보정 직전 이미지다. 인증된 결과 파일 allowlist에만 두 링크를 추가한다.
- 비교 도구 `tools/verify_rpg_hires.py`: 같은 원본·시드로 face-only와 Hires denoise 0.18/0.28을 비교한다. 얼굴은 모두 denoise 0.35로 고정한다. 결과 `outputs/rpg-hires-20261017/preview.html`과 PNG·그래프·설정·Comfy 이력을 보존한다. `--full-smoke`로 운영 `run_job`의 전체 생성/비교 파일/PNG 메타데이터를 검사한다. 별도 디렉터리를 사용하므로 검증 샘플은 팀 갤러리에 등록되지 않는다.


Hires 비교 검증: 라피·엔터프라이즈 각각 얼굴 보정만 / 전신 denoise 0.18 / 0.28 총 6개 결과. 모든 얼굴 패스는 0.35, 모든 최종 출력은 1792×2304. 전신 보정+얼굴 보정은 원본 한 장 기준 약 61–72초였으며 기본 전신 생성 시간은 별도다. 0.28에서 작은 장식·윤곽이 더 바뀌어 운영 고정값은 0.2로 두었다. 백엔드/서버 35개 테스트, 브라우저 모델 전환·두 옵션·비교 링크 검사 통과.

Hires 운영 경로 검증 완료: 새로 생성 → 기본 denoise 0.2 전신 보정 → 얼굴 보정 → 최종 PNG/전신 보정 전/얼굴 보정 전 저장 및 메타데이터 확인. 최종 1792×2304, 이 실행은 약 90초. 기록 `outputs/rpg-hires-20261017/full-smoke.json`. 웹 워커만 재기동 후 HTTP 200 확인.
## 2026-10-17 원본 고해상도 RPG 생성으로 전환

사용자는 Hires 재생성 결과가 더 나쁘다고 평가했고, 시간이 더 걸려도 처음부터 1024×1536으로 생성하는 방향을 요청했다. Hires를 고화질 권장 경로로 간주하지 말 것. Hires와 얼굴 보정은 선택형으로 유지하며 자동 활성화하지 않는다.

**현재 RPG 추천 경로: `flanime-xl` (Flanime · RPG 원본 고해상도) + Epic Seven LoRA**, 1024×1536 / 40 steps / CFG 5 / LoRA 0.6. 기본 Soya 모델은 바꾸지 않는다. Epic Seven 프리셋은 이 Flanime 프로필로 연결한다. UI 해상도 선택에 1024×1536 원본 생성 추가. API 기본 크기도 모델의 `defaultSize`를 읽어 UI와 일치시킨다. `hiresFix=false`, `faceDetail=false`가 기본이며 생성 그래프에는 추가 확대/전신 재생성/얼굴 노드가 없다.

기반 모델은 기존 Soya에 설치된 `rinFlanimeIllustrious_v30.safetensors`를 재사용한다. 출처 Civitai model 1544647 / version 2710976, SHA256 `50ea33bae7b499cee2fad3d04b4152270427f3ffab6776910b439bc4974c5ab3`, 표시 조건 Image 및 RentCivit 허용. 기존 Illustrious XL 1.0 모델은 원래 896×1152 / 28 steps 설정으로 유지한다. Flanime도 Illustrious 계열이므로 LoRA·SDXL 태그 템플릿을 연결했다. 새 Flanime 프로필은 원본 생성이 기본이며 Hires는 지원하지 않는다. 초기 얼굴 보정 0.25/LoRA 포함 실험의 흰색 얼룩 문제 이후, 아래 원본 해상도 얼굴 보정 설정(0.15/LoRA 제외)을 검증해 선택형으로 연결했다.

첫 Illustrious XL 1.0 + Epic Seven 1024×1536 샘플은 회색 실루엣/선화로 무너졌다. 8189 기본 노드 경로, 28/40 steps, VAE tiled decode, LoRA 제거까지 대조했다. VAE tile 변경으로 복구되지 않았고 기반 모델을 Flanime로 교체하면 정상 컬러 원화가 생성됐다. 이 결과만으로 정확한 내부 원인을 확정하지 않는다. 실패 결과는 `outputs/rpg-native-1536-20261017/illustrious-first-test/` 및 `diagnosis/`에 보관하고 성공 예시로 게시하지 않는다.

실제 생성 도구 `tools/verify_native_rpg.py`: Flanime에서 라피/엔터프라이즈 태그로 원본 1024×1536 / 40 steps, 같은 원본에 얼굴 부분 보정 0.25를 선택 비교한다. 얼굴 비교본도 크기를 유지하며 Hires/전체 재생성은 사용하지 않는다. 결과/설정/그래프/Comfy 이력은 `outputs/rpg-native-1536-20261017/preview.html` 및 같은 폴더. 포즈·무기 형태·캐릭터 재현은 여전히 검토해야 한다.


원본 고해상도 검증 완료: Flanime에서 라피 37.25초 / 엔터프라이즈 36.17초(원본+동일 크기 얼굴 비교 실험 포함). 1024×1536 원본의 선·얼굴·복장 확인 후 원본 2장을 라이브러리에 게시했다. 얼굴 보정 비교본은 흰색 얼룩이 추가될 수 있어 새 프로필에서는 비활성화한다. 단위 검사 12개 및 브라우저 기본 크기/40 steps/모델 계열/옵션 검사 통과. Soya 기본값 유지.
## 2026-10-17 Flanime 원본 해상도 얼굴 보정

사용자가 승인한 원본 1024×1536 PNG를 그대로 두고 얼굴만 약하게 보정했다. `image_face_detail.add_native`를 새로 분리해 **denoise 0.15 / CFG 4 / 20 steps / guide 512 / max 1024 / feather 6 / bbox dilation 2**로 고정한다. 얼굴 패스에서는 스프라이트 LoRA를 제외하고 같은 Flanime 체크포인트와 원본의 캐릭터 태그를 사용한다. 전신 배치 태그를 얼굴 프롬프트에서 제외하고, 원본에 side view 지시가 있을 때만 측면 지시를 유지한다. 얼굴 얼룩·페이스 페인트 등을 네거티브에 추가했다. 원래 의도한 얼굴 장식까지 달라질 수 있어 기본값은 꺼짐이다.

Flanime 프로필에서 **얼굴 보정**을 선택할 수 있도록 지원 목록에 복원하되, 다른 프로필의 2배 확대 얼굴 보정과 구분한다. `faceDetail.nativeModels` API 필드로 UI 설명을 분기한다. 최종 출력과 `beforeFaceUrl` 모두 원본 크기를 유지하며, `faceDetailVersion=native-face-detail-v1`, `faceDetailDenoise=0.15`, 정확한 `outputWidth/Height`를 설정/PNG에 기록한다. 임의 요청의 faceDetailDenoise는 채택하지 않는다. Hires는 Flanime에서 계속 비활성화한다.

수동 검증 도구 `tools/refine_native_faces.py`: 승인된 라피/엔터프라이즈 raw PNG를 LoadImage로 읽어 몸을 다시 생성하지 않는다. 강도 0.15/0.22 비교 후 이미지 크기 1024×1536 유지 및 변경 픽셀이 얼굴 주변에 한정되는지 검사한다. 그래프·마스크·설정·Comfy 이력·확대 비교·전체 PNG는 `outputs/rpg-native-face-20261017/`. 작은 인상/홍채/머리카락 변화는 여전히 생길 수 있으므로 원본과 비교한다. 원본 파일 및 기존 라이브러리의 raw 예시는 덮어쓰지 않는다.


원본 얼굴 보정 검증: 라피·엔터프라이즈 각 0.15/0.22 총 4개 결과, 출력 1024×1536 및 변경 영역 얼굴 주변 한정 확인. 최종 기본값 0.15 예시를 육안 확인했고 기존 흰색 얼룩은 보이지 않았다. 단위 검사 13개와 브라우저 원본 해상도 안내·옵션 활성화 검사 통과. 웹 워커만 재기동 후 HTTP 200 확인.

## 카사 사용자 승인 활성화 (2026-10-18)

카사 낮은 변형 결과를 사용자가 검토·승인해 라이브러리에 활성화했다. 실제 받은 SHA256과 공식 게시 SHA256은 다르며 `sha256`/`upstreamSha256`으로 구분하고, `integrityStatus=upstream-mismatch-user-approved`를 기록한다. 공식 해시 일치 성공으로 표시하지 않는다. Flanime 참고 이미지 변형0.3 권장, 포즈 편집은 별도 적용. 구현·실험·이력은 [SPRITE_STUDIO_CONVERSION.md](SPRITE_STUDIO_CONVERSION.md)의 최신 사이트 연결 절을 참조한다.
