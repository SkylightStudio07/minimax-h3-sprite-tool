# 원화 생성기 투명 배경

2026-10-15. 운영 경로 `G:\Minimax`.

## 현재 상태

배경 유지 / 생성 후 투명 PNG 옵션, 원본 별도 저장, 실패 시 원본 반환, 기존 갤러리·스프라이트·Live2D 전달 경로를 구현했다. **모델 해시·실이미지 6장 검증 후 활성화 완료.** 새 작업의 기본값은 투명 배경이다. 이전 작업 재생성 시 설정을 복원하며, 옵션이 없던 과거 작업은 배경 유지로 복원한다.

기존 Anima 스타일 3장에 더해 흰 로브/지팡이, 긴 머리/리본/활, Animagine 총기 전신 캐릭터를 새로 생성했다. RGB와 캔버스 크기가 원본과 동일함을 검사했고, 흰색과 어두운 배경에 합성해 육안 확인했다. 분리 단독 처리 약 1.0~1.34초/장(CPU). 회화풍 배경 얼룩과 바닥 그림자가 제거되고 흰 의상·주요 소품은 보존된다. 다만 매우 가는 활시위는 옅어지고 일부 머리카락 경계에는 원본 배경색이 밝은 테두리로 남는다. 완벽한 매팅이 아니므로 원본을 함께 제공한다.

생성부터 PNG 저장까지 검증하는 도구: `tools/verify_background_generation.py`. 결과: `outputs/background-validation-20261015/generated/` (사례별 원본/투명 PNG/설정, jobs.json, comparison.jpg). 테스트 도구는 운영 갤러리에 항목을 추가하지 않는다.

배포 확인: 팀 작업 대기열이 비어 있음을 확인한 후 HTTPS 설정으로 서버를 재시작했다. 외부 주소의 image-studio.js HTTP 200 및 기본값/원본 링크 코드 반영, 비로그인 모델 API 401을 확인했다. 백엔드 5개 테스트와 브라우저 생성·부분 수정·전달·반응형 테스트 통과.

기존 border-connected 단색 제거를 스타일 검증 이미지 3장에 시험했다. 회화풍에 배경 얼룩과 머리 주변 테두리가 남아 기본 기능으로 채택하지 않았다. `outputs/background-validation-20261015/flat-baseline.jpg` 참고.

## 모델과 실행

- Anime Segmentation ISNet (`skytnt/anime-seg`), 모델 카드 Apache-2.0.
- 출처: https://huggingface.co/skytnt/anime-seg
- revision: `493cb60893f47441b26ec4fb9a306bce9e342982`
- `isnetis.onnx`, 176,069,933 bytes.
- SHA256: `f15622d853e8260172812b657053460e20806f04b9e05147d49af7bed31a6e99`
- 다운로드: `.venv\Scripts\python.exe tools/download_background_model.py`.
- 런타임: onnxruntime 1.31.0 CPU. `.venv`에 설치 완료. 기존 GPU 생성 모델과 VRAM을 경쟁하지 않는다. 런타임은 요청마다 해제한다.
- 모델 위치: `models/background/isnetis.onnx`. 입력은 RGB 0~1, 비율 유지 중앙 패딩, 출력 마스크를 원래 크기로 복원한다. RGB·캔버스·좌표는 그대로 두고 alpha만 적용한다.

## 검증 후 활성화

1. `logs/background-model-download.log` / `logs/background-model-download-error.log` 및 모델 해시 확인. 사용자의 요청으로 다운로드를 시작한 뒤 실시간 감시하지 않는다.
2. `.venv\Scripts\python.exe tools/verify_image_background.py`로 기존 3장 테스트. 추가 인자로 PNG 파일들을 전달할 수 있다. 머리카락·흰 옷·길고 가는 무기/장식·전신 사례를 추가 생성해 비교한다.
3. 결과 `outputs/background-validation-20261015/anime-model-comparison.jpg`를 육안 확인한다. 검증 스크립트는 자동 활성화하지 않는다.
4. 합격 시 `models/background/validated.txt`에 위 모델 SHA256을 기록한다. `image_background.status()`가 파일·런타임·검증 마커를 함께 확인한다.
5. 서버 재시작 및 실제 사이트 확인. 모델을 교체하는 경우에도 이 순서로 재검증한다.

## 구현과 보존 규칙

- `image_background.py`: 모델 상태와 CPU 추론. 미래 모델 교체 시 반드시 새 해시 및 재검증.
- `image_engine.py`: `background=keep|transparent`. 구버전 API 기본값은 keep. 투명 요청 시 흰 배경을 유도하고, `image-N-original.png`와 `image-N.png` 저장. 실패 시 원본 전달과 경고 표시.
- `team_server.py`: 결과에 기록된 originalUrl만 기존 인증 경로로 허용. 미로그인·삭제 후 접근은 차단.
- `web/assets/image-studio.js`, `web/image-studio.html`: 옵션, 체커보드 미리보기, 원본 다운로드. 부분 수정은 배경 제거를 끄고 마스크 밖 RGBA를 보존한다. 참고 이미지 추론 입력은 흰색에 합성하여 투명 영역이 검게 되지 않도록 한다.
- 생성 원본과 투명 결과 모두 같은 생성 설정을 기록한다. 실제 후처리 성공 여부와 경고는 작업 결과의 images 항목에 기록된다.

검증: `python -m unittest test_image_engine` 및 `node tools/test_image_studio.cjs`. 모델 부재 거부, 원본 보존, 추론 실패 대체, 원본 인증, 부분 수정 alpha 보존, 투명 기본값/원본 다운로드 링크/부분 수정 시 배경 유지 요청을 검증한다. 모델 실제 품질은 위 6장으로 검증했다.


## 2026-10-18 MiniMax 영상 기반 스프라이트 시트 연결

- 기존 `removeBackground` bool 보존, `backgroundRemoval=ai|flat` 추가. 신 UI는 투명 시트 생성 체크+AI 기본. 필드가 없는 과거 요청/설정은 flat 호환. `background_options`에서 형식/준비 상태 검증.
- `idle_tool.make_sprite_sheet(..., background_mode='flat')`: 기존과 같은 프레임 샘플/그리드/크기/배치를 사용. AI는 `image_background.remove`를 선택된 프레임에 각각 실행하고 alpha만 변경. RGB 보존을 위해 cutout을 마스크 없이 paste. 원본 시트·영상 유지. `load_session` lru_cache로 CPU ONNX 세션 한 개를 재사용(프레임별 모델 재로딩 방지, CPU4threads).
- 새로운 영상 생성/루프 보정 시트에도 방식 전달. 생성 도중 배경 제거에 실패하면 이미 저장한 원본 시트를 제공하고 경고/투명 파일 없음 표시. 영상 재생성하지 않음.
- 기존 POST `/api/jobs/<jid>/extract`에 `removeBackground`, `backgroundRemoval` 지원. 소유자/관리자, 완료 영상, 공유 extraction lock 유지. 원본+투명 재추출 파일을 exportSheets에 추가. `_transparent` 공개 미디어 허용 정규식 확장, 원본 키/기존 시트 덮어쓰지 않음. 실패한 재추출 임시 결과 정리.
- UI: 스프라이트 탭에서 AI/단색 방식 선택, 단색일 때만 tolerance. 결과에 체크무늬 투명 배경 표시. 갤러리 상세 도구에서 프레임 수+배경 방식 선택, 투명 재추출 파일도 미리보기/다운로드.
- 실제 CPU 검증: `tools/verify_sprite_background.py`, outputs/sprite-background-smoke-20261018/. 기존 캐릭터 영상 4프레임/2176×384 시트, 약2.7초. RGB 배열/캔버스 크기 동일, 원본 영상 hash 불변, 투명/불투명 영역 확인. comparison.webp 시각 검수. 속도는 해상도·프레임 수에 따라 다름.
- 회귀: test_background + 선택 API 테스트7개, 기존 이미지 경로15개, tools/test_sprite_workflows.cjs 통과. 프레임 마스크는 독립 추론이며 시간적 평활화는 구현하지 않음. 복잡한 머리카락·반투명 물체에서 가장자리 흔들림/누락은 별도 확인 필요.

## AI · 윤곽 다듬기 (`ai-smooth`, 2026-11-08, 실험적)

스프라이트 시트 배경 제거의 선택 항목이다. 기본값은 기존 AI 방식이다. `sprite_temporal_matte.py`가 프레임별 AI 누끼의 본체 윤곽에서 작은 틈을 메우고 계단을 완만하게 만든 뒤, 광학 흐름으로 맞춘 앞뒤 2프레임과 가중 중앙값을 낸다. 윤곽 띠만 바뀌며 내부 RGB·불투명도와 본체에서 떨어진 섬광·연기는 유지한다.

처음의 시간축 안정화 단독 시험은 권총 공격 흔들림이 4%만 줄어 충분하지 않았다. 눈에 띄는 결함은 프레임 안의 점선·계단이었고, 윤곽 정리를 더해 아래 결과를 얻었다.

| 클립 | 흔들림 감소 | 거칠기 전→후 (1.0이 매끈) | 내부 변경 픽셀 |
|---|---|---|---|
| 권총 A 공격 | 5.3% | 1.276 → 1.108 | 0 |
| 권총 A 대기 | 28.2% | 1.321 → 1.099 | 0 |
| 금발 대기 | 53.4% | 1.278 → 1.153 | 0 |
| 금발 공격 | 22.9% | 1.317 → 1.217 | 0 |

금발 오른쪽 머리카락에는 점선이 일부 남는다. 빠른 공격 동작의 흔들림 감소는 작다. 기존 결과물은 덮어쓰지 않았다. 비교: `outputs/temporal-matte-experiment-20261108/v2-contour-plus-temporal/*-before-after.webp` (왼쪽 전, 오른쪽 후). 사용자 육안 승인 전이므로 기본값으로 바꾸지 않는다. 선택 프레임마다 앞뒤 프레임까지 AI 누끼를 만들므로 일반 AI 방식보다 느리다.

