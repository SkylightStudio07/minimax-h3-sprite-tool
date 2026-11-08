# Soya 그림체 모델 가져오기 — 2026-10-17

사용자 요청으로 comfyui_hooking_server 설치 목록에서 그림체 및 관련 모델을 가져왔다.
원본 코드나 워크플로를 실행하지 않고, 고정 커밋의 모델 URL·크기·SHA256만 사용한다.

- 원본 커밋: `810733d5b728e9de1b99686893e41de55134ad4c`
- 설치 목록: `data/soya-style-import.json` (30개, 총 44.32 GB; 기존 동일 파일은 검증 후 재사용)
- 상태: `data/soya-style-download-status.json`
- 로그: `data/soya-style-download.log`, `data/soya-style-download-error.log`
- 실행/재개: `.venv/Scripts/python.exe -u tools/download_soya_styles.py`
- API 키: 프로세스의 `CIVITAI_API_KEY`; Windows 사용자 환경 변수에서 전달해 실행했다. 키를 파일이나 로그에 기록하지 않는다.

작가·그림체 LoRA 12개를 우측 라이브러리에 비활성 검증 대기로 추가했다. 다운로드 완료만으로 활성화하지 않는다.
기존 Anima Turbo 세팅으로 실제 생성 및 로더 호환성을 확인한 다음 enabled를 변경해야 한다.
Illustrious는 현재 Anima/Animagine 경로와 별개이므로 전용 생성 경로를 구현하기 전에는 선택 불가다.
프리뷰는 아직 생성하지 않았으며 다른 그림체의 이미지를 재활용하지 않았다.

LoRA는 `ComfyUI/models/loras/soya-import/`, 체크포인트 및 Anima 모델은 원본 manifest의 모델 하위 디렉터리에 저장한다.
속도·비율·구도 보조 LoRA는 다운로드 목록에만 넣었다. FComic은 요청한 전체 수집에는 포함하되 일반 그림체 카드에는 전시하지 않는다.
Qwen 이미지 편집 모델과 동영상 모델은 이번 그림체 수집 범위에서 제외했다.
원본 워크플로의 혼합 강도를 가져오거나 검증한 것은 아니다. 제작자 이용 조건은 각 항목 metadata에 보존했다.

다운로드는 숨겨진 백그라운드 프로세스로 실행하고, 완료까지 계속 감시하지 않는다.
실패 파일은 다른 모델을 막지 않는다. 재실행하면 검증된 파일을 건너뛰고 부분 파일을 이어받는다.
파일 크기와 SHA256이 모두 맞아야 최종 파일명으로 설치되며, 기존 파일이 다르면 덮어쓰지 않는다.

## 실생성 검증 결과

30개 다운로드 및 SHA256 검증 완료. `tools/verify_soya_styles.py`로 Anima용 그림체 11종을
Turbo 1.1 / 768×1024 / 10 steps / CFG 1 / 강도 0.5에서 시험했다.
같은 프롬프트와 시드의 전술요원·남성 검사 2종, LoRA 없는 기준 2장 포함 24장 생성 성공.
추가 `--controls` 실행으로 트리거를 유지하고 강도만 0으로 낮춘 전술요원 11장을 생성했다.
모두 성공했고 각 강도 0.5 출력과 픽셀이 달랐다. 픽셀 차이는 화풍 품질이나 패치 적용량의 점수가 아니다.

- 9종을 실험적으로 활성화하고 로컬 생성 예시 2장씩 연결했다.
- m4me와 Boldline은 전신 예시에 중복 인물/얼굴이 발생하여 비활성 상태로 유지했다. 예시는 문제까지 확인할 수 있도록 표시한다.
- Kieed, Screenshot, ci10ranko, Na tarapisu는 우선 비교할 후보. Screenshot은 의상 세부가 단순해질 수 있다.
- ix7와 Matsuda Hikari는 스타일 변화가 크지만 장비·나이감·구성도 바뀔 수 있어 설명에 명시했다.
- Blue Archive와 Flat0521은 이번 강도에서 시각적 변화가 작다. 강도·시드 전반의 안정성을 보장하지 않는다.
- Illustrious 체크포인트 및 suujiniku는 아직 별도 생성 경로와 실생성 검증이 필요하다. 보조 LoRA도 이번 화풍 비교 대상에는 포함하지 않았다.

결과: `outputs/soya-styles-20261017/`의 `preview.html`, `results.json`, `controls.json`,
`control-differences.json`, 이미지 및 Comfy 이력. 추천 비교표 `recommended.jpg`.
공개 예시: `web/assets/soya-style-previews/`. 생성 메타데이터에 실제 프롬프트와 시드 보존.
단일 작가 LoRA들은 명시적으로 개별 화풍 카드이며 혼합 프리셋으로 가장하지 않는다.

검증: `python -m unittest test_image_engine` 6건 통과, `node tools/test_image_studio.cjs` 통과.
브라우저 검사는 카탈로그 크기에 맞춰 모든 카드·예시 수, 미설치 차단, 계열 전환, 반응형 레이아웃을 확인한다.

## 작가 화풍 이용 안내

카탈로그의 `artistName`이 있는 LoRA는 카드에서 사용하거나 선택 목록에서 선택할 때
`artistRightsDialog`를 표시한다. 프리셋/이전 설정 복원 경로도 같은 안내를 사용한다.
레퍼런스·화풍 연구용을 권장하고, 게임 최종 아트로 그대로 사용하는 것은 권장하지 않는다는
내용 및 원작 유사성·포함 요소·이용 조건 확인 문구와 모델 출처 링크를 제공한다.
안내는 닫기와 Escape로 닫을 수 있고 선택을 차단하거나 법적 판정을 내리지 않는다.
비활성 카드에서도 별도 '작가 화풍 · 이용 안내' 버튼으로 확인 가능하다.
`creator`는 업로더 이름이므로 작가 식별이나 안내 조건으로 사용하지 않는다.
현재 지정한 7종: ci10ranko, Na tarapisu, Kieed, suujiniku, m4me, ix7, Matsuda Hikari.
일반 화풍·품질 보정용 LoRA에는 표시하지 않는다.

## 공유용 워크플로 재조사 및 사용자 추가 LoRA

원본 `frontend/index.html`의 `<script type="application/json" id="share-workflow-data">`에
공유용 API 워크플로 40노드가 포함되어 있음을 확인했다. 별도 배포 팩과 구별해야 한다.
이전 대화의 '혼합 강도를 확인할 수 없다'는 설명은 부정확했다.
읽기 전용 사본: `data/research/soya-share-workflow-source.json` (실행하지 않음).

- Anima Preview + RDBT 고속 LoRA 1.0 + Kieed LoKr 0.3.
- AnimeSharp 업스케일 후 RIN Flanime v3 경로에서 다시 인코딩·샘플링.
- Flanime 경로: DMD2 1.0 + `Detailed anime style.safetensors` 0.3,
  5 steps / CFG 1.7 / LCM / simple / denoise 0.2.
- IL 접두 프롬프트: linear hatching, (thick lineart:1.7), high contrast, pastel colors,
  chromatic aberration, 기타 품질 태그.
- Detailed anime style은 설치 목록에서 원본 모델 URL을 식별하지 못했다.
  임의의 동명 모델로 대체하지 않는다. 사용자 첨부 이미지가 이 워크플로로 생성되었다는 메타데이터 증거는 없다.
  이 경로 전체를 사이트에 이식하거나 검증한 상태도 아니다.

사용자 지정 추가 모델 3종: `data/requested-anime-styles.json`.
다운로드: `tools/download_soya_styles.py --inventory data/requested-anime-styles.json`.
상태: `data/requested-anime-styles-status.json`. 라이브러리에는 검증 대기로 등록.

- Anime_pixel model 196639/version 221090: SDXL, trigger `pixel style`, 약 70.6MB.
- Anime Original Art Style model 231343/version 261140: SD 1.5, 약 7.1MB.
- Anime Original Art Style - Shadow model 861153/version 963502: Illustrious, 약 42.9MB.
- 합계 약 120.6MB. 모델 제작자명은 작가 화풍의 작가명으로 취급하지 않는다.
- 세 모델은 서로 기반 모델이 다르며, SD 1.5·Illustrious 전용 경로는 아직 연결되지 않았다.
브라우저 검사에서 카드/선택 목록 양쪽 안내, 보류 항목 안내, 일반 LoRA 미표시를 확인했다.
