# YuE2 게임 BGM 도구 인수인계

이 문서는 다른 개발 세션이 `G:\Minimax`의 YuE2 게임 BGM 기능을 빠르게 파악하고 이어서 작업하기 위한 저장소 내부 안내서다. 사용자 설치 안내는 루트의 [BGM_SETUP.md](../BGM_SETUP.md)를 함께 참고한다.

## 현재 구현 상태

- 팀 사이트의 **게임 BGM** 탭에서 YuE2 음악 생성을 대기열에 등록한다.
- 입력 방식은 Gemini 기획서 분석, 기본 프리셋, 직접 프롬프트의 세 가지다.
- Notion 연동은 하지 않는다. 사용자가 Notion에서 내보낸 Markdown을 브라우저에서 불러오거나 직접 붙여 넣는다.
- Gemini 인증은 Google AI Studio API 키와 Vertex AI ADC/서비스 계정을 모두 지원한다.
- 직접 입력한 한국어 프롬프트는 Gemini Flash Lite로 영어 Style 프롬프트로 다듬을 수 있다.
- YuE2는 스프라이트 서버와 분리된 `.venv-yue2` 환경과 로컬 모델을 사용한다.
- RTX 5060 Ti 16GB 기준 기본 프로필은 AR FP8, CPU offload, NAR query chunk 1024다.
- 생성 진행률은 공용 작업 대기열에 표시되고 완료된 FLAC/ABC는 팀 갤러리에서 재생·다운로드할 수 있다.
- 2026-09-22 기준 전체 `unittest` 46개가 통과했다.

## 주요 파일

| 경로 | 역할 |
| --- | --- |
| `web/music.html` | 게임 BGM 입력 UI, Markdown 로딩, 프롬프트 변환과 작업 등록 |
| `music_prompts.py` | 프리셋/직접/Gemini 입력 검증, Gemini·Vertex 호출, Style/Lyrics 결정 |
| `music_engine.py` | 팀 대기열 작업을 YuE2 전용 Python 프로세스로 실행하고 결과를 갤러리에 연결 |
| `tools/run_yue2_job.py` | YuE2 파이프라인 실행, 인스트루멘털 계획 후처리, 산출물 저장 |
| `tools/instrumental_abc.py` | 네이티브 ABC의 `V: Vocal` 음표를 길이가 같은 쉼표로 변환 |
| `team_server.py` | `/music`, 음악 API, 대기열, 인증된 결과 파일 제공 |
| `setup_yue2.bat` / `scripts/setup_yue2.ps1` | 전용 환경과 선택적 모델 설치 |
| `BGM_SETUP.md` | 사용자용 설치·인증·운영 안내 |
| `test_music_prompts.py` | 음악 프롬프트/API 회귀 테스트 |
| `test_instrumental_abc.py` | Vocal 악보 무음화 회귀 테스트 |

외부 YuE2 소스는 `vendor/YuE`, 모델은 `yue2-runtime/models/YuE2-3B`와 `yue2-runtime/models/YuE2-Vae`에 있다. 모델 파일과 `.env`는 Git에 넣지 않는다.

## 요청 처리 흐름

1. `POST /api/music/generate`가 로그인 여부와 요청을 검사한다.
2. `music_prompts.resolve()`가 Style, Lyrics, seed, `cot`, 제목을 확정한다.
3. `team_server.py`가 `jobType=music` 작업을 SQLite 대기열에 저장한다.
4. 공용 단일 작업자가 `music_engine.run_job()`을 호출한다.
5. `music_engine.py`가 작업 폴더에 초기 `request.json`을 만들고 `.venv-yue2`의 `tools/run_yue2_job.py`를 자식 프로세스로 실행한다.
6. 자식 프로세스의 `[YuE2]` 로그는 작업 진행 메시지로 저장된다.
7. 성공 시 `audio.flac`, ABC와 메타데이터를 갤러리 결과에 연결한다.

스프라이트, 리깅, 음악은 같은 팀 대기열을 공유한다. 서버를 재시작하기 전에 반드시 실행 중인 YuE2/ComfyUI 작업이 없는지 확인한다.

## Style과 Lyrics

YuE2 요청의 두 텍스트 채널은 역할이 다르다.

- `style`: 장르, 분위기, 악기, 템포, 편곡과 음향 성격
- `lyrics`: 실제로 부를 가사와 섹션 구조

보컬곡은 사용자가 입력한 Lyrics를 그대로 별도 전달한다. 인스트루멘털은 빈 문자열 대신 다음과 같이 본문 없는 구조 태그를 전달한다.

```text
[Intro]

[Instrumental]

[Bridge]

[Instrumental]

[Outro]
```

인스트루멘털 Style에서는 `choir`, `vocal`, `voice`, `singer`, `chant`, `lyrics`, `humming`, 성별과 단독 언어 태그 같은 보컬 유도 표현을 서버가 제거한다. 마지막에는 정규화된 인스트루멘털 지시를 붙인다. Gemini가 충돌하는 표현을 반환하거나 사용자가 직접 입력해도 이 필터가 적용된다.

## 인스트루멘털 처리

빈 Lyrics나 `no vocals`라는 자연어만으로는 YuE2의 보컬 생성을 확실히 막을 수 없다. YuE2는 기본적으로 보컬과 반주를 함께 만드는 모델이고, `full` 계획의 네이티브 ABC는 `Vocal`과 `Ins` 두 보이스를 사용한다.

현재 구현은 다음 순서로 보컬 악보를 제거한다.

1. 인스트루멘털 요청은 서버에서 `cot="full"`로 강제한다. UI에서도 `off`를 선택할 수 없게 한다.
2. YuE2가 먼저 ABC를 계획한다.
3. `tools/instrumental_abc.py`가 각 블록의 정확한 `V: Vocal` 다음 음악 줄만 처리한다.
4. 음정 토큰을 원래 길이의 `z` 쉼표로 바꾸고 tie를 제거한다.
5. 코드 기호, 마디선, 박자 길이, `V: Ins`와 고정 보이스 헤더는 유지한다.
6. 변환한 ABC를 외부 계획 입력으로 다시 넣어 semantic/NAR/VAE 단계를 실행한다.

Hugging Face 토론에서 공유된 단순 정규식은 모든 Vocal 줄을 고정 `z4`로 바꾸지만, 실제 YuE2 ABC 한 줄에는 1~4마디가 들어갈 수 있어 보이스 길이가 어긋난다. 현재 변환기는 음표별 duration을 보존한다.

실제 기존 악보로 검증했을 때 Vocal 29개 블록의 음표 246개를 변환했고 코드명, 마디선과 Ins 파트가 유지됐다.

산출되는 두 악보는 다음과 같다.

- `score.original.abc`: YuE2가 처음 계획한 원본 악보
- `score.abc`: Vocal 음표가 쉼표로 바뀌어 실제 합성에 사용된 악보

중요: Vocal 악보를 모두 무음화해도 오디오 모델이 목소리 같은 질감이나 단어를 환각하지 않는다는 절대 보장은 없다. 현재는 악보 수준의 결정론적 차단까지만 구현돼 있다. 더 강한 보장이 필요하면 Whisper 검사 후 다른 seed로 제한 횟수만큼 재생성하고, 인식 단어가 가장 적은 take를 선택하는 후속 기능을 고려한다.

## Gemini와 Vertex AI

루트 `.env`는 서버 시작 시 자동으로 읽힌다. 실제 비밀값을 문서나 로그에 복사하지 않는다.

Google AI Studio:

```dotenv
GEMINI_PROVIDER=api-key
GEMINI_API_KEY=...
```

Vertex AI 서비스 계정 또는 ADC:

```dotenv
GEMINI_PROVIDER=vertex
GEMINI_VERTEX_PROJECT=project-id
GEMINI_VERTEX_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\service-account.json
```

`GOOGLE_APPLICATION_CREDENTIALS` 대신 실행 환경의 기본 서비스 계정도 사용할 수 있다. `GEMINI_VERTEX_PROJECT`가 없으면 `GOOGLE_CLOUD_PROJECT`도 인식한다.

관련 선택 환경 변수:

```dotenv
GEMINI_MUSIC_MODEL=gemini-3.8-flash
GEMINI_MUSIC_LITE_MODEL=gemini-3.5-flash-lite
GEMINI_MUSIC_MAX_DOCUMENT_CHARS=500000
GEMINI_MUSIC_MAX_MARKDOWN_BYTES=2000000
GEMINI_MUSIC_MAX_OUTPUT_TOKENS=4096
GEMINI_MUSIC_THINKING_BUDGET=1024
YUE2_NAR_QUERY_CHUNK_SIZE=1024
YUE2_MAX_LYRICS_CHARS=12000
```

기획서 분석 기본 출력 한도는 4096토큰, thinking 예산은 1024토큰이다. Flash Lite 직접 프롬프트 변환은 더 작은 별도 예산을 사용한다.

## 설치와 실행

전용 환경만 준비:

```bat
setup_yue2.bat
```

라이선스를 확인하고 모델도 내려받기:

```bat
setup_yue2.bat -DownloadModels
```

통합 HTTPS 서버:

```bat
start_team_tool_https.bat
```

이 배치 파일 하나가 팀 서버를 실행하며 음악 서버를 별도로 띄울 필요는 없다. YuE2 생성 자체는 작업이 시작될 때 전용 자식 프로세스로 실행된다.

서버 준비 여부는 인증된 `/api/status` 응답의 `music` 항목이나 게임 BGM 화면에서 확인한다. 외부 운영 주소는 배포 환경에 따라 달라질 수 있으므로 코드에 고정하지 않는다.

## 결과 파일

작업별 디렉터리는 `outputs/music/<job-id>/`다.

| 파일 | 내용 |
| --- | --- |
| `audio.flac` | 48kHz 최종 오디오 |
| `score.original.abc` | 인스트루멘털일 때 원본 계획 |
| `score.abc` | 실제 합성에 사용된 계획 |
| `request.json` | 실제 YuE2 요청. 인스트루멘털은 변환된 외부 ABC를 포함할 수 있음 |
| `plan.json`, `plan_manifest.json` | 계획과 무결성 정보 |
| `abc_tokens.npy`, `prefix.npy` | 정확한 계획/프리픽스 토큰 |
| `semantic.npy`, `latent.npy` | 중간 생성 산출물 |
| `config.json`, `result.json` | 실행 설정, 모델 정보, 시간, 해시와 완료 상태 |

완료된 파일은 `/outputs/music/<job-id>/<filename>`을 통해 로그인한 팀원에게만 제공된다. 갤러리의 FLAC와 ABC 링크도 이 경로를 사용한다.

## 테스트와 점검

프로젝트 가상환경에서 전체 테스트:

```powershell
.\.venv\Scripts\python.exe -m unittest
```

음악 관련 테스트만:

```powershell
.\.venv\Scripts\python.exe -m unittest test_instrumental_abc.py test_music_prompts.py
```

YuE2 전용 실행기 import/옵션 점검:

```powershell
.\.venv-yue2\Scripts\python.exe tools\run_yue2_job.py --help
```

작업 트리 검토:

```powershell
git diff --check
git status --short
```

실제 오디오 검증은 시간이 오래 걸린다. RTX 5060 Ti 16GB에서 약 261초 FLAC 한 건이 약 14분 50초 걸렸던 기록이 있다. 코드 회귀 테스트와 실제 생성 테스트를 구분해 기록한다.

## 안전한 서버 재시작

1. `run_yue2_job.py` 자식 프로세스나 ComfyUI 생성이 실행 중인지 확인한다.
2. 실행 중이면 완료될 때까지 기다린다. 팀 서버를 먼저 내리면 작업 진행 기록과 생성이 중단될 수 있다.
3. 기존 팀 서버를 종료한 뒤 `start_team_tool_https.bat`을 실행한다.
4. 로컬 7866 리스너와 외부 프록시/터널의 HTTP 상태를 각각 확인한다.
5. 로그인 후 `/music`에 새 UI 문구가 표시되는지 확인한다. `/api/status`는 인증 없이 요청하면 401이 정상이다.

Windows의 `.venv\Scripts\python.exe`가 런타임 Python을 한 번 더 실행해 부모/자식 프로세스 두 개처럼 보일 수 있다. 실제 서버는 로컬 7866 포트 소유 프로세스로 식별한다.

## 알려진 한계와 다음 작업 후보

- 악보 무음화는 음성 환각을 100% 보장하지 않는다.
- 자동 Whisper 검사와 seed 재시도는 아직 없다.
- `cot=off`는 인스트루멘털에서 사용할 수 없다. ABC를 후처리해야 하기 때문이다.
- 현재 Style 보컬 단어 제거는 영어 중심이다. 더 많은 언어·표현이 필요하면 테스트와 함께 확장한다.
- 음악 작업은 공용 GPU 대기열을 사용하므로 스프라이트/리깅과 동시에 실행하지 않는다.
- NAR chunk를 512/256으로 낮추면 피크 VRAM은 줄지만 성능은 별도로 재검증해야 한다.
- 갤러리에서 원본 `score.original.abc` 다운로드는 현재 노출하지 않는다. 필요하면 인증된 결과 API와 UI를 함께 확장한다.

## 작업 트리 주의

이 저장소는 여러 세션이 같은 작업 디렉터리를 공유할 수 있다. 2026-09-22 문서 작성 시점에도 음악 변경 외에 리깅/Live2D 관련 수정과 `.codex-backups`가 함께 존재했다.

- 다른 기능의 변경을 reset, checkout, clean 또는 덮어쓰기 하지 않는다.
- 커밋 전 `git diff`로 음악 파일과 다른 세션 파일을 분리한다.
- `.env`, 모델, 생성 결과, 로그와 백업 폴더를 실수로 커밋하지 않는다.
- 현재 음악 변경도 아직 커밋됐다고 가정하지 않는다.

## 외부 조사 근거

- YuE Issue #18: 섹션 태그와 빈 본문을 사용한 무가사 생성 사례  
  <https://github.com/multimodal-art-projection/YuE/issues/18>
- YuE Issue #172: YuE2에서 full 계획, 보컬 Style 제거, 빈 섹션을 사용한 사례와 seed 의존성  
  <https://github.com/multimodal-art-projection/YuE/issues/172>
- Hugging Face YuE2-3B discussion #1: ABC의 Vocal 줄을 생성 후 제거하는 ComfyUI 사례  
  <https://huggingface.co/m-a-p/YuE2-3B/discussions/1>

외부 사례는 방향을 정하는 근거일 뿐 공식적인 무보컬 보장 규격은 아니다. 저장소 구현과 실제 생성 결과를 기준으로 판단한다.
