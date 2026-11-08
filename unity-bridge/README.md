# Sprite Lab Unity Importer

Unity 2022.3 LTS용 V1/V2 임포터와 `spritelab-unity://` Windows 딥링크 수신기입니다.

0.4.0은 웹 타임라인 클립 가져오기를 지원합니다. 이전 임포터를 설치했다면 사이트에서 새 ZIP을 받아 기존 패키지 폴더를 업데이트하세요. 기록한 동작이 있는 V2는 `Animations/*.anim`과 `RiggingV2ClipPlayer`를 생성합니다. 런타임에서 `GetComponent<RiggingV2ClipPlayer>().Play("클립 이름")`으로 재생하고 `Stop()`으로 기존 idle로 돌아갑니다.

1. 사이트에서 **Unity 임포터 받기**를 눌러 ZIP을 받고 압축을 풉니다.
2. ZIP 안의 `com.skylight.sprite-lab` 폴더를 Unity 프로젝트의 `Packages` 폴더 안에 둡니다.
3. Unity가 2D Animation 9.x와 스크립트를 불러올 때까지 기다립니다.
4. Sprite Lab 결과 갤러리에서 **Unity에서 열기**를 누릅니다.

패키지를 불러온 프로젝트가 원클릭 대상으로 자동 등록됩니다. 다른 프로젝트로 바꾸려면 그 프로젝트를 열거나 `Tools > Sprite Lab > One-click Link > Enable for this project`를 실행하세요.

가져온 폴더에는 월드용 `RiggingV2Avatar.prefab`과 Canvas용 `RiggingV2Portrait.prefab`이 함께 생성됩니다. UI 프리팹은 Canvas 아래에 배치하고 Play 모드에서 확인하세요.
`RiggingV2Portrait` 인스펙터에서 눈 깜빡임·입, 머리카락·의상 흔들림, 몸·머리·호흡 대기 모션을 직접 조정할 수 있습니다.
