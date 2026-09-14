"""Non-destructive paint and eraser revisions for generated rigging packages."""

from __future__ import annotations

import json
import io
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

from PIL import Image, ImageChops, ImageDraw


MAX_STROKES = 100
MAX_POINTS = 12000
MAX_BRUSH = 256.0
VERSION_FILES = ("character.psd", "character-unity-parts.zip", "composite.png", "manifest.json")


def read_manifest(folder: Path) -> dict:
    return json.loads((folder / "manifest.json").read_text(encoding="utf-8"))


def validate_operations(manifest: dict, operations: object) -> tuple[list[dict], list[str]]:
    if not isinstance(operations, list) or not operations:
        raise ValueError("저장할 편집 작업이 없습니다.")
    if len(operations) > MAX_STROKES:
        raise ValueError(f"한 번에 저장할 수 있는 작업은 {MAX_STROKES}개까지입니다.")
    parts = {part["id"]: part for part in manifest.get("parts", [])}
    width = int(manifest["canvas"]["width"])
    height = int(manifest["canvas"]["height"])
    normalized: list[dict] = []
    edited: list[str] = []
    point_count = 0
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("kind", "erase") not in ("erase", "restore"):
            raise ValueError("지원하지 않는 편집 작업입니다.")
        kind = operation.get("kind", "erase")
        layer_id = operation.get("layerId")
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
        normalized.append({"kind": kind, "layerId": layer_id, "size": float(size), "points": clean_points})
        if layer_id not in edited:
            edited.append(layer_id)
    return normalized, edited


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


def _safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for record in archive.infolist():
        target = (destination / record.filename).resolve()
        if not target.is_relative_to(root):
            raise ValueError("패키지 안에 잘못된 파일 경로가 있습니다.")
        archive.extract(record, destination)


def layer_bytes(folder: Path, layer_id: str, original: bool = False) -> bytes:
    manifest = read_manifest(folder)
    part = next((item for item in manifest.get("parts", []) if item.get("id") == layer_id), None)
    if not part:
        raise FileNotFoundError(layer_id)
    archive_path = folder / "character-unity-parts.zip"
    original_path = folder / "revisions" / "0000" / "character-unity-parts.zip"
    if original and original_path.is_file():
        archive_path = original_path
    with zipfile.ZipFile(archive_path) as archive:
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
    with tempfile.TemporaryDirectory(prefix="rig-edit-psd-", dir=extracted) as raw_name:
        raw = Path(raw_name)
        for index, record in enumerate([*manifest.get("parts", []), *manifest.get("expressions", [])]):
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


def save_revision(folder: Path, operations: object, revision: int, writer: Path, node: str | None = None) -> dict:
    folder = folder.resolve()
    manifest = read_manifest(folder)
    normalized, edited = validate_operations(manifest, operations)
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
        by_id = {part["id"]: part for part in manifest["parts"]}
        for operation in normalized:
            part = by_id[operation["layerId"]]
            target = extracted / part["file"]
            with Image.open(target) as opened:
                if operation["kind"] == "erase":
                    changed = erase_stroke(opened, operation, int(part["left"]), int(part["top"]))
                else:
                    with Image.open(io.BytesIO(layer_bytes(folder, part["id"], original=True))) as original:
                        changed = restore_stroke(opened, original, operation, int(part["left"]), int(part["top"]))
            if not changed.getchannel("A").getbbox():
                raise ValueError(f'레이어 "{part["runtimeName"]}" 전체가 지워집니다. 레이어 숨김 기능을 사용하세요.')
            changed.save(target)

        width, height = int(manifest["canvas"]["width"]), int(manifest["canvas"]["height"])
        composite = Image.new("RGBA", (width, height))
        for part in manifest["parts"]:
            with Image.open(extracted / part["file"]) as opened:
                composite.alpha_composite(opened.convert("RGBA"), (int(part["left"]), int(part["top"])))
        for expression in manifest.get("expressions", []):
            if expression.get("fade") != "eyeOpen" and expression.get("id") != "eyebrow":
                continue
            with Image.open(extracted / expression["file"]) as opened:
                composite.alpha_composite(opened.convert("RGBA"), (int(expression["left"]), int(expression["top"])))
        next_revision = revision + 1
        manifest["editRevision"] = next_revision
        manifest["editedParts"] = sorted(set(manifest.get("editedParts", [])) | set(edited))
        (extracted / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        composite.save(extracted / "composite.png")
        _write_psd(extracted, manifest, composite, writer, executable)

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
