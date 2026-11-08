"""Non-destructive paint and eraser revisions for generated rigging packages."""

from __future__ import annotations

import json
import io
import base64
import binascii
import math
import re
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile
import rigging_bones
import rigging_animation

from PIL import Image, ImageChops, ImageDraw


MAX_STROKES = 100
MAX_POINTS = 12000
MAX_BRUSH = 256.0
VERSION_FILES = ("character.psd", "character-unity-parts.zip", "composite.png", "manifest.json")
SOURCE_REFERENCE = "source-original.png"
RECOVERY_TYPES = {
    "hood": {"id": "source_headwear_hood", "runtimeName": "headwear", "sourceLayerName": "원본 복원 · 후드"},
    "headwear": {"id": "source_headwear", "runtimeName": "headwear", "sourceLayerName": "원본 복원 · 머리 장식"},
    "clothing": {"id": "source_topwear", "runtimeName": "topwear", "sourceLayerName": "원본 복원 · 옷/코트"},
    "equipment": {"id": "source_objects", "runtimeName": "objects", "sourceLayerName": "원본 복원 · 장비"},
    "fixed": {"id": "source_preserved", "runtimeName": "source preserved", "sourceLayerName": "원본 복원 · 고정 파츠"},
}


def read_manifest(folder: Path) -> dict:
    return json.loads((folder / "manifest.json").read_text(encoding="utf-8"))


def layer_records(manifest: dict) -> list[tuple[str, dict]]:
    return [(f"part:{item['id']}", item) for item in manifest.get("parts", [])] + [
        (f"expression:{item['id']}", item) for item in manifest.get("expressions", [])
    ]


def effective_layer_order(manifest: dict) -> list[str]:
    available = [key for key, _ in layer_records(manifest)]
    stored = manifest.get("layerOrder")
    return list(stored) if isinstance(stored, list) and len(stored) == len(available) and set(stored) == set(available) else available


def validate_layer_order(manifest: dict, order: object) -> list[str]:
    expected = [key for key, _ in layer_records(manifest)]
    if not isinstance(order, list) or any(not isinstance(item, str) for item in order):
        raise ValueError("레이어 순서 형식을 확인하세요.")
    if len(order) != len(expected) or len(set(order)) != len(order) or set(order) != set(expected):
        raise ValueError("레이어 순서에 빠졌거나 중복된 레이어가 있습니다.")
    return list(order)


def validate_layer_visibility(manifest: dict, visibility: object) -> dict[str, bool]:
    """Validate the editor's persisted layer visibility overrides.

    Visibility is optional for backwards compatibility.  The editor sends a
    complete snapshot, but accepting a partial mapping lets older clients keep
    working while retaining the existing values for omitted layers.
    """
    records = dict(layer_records(manifest))
    current = manifest.get("layerVisibility")
    result = {}
    if isinstance(current, dict):
        result = {key: value for key, value in current.items()
                  if key in records and isinstance(value, bool)}
    if visibility is None:
        return result
    if not isinstance(visibility, dict):
        raise ValueError("레이어 표시 상태 형식을 확인하세요.")
    for key, value in visibility.items():
        if not isinstance(key, str) or key not in records or not isinstance(value, bool):
            raise ValueError("레이어 표시 상태를 확인하세요.")
        result[key] = value
    return result


def validate_operations(manifest: dict, operations: object) -> tuple[list[dict], list[str]]:
    if not isinstance(operations, list):
        raise ValueError("편집 작업 형식을 확인하세요.")
    if len(operations) > MAX_STROKES:
        raise ValueError(f"한 번에 저장할 수 있는 작업은 {MAX_STROKES}개까지입니다.")
    parts = {key: part for key, part in layer_records(manifest)}
    width = int(manifest["canvas"]["width"])
    height = int(manifest["canvas"]["height"])
    normalized: list[dict] = []
    edited: list[str] = []
    point_count = 0
    merged_sources: set[str] = set()
    pending_rig = next((item.get('config') for item in reversed(operations) if isinstance(item, dict) and item.get('kind') == 'rig_config'), None)
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("kind", "erase") not in ("erase", "restore", "source_restore", "merge", "variant_create", "variant_apply", "variant_png", "layer_png", "paint", "rig_config", "rig_animation"):
            raise ValueError("지원하지 않는 편집 작업입니다.")
        kind = operation.get("kind", "erase")
        if kind == 'layer_png':
            key = operation.get('layerKey')
            record = parts.get(key) if isinstance(key, str) else None
            import rigging_regenerate
            if not record or not rigging_regenerate.eligible(record):
                raise ValueError('감긴 눈·입 차분 또는 object 장비 레이어를 선택하세요.')
            geometry = {k: operation.get(k) for k in ('left','top','width','height')}
            if (any(type(v) is not int for v in geometry.values()) or
                min(geometry['left'],geometry['top']) < 0 or min(geometry['width'],geometry['height']) < 1 or
                geometry['left']+geometry['width'] > width or geometry['top']+geometry['height'] > height):
                raise ValueError('재생성 레이어 위치와 크기를 확인하세요.')
            image = variant_png(operation.get('imageData'), geometry, manifest)
            if not image.getchannel('A').getbbox():
                raise ValueError('빈 레이어는 적용할 수 없습니다.')
            image.close()
            record = dict(record, **geometry)
            parts[key] = record
            normalized.append(dict(kind=kind,layerId=key,imageData=operation['imageData'],**geometry))
            edited.append(record['id'])
            continue
        if kind == 'rig_animation':
            authored = pending_rig if pending_rig is not None else operation.get('rig')
            rig = rigging_bones.validate(authored, manifest) if authored is not None else rigging_bones.get_rig(manifest)
            normalized.append({'kind':kind, 'rig':rigging_bones.validate(rig, manifest), 'config':rigging_animation.validate(operation.get('config'), rig, manifest['canvas'])})
            continue
        if kind == "rig_config":
            normalized.append({"kind": kind, "config": rigging_bones.validate(operation.get("config"), manifest)})
            continue
        if kind == "variant_create":
            target_key, variant_id, name = operation.get("targetKey"), operation.get("id"), operation.get("name")
            target = parts.get(target_key) if isinstance(target_key, str) else None
            if not target or target.get("variantOf") or not (target_key.startswith("expression:") or any(word in target["id"] for word in ("eye", "mouth", "brow"))):
                raise ValueError("눈·입·눈썹 레이어를 선택하세요.")
            if not isinstance(variant_id, str) or not re.fullmatch(r"variant_[a-z0-9_]{1,60}", variant_id) or "expression:" + variant_id in parts:
                raise ValueError("차분 ID를 확인하세요.")
            if not isinstance(name, str) or not name.strip() or len(name) > 60:
                raise ValueError("차분 이름은 1~60자로 입력하세요.")
            record = variant_record(target, target_key, variant_id, name.strip(), manifest)
            parts["expression:" + variant_id] = record
            normalized.append({"kind": kind, "record": record, "copy": operation.get("copy") is True})
            edited.append(variant_id)
            continue
        if kind in ("variant_apply", "variant_png"):
            key = operation.get("layerKey")
            record = parts.get(key) if isinstance(key, str) else None
            if not record or not record.get("variantOf"):
                raise ValueError("표정 차분을 선택하세요.")
            clean = {"kind": kind, "layerId": key}
            if kind == "variant_png":
                data = operation.get("imageData")
                image = variant_png(data, record, manifest)
                clean["imageData"] = data
                image.close()
            normalized.append(clean)
            if record["id"] not in edited:
                edited.append(record["id"])
            continue
        if kind == "merge":
            source_key = operation.get("sourceLayerKey")
            target_key = operation.get("targetLayerKey")
            if not isinstance(source_key, str) or not isinstance(target_key, str):
                raise ValueError("병합할 레이어를 확인하세요.")
            source = parts.get(source_key)
            target = parts.get(target_key)
            if not source or not source.get("sourceRecovered"):
                raise ValueError("원본에서 복원한 레이어만 다른 레이어에 병합할 수 있습니다.")
            if not target or not target_key.startswith("part:") or target.get("sourceRecovered"):
                raise ValueError("병합 대상은 기존 파츠 레이어여야 합니다.")
            if source_key == target_key or source_key in merged_sources:
                raise ValueError("레이어 병합 대상을 확인하세요.")
            normalized.append({"kind": "merge", "sourceLayerKey": source_key, "targetLayerKey": target_key})
            merged_sources.add(source_key)
            record_id = target["id"]
            if record_id not in edited:
                edited.append(record_id)
            parts.pop(source_key)
            continue
        if kind == "source_restore":
            recovery_type = operation.get("recoveryType")
            if recovery_type not in RECOVERY_TYPES:
                raise ValueError("원본 복원 레이어 종류를 확인하세요.")
            layer_id = "part:" + RECOVERY_TYPES[recovery_type]["id"]
            if layer_id not in parts:
                parts[layer_id] = recovery_record(recovery_type, manifest)
        else:
            recovery_type = None
            layer_id = operation.get("layerKey") or operation.get("layerId")
            if isinstance(layer_id, str) and ":" not in layer_id:
                layer_id = "part:" + layer_id
            if not isinstance(layer_id, str) or layer_id not in parts:
                raise ValueError("편집할 레이어를 찾을 수 없습니다.")
        size = operation.get("size")
        if isinstance(size, bool) or not isinstance(size, (int, float)) or not math.isfinite(size) or not 1 <= size <= MAX_BRUSH:
            raise ValueError("브러시 크기는 1~256px 범위여야 합니다.")
        points = operation.get("points")
        if not isinstance(points, list) or not points:
            raise ValueError("브러시 궤적이 비어 있습니다.")
        point_count += len(points)
        if point_count > MAX_POINTS:
            raise ValueError("브러시 궤적이 너무 깁니다.")
        clean_points = []
        for point in points:
            if not isinstance(point, dict):
                raise ValueError("브러시 좌표 형식을 확인하세요.")
            x, y, pressure = point.get("x"), point.get("y"), point.get("p", 0.5)
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in (x, y, pressure)):
                raise ValueError("브러시 좌표 형식을 확인하세요.")
            if not -MAX_BRUSH <= x <= width + MAX_BRUSH or not -MAX_BRUSH <= y <= height + MAX_BRUSH or not 0 <= pressure <= 1:
                raise ValueError("브러시 좌표가 캔버스를 벗어났습니다.")
            clean_points.append({"x": float(x), "y": float(y), "p": float(pressure)})
        normalized.append({"kind": kind, "layerId": layer_id, "recoveryType": recovery_type,
                           "size": float(size), "points": clean_points})
        if kind == "paint":
            color = operation.get("color")
            if not parts[layer_id].get("variantOf") or not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                raise ValueError("색상 브러시는 표정 차분에서 사용하세요.")
            normalized[-1]["color"] = color
        record_id = RECOVERY_TYPES[recovery_type]["id"] if recovery_type else parts[layer_id]["id"]
        if record_id not in edited:
            edited.append(record_id)
    return normalized, edited


def variant_record(target: dict, target_key: str, variant_id: str, name: str, manifest: dict) -> dict:
    width, height = int(manifest["canvas"]["width"]), int(manifest["canvas"]["height"])
    left, top = max(0, int(target["left"]) - 24), max(0, int(target["top"]) - 24)
    right, bottom = min(width, int(target["left"]) + int(target["width"]) + 24), min(height, int(target["top"]) + int(target["height"]) + 24)
    return {"id": variant_id, "file": f"expressions/{variant_id}.png", "runtimeName": "차분 · " + name,
            "sourceLayerName": "차분 · " + name, "variantOf": target_key,
            "left": left, "top": top, "width": right-left, "height": bottom-top}


def variant_png(data: object, record: dict, manifest: dict) -> Image.Image:
    if not isinstance(data, str) or not data.startswith("data:image/png;base64,") or len(data) > 28_000_000:
        raise ValueError("차분은 20MB 이하 PNG로 가져오세요.")
    try:
        raw = base64.b64decode(data.split(",", 1)[1], validate=True)
        with Image.open(io.BytesIO(raw)) as opened:
            if opened.format != "PNG" or opened.width * opened.height > 40_000_000:
                raise ValueError("차분 PNG 크기를 확인하세요.")
            crop_size = (record["width"], record["height"])
            if opened.size == crop_size:
                return opened.convert("RGBA")
            if opened.size == (manifest["canvas"]["width"], manifest["canvas"]["height"]):
                return opened.convert("RGBA").crop((record["left"], record["top"], record["left"]+crop_size[0], record["top"]+crop_size[1]))
    except (OSError, binascii.Error, Image.DecompressionBombError):
        raise ValueError("차분 PNG 파일을 읽을 수 없습니다.")
    raise ValueError("PNG 크기는 전체 캔버스 또는 선택 차분 크기와 같아야 합니다.")


def paint_stroke(image: Image.Image, operation: dict, left: int, top: int) -> Image.Image:
    mask = erase_stroke(Image.new("RGBA", image.size, (0, 0, 0, 255)), operation, left, top).getchannel("A")
    mask = ImageChops.invert(mask)
    ink = Image.new("RGBA", image.size, operation["color"])
    ink.putalpha(mask)
    return Image.alpha_composite(image.convert("RGBA"), ink)


def _full_layer_image(extracted: Path, record: dict, canvas_size: tuple[int, int]) -> Image.Image:
    full = Image.new("RGBA", canvas_size)
    with Image.open(extracted / record["file"]) as opened:
        full.alpha_composite(opened.convert("RGBA"), (int(record["left"]), int(record["top"])))
    return full


def _original_layer_crop(folder: Path, record: dict, layer_key: str,
                         canvas_size: tuple[int, int]) -> Image.Image:
    """Align the generated layer with a target whose crop may have grown after merging."""
    snapshot = folder / "revisions" / "0000"
    manifest_path = snapshot / "manifest.json"
    archive_path = snapshot / "character-unity-parts.zip"
    if manifest_path.is_file() and archive_path.is_file():
        original_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        original_record = dict(layer_records(original_manifest)).get(layer_key)
        if original_record:
            with zipfile.ZipFile(archive_path) as archive, \
                    Image.open(io.BytesIO(archive.read(original_record["file"]))) as opened:
                original_size = (int(original_manifest['canvas']['width']), int(original_manifest['canvas']['height']))
                full = Image.new("RGBA", canvas_size)
                ratio_x, ratio_y = canvas_size[0] / original_size[0], canvas_size[1] / original_size[1]
                image = opened.convert('RGBA')
                if original_size != canvas_size:
                    image = image.convert('RGBa').resize((round(image.width * ratio_x), round(image.height * ratio_y)), Image.Resampling.LANCZOS).convert('RGBA')
                full.alpha_composite(image, (round(original_record['left'] * ratio_x), round(original_record['top'] * ratio_y)))
                left, top = int(record["left"]), int(record["top"])
                return full.crop((left, top, left + int(record["width"]), top + int(record["height"])))
    kind = layer_key.split(":", 1)[0]
    with Image.open(io.BytesIO(layer_bytes(folder, record["id"], original=True, kind=kind))) as opened:
        original = opened.convert("RGBA")
    if original.size != (int(record["width"]), int(record["height"])):
        raise ValueError("생성 직후 원본 레이어의 위치를 확인할 수 없습니다.")
    return original


def _stamp(draw: ImageDraw.ImageDraw, x: float, y: float, radius: float) -> None:
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)


def erase_stroke(image: Image.Image, operation: dict, left: int, top: int) -> Image.Image:
    rgba = image.convert("RGBA")
    mask = Image.new("L", rgba.size)
    draw = ImageDraw.Draw(mask)
    points = operation["points"]
    size = float(operation["size"])
    previous = None
    for point in points:
        x, y = point["x"] - left, point["y"] - top
        radius = size * (0.70 + point["p"] * 0.60) * 0.5
        if previous is not None:
            px, py, pr = previous
            distance = math.hypot(x - px, y - py)
            steps = max(1, math.ceil(distance / max(1.0, min(radius, pr) * 0.35)))
            for index in range(1, steps + 1):
                t = index / steps
                _stamp(draw, px + (x - px) * t, py + (y - py) * t, pr + (radius - pr) * t)
        else:
            _stamp(draw, x, y, radius)
        previous = (x, y, radius)
    rgba.putalpha(ImageChops.subtract(rgba.getchannel("A"), mask))
    return rgba


def restore_stroke(image: Image.Image, original: Image.Image, operation: dict, left: int, top: int) -> Image.Image:
    rgba = image.convert("RGBA")
    source = original.convert("RGBA")
    if source.size != rgba.size:
        raise ValueError("원본 레이어 크기가 현재 레이어와 다릅니다.")
    mask = Image.new("L", rgba.size)
    draw = ImageDraw.Draw(mask)
    points = operation["points"]
    size = float(operation["size"])
    previous = None
    for point in points:
        x, y = point["x"] - left, point["y"] - top
        radius = size * (0.70 + point["p"] * 0.60) * 0.5
        if previous is not None:
            px, py, pr = previous
            distance = math.hypot(x - px, y - py)
            steps = max(1, math.ceil(distance / max(1.0, min(radius, pr) * 0.35)))
            for index in range(1, steps + 1):
                t = index / steps
                _stamp(draw, px + (x - px) * t, py + (y - py) * t, pr + (radius - pr) * t)
        else:
            _stamp(draw, x, y, radius)
        previous = (x, y, radius)
    rgba.paste(source, (0, 0), mask)
    return rgba


def recovery_record(recovery_type: str, manifest: dict) -> dict:
    spec = RECOVERY_TYPES[recovery_type]
    width, height = int(manifest["canvas"]["width"]), int(manifest["canvas"]["height"])
    return dict(spec, file=f"layers/{spec['id']}.png", left=0, top=0, width=width, height=height,
                depthMedian=None, recoveryType=recovery_type, sourceRecovered=True)


def source_reference_path(folder: Path, manifest: dict | None = None) -> Path:
    manifest = manifest or read_manifest(folder)
    if manifest.get("sourceReference") != SOURCE_REFERENCE:
        raise FileNotFoundError(SOURCE_REFERENCE)
    target = (folder / SOURCE_REFERENCE).resolve()
    if not target.is_relative_to(folder.resolve()) or not target.is_file():
        raise FileNotFoundError(SOURCE_REFERENCE)
    return target


def save_source_reference(folder: Path, image_data: object) -> Path:
    if not isinstance(image_data, str) or not image_data.startswith("data:image/") or "," not in image_data:
        raise ValueError("원본 이미지를 PNG, JPG 또는 WebP로 선택하세요.")
    header, encoded = image_data.split(",", 1)
    if ";base64" not in header or len(encoded) > 42_000_000:
        raise ValueError("원본 이미지 형식을 확인하세요.")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("원본 이미지 데이터를 읽을 수 없습니다.")
    if len(raw) > 30 * 1024 * 1024:
        raise ValueError("원본 이미지는 30MB 이하여야 합니다.")
    manifest = read_manifest(folder)
    width, height = int(manifest["canvas"]["width"]), int(manifest["canvas"]["height"])
    try:
        with Image.open(io.BytesIO(raw)) as opened:
            opened.load()
            if opened.width < 2 or opened.height < 2 or opened.width * opened.height > 40_000_000:
                raise ValueError("원본 이미지 크기를 확인하세요.")
            rgba = opened.convert("RGBA")
    except (OSError, Image.DecompressionBombError):
        raise ValueError("원본 이미지 파일을 읽을 수 없습니다.")
    scale = min(width / rgba.width, height / rgba.height)
    resized = rgba.resize((max(1, round(rgba.width * scale)), max(1, round(rgba.height * scale))), Image.Resampling.LANCZOS)
    fitted = Image.new("RGBA", (width, height))
    fitted.alpha_composite(resized, ((width - resized.width) // 2, (height - resized.height) // 2))
    target = folder / SOURCE_REFERENCE
    staged = folder / ("." + SOURCE_REFERENCE + ".tmp")
    fitted.save(staged, format="PNG")
    os.replace(staged, target)
    manifest["sourceReference"] = SOURCE_REFERENCE
    manifest_path = folder / "manifest.json"
    staged_manifest = folder / ".source-manifest.tmp"
    staged_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(staged_manifest, manifest_path)
    return target


def _safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for record in archive.infolist():
        target = (destination / record.filename).resolve()
        if not target.is_relative_to(root):
            raise ValueError("패키지 안에 잘못된 파일 경로가 있습니다.")
        archive.extract(record, destination)


def layer_bytes(folder: Path, layer_id: str, original: bool = False, kind: str = "part") -> bytes:
    manifest = read_manifest(folder)
    collection = "expressions" if kind == "expression" else "parts"
    part = next((item for item in manifest.get(collection, []) if item.get("id") == layer_id), None)
    if not part:
        raise FileNotFoundError(layer_id)
    archive_path = folder / "character-unity-parts.zip"
    original_path = folder / "revisions" / "0000" / "character-unity-parts.zip"
    if original and original_path.is_file():
        original_manifest_path = folder / 'revisions' / '0000' / 'manifest.json'
        if original_manifest_path.is_file():
            old_manifest = json.loads(original_manifest_path.read_text(encoding='utf-8'))
            if f'{kind}:{layer_id}' in dict(layer_records(old_manifest)):
                size = (int(manifest['canvas']['width']), int(manifest['canvas']['height']))
                image = _original_layer_crop(folder, part, f'{kind}:{layer_id}', size)
                output = io.BytesIO()
                image.save(output, 'PNG')
                return output.getvalue()
        archive_path = original_path
    with zipfile.ZipFile(archive_path) as archive:
        try:
            return archive.read(part["file"])
        except KeyError:
            if not original:
                raise
    with zipfile.ZipFile(folder / "character-unity-parts.zip") as archive:
        return archive.read(part["file"])


def list_versions(folder: Path, current_revision: int) -> list[dict]:
    """List immutable snapshots plus the current working revision."""
    folder = Path(folder).resolve()
    versions = []
    revisions = folder / "revisions"
    if revisions.is_dir():
        for entry in revisions.iterdir():
            if not entry.is_dir() or not entry.name.isdigit():
                continue
            revision = int(entry.name)
            if revision >= current_revision or not all((entry / name).is_file() for name in VERSION_FILES):
                continue
            versions.append({"revision": revision, "created": (entry / "manifest.json").stat().st_mtime,
                             "current": False, "label": f"작업 버전 v{revision + 1}"})
    if all((folder / name).is_file() for name in VERSION_FILES):
        versions.append({"revision": current_revision, "created": (folder / "manifest.json").stat().st_mtime,
                         "current": True, "label": f"작업 버전 v{current_revision + 1}"})
    return sorted(versions, key=lambda item: item["revision"])


def version_file(folder: Path, revision: int, current_revision: int, filename: str) -> Path:
    if filename not in VERSION_FILES or type(revision) is not int or revision < 0 or revision > current_revision:
        raise FileNotFoundError(filename)
    folder = Path(folder).resolve()
    root = folder if revision == current_revision else folder / "revisions" / f"{revision:04d}"
    target = (root / filename).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise FileNotFoundError(filename)
    return target


def restore_version(folder: Path, target_revision: int, current_revision: int) -> dict:
    """Restore an old snapshot as a new revision, preserving the full history."""
    if type(target_revision) is not int or target_revision < 0 or target_revision >= current_revision:
        raise ValueError("복원할 이전 작업 버전을 확인하세요.")
    folder = Path(folder).resolve()
    source = folder / "revisions" / f"{target_revision:04d}"
    for filename in VERSION_FILES:
        if not (source / filename).is_file():
            raise FileNotFoundError("저장된 작업 버전 파일을 찾을 수 없습니다.")
    next_revision = current_revision + 1
    with tempfile.TemporaryDirectory(prefix="rig-restore-", dir=folder.parent) as temp_name:
        temp = Path(temp_name)
        manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
        if (folder / SOURCE_REFERENCE).is_file():
            manifest["sourceReference"] = SOURCE_REFERENCE
        manifest["editRevision"] = next_revision
        rewritten_manifest = temp / "manifest.json"
        rewritten_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        rebuilt = temp / "character-unity-parts.zip"
        with zipfile.ZipFile(source / "character-unity-parts.zip") as existing, \
                zipfile.ZipFile(rebuilt, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for record in existing.infolist():
                if record.filename != "manifest.json":
                    archive.writestr(record, existing.read(record.filename))
            archive.writestr("manifest.json", rewritten_manifest.read_bytes())

        revision_dir = folder / "revisions" / f"{current_revision:04d}"
        revision_dir.mkdir(parents=True, exist_ok=True)
        for filename in VERSION_FILES:
            if not (revision_dir / filename).exists():
                shutil.copy2(folder / filename, revision_dir / filename)
        sources = {
            "character.psd": source / "character.psd",
            "character-unity-parts.zip": rebuilt,
            "composite.png": source / "composite.png",
            "manifest.json": rewritten_manifest,
        }
        staged = {}
        for filename, item in sources.items():
            target = folder / (".restore-" + filename)
            shutil.copy2(item, target)
            staged[filename] = target
        try:
            for filename in VERSION_FILES:
                os.replace(staged[filename], folder / filename)
        except Exception:
            for filename in VERSION_FILES:
                backup = revision_dir / filename
                if backup.exists():
                    shutil.copy2(backup, folder / filename)
            raise
        finally:
            for target in staged.values():
                target.unlink(missing_ok=True)
    return {"revision": next_revision, "targetRevision": target_revision, "manifest": manifest}


def _write_psd(extracted: Path, manifest: dict, composite: Image.Image, writer: Path, node: str) -> None:
    payload_layers = []
    visibility = manifest.get("layerVisibility") if isinstance(manifest.get("layerVisibility"), dict) else {}
    with tempfile.TemporaryDirectory(prefix="rig-edit-psd-", dir=extracted) as raw_name:
        raw = Path(raw_name)
        records = dict(layer_records(manifest))
        for index, key in enumerate(effective_layer_order(manifest)):
            record = records[key]
            source = extracted / record["file"]
            with Image.open(source) as opened:
                image = opened.convert("RGBA")
            filename = f"layer_{index:03d}.rgba"
            (raw / filename).write_bytes(image.tobytes())
            payload_layers.append({
                "name": record.get("runtimeName") or record["id"],
                "raw": filename,
                "left": int(record["left"]), "top": int(record["top"]),
                "width": image.width, "height": image.height,
                # Alternate animation slots are hidden in the neutral editor preview,
                # but must remain available to the PSD-based web rigger.
                "hidden": bool(record.get("variantOf")) or (
                    visibility.get(key) is False and not (key.startswith("expression:") and
                    (record.get("fade") in ("eyeClose", "eyeClose2", "mouthOpen", "mouthClose") or
                     record["id"].startswith("eye_close") or record["id"] in ("mouth_open", "mouth_close")))),
            })
        (raw / "composite.rgba").write_bytes(composite.tobytes())
        payload = {
            "width": composite.width, "height": composite.height,
            "composite": {"raw": "composite.rgba", "width": composite.width, "height": composite.height},
            "layers": payload_layers, "allowGeneric": False,
        }
        payload_path = raw / "payload.json"
        summary_path = raw / "summary.json"
        payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        completed = subprocess.run(
            [node, str(writer), str(payload_path), str(extracted / "character.psd"), str(summary_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if completed.returncode:
            raise RuntimeError("PSD 재생성 실패: " + completed.stderr[-1000:])


def save_revision(folder: Path, operations: object, revision: int, writer: Path, node: str | None = None,
                  layer_order: object = None, layer_visibility: object = None) -> dict:
    folder = folder.resolve()
    manifest = read_manifest(folder)
    normalized, edited = validate_operations(manifest, operations or [])
    current_order = effective_layer_order(manifest)
    new_variants = [item for item in normalized if item["kind"] == "variant_create"]
    for item in new_variants:
        manifest.setdefault("expressions", []).append(item["record"])
    new_recovery_types = []
    existing_ids = {item.get("id") for item in manifest.get("parts", [])}
    for operation in normalized:
        recovery_type = operation.get("recoveryType")
        if recovery_type and RECOVERY_TYPES[recovery_type]["id"] not in existing_ids:
            manifest.setdefault("parts", []).append(recovery_record(recovery_type, manifest))
            existing_ids.add(RECOVERY_TYPES[recovery_type]["id"])
            new_recovery_types.append(recovery_type)
    augmented_order = current_order + ["part:" + RECOVERY_TYPES[item]["id"] for item in new_recovery_types] + ["expression:" + item["record"]["id"] for item in new_variants]
    current_visibility = validate_layer_visibility(manifest, None)
    requested_visibility = validate_layer_visibility(manifest, layer_visibility)
    merge_operations = [item for item in normalized if item["kind"] == "merge"]
    archive_path = folder / "character-unity-parts.zip"
    if not archive_path.is_file():
        raise FileNotFoundError("Unity 패키지를 찾을 수 없습니다.")
    executable = node or shutil.which("node")
    if not executable:
        raise RuntimeError("PSD 저장에 필요한 Node.js를 찾을 수 없습니다.")

    with tempfile.TemporaryDirectory(prefix="rig-edit-", dir=folder.parent) as temp_name:
        extracted = Path(temp_name) / "package"
        extracted.mkdir()
        with zipfile.ZipFile(archive_path) as archive:
            _safe_extract(archive, extracted)
        # The standalone manifest is the current source of truth because old ZIPs
        # may contain warnings that were corrected after generation.
        (extracted / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        for recovery_type in new_recovery_types:
            record = recovery_record(recovery_type, manifest)
            target = extracted / record["file"]
            target.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGBA", (record["width"], record["height"])).save(target)
        by_id = dict(layer_records(manifest))
        canvas_size = (int(manifest["canvas"]["width"]), int(manifest["canvas"]["height"]))
        recovery_images = {}
        variant_originals = {}
        for key, part in by_id.items():
            if not part.get("sourceRecovered"):
                continue
            full = Image.new("RGBA", canvas_size)
            with Image.open(extracted / part["file"]) as opened:
                full.alpha_composite(opened.convert("RGBA"), (int(part["left"]), int(part["top"])))
            recovery_images[key] = full
        for operation in normalized:
            if operation['kind'] == 'layer_png':
                record = by_id[operation['layerId']]
                record.update({k:operation[k] for k in ('left','top','width','height')})
                variant_png(operation['imageData'],record,manifest).save(extracted / record['file'])
                record.pop('activeVariant',None)
                if record.get('sourceRecovered'):
                    recovery_images[operation['layerId']] = _full_layer_image(extracted,record,canvas_size)
                continue
            if operation['kind'] == 'rig_animation':
                manifest['rigAnimations'] = operation['config']
                manifest['rigEditor'] = operation['rig']
                continue
            if operation["kind"] == "rig_config":
                manifest['rigEditor'] = operation['config']
                continue
            if operation["kind"] == "variant_create":
                record = operation["record"]
                image = Image.new("RGBA", (record["width"], record["height"]))
                if operation["copy"]:
                    original = _full_layer_image(extracted, by_id[record["variantOf"]], canvas_size)
                    image = original.crop((record["left"], record["top"], record["left"]+record["width"], record["top"]+record["height"]))
                (extracted / record["file"]).parent.mkdir(parents=True, exist_ok=True)
                image.save(extracted / record["file"])
                variant_originals[record["id"]] = image.copy()
                continue
            if operation["kind"] == "variant_apply":
                variant = by_id[operation["layerId"]]
                slot = by_id[variant["variantOf"]]
                with Image.open(extracted / variant["file"]) as image:
                    if not image.getchannel("A").getbbox():
                        raise ValueError("비어 있는 차분은 적용할 수 없습니다.")
                    image.save(extracted / slot["file"])
                slot.update({key: variant[key] for key in ("left", "top", "width", "height")})
                slot["activeVariant"] = variant["id"]
                edited.append(slot["id"])
                continue
            if operation["kind"] == "variant_png":
                record = by_id[operation["layerId"]]
                variant_png(operation["imageData"], record, manifest).save(extracted / record["file"])
                continue
            if operation["kind"] == "merge":
                continue
            part = by_id[operation["layerId"]]
            target = extracted / part["file"]
            if part.get("sourceRecovered"):
                opened = recovery_images[operation["layerId"]]
                if operation["kind"] == "erase":
                    recovery_images[operation["layerId"]] = erase_stroke(opened, operation, 0, 0)
                elif operation["kind"] == "source_restore":
                    with Image.open(source_reference_path(folder, manifest)) as original:
                        fitted = original.convert('RGBA')
                        if fitted.size != canvas_size:
                            fitted = fitted.convert('RGBa').resize(canvas_size, Image.Resampling.LANCZOS).convert('RGBA')
                        recovery_images[operation["layerId"]] = restore_stroke(opened, fitted, operation, 0, 0)
                else:
                    original_crop = _original_layer_crop(folder, part, operation["layerId"], canvas_size)
                    original = Image.new("RGBA", canvas_size)
                    original.alpha_composite(original_crop, (int(part["left"]), int(part["top"])))
                    recovery_images[operation["layerId"]] = restore_stroke(opened, original, operation, 0, 0)
                continue
            with Image.open(target) as opened:
                if operation["kind"] == "erase":
                    changed = erase_stroke(opened, operation, int(part["left"]), int(part["top"]))
                elif operation["kind"] == "paint":
                    changed = paint_stroke(opened, operation, int(part["left"]), int(part["top"]))
                else:
                    original = variant_originals.get(part["id"])
                    if original is None:
                        original = _original_layer_crop(folder, part, operation["layerId"], canvas_size)
                    changed = restore_stroke(opened, original, operation, int(part["left"]), int(part["top"]))
            if not part.get("variantOf") and not changed.getchannel("A").getbbox():
                raise ValueError(f'레이어 "{part["runtimeName"]}" 전체가 지워집니다. 레이어 숨김 기능을 사용하세요.')
            changed.save(target)

        merged_source_keys = {item["sourceLayerKey"] for item in merge_operations}
        for key, image in recovery_images.items():
            if key in merged_source_keys:
                continue
            part = by_id[key]
            box = image.getchannel("A").getbbox()
            if not box:
                raise ValueError(f'레이어 "{part["sourceLayerName"]}" 전체가 지워집니다. 레이어 숨김 기능을 사용하세요.')
            cropped = image.crop(box)
            part.update(left=box[0], top=box[1], width=cropped.width, height=cropped.height)
            cropped.save(extracted / part["file"])

        for operation in merge_operations:
            source_key, target_key = operation["sourceLayerKey"], operation["targetLayerKey"]
            source = by_id[source_key]
            target = by_id[target_key]
            source_full = recovery_images.get(source_key)
            if source_full is None:
                source_full = _full_layer_image(extracted, source, canvas_size)
            target_full = _full_layer_image(extracted, target, canvas_size)
            target_full.alpha_composite(source_full)
            box = target_full.getchannel("A").getbbox()
            if not box:
                raise ValueError("병합한 레이어가 비어 있습니다.")
            cropped = target_full.crop(box)
            target.update(left=box[0], top=box[1], width=cropped.width, height=cropped.height)
            cropped.save(extracted / target["file"])
            (extracted / source["file"]).unlink(missing_ok=True)
            manifest["parts"] = [item for item in manifest.get("parts", []) if item.get("id") != source["id"]]
            manifest["editedParts"] = [item for item in manifest.get("editedParts", []) if item != source["id"]]
            by_id.pop(source_key, None)
            augmented_order = [key for key in augmented_order if key != source_key]
            requested_visibility.pop(source_key, None)

        requested_order = augmented_order if layer_order is None else validate_layer_order(manifest, layer_order)
        visibility_changed = requested_visibility != current_visibility
        if not normalized and requested_order == current_order and not visibility_changed:
            raise ValueError("저장할 편집 작업이 없습니다.")

        width, height = int(manifest["canvas"]["width"]), int(manifest["canvas"]["height"])
        composite = Image.new("RGBA", (width, height))
        records = dict(layer_records(manifest))
        for key in requested_order:
            expression = records[key]
            if expression.get("variantOf"):
                continue
            if key.startswith("part:"):
                visible = True
            else:
                visible = (
                    expression.get("fade") == "eyeOpen" or expression.get("id") == "eyebrow" or
                    (manifest.get("sourceMouthState") == "closed" and expression.get("id") == "mouth_close") or
                    (manifest.get("sourceMouthState") == "slightly-open" and expression.get("id") == "mouth_open")
                )
            if key in requested_visibility:
                visible = requested_visibility[key]
            if not visible:
                continue
            with Image.open(extracted / expression["file"]) as opened:
                composite.alpha_composite(opened.convert("RGBA"), (int(expression["left"]), int(expression["top"])))
        next_revision = revision + 1
        manifest["editRevision"] = next_revision
        manifest["layerOrder"] = requested_order
        manifest["layerVisibility"] = requested_visibility
        manifest["editedParts"] = sorted(set(manifest.get("editedParts", [])) | set(edited))
        if manifest.get('rigEditor'):
            manifest['rigEditor'] = rigging_bones.reconcile(manifest['rigEditor'], manifest)
        if manifest.get('rigAnimations'):
            rig = rigging_bones.get_rig(manifest)
            manifest['rigAnimations'] = rigging_animation.reconcile(manifest['rigAnimations'], rig)
        (extracted / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        composite.save(extracted / "composite.png")
        _write_psd(extracted, manifest, composite, writer, executable)
        # Refresh packaged importer sources so older results understand stored variants.
        unity_root = Path(__file__).parent / "unity-package"
        for source in unity_root.rglob("*.cs"):
            target = extracted / "Unity" / source.relative_to(unity_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

        rebuilt = Path(temp_name) / "character-unity-parts.zip"
        with zipfile.ZipFile(rebuilt, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in sorted(extracted.rglob("*")):
                if item.is_file():
                    archive.write(item, item.relative_to(extracted).as_posix())

        revision_dir = folder / "revisions" / f"{revision:04d}"
        revision_dir.mkdir(parents=True, exist_ok=True)
        current_files = VERSION_FILES
        for name in current_files:
            if not (revision_dir / name).exists():
                shutil.copy2(folder / name, revision_dir / name)
        staged = {}
        sources = {
            "character.psd": extracted / "character.psd",
            "character-unity-parts.zip": rebuilt,
            "composite.png": extracted / "composite.png",
            "manifest.json": extracted / "manifest.json",
        }
        for name, source in sources.items():
            target = folder / (".edit-" + name)
            shutil.copy2(source, target)
            staged[name] = target
        try:
            for name in current_files:
                os.replace(staged[name], folder / name)
        except Exception:
            for name in current_files:
                backup = revision_dir / name
                if backup.exists():
                    shutil.copy2(backup, folder / name)
            raise
        finally:
            for target in staged.values():
                target.unlink(missing_ok=True)
    return {"revision": next_revision, "editedParts": edited, "manifest": manifest}
