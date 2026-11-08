> 2026-10-19: 원화 업로드→설명 초안 검토→그림체 선택→생성→동작·Live2D 연결을 점검했습니다. 업로드 위치·방향 전달·이미지 로딩 완료 처리·분석 초안의 자세 충돌을 수정했습니다. [검증 및 유지보수 기록](IMAGE_STUDIO_UX_REVIEW.md)을 참고하세요.

> 2026-10-18: 기본 생성 seed 상한 버그와 추가 그림체 선택 흐름을 수정했습니다. 설명→그림체→출력의 현재 UI 및 검증은 [사용성 재검토](IMAGE_STUDIO_UX_REVIEW.md)를 먼저 참고하세요.

# 캐릭터 원화 생성 · 운영 및 인계

2026-10-19: **픽셀 아트** 작업을 추가했습니다. SDXL Base + Pixel Art XL 고정 조합, 64·96·128px 출력·색 수 제한·참고 이미지 변형을 제공합니다. 설치와 실제 품질 검증 상태는 [로컬 픽셀 아트 인계](PIXEL_ART.md)를 참고하세요. 기존 4방향 시트 기능과 구분합니다.

## 생성 후 얼굴만 보정 · 2026-10-19

- 이미지 스튜디오의 후보 아래 또는 팀 갤러리의 원화 상세에서 **얼굴만 보정**을 누릅니다. **약하게 0.12 / 더 선명하게 0.20**을 선택하고 시작합니다. 원화 변환·관절 포즈로 만든 결과에도 사용할 수 있습니다.
- 원본은 유지하고 팀 대기열에서 별도 원화 작업으로 처리합니다. 보정본은 갤러리에 새 결과로 저장하며 **얼굴 전후 비교**에서 얼굴 주변을 확대해 비교할 수 있습니다. 비교창의 PNG 저장·전체 이미지 보기로 내보냅니다.
- 최종 이미지의 해상도와 알파 채널은 원본과 같고, 검출 얼굴의 경계 처리 영역 밖 픽셀은 원본을 사용합니다. 얼굴 검출에 실패하면 원본을 그대로 저장하고 실패 안내를 표시합니다. 이때는 부분 수정에서 얼굴을 직접 지정하세요.
- 검토된 일러스트 모델의 결과는 같은 기본 모델을 사용합니다. 그 외 결과는 Flanime 얼굴 보정으로 처리하므로 인상·화풍이 조금 달라질 수 있다는 안내를 표시합니다. 전투 형식 LoRA는 얼굴 패스에서 제외하며 셀 채색 조합은 해당 얼굴 화풍 LoRA를 유지합니다. 4방향 시트는 자동 얼굴 보정 대상에서 제외합니다.
- API: 인증된 `POST /api/images/<sourceJob>/face-refine`, `{image: 0..3, strength: 0.12|0.20}`. 완료된 이미지 작업의 실제 후보 파일만 허용합니다. 파일 경로·임의 워크플로·클라이언트가 보낸 이미지 데이터는 받지 않습니다. 기존 개인 3개/전체 20개 대기 한도를 적용합니다.
- 원본 후보를 새 작업의 `image-1-before-face.png`로 복사한 뒤 등록합니다. 이후 원본 작업이 삭제돼도 보정 입력은 유지됩니다. 새 payload는 `jobType=image`, `operation=face-refine`, `parentJob`, `sourceImage`, `sourceModel`을 포함합니다. 일반 이미지 FIFO가 `image_engine.run_job`에서 `image_face_refine.run_job`으로 전달하고 8191을 사용합니다.
- 구현: `image_face_refine.py`, `team_server.py`의 refine_saved_face, `web/assets/image-face-refine.js` / `.css`. 이미지 스튜디오와 갤러리 상세에서 같은 UI를 사용합니다.
- 검증: `test_image_face_refine.py`(원본 스냅샷·권한·한도·본문 픽셀/알파 보존·미검출), `tools/test_image_face_refine.cjs`(HTTP/UI), `--real-image`(실제 GPU). 실제 검증 기록은 `outputs/image-journey-27tndgck/face-refine-test.json`, 화면은 `outputs/face-refine-real-comparison.png`입니다. 832×1216 원본에서 얼굴 검출 [382,191,491,296], 실제 변경 [376,185,497,302], 알파 동일을 확인했습니다. 단일 사례의 시각 품질을 모든 캐릭터에 보장하지 않습니다.

작성: 2026-10-15. 운영 저장소는 `G:\Minimax`.

## 2026-10-18 사용자 작업 중심 UI 재설계

현재 진입 경로: 팀 사이트 **이미지 스튜디오** (`#/create/image`). 초기 화면에서 생성 모델을 고르게 하지 않는다. 상단에서 **새 이미지 만들기 / 원화를 스프라이트로 / 그림 일부 고치기 / 4방향 시트 만들기**를 선택하면 검토한 설정을 준비한다.

- 새 이미지: 기본 Soya. 이미지 용도/설명/그림체/후보 수/배경을 중심으로 구성. 한국어 예시 버튼은 영어 외형 설명을 입력한다. 한국어 프롬프트 자동 번역 기능은 아님.
- 원화 변환: WAI+Cutscene+Counter 혼합, 832×1216, 변형0.8, 전용 포즈1.2, 후보3장. 방향 선택 및 관절 편집 지원. 업로드 이미지와 결과는 작업 영역에 있고 라이브러리 아래로 밀리지 않음.
- 부분 수정: 혼합 모델 등 지원 경로, 마스크 없는 제출 방지. 결과에서 진입 시 후보1장/변형0.3/포즈 해제. 작업 제목과 선택 탭도 실제 처리 방식과 동기화. 기존 서버의 마스크 밖 원본 합성 유지.
- 시트: 도트풍/SD풍 선택으로 기존 Anima/Flanime 전용 조합 연결. 3×4 초안이며 프레임 정렬 검수 필요.
- **그림체 선택/그림체 둘러보기**는 우측 패널. 추천 그림체 / 추가 그림체 / 설명 도우미 / 자세 조정. 검색·9개 단위 페이지 유지. 현재 입력 방식과 호환되지 않는 추천 조합은 숨기고 추가 그림체의 사용 불가 이유는 표시. 선택하면 패널이 닫히며 원화 변환/부분 수정의 이미지·방향·변형 강도 유지.
- LoRA/모델/CFG/steps/시드/개별 강도는 **고급 설정** 또는 카드의 세부 정보로 이동. 특정 작가 화풍의 이용 안내는 그대로 유지. 일반 화면에 게임명 직접 노출 금지.
- 후보 이미지를 클릭/Enter하면 확대 대화상자. 결과에서 PNG 저장 / 부분 수정 / 동작 만들기 / Live2D 만들기. 결과·재현 번호·기존 갤러리 저장 체계 유지.
- 공통 `ui.css`/`ui.js` 토큰과 테마를 사용한다. `team.html`은 새 이미지 iframe에는 `embed-legacy.css`를 덧씌우지 않는다. 해당 iframe만 화면 높이로 유지해 내부 도구 스크롤과 우측 패널 위치를 안정화. 다른 생성 도구의 iframe 동작은 유지.
- 구현: `web/image-studio.html`, `web/assets/image-workspace.js`, `image-workspace.css`, `image-library.js`. 기존 `asset-start.js`는 동작 도구에 유지하며 이미지 도구는 새 UI의 `window.assetStart`가 payload/restore/plan/receiveGeneratedImage 연계를 제공한다.
- 검증: `tools/test_image_studio.cjs`에서 작업 전환/기본 전문용어 비노출/검색·페이지/포즈 이동·되돌리기/방향 유지/마스킹 제출/확대/재생성/모바일 검사. GPU 생성 로직은 이번 UI 변경에서 수정하지 않음.

이하 문서에는 이전 UI 이름과 모델별 운영 이력이 포함되어 있다. 사용자 진입 안내는 위 흐름을 우선한다.


## 2026-10-17 기본값 변경: Soya Anima → Flanime

사용자 지시로 `soya-anima-flanime`을 첫 모델 및 API 모델 생략 시 기본값으로 설정했다.
`image_soya.py`가 고정 원본 JSON을 읽고 모델 경로·프롬프트·시드·설정을 연결한다.
실행 서버 8191은 `.venv-workflows` overlay와 별도 user/DB를 사용하며 `team_server.py`가
시작할 때 자동 기동한다. 기존 8189/8190은 계속 사용한다.

- 기본 base 768×768 / 16 steps / CFG 2, 최종 1536×1536. base 최대 786,432 pixels.
- 768×1024를 선택하면 1536×2048 출력. 해상도 선택은 첫 생성 단계 기준이다.
- 원본의 1024 latent를 0.75배 줄이는 연산은 이미 줄인 base 크기로 입력하고 scale=1로 연결했다.
- 고정 RDBT 1.0, Kieed 0.3, DMD2 1.0, Detailed anime 후보 0.3 및 Flanime 5steps/CFG1.7/denoise0.2 유지.
- 사용자가 Anima LoRA를 선택하면 base Kieed 자리를 대체한다. 고정 Flanime 후보 LoRA는 유지한다.
  이 변형 조합 전체를 검증한 것은 아니다. PNG/생성 JSON의 baseLora에 실제 선택을 기록한다.
- 새 생성만 지원. 참고 이미지/부분 수정 선택 시 UI가 Anima Turbo로 전환하며 서버도 지원하지 않는 조합을 거부한다.
- 기본 조합의 작가 안내 버튼, 수동 모델 선택 시 작가 안내 모달을 제공한다.
  페이지 초기 진입 시에는 모달을 자동으로 열지 않는다. iframe에서도 닫기 버튼이 보이도록 위쪽에 배치했다.
- 원본과 동일성 미확인 Detailed anime 후보 사용, 자동 태깅으로 소품·의상이 바뀔 수 있음을 모델 설명에 표시한다.
- `backend_url()`로 생성/이력/출력/취소/메모리 해제를 해당 서버로 라우팅한다.
- 이미지 대기열은 8189, 8190, 8191의 실행/대기 작업을 확인한다. Soya 실행 전 idle 8189의 모델 캐시를 해제한다.
- PNG 및 generation.json에 workflowVersion, outputWidth/Height, baseLora, refinerLora를 기록한다.

검증: `test_image_engine` 7건, 브라우저 생성/라이브러리/부분수정 전환/반응형 검사 통과.
실제 인증된 테스트 계정과 격리 DB의 FIFO 대기열에서 모델 생략 요청으로 생성했다.
30.06초, 1536×1536 RGBA PNG(실제 투명 픽셀), 배경 있는 원본, PNG 메타데이터,
팀 갤러리 기록을 확인했다. `tools/verify_soya_default.py`, `outputs/soya-default-smoke-20261017/`.
기존 Soya 3종 비교는 `workflows/soya/README.md` 참고.

Soya용 그림체 프리셋 36종을 추가했다. 기존 일반 추천과 합쳐 69종이며 오른쪽 그림체 탭의
초기 필터는 Soya 전체다. 셀·게임 계열은 첫 캐릭터 생성 결과에 Flanime 스타일을 적용하고,
선화·질감 계열은 첫 생성에도 공통 스타일을 유도한다. 흑백/청색/세피아 마감은 마지막 GLSL 노드로 처리한다.
`lookWorkflow`, `workflowBasePrompt`, `workflowBaseNegativePrompt`, `lookFinalTone`을 생성 설정에 기록한다.
자세한 구성과 실제 예시 생성 절차는 `IMAGE_LOOKS.md`의 최신 절 참고.

## 진입과 사용

LoRA 라이브러리/그림체 프리셋/프롬프트 템플릿을 별도 탭으로 나눴다. 검증한 프리셋 36종 중 사용자 선호에 맞춰 30종을 추천에 표시하고, 서양 카툰·반실사 계열 6종은 보관한다. [IMAGE_LOOKS.md](IMAGE_LOOKS.md)에 구성·검증·한계·추가 방법을 기록했다.

투명 배경 후처리와 원본 보존 기능을 추가했다. 실제 6장 검증 후 새 작업의 기본값으로 활성화했다. 한계와 재검증 절차는 [IMAGE_BACKGROUND.md](IMAGE_BACKGROUND.md)를 참고한다.

그림체 LoRA 3종과 각 4장의 제작자 예시 갤러리를 추가했다. 설치·Turbo 호환 검증 중인 항목은 선택을 막는다. 구현과 다음 작업은 [IMAGE_STYLES.md](IMAGE_STYLES.md)를 참고한다.

### 2026-10-15 템플릿 추가

원화 생성 화면 오른쪽 **그림체·구도 템플릿**: 그림체/구도/자세/의상/배경·조명 각 10개, 총 50개와 추천 조합 10개. `web/assets/image-templates.json`이 카탈로그이며 `image-templates.js`가 UI를 구성한다. Anima는 문장형, Animagine은 태그형으로 미리보기를 생성한다. ‘설명에 추가’를 눌러야 기존 프롬프트에 반영되고, 미리보기와 적용한 설명 모두 직접 편집 가능하다. 직접 조합은 용도를 일반 일러스트로 바꿔 서버의 정면/전신 지시와 충돌하지 않도록 한다. 추천 조합은 표시된 용도·해상도도 함께 적용한다. 되돌리기는 적용 이후 수동 편집이 없을 때만 실행한다. 적용된 텍스트는 기존 생성 기록과 PNG 메타데이터에 그대로 저장된다.

포즈 제어 모델 조사와 후속 구현 순서는 [IMAGE_POSE_COMPATIBILITY.md](IMAGE_POSE_COMPATIBILITY.md) 참고. 현재 템플릿의 자세는 프롬프트 유도이며 골격 제어가 아니다.

로그인 → 만들기 → **캐릭터 원화** (`/#/create/image`). 최신 공통 프론트의 메뉴·홈 카드·모바일 만들기 메뉴·팀 갤러리에 통합했다.

1. 모델, 용도, 캐릭터 설명, 해상도를 선택한다. 영어 태그/영문 문장이 권장된다.
2. 일반 일러스트 / 전신 스프라이트 / Live2D 정면 프리셋이 구도 프롬프트를 덧붙인다.
3. 1–4장을 팀 FIFO 대기열에서 한 장씩 생성한다. 시드는 첫 값부터 1씩 증가한다.
4. 결과의 PNG 저장 / 부분 수정 / 스프라이트로 / Live2D로 버튼을 사용한다.
5. 팀 갤러리의 **원화** 필터와 결과 상세에서도 다운로드·후속 도구 전달·설정 재사용이 가능하다.

참고 이미지는 img2img이며 정체성 고정용 IP-Adapter가 아니다. 부분 수정은 **B** 칠하기 / **E** 지우기 / **Ctrl+Z** 되돌리기, 반투명 붉은 마스크를 지원한다. 최종 합성에서 마스크 바깥 원본 픽셀을 유지한다. 입력을 선택한 출력 해상도로 리사이즈하므로 비율이 다르면 형태가 늘어날 수 있다. 투명 배경·레이어 분리·동일 캐릭터 보존을 보장하지 않는다. 원화에서 리깅으로 전달한 후 눈·입 마스크는 사용자가 지정한다.

## 모델

공식 Hugging Face 배포를 사용한다. 약 12.57 GB (decimal), safetensors만 다운로드한다.

| 선택 | 용도 | 기본 설정 | 라이선스 |
|---|---|---|---|
| Anima Turbo 1.1 | 빠른 시안 | 10 steps, CFG 1, Euler/simple | CircleStone Labs Non-Commercial v1.2 + NVIDIA 기반 조건 |
| Animagine XL 4.0 optimized | SDXL 애니 원화 비교 | 28 steps, CFG 5, Euler ancestral/normal | CreativeML Open RAIL++-M |

- Anima: https://huggingface.co/circlestone-labs/Anima
- Anima 라이선스: https://huggingface.co/circlestone-labs/Anima/blob/main/LICENSE.md
- Animagine: https://huggingface.co/cagliostrolab/animagine-xl-4.0

Anima 모델 카드상 이미지 결과물의 판매·게임 에셋 이용은 허용된다. 모델을 유료 생성 API/플랫폼으로 제공하거나 수익화된 제품 기능으로 서비스하는 것은 별도 라이선스 대상이다. 현재 동아리의 비상업 공유 도구를 전제로 선택했다. Anima가 시장 전체를 대체했다거나 인기 순위 상위라는 의미는 아니다.

설치: `.venv\Scripts\python.exe tools\download_image_models.py`. 저장소 revision, 파일 크기, SHA256을 고정했다. 부분 다운로드는 이어받고 해시 검증 성공 후에만 `.safetensors`로 공개한다. 출력 로그에는 진행 바이트 수가 표시된다. 변경된 라이선스 원문은 재설치 시 확인한다. 확인한 원문과 모델 카드 사본은 `DOCS/model-licenses/`에 보관한다.

## 코드와 API

- `image_engine.py`: 파라미터 검증, 모델 allowlist, Comfy 그래프, 마스크 합성, PNG 메타데이터 저장.
- `team_server.py`: 인증·CSRF·공통 FIFO·갤러리·삭제 연동.
- `web/image-studio.html`, `web/assets/image-studio.js`: 생성/마스킹 UI.
- `web/team.html`, `web/assets/results.js`: 메뉴·결과와 후속 작업 전달.
- 기존 `web/index.html`, `web/rigging.html`은 `receiveGeneratedImage(File)`만 노출하고 기존 로더를 재사용.
- `GET /api/images/models`, `POST /api/images/generate`, `GET /api/images/<jid>/<filename>`.
- `jobType: image`, 결과 `images: [{url, seed}]`, 대표 `image`, `metadata`.
- 저장: `outputs/images/<jid>/image-N.png`, `generation.json`. PNG 안에도 실제 시드·모델·프롬프트·설정을 저장한다.

계정 승인과 기존 개인 3개/전체 20개 대기 한도를 적용한다. 원화는 팀 전용이며 비로그인 갤러리에 공개하지 않는다. 결과를 내리면 원화 파일 API도 404. 서버에서 경로와 파일명을 생성하며 임의 체크포인트/워크플로/외부 URL을 요청받지 않는다. 원본/마스크 base64는 완료·취소 후 DB payload에서 제거한다.

## GPU와 제한

영상 ComfyUI `127.0.0.1:8189`를 재사용한다. 모델 파일은 `ComfyUI/models/{checkpoints,diffusion_models,text_encoders,vae}`에 있다. FIFO worker가 이미지·영상·리깅·음악을 직렬 실행한다. 이미지 시작 전 8189/8190의 외부 Comfy 작업도 확인한다. 이미지 종료 시 8189 모델 캐시를 해제한다. 관리자가 ComfyUI에 직접 GPU 작업을 넣는 동시 사용은 피한다.

512–1536 축, 64 단위, 최대 1.5MP, 1–50 steps. 세로 832×1216이 기본. 30분 타임아웃이며 이미 Comfy에 제출한 실행 중 작업을 웹에서 취소하는 기능은 아직 없다. 기존 대기 취소는 가능하다. 생성 실패 시 같은 시드와 설정으로 다시 요청한다.

## 검증

```
.venv\Scripts\python.exe -m unittest test_image_engine test_team_server
node tools/test_image_studio.cjs
```

브라우저 테스트는 Playwright가 있는 NODE_PATH를 사용한다. 모의 API로 생성·부분 수정·갤러리·두 제작 도구 전달과 1440/390px 너비를 검증한다. Python은 입력 검증·권한·큐 한도·삭제·마스크 외부 보존·PNG 메타데이터를 검증한다. 실제 모델 검증 기록은 아래에 추가한다.

### 실제 GPU 확인 (2026-10-15)

RTX 5060 Ti 16GB, Anima Turbo 1.1, 832×1216, 10 steps: 첫 text-to-image 약 11.4초, 후속 약 8.1초. 참고 이미지 변형과 부분 수정도 실행 성공. 부분 수정 약 9.3초, 마스크 외부 픽셀 동일성 확인. 속도는 이 설정의 단건 측정이며 부하·스텝·모델에 따라 달라진다. 샘플은 `outputs/image-smoke-20261015`에 저장했으며 사용자 갤러리를 수정하지 않았다.
## 얼굴 보정 옵션 (2026-10-17)

Illustrious XL / Animagine 새로 생성에서 **얼굴 보정 · 실험적**을 선택할 수 있다. 결과 캔버스를 가로·세로 2배로 확대하고 FaceDetailer로 검출한 얼굴만 재생성한다. 보정 전 단순 확대본도 저장하며 결과의 **보정 전 보기**에서 비교한다. 캐릭터 인상이 달라질 수 있어 기본값은 꺼져 있다. Anima/Soya 및 참고 이미지/부분 수정은 현재 제외한다. 설정 복원·팀 FIFO·PNG 메타데이터·갤러리 저장은 기존 경로를 사용한다. 구현과 인계는 [IMAGE_STYLES.md](IMAGE_STYLES.md)의 RPG 얼굴 보정 절 참고.

## 고해상도 2차 생성 (2026-10-17)

Illustrious / Animagine 새로 생성에서 **고해상도 2차 생성**을 켜면 AnimeSharp 2배 확대 후 전체를 낮은 변형 강도(0.2)로 다시 그린다. 얼굴 보정과 함께 선택해도 최종 크기는 가로·세로 2배다. **전체 보정 전 보기**는 재생성 전 확대본, **보정 전 보기**는 얼굴 보정 직전 결과다. 이미지 전체를 다시 생성하므로 장비·복장·배경이 달라질 수 있으며 시간도 늘어난다. 기본값은 꺼짐. 구현·비교·인계는 [IMAGE_STYLES.md](IMAGE_STYLES.md)의 Hires fix 절 참고.

## 원본 고해상도 RPG 생성 (2026-10-17)

현재 RPG 원화는 **Flanime · RPG 원본 고해상도 → Epic Seven LoRA → 1024×1536 / 40 steps** 조합으로 시험한다. 확대·전신 재생성·얼굴 보정은 기본 꺼짐이며, Hires 결과가 더 나쁘다는 사용자 평가에 따라 원본 해상도를 높이는 방향으로 전환했다. 기존 Illustrious XL 1.0과 새 Flanime 프로필을 구분한다. API도 모델별 기본 크기를 사용한다. 비교와 실패 원인 조사 기록은 [IMAGE_STYLES.md](IMAGE_STYLES.md)의 원본 고해상도 절 참고.

## Flanime 얼굴 보정 (2026-10-17)

**Flanime · RPG 원본 고해상도**에서도 선택형 얼굴 보정을 지원한다. 다른 프로필의 2배 확대와 달리 **1024×1536 원본 크기를 유지**하며 얼굴만 강도 0.15로 보정한다. 얼굴 패스에서는 스프라이트 LoRA를 제외한다. 결과의 **보정 전 보기**로 원본과 비교할 수 있고, 기본값은 꺼져 있다. Hires는 이 프로필에서 사용하지 않는다. 설정·검증·인계는 [IMAGE_STYLES.md](IMAGE_STYLES.md)의 원본 해상도 얼굴 보정 절 참고.


## 카사 원화 변형 및 관절 포즈 (2026-10-18)

**카사 · 원화 변형 시작** 버튼으로 검토한 Flanime+카사0.6/reference/변형0.3/1024×1536/32steps 설정을 불러온다. 이미지를 올리고 캐릭터 설명을 입력한다. 우측 **관절 포즈** 탭에서 관절 드래그·선택·방향키·되돌리기·반전을 지원하며, 적용 체크를 켜야 생성에 전달된다. Flanime text/reference만 지원하고 얼굴 보정과 동시 적용은 불가. 낮은 변형은 외형 보존에 유리하고 큰 자세 변경에는 더 높은 변형이 필요해 의상 손실이 늘 수 있다. 파일 이력과 상세 인계는 [SPRITE_STUDIO_CONVERSION.md](SPRITE_STUDIO_CONVERSION.md) 참고.

## 에셋 유형 진입 (2026-10-18)

원화/모션 스튜디오 첫 진입에서 에셋 유형·원화 준비 방법·방향 수·기준 방향을 고른다. 4/8방향은 제작 계획이며 현재는 한 방향 출력. 모델/구도 추천·메타데이터·복원·도구 전달과 LoRA 조사 상세는 [ASSET_TYPES_AND_DIRECTIONS.md](ASSET_TYPES_AND_DIRECTIONS.md) 참고.

## RPG 4방향 시트 등록

원화 화면에서 **RPG 4방향 · 도트풍 / SD풍**을 선택하면 검토된 Anima Base 또는 Flanime 조합을 적용한다. 전용3×4시트 모드, 칸별 배경 제거와 원본 보관, 실제 예시를 제공한다. 8방향·정렬 보장은 아니다. 상세는 [ASSET_TYPES_AND_DIRECTIONS.md](ASSET_TYPES_AND_DIRECTIONS.md)의 사이트 등록 절 참고.

## 검토한 블아풍 혼합 프리셋

원화의 **블아풍 + 카사 · 검토한 조합** 버튼에서 WAI17+Cutscene1.0+카사0.4를적용한다. 헤일로억제자동, 얼굴보정0.12/0.20선택(체크시적용), 원본해상도/보정전이미지보관. 신규생성전용. 상세인계는 [SPRITE_STUDIO_CONVERSION.md](SPRITE_STUDIO_CONVERSION.md)의사이트등록절참고.


2026-10-18 UI 재설계 검증 완료: 이미지 흐름 브라우저 검사(참고 이미지 입력/방향·포즈/추천 조합 재선택 시 입력 유지/마스크 유효성/부분 수정 탭·후보1장/4방향 SD·도트/설정 재생성/확대/모바일 320·390·768·1024/독립 페이지 다크테마) 통과. 기존 사이트 1440·1024·768·390·320px의 주요 10경로 회귀 검사 통과. 관련 Python 25개 통과. 현재 웹 서버의 새 JS/CSS 제공 200 및 파일 일치 확인, 정적 파일 변경으로 서버 재시작 불필요. 스크린샷 outputs/image-workspace-*.png.


2026-10-18 접근성 후속: 사용자는 기본 그림체·세팅과 추가 그림체(LoRA)를 고급 설정에 숨기는 대신 기본 화면에서 직접 선택하도록 요청했다. `generationSetup`/`styleSettingControls`에 기존 모델·추가 그림체·반영 정도 컨트롤을 노출. 표시명은 기본 일러스트/셀 채색 전투/빠른 시안 등 용도 중심이며 실제 IDs는 보존. 크기·CFG·steps·시드는 고급 설정 유지. 원화 변환 중 처리 방식을 지원하지 않는 세팅 선택은 비활성. referencePromptGuide는 남길 외형+원하는 변화와 영어 예시를 제공한다. 현재 자동 이미지 캡션/Qwen-VL 분석은 미구현이며 원본이미지→VAEEncode와 사용자 설명을 함께 사용함.


### 로컬 reference caption · 2026-10-18

사용자 요청으로 외부 Gemini 연결 대신 Qwen/Qwen3-VL-2B-Instruct를 별도로 설치한다.
- 공식 HF revision `89644892e4d85e24eaac8bacfd4f463576704203`, Apache-2.0, 단일 safetensors 4,255,140,312 bytes. 도구 `tools/download_reference_caption.py`, 설치 위치 `models/reference-caption/qwen3-vl-2b-instruct` (Git 제외).
- 다운로드는 백그라운드로만 시작하고 이 세션에서 완료 감시하지 않는다. 완료 시 installation.json 원자적 기록. 프로세스/로그: outputs/reference-caption-download.stdout.log, .stderr.log.
- `image_caption.py`/`tools/run_reference_caption.py`: 로컬 파일만 사용, offline 환경, CPU 별도 프로세스, 종료 시 모델 메모리 반환, 240초 제한, 동시분석1개. 웹 서버 안에 모델 상주시키거나 Comfy GPU/음악 모듈을 변경하지 않는다. 외부 AI 서비스로 이미지 전송 없음.
- 2026-10-19 상세 분석: 짧은 요약 지시 대신 머리·얼굴·머리 장식·상의 각 겹·팔/장갑·허리·하의/신발·장비를 순서대로 조사합니다. 묘사 항목을 촘촘하게 지정하되 고정 단어 수를 강제하지 않습니다. 실제 검증에서 분량 강제 시 같은 태그 반복이 생겨 반복 페널티·6-gram 반복 방지·동일 태그 중복 제거를 적용했습니다. 보이지 않는 부분을 추측해서 분량을 채우지 않습니다. 프롬프트 최대 4,000자(서버와 편집란 공통), 모델 출력 상한 500토큰. Qwen 이미지 처리 상한을 준비 이미지와 같은 768² 픽셀로 올렸습니다. 자세·방향·배경·품질 태그는 외형 분석에서 제외하고 사용자의 선택을 유지합니다. 모델은 외형 텍스트만 출력하며, JSON과 한국어 검수 메모는 서버가 구성해 길어진 응답의 JSON 잘림 오류를 피합니다. 토큰 상한에 닿으면 마지막 미완성 구절을 제외합니다. 시간 초과 시 Windows venv 런처와 분석 인터프리터 자식 프로세스를 함께 종료하며 다른 요청의 프로세스는 건드리지 않습니다. 입력 설명 전체 상한은 기존 6,000자라 기존 설명과 합칠 때 넘으면 줄이라는 안내를 표시합니다.
- 승인 계정의 POST /api/images/describe 및 /api/images/models.caption. 버튼을 눌러야 분석하며 생성 시 자동 실행하지 않는다. 입력은 최대24MP 검증 후 투명 여백 정리/768px JPEG 준비, 임시 파일은 종료 시 삭제.
- UI `image-caption.js`: 결과는 편집 가능한 초안. 기존 설명은 자동 변경하지 않고 사용자가 추가/교체 선택. 분석 중 이미지가 바뀌면 오래된 결과 무시. 다운로드 완료 전 버튼 비활성.
- 상세 분석 실제 검증: `outputs/reference-caption-detailed-20261019/result-verified.json`. 같은 원화의 기존 32단어·176자에서 158단어·978자로 증가, CPU 77.94초. 자동 검증은 caption/API 8개 및 이미지 스튜디오 브라우저 테스트 통과. 상세 묘사에서도 머리 묶음·물건·색상 오독이 남았으므로 정보량 증가를 인식 정확도 향상으로 해석하지 않습니다. 사용자 확인 후 적용 원칙을 유지합니다.
- 실제 Qwen 추론 품질·속도는 다운로드 후 별도 검증 필요. 준비/타임아웃/CPU·offline 격리/입력 검증·인증/프론트 초안 적용은 mock 테스트로 확인한다.
