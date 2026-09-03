# MiniMax H3 Sprite Motion Tool

MiniMax H3와 ComfyUI를 이용해 기준 이미지 한 장에서 캐릭터 동작 영상과 스프라이트 시트를 만드는 Windows 로컬 도구입니다.

- 원본 종횡비 유지 및 32픽셀 단위 자동 해상도 계산
- Idle, Walk, Run, Attack, Cast, Hit, Death, Jump, Custom 동작
- 루프/1회 동작과 캐릭터 방향 고정
- 투명 입력용 중간 회색 매트 및 배경 고정 프롬프트
- 원본 영상, 정규화 영상, PNG 스프라이트 시트 저장
- RTX 5060 Ti 16GB에서 검증

## 빠른 시작

1. `setup_windows.bat`
2. MiniMax H3 라이선스상 사용할 권한이 있는 경우에만 `download_h3_models.bat`
3. `start_idle_tool.bat`
4. 브라우저에서 `http://127.0.0.1:7866`

자세한 설치, 메모리 및 출력 설명은 [README_KO.md](README_KO.md)를 참고하세요.

## 라이선스 주의

모델 가중치는 이 저장소에 포함되지 않습니다. MiniMax H3 Community License의 지역 및 용도 제한을 직접 확인하고 필요한 승인을 받은 경우에만 모델을 다운로드하고 사용하세요. 이 저장소는 모델 사용 권한을 부여하지 않습니다.
