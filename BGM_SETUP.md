# YuE2 게임 BGM 설정

사이트의 **게임 BGM** 탭은 세 가지 입력 방식을 제공합니다.

- Gemini 기획서 분석: 붙여 넣거나 업로드한 Markdown을 음악 프롬프트로 정리
- 기본 프리셋: 탐험, 마을, 전투, 보스, 메뉴
- 직접 프롬프트: YuE2 스타일 프롬프트를 직접 입력

직접 프롬프트에는 탐험·전투·마을 예제가 있으며, 한국어 초안을 Gemini Flash Lite로 YuE2용 영어 프롬프트로 다듬을 수 있습니다. 기본 Lite 모델은 gemini-3.5-flash-lite이고 GEMINI_MUSIC_LITE_MODEL로 변경할 수 있습니다.

모든 방식은 인스트루멘털과 보컬 금지를 최종 프롬프트에 추가합니다.

## 1. 전용 환경

기존 스프라이트 환경과 분리된 .venv-yue2를 사용합니다.

    setup_yue2.bat

YuE2 모델 라이선스를 확인한 뒤 모델까지 받을 때:

    setup_yue2.bat -DownloadModels

모델은 yue2-runtime/models/에 저장되며 Git에 포함되지 않습니다. 기본 실행 프로필은 RTX 5060 Ti 16GB용 FP8 AR + CPU offload + 16GB budget입니다. NAR 오디오 합성은 피크 VRAM을 낮추면서 속도를 유지하도록 attention을 1024토큰 단위로 처리합니다. 생성 단계와 NAR 진행률은 팀 대기열에 실시간 표시됩니다. 다른 GPU 프로그램을 함께 사용해 메모리가 부족한 환경에서는 .env의 YUE2_NAR_QUERY_CHUNK_SIZE를 512 또는 256으로 낮출 수 있습니다.

## 2. Gemini

저장소 루트의 .env 파일에서 인증 방식을 설정합니다. Google AI Studio API 키 방식:

    GEMINI_PROVIDER=api-key
    GEMINI_API_KEY=여기에_AI_Studio_API_키

저장한 뒤 start_team_tool.bat으로 서버를 시작합니다. .env는 Git에서 제외되며 이미 설정된 시스템 환경변수가 있으면 시스템 값이 우선합니다.

Vertex AI 방식은 프로젝트에서 Vertex AI API를 활성화하고 실행 계정에 Vertex AI User 권한을 부여한 뒤 ADC(Application Default Credentials)를 준비합니다.

    GEMINI_PROVIDER=vertex
    GEMINI_VERTEX_PROJECT=Google Cloud 프로젝트 ID
    GEMINI_VERTEX_LOCATION=us-central1

개발 PC에서는 서버 실행 전에 gcloud auth application-default login을 한 번 실행합니다.

서비스 계정으로 운영할 때는 `GOOGLE_APPLICATION_CREDENTIALS`를 설정하거나 해당 런타임의 기본 서비스 계정을 사용하면 됩니다. `GEMINI_VERTEX_PROJECT` 대신 `GOOGLE_CLOUD_PROJECT`도 인식합니다. 리전은 기본 `us-central1`이며 Vertex 전역 엔드포인트를 사용할 경우 `global`로 지정합니다.

`GEMINI_PROVIDER`를 생략하면 API 키를 우선 사용하고, 키가 없으면 Vertex 프로젝트 설정을 감지합니다. 기본 모델은 gemini-3.8-flash이며 다른 모델은 `GEMINI_MUSIC_MODEL`로 지정할 수 있습니다. API 키와 Google 자격 증명은 브라우저에 전달하거나 DB에 저장하지 않습니다.

대형 기획서는 기본 2MB·50만 자까지 입력할 수 있습니다. Gemini 출력은 4096토큰, Thinking 예산은 1024토큰입니다. 프로젝트 규모와 비용 정책에 따라 .env에서 GEMINI_MUSIC_MAX_DOCUMENT_CHARS, GEMINI_MUSIC_MAX_MARKDOWN_BYTES, GEMINI_MUSIC_MAX_OUTPUT_TOKENS, GEMINI_MUSIC_THINKING_BUDGET 값을 조정할 수 있습니다.

## 3. Notion 기획서

Notion에서 기획서를 Markdown으로 내보낸 뒤 BGM 화면에서 .md 또는 .markdown 파일을 선택합니다. 브라우저가 파일을 읽어 입력란에 채우며 서버에는 Gemini 분석에 필요한 텍스트만 전달합니다. Notion integration이나 API 토큰은 필요하지 않습니다.

## 4. 결과

결과는 outputs/music/<작업 ID>/에 저장됩니다.

- audio.flac: 48kHz BGM
- score.abc: 악보 계획을 사용한 경우 생성되는 ABC 악보
- request.json, result.json: 실제 프롬프트와 생성 메타데이터

BGM 결과와 프롬프트는 로그인한 팀원 갤러리에서만 볼 수 있습니다.

## 라이선스

YuE2 코드와 모델 가중치의 라이선스는 서로 다릅니다. 개인 창작자의 생성물 수익화 허용과 회사의 모델 가중치 상업 사용 조건이 다르므로 배포 주체에 맞게 vendor/YuE/MODEL_LICENSE를 확인하세요.
