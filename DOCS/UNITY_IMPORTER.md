# Sprite Lab Unity 임포터

Sprite Lab의 V2 스켈레톤 결과를 Unity 2022.3 LTS 프로젝트로 가져오는 편집기 확장입니다. 웹의 **Unity에서 열기** 버튼은 Asset Store 전용 주소 대신 `spritelab-unity://` 링크를 사용합니다.

## 최초 설치

1. 로그인한 뒤 결과 갤러리에서 **Unity 임포터 받기**를 누릅니다.
2. ZIP을 풀고 `com.skylight.sprite-lab` 폴더 전체를 Unity 프로젝트의 `Packages` 폴더에 복사합니다.
3. Unity Package Manager에서 `2D Animation` 9.x가 설치되고 컴파일이 끝날 때까지 기다립니다.
4. 패키지 컴파일이 끝나면 현재 프로젝트가 원클릭 대상으로 자동 등록됩니다.

한 PC에서 대상 프로젝트를 바꾸려면 새 프로젝트를 열거나 그 프로젝트에서 **Tools > Sprite Lab > One-click Link > Enable for this project**를 실행합니다. 여러 Unity 프로젝트가 열려 있어도 마지막으로 등록한 프로젝트만 요청을 받습니다.

## 사용

1. Sprite Lab 결과 갤러리에서 현재 레이어 버전의 **V2 스켈레톤 생성**을 누릅니다.
2. 생성이 끝나고 갤러리를 새로 불러오면 **Unity에서 열기**가 표시됩니다.
3. 브라우저의 외부 앱 열기 확인을 승인합니다.
4. Unity가 닫혀 있으면 등록된 프로젝트가 실행됩니다. 열려 있으면 해당 창이 활성화됩니다.
5. 처음 연결하는 서버 주소는 Unity에서 한 번 더 확인합니다.

가져온 결과는 `Assets/RiggingV2/Imported/<이름_시간>/` 아래에 두 가지로 만들어집니다.

- `RiggingV2Avatar.prefab`: 필드 캐릭터와 월드 오브젝트용 `SpriteRenderer` 프리팹
- `RiggingV2Portrait.prefab`: Canvas 아래에 바로 넣는 `RawImage` UI 프리팹

UI 프리팹은 Play 모드에서 전용 투명 카메라와 RenderTexture를 자동 생성합니다. 에디터의 정지 상태에서는 RawImage가 비어 있는 것이 정상이며, 실행하면 본·표정·자동 대기 모션이 표시됩니다. RectTransform 크기가 바뀌면 출력 해상도도 최대 1024픽셀 범위에서 자동 조정됩니다.

`RiggingV2Portrait` 컴포넌트에는 다음 설정이 직접 표시됩니다.

- **Eyes and mouth**: 자동 눈 깜빡임, 간격·지속 시간, 자동 립싱크, 입 열림 정도
- **Hair, equipment, and cloth**: 머리카락 흔들림 각도·속도, 장비·의상 흔들림 각도
- **Body idle**: 몸통 흔들림, 머리 따라오기, 호흡 크기, 상체 상하 움직임(`bodyBob`), 전체 대기 모션 속도

Play 모드에서 값을 바꾸면 숨겨진 실제 아바타 인스턴스에 즉시 반영됩니다. 원본 파츠에 해당 분류가 없으면 관련 흔들림 값은 효과가 없습니다.

머리카락 파츠(이름에 `hair`가 들어간 레이어)는 가져올 때 머리 뼈 아래에 `hair_<파츠>` 뼈가 자동으로 추가됩니다. 정수리 쪽은 머리 뼈를, 끝으로 갈수록 이 뼈를 따르도록 가중치가 들어가며, 머리카락 흔들림은 이 뼈를 회전시킵니다. 이 기능이 생기기 전에 가져온 폴더는 Project 창에서 폴더를 선택하고 **Tools > Sprite Lab > Reimport Selected Rigging V2 Folder**를 실행하면 ZIP 없이 그 자리에서 다시 생성됩니다. 같은 경로에 프리팹을 다시 저장하므로 씬에 배치한 프리팹 참조와 설정값은 유지됩니다.

스크립트에서 표정 등을 제어하려면 `RiggingV2Portrait.AvatarInstance`로 렌더링 중인 실제 캐릭터 인스턴스에 접근할 수 있습니다.

## V1 파츠 프리팹

**Tools > Sprite Lab > Import Rigging V1 ZIP**으로 가져오면 `Assets/RiggingV1/Imported/` 아래에 프리팹이 생깁니다. 구조는 `루트(SortingGroup) > Body > Head`이고, 얼굴·머리카락·모자·표정은 Head 아래에 있습니다.

- 대기 동작: 깜박임, 입, 머리카락·장비·치마 흔들림에 더해 고개 기울임, 몸 흔들림, 호흡이 있습니다. 크기는 `RiggingV1Avatar` Inspector에서 조절합니다. 캐릭터마다 시작 시점이 달라 여럿을 세워도 똑같이 움직이지 않습니다.
- 회전축: 치마는 허리, 장비는 겹치는 손 위치에서 돕니다. 손과 겹치지 않으면 몸에 가장 가까운 지점을 씁니다.
- 표정: `SetExpression("이름")`, `ClearExpression()`, `ExpressionNames`. 사이트에서 보관한 차분 이름을 그대로 씁니다.
- 갱신: 폴더를 선택하고 **Reimport Selected Rigging V1 Folder**를 실행하거나, 새 ZIP으로 **Update Selected Rigging V1 Folder From ZIP**을 실행합니다. 같은 자리에 프리팹을 다시 저장하므로 씬 연결이 유지됩니다.

- 시선과 입체감: 고개를 돌리면 앞머리·이목구비는 그쪽으로, 뒷머리와 귀는 반대로 움직여 깊이가 생깁니다. Inspector의 `Look Target`에 오브젝트를 넣으면 따라보고, 코드에서는 `SetLook(방향)`, `LookAt(월드 좌표)`, `ClearLook()`을 씁니다. 세기는 `Parallax`, 대기 중 시선 흔들림은 `Idle Look`으로 조절합니다.

이전에 가져온 폴더는 임포터를 받아 교체한 뒤 위 Reimport를 한 번 실행해야 새 구조가 적용됩니다. 목 기준점이 없는 오래된 패키지는 예전처럼 평평한 구조로 만들어집니다.

## 스프라이트 시트

사이트의 게임용 시트나 `sprite_sheet_cli`, `sprite_pack_cli` 결과(PNG + JSON)를 슬라이스, 애니메이션 클립, Animator Controller, 프리팹으로 만듭니다. 결과는 `Assets/SpriteLab/Sheets/<이름>/`에 생깁니다.

- **Tools > Sprite Lab > Import Sprite Sheet JSON**: 시트 하나를 가져옵니다.
- **Tools > Sprite Lab > Import Sprite Sheet Folder (One Character)**: 폴더의 시트를 한 캐릭터의 동작들로 묶습니다. 같은 동작이 여러 개면 파일 이름순으로 앞의 것만 씁니다.
- 프리팹의 위치가 곧 JSON의 발 기준점입니다. 시작 상태는 `idle`이고, 없으면 첫 반복 동작입니다.
- 동작 이름이 Animator 트리거입니다. `GetComponent<Animator>().SetTrigger("attack")`. 반복하지 않는 동작은 끝나면 시작 상태로 돌아갑니다.
- JSON에 fps가 있으면 그 프레임 번호로, 없으면 프레임별 시간으로 클립을 만듭니다.
- 다시 가져오면 텍스처, 스프라이트, 클립, 컨트롤러의 참조가 유지됩니다. 이미 있는 프리팹은 덮어쓰지 않으므로 게임에서 붙인 컴포넌트가 남습니다.
- 압축 설정은 건드리지 않습니다. 큰 시트의 메모리와 화질은 프로젝트의 텍스처 설정에서 정합니다.

## 보안과 문제 해결

- 다운로드 주소는 5분 뒤 만료되며 현재 V2 버전이 바뀌면 즉시 무효가 됩니다.
- Unity는 HTTPS 서버 또는 이 PC의 localhost 주소만 허용합니다.
- 웹 로그인 쿠키나 API 키는 Unity로 전달하지 않습니다.
- 버튼에 반응이 없으면 임포터 폴더 위치와 Unity 컴파일 오류를 확인한 뒤 필요할 때만 Enable을 다시 실행합니다.
- Windows 연결을 지우려면 **Tools > Sprite Lab > One-click Link > Disable**을 실행합니다.
- 자동 연결 없이도 기존 **Tools > Sprite Lab > Import Rigging V2 ZIP** 메뉴로 ZIP을 직접 가져올 수 있습니다.
- 프록시가 외부 호스트를 바꾸는 구성이라면 `.env`에 `SPRITE_PUBLIC_ORIGIN=https://공개호스트:포트`를 지정합니다. 일반 HTTPS 실행 배치는 자동으로 HTTPS 링크를 만듭니다.

## 구성

- `unity-bridge/`: UPM 메타데이터, Windows 링크 수신기, Unity 큐 감시 코드
- `unity-package/`: V1 런타임과 임포터
- `unity-v2/`: V2 런타임과 임포터
- `/unity-importer.zip`: 위 파일을 설치 가능한 단일 폴더 구조로 묶는 로그인 전용 다운로드
- `/api/jobs/<작업ID>/unity-link`: 5분짜리 서명 링크 생성
