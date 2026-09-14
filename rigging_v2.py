"""Build an on-demand Unity 2D Animation skeleton package from a V1 rig."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import zipfile

from PIL import Image


V2_FILENAME = "character-unity-skeleton.zip"


def _number(value, fallback: float) -> float:
    return float(value) if isinstance(value, (int, float)) else float(fallback)


def _silhouette_bounds(folder: Path, manifest: dict) -> tuple[int, int, int, int]:
    composite_path = folder / "composite.png"
    with Image.open(composite_path) as opened:
        alpha = opened.convert("RGBA").getchannel("A")
        bounds = alpha.getbbox()
    if bounds:
        return bounds
    canvas = manifest["canvas"]
    return 0, 0, int(canvas["width"]), int(canvas["height"])


def build_skeleton(manifest: dict, bounds: tuple[int, int, int, int]) -> dict:
    """Create a conservative humanoid draft in top-left canvas coordinates."""
    x0, y0, x1, y1 = bounds
    width, height = max(1.0, x1 - x0), max(1.0, y1 - y0)
    anchors = manifest.get("anchors") or {}
    face = anchors.get("face") or {}
    neck_anchor = anchors.get("neckPivot") or {}
    center_x = _number(face.get("cx"), (x0 + x1) * 0.5)
    head_y = _number(face.get("cy"), y0 + height * 0.12)
    neck_x = _number(neck_anchor.get("cx"), center_x)
    neck_y = _number(neck_anchor.get("cy"), y0 + height * 0.24)
    neck_y = min(y0 + height * 0.34, max(head_y + height * 0.06, neck_y))
    pelvis_y = y0 + height * 0.56
    pelvis_x = neck_x * 0.65 + ((x0 + x1) * 0.5) * 0.35
    chest_y = neck_y + (pelvis_y - neck_y) * 0.42
    spine_y = neck_y + (pelvis_y - neck_y) * 0.72
    shoulder_half = max(width * 0.13, height * 0.07)
    hip_half = max(width * 0.075, height * 0.035)
    arm_drop = height * 0.17
    leg_length = max(height * 0.36, y1 - pelvis_y)
    knee_y = pelvis_y + leg_length * 0.52
    ankle_y = min(y1 - 1, pelvis_y + leg_length * 0.94)

    points = {
        "hips": (pelvis_x, pelvis_y),
        "spine": (pelvis_x, spine_y),
        "chest": (neck_x, chest_y),
        "neck": (neck_x, neck_y),
        "head": (center_x, head_y),
        "shoulder_l": (neck_x - shoulder_half, chest_y),
        "arm_l": (neck_x - shoulder_half * 1.65, chest_y + arm_drop * 0.48),
        "hand_l": (neck_x - shoulder_half * 2.05, chest_y + arm_drop),
        "shoulder_r": (neck_x + shoulder_half, chest_y),
        "arm_r": (neck_x + shoulder_half * 1.65, chest_y + arm_drop * 0.48),
        "hand_r": (neck_x + shoulder_half * 2.05, chest_y + arm_drop),
        "leg_l": (pelvis_x - hip_half, pelvis_y),
        "knee_l": (pelvis_x - hip_half * 1.15, knee_y),
        "foot_l": (pelvis_x - hip_half * 1.25, ankle_y),
        "leg_r": (pelvis_x + hip_half, pelvis_y),
        "knee_r": (pelvis_x + hip_half * 1.15, knee_y),
        "foot_r": (pelvis_x + hip_half * 1.25, ankle_y),
    }
    hierarchy = [
        ("hips", None), ("spine", "hips"), ("chest", "spine"),
        ("neck", "chest"), ("head", "neck"),
        ("shoulder_l", "chest"), ("arm_l", "shoulder_l"), ("hand_l", "arm_l"),
        ("shoulder_r", "chest"), ("arm_r", "shoulder_r"), ("hand_r", "arm_r"),
        ("leg_l", "hips"), ("knee_l", "leg_l"), ("foot_l", "knee_l"),
        ("leg_r", "hips"), ("knee_r", "leg_r"), ("foot_r", "knee_r"),
    ]
    bones = []
    for index, (name, parent) in enumerate(hierarchy):
        x, y = points[name]
        children = [child for child, owner in hierarchy if owner == name]
        if children:
            cx, cy = points[children[0]]
            length = max(8.0, ((cx - x) ** 2 + (cy - y) ** 2) ** 0.5)
        else:
            length = max(8.0, height * 0.055)
        bones.append({"name": name, "parent": parent, "x": round(x, 3), "y": round(y, 3), "length": round(length, 3)})

    return {
        "schemaVersion": 1,
        "kind": "unity-2d-animation-draft",
        "canvas": manifest["canvas"],
        "bounds": {"left": x0, "top": y0, "right": x1, "bottom": y1},
        "bones": bones,
        "mesh": {"columns": 5, "rows": 5, "maxInfluences": 2},
        "warnings": [
            "전신 본 위치는 레이어와 얼굴·목 앵커로 계산한 자동 초안입니다.",
            "측면 자세, 교차한 팔, 무기와 가려진 팔다리는 Unity Skinning Editor에서 보정하세요.",
        ],
    }


def build_package(folder: Path, unity_root: Path, source_revision: int) -> dict:
    folder = folder.resolve()
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    v1_path = folder / "character-unity-parts.zip"
    if not v1_path.is_file():
        raise FileNotFoundError("V1 Unity 패키지를 찾을 수 없습니다.")
    if not (unity_root / "Editor" / "RiggingV2Importer.cs").is_file():
        raise FileNotFoundError("V2 Unity importer를 찾을 수 없습니다.")

    rig = build_skeleton(manifest, _silhouette_bounds(folder, manifest))
    rig["sourceRevision"] = int(source_revision)
    output = folder / V2_FILENAME
    with tempfile.TemporaryDirectory(prefix="rig-v2-", dir=folder) as raw:
        staged = Path(raw) / V2_FILENAME
        with zipfile.ZipFile(v1_path) as source, zipfile.ZipFile(staged, "w", compression=zipfile.ZIP_DEFLATED) as target:
            replaced = {"rig-v2.json", "UNITY_V2_IMPORT.md"}
            for record in source.infolist():
                if record.filename in replaced or record.filename.startswith("UnityV2/"):
                    continue
                target.writestr(record, source.read(record.filename))
            target.writestr("rig-v2.json", json.dumps(rig, ensure_ascii=False, indent=2))
            target.writestr("UNITY_V2_IMPORT.md", """# Unity 2D Animation V2 import

1. Unity 2022.3 LTS 프로젝트에 `2D Animation` 패키지 9.x를 설치합니다.
2. ZIP의 `Unity/Runtime`과 `UnityV2/Runtime`, `UnityV2/Editor`를 프로젝트의 `Assets` 아래에 복사합니다.
3. Unity 메뉴 `Tools > Sprite Lab > Import Rigging V2 ZIP`에서 이 ZIP을 선택합니다.
4. 생성된 `RiggingV2Avatar.prefab`에는 공유 전신 본, 각 파츠의 메시와 자동 웨이트, 눈·입 컨트롤이 들어 있습니다.
5. Sprite Editor의 Skinning Editor에서 본 위치와 웨이트를 캐릭터 자세에 맞게 보정합니다.

V2는 자동 리깅 초안입니다. 측면 자세, 겹친 팔다리, 무기와 긴 머리카락은 수동 보정이 필요합니다.
""")
            for item in sorted(unity_root.rglob("*.cs")):
                target.write(item, "UnityV2/" + item.relative_to(unity_root).as_posix())
        if staged.stat().st_size < 1024:
            raise RuntimeError("V2 Unity 패키지 생성 결과가 비어 있습니다.")
        with zipfile.ZipFile(staged) as check:
            if check.testzip() is not None:
                raise RuntimeError("V2 Unity 패키지 검증에 실패했습니다.")
        shutil.copy2(staged, output)
    return {"path": output, "bones": len(rig["bones"]), "sourceRevision": int(source_revision), "warnings": rig["warnings"]}
