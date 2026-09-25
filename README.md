# MiniMax H3 Sprite Motion Tool

MiniMax H3와 ComfyUI를 이용해 기준 이미지 한 장에서 캐릭터 동작 영상과 스프라이트 시트를 만드는 Windows 로컬 도구입니다.

예시 :  

<img width="832" height="1216" alt="idle" src="https://github.com/user-attachments/assets/3eb02ecb-b94d-48e8-9971-6fb2c513f18d" />
<img width="768" height="1344" alt="idle (5)" src="https://github.com/user-attachments/assets/bbcb2988-ea0a-42f9-a44d-e1f047887822" />

- 원본 종횡비 유지 및 32픽셀 단위 자동 해상도 계산
- Idle, Walk, Run, Attack, Cast, Hit, Death, Jump, Custom 동작
- 루프/1회 동작과 캐릭터 방향 고정
- 투명 입력용 중간 회색 매트 및 배경 고정 프롬프트
- 원본 영상, 정규화 영상, PNG 스프라이트 시트 저장
- RTX 5060 Ti 16GB에서 검증 / RX 9070 XT용 AMD 설치 경로는 실험 지원
- 인간형·생물/괴물·부유 기계·지상 기계 템플릿과 조준 대기 세팅
- 2~64프레임 시트, 기존 영상 재추출, 선택형 단색 누끼, 동작 여백
- 계정 승인·팀 대기열·공개 갤러리·6개 단위 페이지·가이드 탭
- See-through/Qwen 기반 2D 레이어 분리와 눈·눈썹·입 마스크
- Live2D풍 웹 미리보기, 레이어 편집·원본 복원·병합, 작업 버전 관리
- PSD와 Unity V1/V2 패키지, 내부 공유, 관리자 선별 공개 Live2D 워크스페이스
- YuE2 게임 BGM 생성, Gemini/Vertex 기획서 분석, 직접 프롬프트와 보컬/인스트루멘털 모드

## 2D 리깅·Live2D풍 도구

로그인 후 **2D 리깅** 탭에서 이미지 한 장을 레이어와 표정 파츠로 분리할 수 있습니다. 결과 갤러리의 레이어 편집기는 지우기, 생성 직후 픽셀 복원, 업로드 원본 복원, 레이어 순서 변경과 복원 레이어 병합을 지원합니다. 결과는 PSD, Unity V1 파츠 패키지 또는 V2 스켈레톤 초안으로 받을 수 있습니다.

이 기능은 Live2D Cubism `.moc3` 모델을 생성하지 않습니다. 분리된 파츠와 Anime2.5DRig/Unity 런타임으로 Live2D와 비슷한 효과를 만듭니다.

개발·운영 구조, 공유 정책, API, 테스트와 배포 절차는 `G:\111\docs\LIVE2D_TOOL_HANDOFF.md`를 참고하세요. 레이어 편집 단축키와 원본 복원·병합 방법은 `G:\111\docs\LAYER_EDITING_GUIDE.md` 또는 웹의 **가이드** 탭에서 확인할 수 있습니다.

## YuE2 게임 BGM 도구

로그인 후 **게임 BGM** 탭에서 Markdown 기획서를 Gemini로 분석하거나 기본 프리셋·직접 프롬프트를 사용해 YuE2 음악을 생성할 수 있습니다. Google AI Studio API 키와 Vertex AI 서비스 계정을 지원하며, 보컬곡은 Style과 Lyrics를 분리해 전달합니다.

인스트루멘털 모드는 빈 섹션 구조로 악보를 계획한 뒤 ABC의 Vocal 음표를 같은 길이의 쉼표로 바꾸어 합성합니다. 설치와 사용자 설정은 [BGM_SETUP.md](BGM_SETUP.md), 개발·운영·테스트 인수인계는 [DOCS/YUE2_BGM_HANDOFF.md](DOCS/YUE2_BGM_HANDOFF.md)를 참고하세요.

## 먼저 확인하세요

**실사용을 시작할 권장 시스템 RAM은 32GB 이상입니다. GPU의 VRAM과는 별개입니다.**
32GB는 모든 해상도·모델에서 정상 동작을 보장하는 수치가 아닙니다. AMD INT8 인코더와 고해상도 영상은 RAM/VRAM 부담이 크며, 다른 프로그램을 함께 쓰면 더 여유 있는 메모리가 필요합니다.

현재 NVIDIA 경로는 RTX 5060 Ti 16GB에서 검증했습니다. AMD 경로는 Windows 11 + RX 9070 XT 16GB를 위한 **설치 옵션이며 이 저장소에서는 AMD 실생성을 아직 검증하지 않았습니다.**

## 빠른 시작

1. Git for Windows와 Python 3.12 x64를 설치한 뒤 저장소를 clone합니다.
2. NVIDIA는 `setup_windows.bat`
3. MiniMax H3 라이선스상 사용할 권한이 있는 경우에만 `download_h3_models.bat`
4. 팀 UI는 `start_team_tool.bat` (단독 UI는 `start_idle_tool.bat`, 동시 실행 금지)
5. 브라우저에서 `http://127.0.0.1:7866`

AMD는 **[AMD 설치 가이드](AMD_INSTALL.md)**를 먼저 읽고 `setup_windows_amd.bat` → `download_h3_models_amd.bat` → `start_team_tool_amd.bat` 순서로 진행합니다. 기존 NVIDIA 가상환경을 재사용하지 않습니다.

자세한 설치, 메모리 및 출력 설명은 [README_KO.md](README_KO.md)를 참고하세요.

## 생성 전 알아둘 점

- 기본 생성은 **일반 20스텝**입니다. 빠른 테스트는 Turbo 4스텝·3초·낮은 해상도로 시작하세요.
- RTX 5060 Ti에서 832×1216·5초·일반 20스텝이 약 24분 걸린 사례가 있습니다. 예전 Turbo 수십 초 기록과 같은 설정이 아닙니다.
- 시트 프레임을 8에서 64로 늘려도 AI 영상 생성 스텝은 늘지 않습니다. 잘 나온 영상은 갤러리에서 시트만 재추출하세요.
- 투명 PNG 입력도 생성 영상에서는 RGB 배경으로 합성됩니다. ‘배경 고정’은 투명 출력 기능이 아닙니다.
- 큰 시트는 게임 엔진의 텍스처 최대 크기와 메모리를 확인하세요. 비동기 로딩이 텍스처 메모리를 없애지는 않습니다.
- 완성 결과는 로그인 없이 공개 갤러리에서 볼 수 있습니다. 민감한 이미지/결과를 사용하지 마세요.
- 기능별 상세 안내는 웹의 **가이드 탭**에서도 확인할 수 있습니다.

## 팀 공동 사용

`start_team_tool.bat`으로 로그인·관리자 승인·공용 대기열·결과 갤러리가 있는 팀 서버를 실행합니다. 첫 관리자 등록과 외부 연결 준비는 [TEAM_SETUP.md](TEAM_SETUP.md)를 참고하세요. 기존 단독 서버와 동시에 실행하지 마세요.

## 라이선스 주의

모델 가중치는 이 저장소에 포함되지 않습니다. MiniMax H3 Community License의 지역 및 용도 제한을 직접 확인하고 필요한 승인을 받은 경우에만 모델을 다운로드하고 사용하세요. 이 저장소는 모델 사용 권한을 부여하지 않습니다.
