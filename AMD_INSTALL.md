# AMD Radeon 설치 가이드 — 실험 지원

대상: Windows 11 x64, RX 9070 XT 16GB 등 해당 ROCm 버전이 지원하는 Radeon.
**이 저장소의 AMD 경로는 코드·설정 검사만 했으며 AMD 실기기 H3 생성은 미검증입니다.**
PyTorch의 GPU 인식 성공과 H3 영상 생성 성공은 다른 단계입니다.

## 메모리와 준비물

- 시스템 RAM **32GB 이상을 실사용 권장 시작점**으로 잡습니다. 32GB라도 긴 영상/고해상도/병행 프로그램 때문에 메모리가 부족할 수 있습니다.
- 9070 XT의 16GB VRAM은 시스템 RAM 32GB와 별개입니다. 모자란 VRAM을 RAM으로 오프로딩하면 실행되더라도 느릴 수 있습니다.
- 설치 스크립트는 물리 RAM을 출력하고, 약 32GB 미만(예약 메모리를 고려해 30GiB 미만)이면 중단합니다.
- Python 3.12 x64와 Python Launcher(`py`), Git for Windows가 필요합니다.
- 모델·환경·캐시·출력 공간까지 고려해 여유 공간을 충분히 확보하세요. AMD 인코더는 NVIDIA NVFP4보다 크며 모델만 수십 GB입니다. 별도 환경을 두 개 설치하면 공간도 중복됩니다.

## 이 설치 옵션의 고정 조합

| 항목 | 설정 |
| --- | --- |
| PyTorch / torchvision / torchaudio | 2.9.1 / 0.24.1 / 2.9.1, ROCm 7.2.1 빌드 |
| ComfyUI | 새 설치는 v0.34.0 |
| 영상 모델 | MiniMax H3 FL2VA pruned INT8 ConvRot |
| 텍스트 인코더 | Qwen3VL H3 INT8 ConvRot (NVFP4 아님) |
| 가상환경 / ComfyUI | `.venv-amd` / `ComfyUI-amd` |

드라이버는 ROCm 버전과 맞아야 합니다. AMD의 7.2.1 설치 문서는 Adrenalin 26.2.2를 명시합니다. 더 최신 ROCm을 임의로 섞지 마세요. 이 스크립트는 드라이버 설치·다운그레이드나 보안 설정 변경을 하지 않습니다.

## 설치 순서

1. 새 폴더에 이 저장소를 clone합니다. 다른 PC의 `.venv`를 복사하지 마세요.
2. [AMD 공식 7.2.1 설치 문서](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2.1/docs/install/installrad/windows/install-pytorch.html)의 드라이버·지원 GPU 조건을 확인하세요.
3. `setup_windows_amd.bat` 실행. RAM/GPU 표시를 확인하고 `INSTALL` 입력.
4. 전용 가상환경, 공식 ROCm 휠, ComfyUI 및 앱 의존성을 설치합니다. 버전 제약으로 CUDA/CPU PyTorch로 교체되는 것을 막고, 의존성 충돌 시 중단합니다.
5. 마지막에 ROCm 빌드 여부·GPU 인식·작은 행렬 연산을 검사합니다. 여기서 실패하면 모델을 받기 전에 해결하세요.
6. 모델 라이선스와 필요한 별도 사용 승인을 확인한 경우에만 `download_h3_models_amd.bat` 실행. 로컬 승인 마커는 사용 권한을 부여하는 문서가 아닙니다.
7. `start_team_tool_amd.bat` 실행 → `http://127.0.0.1:7866`.
8. 첫 관리자 등록과 계정 승인은 [팀 서버 안내](TEAM_SETUP.md)를 따르세요.

AMD 실행 배치는 `SPRITE_BACKEND=amd`를 프로세스에만 설정합니다. 일반 NVIDIA 실행 배치는 기존 경로를 유지합니다. 같은 폴더에서는 데이터·출력·포트를 공유하므로 두 서버/ComfyUI 백엔드를 동시에 켜지 마세요.

HTTPS 역방향 프록시 뒤에서는 `start_team_tool_amd_https.bat`을 사용합니다. 일반 로컬 HTTP 접속은 HTTPS 배치가 아닌 일반 배치를 쓰세요.

## 첫 실제 생성 점검

1. 우선 작은 입력, 빠른 해상도, 3초, 8프레임, 네거티브 꺼짐으로 테스트합니다.
2. Turbo에서 실패하거나 형태가 깨지면 작은 해상도의 일반 20스텝으로 비교합니다. 가속 LoRA 성공을 기본 모델 성공과 구분하세요.
3. `logs/comfy.stderr.log`에서 오류를 확인하고 결과가 검은 영상인지, 참조 이미지가 반영되는지 확인합니다.
4. 성공 후 해상도와 길이를 하나씩 늘리세요. 생성 시간은 실제 측정해서 기록하며 NVIDIA 속도를 그대로 예상하지 마세요.
5. 잘 나온 영상은 갤러리에서 64프레임 시트로 재추출할 수 있습니다. AI 생성은 다시 실행하지 않습니다.

## 오류가 날 때

- `torch.version.hip`가 비어 있음: 다른 PyTorch 빌드입니다. NVIDIA 설치 배치를 AMD 환경에 실행하지 마세요.
- GPU 인식 실패 / DLL 로드 오류: Python 3.12 x64, ROCm과 드라이버 조합을 먼저 확인하세요. 보안 기능을 무작정 끄지 마세요.
- 의존성 충돌: 설치는 실패한 상태입니다. 제약 파일을 지워 강제 진행하지 말고 오류와 버전을 기록하세요.
- NVFP4 관련 오류: AMD 실행 배치와 INT8 인코더 다운로드 여부를 확인하세요.
- 검은 출력 / NaN / LoRA 오류: 가속 옵션을 줄이고 기본 모델부터 확인하세요. 커스텀 로더·Triton 패치를 무작정 여러 개 설치하지 마세요.
- 메모리 부족: 길이·해상도를 낮추고 다른 GPU 프로그램을 종료하세요. Windows 페이지 파일은 시스템 관리 상태로 충분한 디스크 여유를 확보하되, RAM/VRAM을 대체하는 성능 해결책으로 보지 마세요.
- ComfyUI 버전 업데이트: 스크립트는 기존 체크아웃을 자동으로 pull하지 않습니다. 재현 가능한 조합을 먼저 보관하고 별도 환경에서 검증하세요.

## 참고 근거와 한계

- [AMD Windows 지원표](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2.1/docs/compatibility/compatibilityrad/windows/windows_compatibility.html): 하드웨어/프레임워크 지원 확인용. 우리 앱 검증을 뜻하지 않습니다.
- [Windows Radeon H3 실행 프로젝트](https://github.com/mitsuharu/ComfyUI-ROCm): INT8 인코더를 이용한 Radeon 실행 참고 사례입니다. 현재 문서의 최신 조합이 여기 고정 버전과 다를 수 있습니다.
- [ROCm INT8 로더 개발 문서](https://github.com/patientx/ComfyUI-INT8-Fast-ROCM): 연산 호환성 참고용이며 이 저장소는 해당 커스텀 노드를 자동 설치하지 않습니다.

문제가 생기면 Windows/드라이버 버전, RAM·VRAM, PyTorch/ROCm 버전, ComfyUI 커밋, 설정, 오류 로그를 함께 전달하세요. 비밀번호·세션·원본 이미지가 포함된 DB는 공유하지 마세요.
