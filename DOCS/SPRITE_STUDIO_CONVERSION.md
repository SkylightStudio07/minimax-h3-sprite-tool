# 원화 입력 → 전투 스프라이트 변환 실험

2026-10-18. 사용자가 새 원화를 생성하는 대신 제공한 일러스트를 게임 전투 스프라이트로 변환할 수 있는지 요청했고, 우선 실제 생성으로 검증했다. **후속으로 기존 원화 생성 화면에 Flanime 참고 이미지 변형과 관절 포즈 편집을 연결했다. 별도 스프라이트 스튜디오 탭은 아직 없다. 최신 구현은 아래 사이트 연결 절 참고.**

## 입력과 실행

- 기존 사용자 원화: `outputs/rigging/5ed3fddd3383252008ecd0c8e7dce9df/source-original.png` (후드, 자주색 안감 긴 검은 코트, 기계 장갑 캐릭터).
- `tools/verify_sprite_conversion.py`: 투명 여백만 잘라 비율 유지, 1024×1536 회색 캔버스에 배치. 원본은 복사 보존한다.
- Flanime v3 + Epic Seven LoRA 0.6, 32 steps / CFG 5 / Euler ancestral / normal. 카사 LoRA는 기존 SHA 불일치로 사용하지 않았다.
- LoadImage → VAEEncode → KSampler img2img → VAEDecode → SaveImage. 원화 픽셀을 latent 입력으로 사용하며 새 전신 이미지를 텍스트만으로 생성하지 않는다. `build_workflow`의 기존 reference 분기를 수동 실험에서 사용했다. 운영 Flanime 검증은 여전히 reference 모드를 받지 않는다.
- 출력: `outputs/sprite-conversion-20261018/preview.html`, 전체 PNG, 입력 원본/준비본, 설정·그래프·Comfy 실행 이력. 원본 대비 예시 `source-vs-converted.webp`.

## 실제 결과

| 실험 | 시간 | 관찰 |
|---|---:|---|
| img2img 0.30, LoRA 0.6 | 26.16초 | 후드·코트·장갑과 기존 포즈를 대체로 유지하며 선·채색이 단순화. 현재 외형 보존용 우선 후보. 눈·얼굴 세부는 달라짐. |
| img2img 0.50, LoRA 0.6 | 22.06초 | 화풍 변화와 함께 손 근처에 원본에 없는 작은 금색 장식이 생김. |
| img2img 0.70, LoRA 0.6 | 22.08초 | 장갑·벨트·코트 선 등이 더 바뀌고 떠 있는 물체가 생김. 원본 보존용 기본값으로 부적합. |
| img2img 0.50, LoRA 0 | 23.09초 | 같은 입력/시드의 기반 모델 대조. LoRA와 변형 강도의 효과를 구분할 비교군. |
| OpenPose + img2img 0.65 | 33.14초 | 지정한 전투 포즈를 거의 따르지 않음. |
| OpenPose + img2img 0.80 | 29.30초 | 포즈 지시가 여전히 약하고 의상·장식 변화가 커짐. |

따라서 **동일 포즈의 게임풍 가공은 가능성이 있지만, 다른 전투 자세로 바꾸면서 외형까지 보존하는 기능은 아직 검증되지 않았다.** 1개 원화·1개 시드에 대한 실험이며 다른 그림체/비율에 일반화하지 않는다.

0.30 결과는 기존 Anime Segmentation ISNet을 CPU에서 사용해 `preserve-030-transparent.png`도 생성했다. 1024×1536, 모서리 alpha 0 및 전체 약 64%가 alpha<10임을 확인했다. RGB는 유지하고 alpha만 바꾸는 경로다. 최종 사용 전 코트 끝·리본·장갑 틈새를 눈으로 검토해야 한다.

## 포즈 제어 후속

설치된 xinsir SDXL OpenPose + ControlNetApplyAdvanced (strength 0.65, start 0, end 0.85)를 실험했다. 손으로 그린 COCO-18 OpenPose `battle-pose.png`를 사용했다. 현재 Flanime 조합에서는 이 조건의 자세 지시가 거의 반영되지 않았다. 모든 포즈 제어가 불가능하다고 결론 내리지 않는다.

[Illustrious-XL ControlNet Openpose](https://civitai.com/models/1359846)를 추가 후보로 확보했다. 설명상 fengyin/windsingai가 학습했고 preprocessor와 모델 유형을 맞추라고 안내한다. 업로드 원래 이름이 `IllustriousXL_openpose`인데 다운로드 이름이 체크포인트처럼 바뀌었다는 제작자 주의가 있다. 실제 설치는 혼동을 피하도록 **controlnet 폴더**의 `illustrious-openpose-v1.safetensors`로 고정했다.

- model 1359846 / version 1536174 / file 1436139.
- 약 2.50 GB. SHA256 `0d8bacf24534dc6f2716f5d0ffa6085571928776f8687565ef290a17d9f3615c`.
- Civitai 표시 조건에 Image 상업 이용 허용, 크레딧 필수 아님. 원문 스냅샷 `data/research/civitai-1359846.json`.
- 다운로드 목록 `data/illustrious-openpose-import.json`, 상태 `data/illustrious-openpose-import-status.json`, 로그 `data/illustrious-openpose-download.log`와 `-error.log`.
- 다운로드 완료 및 검증됨. 아래 후속 실험에서 실제 로드·생성까지 확인했다.
- IPAdapter/캐릭터 참조 어댑터는 이번 실험에 사용하지 않았다. 포즈만 강하게 바꿀 때 생기는 외형 손실을 해결하려면 참조 조건을 별도로 조사해야 한다.

## 사이트 연결 제안

원화 생성과 별도로 스프라이트 스튜디오에서 원화 업로드 → 투명 여백/비율 준비 → 화풍 변환(기본 0.3) → 동일 포즈/포즈 변경 선택 → 검수 → 모션/시트 제작으로 이어가는 구성이 적절하다. 현재는 동일 포즈 변환부터 제품화하고 포즈 변경은 호환 모델 검증 후 실험 옵션으로 붙인다. Hires나 얼굴 보정은 자동으로 켜지 않는다.

## 카사 및 전용 OpenPose 후속 실험 (2026-10-18)

재현: `tools/verify_counter_conversion.py --pose-only` 및 `--isolated-unverified`. 출력은 `outputs/counter-side-conversion-20261018/preview.html`. 기존 원본·운영 카탈로그·갤러리·기본 Soya 경로는 변경하지 않았다.

### 카사 파일 검증 상태 — 당시 보류 기록 (후속 사용자 승인으로 활성화)

공식 model 1942132 / version 2198107 / file 2091877에서 반복 다운로드했고, 캐시 갱신 쿼리를 붙인 새 다운로드도 동일 파일이었다. 크기 228481396 bytes, safetensors 헤더의 제목 CounterSide, 2958 tensor entries와 slice shape 파싱을 확인했다. 그러나 **이는 공식 게시 파일과 같은 가중치임을 증명하지 않는다**.

- 게시 SHA256: `d5224d243d68bef339f09b728d315a4fb7d796a0d9fe21652a69dbb241a972f2`.
- 실제 반복 수신 SHA256: `9f3a0f44bea6c093c178700521a22576f4e10ae5a8ffe30a2c1c6680f02030d8`.
- 실제 tensor payload SHA256: `8497b2adc57e9b9e5830a3cdd917642ff522bbf2ad90fda271694287b0b52ce2` (파일 자체 metadata의 sshs_model_hash와 일치). 게시 AutoV3 `ECA95D5CE3DB`와도 다르므로 **단순 metadata 변경 때문이라고 단정할 수 없다**.
- 실제 전체 SHA에 대한 공식 by-hash API는 404. 원인 미확정.
- 요청된 실생성 비교에만 별도 `models/loras/isolated-tests/counter-side-unverified-9f3a0f44.safetensors` 복사본을 사용. 일반 다운로더의 검증 정책이나 게시 해시는 수정하지 않았다. 운영 카사 항목은 계속 disabled.
- 결과별 JSON에 `integrityVerified: false`, 별도 `provenance.json`에 불일치 기록. 정식 검증 성공으로 표현하지 말 것.
- 공식 설명은 “CounterSide sprites로 학습” 정도이며 추가 사용법/트리거가 명시되지 않았다. 최신 원문 snapshot: `data/research/civitai-counter-side-current.json`.

### 전용 포즈 모델 비교

Flanime + Epic Seven 0.6 / 1024×1536 / 32 steps / CFG5 / seed20261018. 이전 xinsir 실험과 달리 **Illustrious 전용 ControlNet strength 1.0, start0/end1.0** 사용. 모델 교체와 강도를 동시에 바꿨으므로 개선을 모델 하나의 효과로만 해석하지 않는다.

- denoise0.8: 팔 굽힘·다리 간격·우측 방향 변화가 관찰되나 원화의 장갑·벨트가 다시 그려진다.
- denoise1.0: 우측 측면과 구부린 팔·벌린 다리 변화가 더 뚜렷하다. 원본 코트/부츠 세부는 크게 줄고 바뀐다. **입력 latent를 완전히 노이즈화하므로 원본 이미지 참조 보존 실험의 성공으로 볼 수 없다.** 색/복장 유사성은 텍스트 설명에서도 유도된다.
- 목표 뼈대를 픽셀 단위로 정확히 재현한 것은 아니다. 실제 출력 이미지와 설정/이력은 함께 보관.

### 조사한 다음 방법

카사 격리 파일 + LoRA0.6 실생성 4건도 완료했다 (동일 원화/시드/해상도/32steps).

| 출력 | 시간 | 육안 검토 |
|---|---:|---|
| counter-preserve-030 | 24.08초 | 원화 실루엣·얼굴·후드·기계 장갑이 대체로 유지됨. 장갑 옆 작은 금색 부분이 추가됨. 기존 자세 유지. |
| counter-style-050 | 22.09초 | 부츠·금속 장식이 변하고 손 위에 떠 있는 소품 추가. 보존 목적에는 0.30 우선. |
| counter-dedicated-pose-080 | 34.11초 | 팔·다리 자세 변경. 홀스터·파우치·벨트가 추가되고 기계 장갑은 단순화. |
| counter-dedicated-pose-100 | 31.12초 | 우측 측면·굽힌 팔·벌린 다리. 코트 안감과 기계 장갑 등 원본 세부 손실. 원화 latent 의존이 사라져 텍스트 유사 캐릭터로 해석해야 함. |

`style-comparison.webp`는 원화/기존 Epic Seven0.3/카사0.3, `pose-comparison.webp`는 원화/카사포즈0.8/1.0 비교다. 세부 기록 `visual-review.json`. 총 6개 생성 이력(Epic 전용포즈 2개 포함)에서 success 및 PNG 해상도 확인. 다른 원화/시드로 검증하지 않았음.

1. **원화 참조 + 목표 OpenPose + 카사 LoRA**: img2img의 원래 자세 저항을 줄이면서 원화 외형을 별도 이미지 조건으로 넣는 구성. [IPAdapter Plus](https://github.com/cubiq/ComfyUI_IPAdapter_plus)의 SDXL 참조/스타일·구도 분리 예제를 확보했다. 코드/모델 미설치·효과 미검증이며 SDXL 지원이 Illustrious의 캐릭터 보존 성능을 보장하지 않는다. `data/research/ipadapter-sprite-reference/`에 commit 고정 원본 예제와 README 저장.
2. **Qwen 편집으로 자세 변경 → 저 denoise 카사 화풍 가공**: [공식 Qwen Image Edit 2509](https://huggingface.co/Qwen/Qwen-Image-Edit-2509)는 다중 이미지 입력으로 캐릭터와 키포인트 맵을 함께 받는 포즈 변경 예제를 제공한다. 원본/목표 포즈를 넣는 실험 후보이며 아직 로컬 검증하지 않았다. 카사 LoRA를 Qwen에 직접 연결하는 구성은 아니다.

우측을 보는 것, 목표 전투 자세를 따르는 것, 동일 캐릭터의 의상·얼굴을 보존하는 것은 각각 검수해야 한다. 현 단계는 1개 원화·1개 시드의 실험이며 얼굴 보정/Hires는 적용하지 않았다.


## 사이트 연결 완료 — 2026-10-18 사용자 후속 승인

사용자가 낮은 변형 결과를 승인하고 카사 활성화와 관절 편집을 요청했다. **현재 카사는 enabled**이며 아래 내용이 과거 보류 기록보다 우선한다. 해시 불일치를 검증 성공으로 바꾸지는 않았다.

- 라이브러리 `counter-side-sprites`는 반복 수신·실생성 검토한 파일 `requested/counter-side-sprites-reviewed-9f3a0f44.safetensors` 사용. `sha256`에는 실제 받은 파일 해시, `upstreamSha256`에는 공식 게시 해시를 따로 보존. `integrityStatus=upstream-mismatch-user-approved`. 결과 PNG·generation.json에도 둘의 이력을 저장한다. 자동 다운로더의 검증 규칙과 과거 목록은 그대로다.
- **원화 생성 → 카사 · 원화 변형 시작**: Flanime, reference, 카사0.6, 1024×1536,32steps/CFG5,denoise0.3 설정. 사용자가 이미지와 캐릭터 설명을 입력한다. 화풍 프리셋의 카사 항목도 Flanime으로 변경. 새 미리보기는 참고 이미지 변형임을 표시했다.
- Flanime reference는 `image_pose.prepare_reference`로 투명 여백 crop, 비율 유지, 회색 캔버스에 contain한다. 기존 Anima/Animagine reference와 마스크 수정 경로는 유지. Flanime inpaint는 미지원. Soya 기본값 유지.
- 우측 **관절 포즈** 탭: COCO18 점 드래그, 관절 선택 드롭다운, 선택 후 방향키(Shift로 큰 이동), 캔버스 Ctrl+Z, 되돌리기/초기화/좌우 반전, 정면/우측 전투 프리셋, 원화 반투명 겹치기, 포즈 강도. 적용 체크는 기본 OFF. 체크 시 얼굴 보정은 비활성화한다.
- `web/assets/image-pose.js`는 정규화 좌표18개와 strength만 전송. `image_pose.py`가 유한 숫자·0..1 좌표·0.1..1.5강도·호환 모델/모드를 검증하고 검은 배경 조건 PNG를 서버에서 그린다. 임의 사용자 노드 그래프나 파일 경로는 받지 않는다.
- 지원은 **Flanime text/reference**에 한정. 전용 `illustrious-openpose-v1.safetensors` 사용, strength 사용자 값/start0/end1. `image_engine.build_workflow(...,pose_image_name=...)`의 50/51/52 노드로 연결. 원본 애니메이션용 본/웨이트 편집과는 별개의 이미지 생성 자세 조건이다. 자동 포즈 검출·손가락 뼈대·캐릭터 참조 어댑터 미구현.
- 좌표는 `pose.version=illustrious-joints-v1`과 함께 큐/갤러리 설정/PNG/generation.json에 기록. 다시 만들기 설정 복원에서 포즈 좌표·강도 복원. 입력 원화는 기존 정책에 따라 다시 업로드해야 한다. 조건 PNG는 각 출력 폴더의 `pose.png`에 보관(외부 미디어 API에는 노출하지 않음).
- `test_image_pose.py`: 유효하지 않은 좌표/미지원 조합 거부, 이미지 비율/빈 alpha, sampler 양쪽 conditioning 연결, 포즈 없는 기존 경로 확인. `tools/test_image_studio.cjs`: 우측 관절 탭, 드래그/Undo/반전, 카사 시작 버튼, reference+pose 생성 payload와 반응형 확인.
- 실제 운영 `image_engine.run_job` smoke: `outputs/counter-site-integration-20261018/pose-smoke/`의 image-1.png/pose.png/generation.json.1024×1536,32steps,denoise0.8,카사0.6,포즈1.0 실행 및 PNG 메타데이터 확인. 팔/다리 자세는 변하지만 새 소품·의상 변형이 생길 수 있어 완전 보존으로 설명하면 안 된다. 실제 사용자 큐/갤러리는 수정하지 않았다.


## 카사 + 추가 그림체 LoRA 비교 — 2026-10-18

사용자가 동시 적용 또는 후처리 방식을 시험해 달라고 요청했다. `tools/verify_counter_style_mix.py`, `outputs/counter-style-mix-20261018/preview.html`. 운영의 단일 LoRA UI나 카탈로그를 바꾸지 않는 격리 실험이다.

- 기존 사용자 후드/코트 원화와 검토한 카사0.6/Flanime/1024×1536/32steps/CFG5/seed20261018/denoise0.3 고정.
- 카사 단독 대조, 카사+FSThicc Illustrious0.3, 카사+FSThicc0.5, 기존 카사0.3결과를 입력해 카사 없이 FSThicc0.3을 다시 적용하는2차 img2img를 비교한다.
- FSThicc LoRA 전체 SHA256 검증 후 로드. MODEL/CLIP 양쪽에 카사→추가 그림체 순으로 연결하고 thick black outline 트리거를 추가한다. 두 모델의 효과만 분리하는 통계 실험이 아니라 실제 적용 레시피 비교다.
- FSThicc는 선화뿐 아니라 신체 비율에도 영향을 줄 수 있어 검사 대상이다. 사용자 게임용 최종 화풍으로 추천/허용 완료를 의미하지 않는다. 라이브러리는 계속 disabled, 출처/이용 조건 기록은 기존 catalog 참조.
- 카사 파일은 기존 actualHash 및 사용자 승인 upstream mismatch 이력을 결과별 기록에 유지한다.
- 2차 결과의 시간은 2차 처리만이며 총시간에 최초 카사 생성 시간을 더해야 한다. 모든 입력/출력은 별도 폴더로 보존. 원본이나 갤러리는 덮어쓰지 않는다.


실제 결과: 카사 단독24.11초 / 동시FSThicc0.3 23.08초 / 0.5 23.11초 / 2차만23.20초。

동시0.3은 전체 외형을 유지하며 선·음영 변화가 미묘하다.0.5는 얼굴/장갑/벨트 변화가 더 크다.2차 변형은 선·채색 변화가 더 강하지만 장갑 근처 색색의 떠 있는 물체, 어깨 고정구/부츠 변경 등 오류가 누적된다. 이 입력에서는 동시0.3을 우선 시험값으로 보며 일반화하지 않는다.4건 history success/1024×1536 및 육안 검토 완료. comparison.webp와 visual-review.json 저장. 운영 다중LoRA UI는 아직 구현하지 않았다.


## 카사 + 블루 아카이브풍 시험 준비

사용자가 선화 변화가 아닌 눈/얼굴 비율과 채색이 바뀌는 게임 화풍의 동시 적용을 원한다고 정정했다. 앞선 FSThicc 결과를 목표 성공으로 취급하지 않는다.

- 공식 Civitai model2994388/version3395865 Kivotos Story Style (Illustrious). 약340.8MB. 원문 snapshot `data/research/blue-archive-illustrious.json`. 기존 설치 BlueArchiveStyleB1은 Anima용이므로 사용하지 않는다.
- 제작자 설명: 스토리 일러스트/PV의 soft cel shading, bright pastel, clean thin lineart. `bastory`를 프롬프트 앞에 사용. 혼합 강도0.6~0.8, 단독0.8~1.0, Euler a25~30steps/CFG4~5/CLIP skip2 안내. 주 시험 체크포인트는 WAI17로 로컬 Flanime과 동일하지 않다.
- 목록 `data/blue-archive-illustrious-import.json`, 상태 `data/blue-archive-illustrious-import-status.json`, 로그 `logs/blue-archive-illustrious-download.log` 및 `-error.log`. 모델은 사이트 등록하지 않고 로컬 비교용으로 받는다. 자유로운 상업 이용 허용으로 해석하지 말 것. 원문에 비상업 팬 프로젝트/모델 판매 금지 문구가 있다.
- 비교 도구 `tools/verify_counter_blue_archive.py`, 출력 예정 `outputs/counter-blue-archive-20261018/preview.html`. 원화 잠금 영향을 제거한 신규 text 생성에서 카사0.6+블아0/0.6/1.0, 같은 외형 설명·시드. 별도 원화 입력은 denoise0.65+블아0.8+카사0.6 동시 적용. 선화 테스트의2차 후처리 경로를 사용하지 않는다.
- 1024×1536/32steps/CFG4.5/CLIPskip2. 얼굴/의상/실루엣/채색 및 원본과의 차이를 확인할 것. 신규text군은 같은 캐릭터 정체성 보장이 아니라 화풍 혼합 능력 비교이다. 다운로드 완료 후 SHA256 확인을 통과해야 실행된다. Sprute 재개 금지.

블아풍 실제 비교6건 완료: text 카사0.6+블아0/0.6/1.0, reference denoise0.65/카사0.6+블아0.8, 추가 text카사0.3+블아1.0 및 블아단독1.0. 각23~24초.6개 history success/1024×1536 확인. face-comparison.webp/comparison.webp/visual-review.json 저장. 눈·얼굴·의상 비율은 바뀌지만 기대한 블아풍 채색/얼굴의 뚜렷한 전환은 부족하다. 블아 단독에서도 담백하고 평평한 채색이 남으므로 카사 혼합만의 문제라고 단정하지 않는다. 제작자 주시험 WAI17과 다른 Flanime의 조합, 프롬프트/LoRA 자체 효과 등을 후속 확인할 필요. 이번 결과를 성공한 블아풍 변환으로 과장하거나 카탈로그 활성화하지 않았다.


## 후속 체크포인트·다른 블아풍 다운로드 시작

사용자가 WAI 또는 다른 블아 LoRA 비교를 승인했다.2026-10-18.

- Blue Archive Cutscene Style (Illustrious) model1884029/version2132494/file2026379, 약228.5MB. 여러 블아 작가/공식컷신 삽화 기반 설명. 원문 `data/research/civitai-1884029-style-followup.json`, 다운로드목록 `data/blue-archive-cutscene-import.json`, 상태 `data/blue-archive-cutscene-import-status.json`, 로그 `logs/blue-archive-cutscene-download.log` 및 `-error.log`.
- WAI Illustrious v17 model827184/version2883731/file2763986, 약6.94GB. 공식 설명에 VAE 내장,15~30steps/CFG5~7/Euler a, 지나친 품질태그/장문 네거티브 지양 안내. 원문 `data/research/civitai-827184-style-followup.json`, 다운로드목록 `data/wai-illustrious-import.json`, 상태 `data/wai-illustrious-import-status.json`, 로그 `logs/wai-illustrious-download.log` 및 `-error.log`.
- 두 다운로드를 백그라운드 시작했고 완료까지 감시하지 않는다. Sprute는 재개하지 않았다. 사이트 기본값·활성 목록·서버 변경 없음.
- `tools/verify_counter_blue_archive.py`에 `--base flanime|wai17`, `--style kivotos|cutscene` 인자 추가. 각 조합 출력 별도 폴더. WAI는 SHA 검증 및 체크포인트 내장 VAE 사용. Cutscene 트리거 공식 API 목록을 참고한 official art/game cg/blue archive 사용, 임의 캐릭터 LoRA가 아님.
- 다운로드 후 먼저 `--style cutscene`으로 기존 Flanime과 비교, 이어 `--base wai17`로 기존 Kivotos를 비교할 수 있다. 기본 비교 스텝32/CFG4.5는 기존 조건 고정 목적이며 WAI 권장값과 동일하지 않으므로 필요 시 별도 recipe로 기록할 것. 현재 플래그 확장은 syntax만 확인했으며 WAI/Cutscene 실생성은 아직 하지 않았다.


### WAI/Cutscene 비교 실행 개시

두 파일 다운로드/해시 verified를 확인한 다음 사용자 요청으로 Flanime+Cutscene6조건과 WAI17+Kivotos6조건을 순차 실행. 기존 동일 외형prompt/seed20261018/1024×1536/32steps/CFG4.5/CLIPskip2. WAI는 내장VAE 사용. 이 고정값은 기반모델만의 차이 비교 목적이며 WAI권장15~30steps/CFG5~7 recipe로 최적화했다는 뜻이 아니다. Cutscene의 official art/game cg/blue archive 태그는 블아 헤일로 생성에도 영향을 줄 수 있으므로 화풍과 내용 변화를 구분한다. 결과폴더 counter-blue-flanime-cutscene-20261018 및 counter-blue-wai17-kivotos-20261018. 운영 설정 변경 없음.


WAI/Cutscene12건 실생성 완료. Flanime+Cutscene6건25.11/23.08/23.06/24.08/23.11/23.06초, WAI17+Kivotos6건23.08/23.05/23.08/24.09/23.08/22.31초. 각history success/PNG1024×1536 및 육안 확인. 통합 outputs/counter-blue-followup-20261018/preview.html, faces.webp, quick-comparison.webp, visual-review.json. 이번 비교에서는 Flanime+Cutscene이 눈매·얼굴 비율 변화가 더 뚜렷하나 헤일로/머리길이/벨트/코트 변형도 발생. WAI17+Kivotos는 붉고 검은 면이 더 강해지고 디테일이 줄어 개선으로 판단하지 않음. 단일 원화 외형설명/단일seed/고정recipe이며 LoRA+트리거가 동시에 바뀌므로 순수 가중치효과로 단정하지 않는다. 사이트 기본모델·카탈로그 활성 목록은 바꾸지 않았다.


## 블아 스타일 단독 확인 — 사용자 평가 정정 후

사용자가 이전 결과를 블아 그림체로 보지 않는다고 지적했다. 이전의 얼굴 변화만으로 블아풍 성공을 판단한 표현은 철회한다. `tools/verify_blue_archive_standalone.py`로 카사·full body·battle sprite·clean lineart·입력latent를 전부 빼고6건 비교했다.

- WAI17 내장VAE/832×1216/Euler a/28steps/CFG4.5/CLIPskip2/seed20261018. Kivotos 제작자 예시 Arona 프롬프트(+solo,upper body)와 자체 성인 검은코트 캐릭터 prompt 각각 LoRA없음/Kivotos1.0/Cutscene1.0. 공개 API image meta/seed는 null이라 제작자 샘플의 픽셀 동일 재현은 아니다.
- 파일 SHA 확인 및 두LoRA 샘플tensor 비영점 확인. 이번 구간만 저장한 comfy-stderr-segment.log에는 lora key not loaded/size mismatch/error 경고0건. 이는 로그 관측이며 전체tensor수학적효과를 증명하는 것은 아님.
- 각16.09/15.27/16.05/14.08/15.05/15.05초,6개history success/832×1216확인. 출력 `outputs/blue-archive-standalone-20261018/preview.html`, original-comparison.webp, visual-review.json.
- 자체 캐릭터는 LoRA가 없을 때 상대적으로 상세한 얼굴명암/코 표현, Kivotos에서 더 평평하고 부드러운 얼굴명암·그래픽한 눈·단순한코, Cutscene은 얼굴/머리표현변경 및 원치 않은halo 추가. Arona는 LoRA없는 기반모델에서도 알려진캐릭터로 나오므로 그것만으로 화풍효과를 판단하면 안 됨.
- 단독 스타일 효과는 확인됐으나 공식블아스타일 충분성은 사용자검토가 필요. 이전 카사/전신프롬프트/얼굴크기 혼합의 효과저하가 유력하나 각원인을 분리검증하지 않았으므로 카사하나만의 원인으로 단정하지 않는다. 운영기본값·카탈로그는 바꾸지 않음.


## 승인한 Cutscene1.0 기준 카사 강도 sweep

사용자가 단독 Cutscene1.0 결과를 블아 그림체로 확인했고 테스트 지속을 요청했다. `tools/verify_cutscene_counter_balance.py`, 출력 `outputs/cutscene-counter-balance-20261018/preview.html`.

- 승인한 자체캐릭터 Cutscene1.0/WAI17/832×1216/28steps/CFG4.5/CLIPskip2/seed20261018을 고정. 카사0/0.2/0.4 MODEL+CLIP. 순서는 기반모델→카사→Cutscene, 전부 동시적용. 상반신0은 승인원본 재사용, 나머지5건 신규 생성. 원본/기반모델/LoRA 해시 확인.
- 첫행은 상반신의기존prompt, 둘째행만 fullbody/측면/우측전투/흰배경/긴코트·바지·부츠·기계장갑으로변경. 카사효과는 동일행내에서비교. 행간은 얼굴크기/배경/의상설명 등여러변수가바뀌므로 단일요인시험이아님.
- 상반신0.2/0.4는 눈/얼굴/머리채색을 유지하면서 표정·실루엣·옷주름이바뀜. 전신0/0.2는원하지않은긴머리·halo가남음. 전신0.4는단발에더가까운머리와뚜렷한전신전투자세, 단순하고부드러운눈/얼굴표현유지가관찰되어후보로평가. 정확한측면/캐릭터외형보존은보장하지않음. halo/의상뱃지추가도남는다.
- 신규16.12/14.08/14.05/14.06/14.11초.5개history success/6개PNG832×1216확인, portrait-comparison.webp/sprite-comparison.webp/sprite-faces.webp/visual-review.json저장. 단일캐릭터설명·단일seed이며결과선택은사용자검토필요. 배경제거·얼굴보정·입력참조없음. 운영카탈로그/기본값/서버는바꾸지않음.


## 헤일로 억제 및 Cutscene 유지 얼굴보정

사용자 요청으로 `tools/verify_cutscene_cleanup.py` 실행. 출력 `outputs/cutscene-cleanup-20261018/preview.html`, face-comparison.webp/visual-review.json 및 원본·설정·history·검출mask 보관.

- 카사0.4+Cutscene1.0/WAI17/832×1216/28steps/CFG4.5/seed20261018 고정. 첫 후보는 원본prompt에 `halo, floating ring, ring above head` negative 추가, 두번째는 동일negative에 `blue archive` 시리즈태그 제거.2개에서 모두 halo가보이지않음.18.09/16.28초. 다만 전신재생성이므로 자세/머리/복장도변하며 국소지우개와다름. 타seed효과미검증.
- 두번째 결과를 face pass 입력으로사용.8191 Impact FaceDetailer, WAI내장VAE/Cutscene1.0을 MODEL+CLIP에유지하고카사만제외. native face helper로0.12/0.20, guide512/max1024/20steps/CFG4.5/feather6/dilation2.14.14/10.08초. 출력은832×1216으로확대하지않음.
- 두결과 검출mask 비어있지않음, 원본대비 RGB변화가mask24px여유영역내에한정됨을검사. 얼굴영역외픽셀과해상도보존.0.12는눈디테일을다듬으면서인상변화가작은후보,0.20은눈/얼굴음영변화가더커사용자검토필요.4개history success/PNG크기검증. 사이트기본값/카탈로그/서버변경없음.


## 블아풍 혼합 사이트 등록 — 사용자 승인

사용자가 얼굴0.12/0.20둘다괜찮다고확인하고사이트연결을승인했다. 기존Soya기본은유지한다.

- 원화화면 **블아풍 + 카사 · 검토한 조합** 버튼 및 그림체프리셋의 동일항목. 전용모델id `wai-cutscene-counter`, WAI17내장VAE/Cutscene1.0+카사0.4/832×1216/28steps/CFG4.5/CLIPskip2. 새로생성만지원. 사용자외형설명은유지. 시리즈태그를자동추가하지않고officialart/gamecg스타일태그만사용, halo/floatingring/ringabovehead네거티브자동추가.
- 카사강도0~0.6, Cutscene0.5~1.2독립조절. 입력은고정파일allowlist와유한숫자검증을사용. 얼굴보정체크시0.12기본/0.20선택. 다른일반LoRA/그림체lookId/pose/hires/sheet조합은이전용모델에서거부. 일반UI LoRA선택도전용모델에서는비활성화.
- `image_cutscene.py`에서전용recipe검증/graph구성. MODEL/CLIP은WAI→카사→Cutscene순. 얼굴패스는WAI→Cutscene만적용하여카사제외, 원본크기유지. 8191Impact백엔드사용, 얼굴미선택은8189사용. 선택강도/recipe버전/LoRA해시/카사upstream불일치승인이력을PNG·generation.json·큐·갤러리설정에보존.
- `image_engine.py`의신규모델은목록뒤에추가하여첫기본Soya선택을유지. faceDetail지원/native모델목록에신규id포함. 일반Flanime얼굴0.15정책은변경안함. 보정전보기/원본/투명배경은기존결과경로사용.
- 단위검사49개+브라우저검사통과:2단계LoRA경로/face전용Cutscene경로/0.12·0.20허용/불량입력거부/해상도·metadata/버튼·요청·설정복원검증. `test_image_cutscene.py`. 실제production runner smoke `outputs/cutscene-site-smoke-20261018/verified-recipe/`에서생성완료/832×1216/PNGmetadata/보정전파일확인. 운영갤러리는수정하지않음.
- 실험대비일반프롬프트/assetSpec에따라포즈·얼굴은달라질수있다. 새모델/LoRA화풍성능을일반화하지않는다. halo억제100%보장/원본캐릭터외형고정/정확한측면보장없음. preview는기존검토실험이미지임.

추가통합검토: 일반assetSpec의eye-level camera 문구가실물카메라소품으로생성되어, 전용혼합모델side구도는검토때의fullbody/sideview/facingright/battlereadystance문구로고정교체했다. 방향선택은반영하지만camera단어는추가하지않는다. 회귀검사로resolvedPrompt에camera가없는지검증. 수정후smoke는outputs/cutscene-site-smoke-20261018/reviewed-framing/에별도저장한다.


### 게임명 비노출 표시 정책

사용자 요청으로 사용자 화면의 게임명·약칭을 중립적 이름으로 교체했다. 혼합레시피는 셀 채색 전투, 카사계열은 현대 전투/전투 형식, 에픽계열은 판타지 전투, 블아계열은 밝은 셀 채색으로 표시한다. 모델/버튼/강도라벨/안내/오류/LoRA·그림체라이브러리 제목과설명 모두적용. 프리셋settings에도raw styleId대신display name표시. 내부id/모델파일명/트리거/출처링크·기술인계이력은정확성과호환성을위해유지하며이들을표시명으로되돌리지말것. 브라우저통합검사및Python15개통과.


## 실제 원화 레퍼런스 입력 · 검토 혼합 조합

사용자가 이미지 레퍼런스로도 생성 요청. `tools/verify_cutscene_reference.py`, 출력 `outputs/cutscene-reference-20261018/preview.html` 및comparison.webp/원본/준비본/설정/graph/history/visual-review.json.

- 실제입력은기존사용자원본 `outputs/rigging/5ed3fddd3383252008ecd0c8e7dce9df/source-original.png`. 원본sha보존확인. 텍스트설명만의신규생성이아니다. 투명여백crop/비율유지회색832×1216캔버스→LoadImage→WAI내장VAEEncode→img2img.
- 검토한WAI17/Cutscene1.0+전투형식0.4/28steps/CFG4.5/CLIPskip2/seed20261018, 시리즈태그제외+halo네거티브유지. 원본의후드·기계장갑외형설명포함, 별도전투자세변경지시없음.
- denoise0.3/0.5/0.7각15.11/13.08/13.08초.3개history success/832×1216/VAEEncode실입력확인.
- 0.3은후드·코트·전체자세·벌린손가락/기계장갑세부대체로보존, 화풍변화작음.0.5는선/채색변화커지지만기계장갑단순화·벨트/부츠변화.0.7은눈/얼굴단순화와함께손이주먹으로바뀌고의상장식변경, 충실변환에는손실큼.0.3보존우선/0.5절충후보. 원화보존과화풍완전변환동시보장은안됨.
- 얼굴보정/누끼/포즈/참조어댑터미사용. 현재사이트혼합모델은여전히text전용, 이번reference는격리실험이며사이트연결변경없음. UI/답변에게임명직접노출금지정책유지.


### 레퍼런스 원화 우측 유도

사용자가원화변환도우측전투스프라이트방향으로유도요청. tools/verify_cutscene_reference_right.py, outputs/cutscene-reference-right-20261018/. 원화실입력+동일혼합조합으로positive(sideview1.2/facingright1.35/lookingtotheright/bodyturnedright/battleready),negative정면/좌측/lookingatviewer추가. denoise0.5/0.65각17.39/13.34초. 둘다원래정면자세를거의유지하여우측회전성공으로보지않는다. 추가로전용IllustriousOpenPose1.2+변형0.85한건시험. 원본보존과방향변경은별도검수.

추가 목표 포즈 조건 결과: OpenPose1.2+변형0.85에서우측측면은확인(26.09초). 후드·코트는대체로남지만기계장갑손실과손이코트를잡는의도치않은자세, 의상/뱃지변화. 정확한전투포즈나원본디자인보존성공은아님.3개history success/832×1216확인. 비교화면에실패한promptonly와성공한방향/실패한세부를함께표시. 운영변경없음.


### 우측 전투 자세 · 손/의상 후속 조정 (2026-10-18)

`tools/verify_reference_battle_adjust.py`, `tools/verify_reference_outfit_adjust.py`; `outputs/reference-battle-adjust-20261018/`에 PNG/graph/history/비교화면/visual-review.json 보존. 손목·팔꿈치를 코트에서 분리하고 기계장갑 강조, 옷잡기 억제. 변형0.7/0.8, OpenPose1.2/1.45 세 건: 0.8은 우측 가드 자세지만 후드가 내려가고 반바지/샌들 등 원본 의상이 변경됨. 후드 착용·긴 바지·부츠 추가 강조 0.75/0.8 두 건: 0.75는 정면 회귀 및 과장된 장갑, 0.8은 우측 방향과 후드/바지는 회복하나 뒤쪽 여분 손·분리된 하단 소품 발생. 최종 에셋으로 승인할 후보 없음. 다섯 history success/832×1216 검증. 얼굴보정/누끼 미사용, 운영 사이트 변경 없음. 프롬프트/포즈만의 원화 디자인 보존 한계가 확인되어 참조 외형 조건 분리 또는 국소 마스크 보정 검토 필요(미구현·미검증). 비교 `outfit-preview.html`, `outfit-comparison.webp`.


### 운영 스튜디오 연결 · 원화 후보 선택/부분 수정 (2026-10-18)

사용자는 일회 생성의 디자인 오차를 허용하고 여러 후보를 선택·보정하는 흐름을 채택했다. `wai-cutscene-counter`는 이제 text/reference/inpaint를 지원한다. 기존 기본 Soya 선택은 유지. 혼합 조합을 고른 뒤 **원화 → 우측 전투 자세 · 후보 3장** 버튼: 원화 입력/832×1216/변형0.8/포즈1.2/후보3장/얼굴·확대 보정 끔. 관절은 후속 실험의 손목을 코트에서 분리한 포즈이며 사용자가 드래그 수정 가능. 후드 등 특정 캐릭터 전용 묘사는 자동 주입하지 않으므로 직접 설명한다. 1~4장 count는 기존 연속 시드 실행/갤러리 저장 사용.

reference는 비율 유지 준비본→WAI 내장 VAEEncode, 설치된 전용 Illustrious OpenPose를 사용. 결과 **부분 수정**은 혼합 모델과 강도를 유지하고 pose를 해제, 변형0.3으로 마스킹 화면 전환. inpaint는 캔버스 비율 보정/crop 없이 원래 화면 좌표를 쓰며 VAEEncodeForInpaint 후 서버에서 마스크 바깥을 원본과 합성한다. 자동 외형 고정/손가락 복구 보장은 없음. 얼굴 자동 보정은 여전히 text 모드만 지원하며 reference/pose/부분 수정 조합에는 사용하지 않는다.

검증: Python 25개 및 tools/test_image_studio.cjs의 원화 버튼→업로드→3후보/포즈 payload→부분 수정 전환 통과. `tools/verify_cutscene_reference_site.py`는 갤러리 레코드를 만들지 않고 production run_job으로 reference 및 마스크 보정을 검증하며 결과는 outputs/reference-site-smoke-20261018/. 실제 GPU 검증 결과는 verification.json 참조.

실제 GPU 검증 완료: production run_job으로 원화+포즈 생성 및 같은 혼합 모델의 마스크 수정 성공. 보정 전후의 마스크 바깥 RGB 픽셀 동일, 마스크 안 변화 확인. 팀/Comfy 대기열 idle 확인 후 HTTPS 설정으로 웹 서버 재시작. 인증 경로 401 정상, 공개 정적 JS 200 및 새 버튼 코드 제공 확인.
