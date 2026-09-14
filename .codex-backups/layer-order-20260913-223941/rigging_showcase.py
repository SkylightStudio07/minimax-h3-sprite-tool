"""Render a public, flattened animation without exposing PSD or layer assets."""

from __future__ import annotations

import io
import json
import math
from pathlib import Path
import zipfile

from PIL import Image


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
                   frame_count: int = 36, duration_ms: int = 90) -> dict:
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
    archive_path = folder / "character-unity-parts.zip"
    if not archive_path.is_file():
        raise FileNotFoundError("Unity 파츠 패키지를 찾을 수 없습니다.")

    with zipfile.ZipFile(archive_path) as archive:
        part_images = {item["id"]: _record_image(archive, item, scale) for item in parts}
        expression_images = {
            key: _record_image(archive, item, scale)
            for key, item in expressions.items() if key in ("eye_open_original", "eye_close", "mouth_open", "mouth_close", "eyebrow")
        }

    eye_indices = [index for index, part in enumerate(parts)
                   if str(part.get("id", "")).startswith(EYE_PREFIXES)]
    eye_insert = max(eye_indices, default=-1)

    def paste_record(target: Image.Image, record: dict, image: Image.Image, opacity: float = 1.0,
                     dx: float = 0.0, dy: float = 0.0) -> None:
        layer = _opacity(image, opacity)
        left = round(float(record["left"]) * scale + dx)
        top = round(float(record["top"]) * scale + dy)
        target.alpha_composite(layer, (left, top))

    frames: list[Image.Image] = []
    for frame_index in range(frame_count):
        phase = 2.0 * math.pi * frame_index / frame_count
        blink = _blink_amount(frame_index, frame_count)
        mouth_open = max(0.0, math.sin(phase - 0.35)) ** 8 * 0.72
        back_sway = math.sin(phase) * max(2.0, width * 0.0065)
        front_sway = math.sin(phase + 0.65) * max(1.5, width * 0.0045)
        composed = Image.new("RGBA", (width, height))

        for index, part in enumerate(parts):
            part_id = str(part.get("id", ""))
            opacity = 1.0
            if part_id.startswith(EYE_PREFIXES):
                opacity = 1.0 - blink
            elif part_id == "mouth_open":
                opacity = mouth_open
            dx = dy = 0.0
            if part_id == "back_hair":
                dx, dy = back_sway, math.sin(phase + 0.4) * 1.2
            elif part_id == "front_hair":
                dx, dy = front_sway, math.sin(phase + 1.0) * 0.8
            paste_record(composed, part, part_images[part_id], opacity, dx, dy)

            if index == eye_insert and "eye_close" in expression_images:
                if "eye_open_original" in expression_images:
                    paste_record(composed, expressions["eye_open_original"], expression_images["eye_open_original"], 1.0 - blink)
                paste_record(composed, expressions["eye_close"], expression_images["eye_close"], blink)
        if "eyebrow" in expression_images:
            paste_record(composed, expressions["eyebrow"], expression_images["eyebrow"])
        if "mouth_open" in expression_images:
            paste_record(composed, expressions["mouth_open"], expression_images["mouth_open"], mouth_open)
        if "mouth_close" in expression_images:
            paste_record(composed, expressions["mouth_close"], expression_images["mouth_close"], 1.0 - mouth_open)

        # Gentle breathing is anchored at the bottom, so the feet remain planted.
        breath = (1.0 + math.sin(phase - math.pi / 2.0)) * 0.5
        scale_x, scale_y = 1.0 + 0.0025 * breath, 1.0 + 0.0050 * breath
        resized = composed.resize((round(width * scale_x), round(height * scale_y)), Image.Resampling.BICUBIC)
        frame_image = Image.new("RGBA", (width, height))
        frame_image.alpha_composite(resized, ((width - resized.width) // 2, height - resized.height - round(1.5 * breath)))
        frames.append(frame_image)

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
