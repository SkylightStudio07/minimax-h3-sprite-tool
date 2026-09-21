# 반응형 스튜디오 UI 인수인계

## 범위

- `web/team.html`: 로그인 랜딩, 공개 갤러리, PC 사이드바 / 모바일 가로 탐색, 작업 현황, 공통 색상과 반응형 스타일.
- `web/index.html`: 원본 이미지 / 움직임 설정 구분과 업로드 안내.
- `web/music.html`: 사용자 중심의 음악 설정 안내 문구. 기존 모드와 요청 데이터는 유지.
- 리깅 편집기, 인증 API, 생성 엔진, 큐 데이터는 변경하지 않음.

## 구조와 유지보수

- 서버에 새 정적 파일 라우트를 추가하지 않아 기존 배치 실행 방식을 그대로 사용한다.
- `studio-shell` 스타일은 메인 화면에, `tool-theme` 스타일은 같은 출처의 생성 iframe에 적용한다. `tool-theme`은 메인 문서에서는 `media="not all"`로 비활성화하고 iframe 로드 시 복사한다.
- 도구 화면은 처음 선택할 때 지연 로드한다. 이후 탭 전환에서는 iframe을 유지해 입력값을 보존한다. 로그아웃 시 iframe과 크기 관찰을 해제한다.
- `ResizeObserver`가 iframe 본문 높이를 측정한다. 숨긴 탭은 측정하지 않고 다시 선택할 때 갱신한다. 별도 도구 페이지를 직접 열면 해당 페이지의 기존 스타일이 유지된다.
- 850px 이하에서는 사이드바가 가로 스크롤 탐색으로 전환된다. 좁은 화면에서는 폼과 갤러리를 한 열로 표시한다.
- 키보드 포커스 표시 및 동작 줄이기 설정을 지원한다.

## 검증

`tools/test_responsive_ui.cjs`는 Playwright + 설치된 Chrome을 사용한다. Playwright가 모듈 검색 경로에 있어야 한다.

```powershell
node tools/test_responsive_ui.cjs
.\.venv\Scripts\python.exe -m unittest test_team_server test_music_prompts test_sprite_prompts
git diff --check
```

브라우저 테스트는 `sprite-lab.test`의 모든 요청을 가로채 로컬 HTML과 가짜 API 응답으로 처리한다. 실제 사용자 계정이나 GPU 작업을 생성하지 않는다. 1440 / 1024 / 768 / 390 / 320px에서 로그인·가입 전환, 작업 탭, iframe 높이, BGM 모드, 갤러리, 로그아웃을 검사하고 임시 폴더에 화면 캡처를 저장한다.

실제 사이트 검증은 서버가 실행 중일 때 별도로 수행한다. HTML 변경만으로는 서버 재시작이 필요하지 않으며, 서버가 꺼져 있다면 기존 `start_team_tool_https.bat`로 실행한다.
