# Soya Anima → Flanime 공유 워크플로

`lbh848/comfyui_hooking_server` 프론트엔드에 포함된 `share-workflow-data`를 가져온 40노드 API 그래프다.
원본 출처·고정 커밋·SHA256은 `source.json` 참고. 원본 프로젝트는 CC BY-NC-SA 4.0이며,
모델 및 외부 노드는 각 배포처 조건이 별도로 적용된다.

- `anima-flanime.original.api.json`: 원본 JSON. 모델명·프롬프트·강도 변경 없음.
- `anima-flanime.local-paths.api.json`: 찾을 수 있는 기존 모델의 하위 폴더 경로만 수정한 사본.
- `local-path-changes.json`: 수정한 경로 목록.
- `dependencies.json`: 기존 8189 서버 및 모델 폴더를 대상으로 확인한 준비 상태. 실험 서버 8191의 로딩 결과가 아니다.

ComfyUI에서 API 형식 JSON을 불러와 사용한다. 원본은 캔버스 위치·그룹을 담은 UI JSON이 아니라
API 실행 그래프이므로 원저자의 화면 배치까지 재현하지는 않는다.
두 파일은 일반 및 별도 Comfy 환경의
`user/default/workflows/SpriteLab-Community/Soya/`에도 복사했다.

## 원본 구성

1. Anima Preview + RDBT 1.0 + Kieed LoKr 0.3, AuraFlow shift 8.
2. 빈 latent 1024×1024를 0.75배로 줄여 시작. er_sde / simple / 16 steps / scheduled CFG 2.
3. `2x-AnimeSharpV4_Fast_RCAN_PU.safetensors`로 확대.
4. GLSL 색 보정: vibrance 20, saturation 20.
5. WD14 태깅 결과에 굵은 선·해칭·파스텔색 등의 프롬프트를 추가.
6. RIN Flanime v3 + DMD2 1.0 + Detailed anime style 0.3.
7. LCM / simple / 5 steps / CFG 1.7 / denoise 0.2로 재처리 후 PNG 저장.

입력: 노드 125 `{{risu_prompt}}`, 노드 126 `{{risu_neg}}`를 실제 설명과 제외 태그로 바꿔야 한다.
노드 290/291의 -1 시드는 rgthree가 실행 시 처리하는 원본 설정이다.

## 아직 실행 준비가 끝나지 않은 항목

- `anima-preview.safetensors`: 정확한 원본 버전 파일이 없음. Base/Turbo/2.9B로 조용히 대체하지 않았다.
- `2x-AnimeSharpV4_Fast_RCAN_PU.safetensors`: 현재 모델 폴더에 없음.
- `Detailed anime style.safetensors`: 파일 없음. 유사한 이름의 공개 모델은 발견했지만
  원본 워크플로와 같은 버전이라는 해시 증거가 없어 자동 다운로드·대체하지 않았다.
- `JoinStrings`/`ScheduledCFGGuidance`: KJNodes. `Seed (rgthree)`: rgthree.
- `WD14Tagger|pysssss`: pythongosssss/ComfyUI-WD14-Tagger와 wd-vit-tagger-v3 모델 필요.
- 기본 Anima/Flanime 모델, RDBT/Kieed/DMD2 및 Qwen 텍스트 인코더/VAE는 로컬에서 찾았다.

실생성은 아직 하지 않았다. 참고로 사용자가 첨부한 이미지가 이 그래프로 생성되었다는
메타데이터는 확보되지 않았다. 별도 실행환경 설치 절차는 `DOCS/COMMUNITY_IMAGE_WORKFLOWS.md` 참고.

## 누락 모델 다운로드 시작

사용자 승인으로 다음 파일을 백그라운드 다운로드 목록에 넣었다. 완료 여부는
`data/soya-missing-models-status.json`에서 확인해야 한다. 고정 URL·크기·해시는
이 폴더의 `model-downloads.json`에도 보관했다. 총 약 4.62GB.

- 공식 `anima-preview.safetensors`: 약 4.18GB, HF 고정 커밋
  `f973fc41ec7545364ac9776c2440285f43ff2a30`, SHA256
  `41fa7b78613dfe0d888b3647f70c7fb8cdfda2ff177e78d2e16e06dc810d9dcc`.
- `2x-AnimeSharpV4_Fast_RCAN_PU.safetensors`: 약 31.4MB, 원본 Git 설치 목록의 URL·해시 사용.
- 비교 후보: Detailed anime style - Illustrious V2.0 / v0.7,
  Civitai model 1547435 / version 1750914, 약 405MB.
  `loras/soya-candidates/Detailed_anime_style_Illustrious_v0.7.safetensors`에 저장한다.
  원본에서 사용한 LoRA와 같은 파일인지 확인할 해시가 없어 원본 이름으로 바꾸거나
  워크플로를 자동으로 수정하지 않았다. Git 설치 명세의 과거 20개 리비전 조사에서도
  이 원본 LoRA의 명시적인 배포 URL/해시를 찾지 못했다.

재개 명령: `.venv/Scripts/python.exe tools/download_soya_styles.py --inventory data/soya-missing-models.json`.
로그: `data/soya-missing-models.log`, `data/soya-missing-models-error.log`.
크기와 SHA256 검증을 통과한 파일만 최종 파일명으로 설치한다.
위의 이전 누락 목록은 다운로드 시작 전 조사 기록이다.

## 2026-10-17 실제 생성 테스트 완료

다운로드 3개 모두 크기·SHA256 검증 완료. `tools/verify_soya_workflow.py`로
전술요원/남성 검사/메이드 3종을 실행했다. 각 1시드이며 결과 성공률 일반화는 금지한다.

원본 그래프에서 모델 하위 폴더 경로, 실제 프롬프트, 고정 시드, 저장 경로를 변경했다.
Detailed anime LoRA만 명시적으로 Civitai model 1547435/version 1750914 후보에 연결했다.
그 외 원본 샘플링·업스케일·태깅·색 보정·LoRA 강도를 유지했다.
Anima 768×768 → AnimeSharp/색 보정 1536×1536 → Flanime 1536×1536.
중간 단계 SaveImage 2개를 추가해 실제 비교할 수 있게 했다.

- 첫 실행 전술요원 64.11초(태깅 모델 초기 다운로드/로딩 포함).
- 이후 남성 검사 24.12초, 메이드 24.09초. 환경: RTX 5060 Ti 16GB.
- 이번 실행에서는 메모리 부족이나 노드 실행 오류가 없었다. 최대 VRAM은 계측하지 않았다.
- 선·얼굴·명암이 후처리로 뚜렷하게 바뀌었다.
- 전술요원: WD14가 무전기를 gun/handgun으로 오인하여 최종 이미지에서 총 형태가 강화됨.
- 남성 검사: 최초 Anima 생성에서부터 코트가 일본식 의상으로 바뀌고 검이 두 개 생성됨.
- 메이드: 사용자 첨부와 유사한 설명만 사용한 독립 생성. 원본 이미지의 재현/편집 시험은 아니다.
- 따라서 그림체 후보로는 유효하나 장비·의상 보존이 중요한 게임 아트 기본 경로로 바로 활성화하지 않았다.

결과: `outputs/soya-workflow-test-20261017/preview.html`, `comparison.jpg`, `finals.jpg`.
각 이미지의 실행 그래프, Comfy 이력 및 프롬프트/시드/실측 시간을 함께 저장했다.
원본 자동 태깅만으로 Flanime 프롬프트를 만드는 대신 사용자의 원래 장비/의상 설명을 유지하는
비교 시험이 다음 개선 후보이며 아직 구현하지 않았다.

## 사이트 기본값 적용

위 결과를 확인한 사용자가 기본값 적용을 지시하여 `image_soya.py`와 `image_engine.py`에
`soya-anima-flanime` 기본 프로필을 연결했다. CLI 기본 그래프 사본은 계속 보관한다.
기본 UI는 768×768 첫 생성 → 1536×1536 최종 출력이며, 팀 FIFO와 갤러리 저장을 사용한다.
상세 구현·검증·후속 운영은 `DOCS/IMAGE_STUDIO.md`의 최신 절 참고.
