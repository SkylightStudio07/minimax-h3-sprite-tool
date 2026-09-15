"""Render a public, flattened animation without exposing PSD or layer assets."""

from __future__ import annotations

import io
import json
import math
from pathlib import Path
import zipfile

from PIL import Image
from rigging_motion import idle_profile, warp_idle


SHOWCASE_FILENAME = "showcase.webp"
EYE_PREFIXES = ("eyewhite", "irides", "eyelash")


def _opacity(image: Image.Image, amount: float) -> Image.Image:
    if amount >= 0.999:
        return image
    if amount <= 0.001:
        return Image.new("RGBA", image.size)
    faded = image.copy()
    faded.putalpha(faded.getchannel("A").point(lambda value: round(value * amount)))
    return faded


def _record_image(archive: zipfile.ZipFile, record: dict, scale: float) -> Image.Image:
    with Image.open(io.BytesIO(archive.read(record["file"]))) as opened:
        image = opened.convert("RGBA")
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    if image.size != size:
        image = image.resize(size, Image.Resampling.LANCZOS)
    return image


def _blink_amount(frame: int, frame_count: int) -> float:
    # One deliberate blink and one quicker blink make the loop feel less mechanical.
    phase = frame / frame_count
    amount = 0.0
    for center, width in ((0.31, 0.055), (0.78, 0.042)):
        distance = abs(phase - center)
        amount = max(amount, max(0.0, 1.0 - distance / width))
    return min(1.0, amount)


def build_showcase(folder: Path, output: Path | None = None, *, max_size: int = 640,
                   frame_count: int = 48, duration_ms: int = 100) -> dict:
    """Build a compact animated WebP from the current flattened rig package."""
    folder = Path(folder).resolve()
    output = Path(output or folder / SHOWCASE_FILENAME).resolve()
    if not output.is_relative_to(folder):
        raise ValueError("쇼케이스 출력 경로가 결과 폴더를 벗어났습니다.")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    canvas = manifest["canvas"]
    source_width, source_height = int(canvas["width"]), int(canvas["height"])
    scale = min(1.0, max_size / max(source_width, source_height))
    width, height = max(1, round(source_width * scale)), max(1, round(source_height * scale))
    parts = manifest.get("parts", [])
    expressions = {item.get("id"): item for item in manifest.get("expressions", [])}
    records = dict([(f"part:{item['id']}", item) for item in parts] +
                   [(f"expression:{item['id']}", item) for item in expressions.values()])
    layer_order = manifest.get("layerOrder") or list(records)
    if len(layer_order) != len(records) or set(layer_order) != set(records):
        layer_order = list(records)
    archive_path = folder / "character-unity-parts.zip"
    if not archive_path.is_file():
        raise FileNotFoundError("Unity 파츠 패키지를 찾을 수 없습니다.")

    with zipfile.ZipFile(archive_path) as archive:
        part_images = {item["id"]: _record_image(archive, item, scale) for item in parts}
        expression_images = {
            key: _record_image(archive, item, scale)
            for key, item in expressions.items() if key in ("eye_open_original", "eye_close", "mouth_open", "mouth_close", "eyebrow")
        }
    motion_parts = [dict(item, left=float(item['left']) * scale,
                         top=float(item['top']) * scale,
                         width=part_images[item['id']].width,
                         height=part_images[item['id']].height) for item in parts]
    source_anchors = manifest.get('anchors', {})
    motion_anchors = {'neckPivot': {'cx': source_anchors.get('neckPivot', {}).get('cx', source_width / 2) * scale}}
    motion = idle_profile(motion_parts, motion_anchors, height)

    def paste_record(target: Image.Image, record: dict, image: Image.Image, opacity: float = 1.0,
                     dx: float = 0.0, dy: float = 0.0, angle: float = 0.0,
                     pivot_y: float = 0.5) -> None:
        layer = _opacity(image, opacity)
        if abs(angle) > 0.001:
            layer = layer.rotate(angle, Image.Resampling.BICUBIC, expand=False,
                                 center=(layer.width * 0.5, layer.height * pivot_y))
        left = round(float(record["left"]) * scale + dx)
        top = round(float(record["top"]) * scale + dy)
        layer, left, top = warp_idle(layer, str(record['id']), left, top, motion, phase)
        target.alpha_composite(layer, (round(left), round(top)))

    frames: list[Image.Image] = []
    back_record = next((item for item in parts if item.get("id") == "back_hair"), None)
    headwear_record = next((item for item in parts if item.get("id") == "headwear"), None)
    # See-through sometimes puts a beret/hood body in back_hair and only its badge
    # in headwear. Independent hair sway would tear that composite headgear apart.
    mixed_headgear = bool(back_record and headwear_record and
                          float(headwear_record.get("width", 0)) < float(back_record.get("width", 0)) * 0.55)
    for frame_index in range(frame_count):
        phase = 2.0 * math.pi * frame_index / frame_count
        blink = _blink_amount(frame_index, frame_count)
        mouth_open = max(0.0, math.sin(phase - 0.35)) ** 8 * 0.72
        if mixed_headgear:
            back_sway = front_sway = math.sin(phase) * max(0.45, width * 0.0012)
        else:
            back_sway = math.sin(phase) * max(2.0, width * 0.0065)
            front_sway = math.sin(phase + 0.65) * max(1.5, width * 0.0045)
        composed = Image.new("RGBA", (width, height))

        for layer_key in layer_order:
            part = records[layer_key]
            part_id = str(part.get("id", ""))
            opacity = 1.0
            if layer_key.startswith("part:") and part_id.startswith(EYE_PREFIXES):
                opacity = 1.0 - blink
            elif layer_key.startswith("part:") and part_id == "mouth_open":
                opacity = mouth_open
            elif layer_key.startswith("expression:"):
                if part_id == "eye_open_original": opacity = 1.0 - blink
                elif part_id.startswith("eye_close"): opacity = blink
                elif part_id == "mouth_open": opacity = mouth_open
                elif part_id == "mouth_close": opacity = 1.0 - mouth_open
                elif part_id != "eyebrow": opacity = 0.0
            dx = dy = 0.0
            angle = 0.0
            if part_id == "back_hair":
                dx, dy = back_sway, math.sin(phase + 0.4) * 1.2
            elif part_id == "front_hair":
                dx, dy = front_sway, math.sin(phase + 1.0) * 0.8
            elif part_id == "objects":
                angle = math.sin(phase + 0.35) * 0.75
                dx, dy = math.sin(phase + 0.35) * max(0.7, width * 0.0018), -math.sin(phase - 0.8) * 0.8
            elif part_id == "bottomwear" and not (motion['coatBottom'] and part_images[part_id].height < motion['height'] * .15):
                angle = math.sin(phase + 1.1) * 1.05
                dx = math.sin(phase + 1.1) * max(0.9, width * 0.0020)
            image = expression_images.get(part_id) if layer_key.startswith("expression:") else part_images.get(part_id)
            if image is not None and opacity > 0.001:
                paste_record(composed, part, image, opacity, dx, dy, angle,
                             0.08 if part_id == "bottomwear" else 0.5)

        frames.append(composed)

    staged = output.with_name("." + output.name + ".tmp")
    try:
        frames[0].save(staged, format="WEBP", save_all=True, append_images=frames[1:],
                       duration=duration_ms, loop=0, lossless=False, quality=84, method=4)
        with Image.open(staged) as check:
            if getattr(check, "n_frames", 1) < 2:
                raise RuntimeError("애니메이션 WebP를 만들 수 없습니다.")
        staged.replace(output)
    finally:
        staged.unlink(missing_ok=True)
        for image in frames:
            image.close()
    return {"path": output, "frames": frame_count, "width": width, "height": height,
            "durationMs": frame_count * duration_ms, "bytes": output.stat().st_size}
