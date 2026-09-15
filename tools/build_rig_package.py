"""Convert See-through PNG layers into a PSD and a Unity-oriented ZIP package."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter


FRONT_OCCLUDER_IDS = (
    "front_hair", "hair_front", "headwear", "headgear", "hood", "hat",
    "glasses", "eyewear", "spectacles",
)
FACE_LAYER_IDS = ("face", "eyewhite", "irides", "eyelash", "eye", "brow", "nose", "mouth")


def default_layer_order(parts: list[dict], expressions: list[dict]) -> list[str]:
    """Place facial expressions below front hair and headwear by default."""
    part_keys = [f"part:{item['id']}" for item in parts]
    expression_keys = [f"expression:{item['id']}" for item in expressions]
    facial_indices = [index for index, item in enumerate(parts)
                      if any(token in str(item.get("id", "")).lower() for token in FACE_LAYER_IDS)]
    after_face = max(facial_indices, default=-1) + 1
    insert = len(part_keys)
    for index, item in enumerate(parts[after_face:], after_face):
        layer_id = str(item.get("id", "")).lower()
        if any(token in layer_id for token in FRONT_OCCLUDER_IDS):
            insert = index
            break
    return [*part_keys[:insert], *expression_keys, *part_keys[insert:]]


def filter_absent_eye_warnings(warnings: list[str], left_absent: bool, right_absent: bool) -> list[str]:
    ignored = set()
    if left_absent: ignored.add('"eyebrow_1"')
    if right_absent: ignored.add('"eyebrow_2"')
    return [warning for warning in warnings
            if not ((left_absent or right_absent) and "눈 앵커가 불완전" in warning)
            and not any(token in warning for token in ignored)]


def runtime_name(name: str) -> str:
    if name == "mouth":
        return "mouth_open"
    if name.endswith("-r"):
        return f"{name[:-2]}_1"
    if name.endswith("-l"):
        return f"{name[:-2]}_2"
    return name


def file_id(name: str) -> str:
    """Return a stable Unity-friendly identifier without changing the PSD layer name."""
    value = re.sub(r"[^a-z0-9_]+", "_", name.lower().replace(" ", "_"))
    return value.strip("_") or "part"


def localize_warning(message: str) -> str:
    unknown = re.fullmatch(r'未知のレイヤー名 "(.+)" — body として扱います', message)
    if unknown:
        return f'알 수 없는 레이어 "{unknown.group(1)}"를 body로 처리했습니다.'
    split = re.fullmatch(r'"(.+)" の左右分離に失敗（空レイヤー？）', message)
    if split:
        return f'"{split.group(1)}" 좌우 분리에 실패했습니다. 비어 있는 레이어인지 확인하세요.'
    translations = {
        "目のアンカーが不完全です（eyewhite/irides を確認）": "눈 앵커가 불완전합니다. eyewhite/irides 레이어를 확인하세요.",
        "不足する閉じ目を自動配置しました（「目」の差分バーで調整可）": "없는 닫힌 눈을 범용 파츠로 자동 배치했습니다. 미리보기의 눈 차분 값을 조정하세요.",
        "mouth_close が無いため汎用閉じ口を自動配置しました（「口」のバーで調整可）": "mouth_close가 없어 범용 닫힌 입을 자동 배치했습니다. 미리보기의 입 값을 조정하세요.",
    }
    return translations.get(message, message)


def alpha_over(base: Image.Image, layer: Image.Image, left: int, top: int) -> None:
    base.alpha_composite(layer, (left, top))


def fit_to_canvas(image: Image.Image, width: int, height: int, resample: int) -> Image.Image:
    scale = min(width / image.width, height / image.height)
    resized = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        resample,
    )
    canvas = Image.new(image.mode, (width, height))
    canvas.paste(resized, ((width - resized.width) // 2, (height - resized.height) // 2))
    return canvas


def load_mask(path: Path, width: int, height: int, *, binary: bool = True) -> Image.Image:
    with Image.open(path) as opened:
        rgba = opened.convert("RGBA")
        mask = ImageChops.multiply(rgba.convert("L"), rgba.getchannel("A"))
    mask = fit_to_canvas(
        mask,
        width,
        height,
        Image.Resampling.NEAREST if binary else Image.Resampling.LANCZOS,
    )
    return mask.point(lambda value: 255 if value >= 32 else 0) if binary else mask


def feature_color(source: Image.Image, mask: Image.Image) -> tuple[int, int, int, int]:
    rgba = np.asarray(source, dtype=np.uint8)
    selected = np.asarray(mask, dtype=np.uint8) > 0
    selected &= rgba[:, :, 3] > 16
    pixels = rgba[:, :, :3][selected]
    if len(pixels) < 4:
        return (65, 45, 55, 255)
    luminance = pixels[:, 0] * 0.2126 + pixels[:, 1] * 0.7152 + pixels[:, 2] * 0.0722
    darkest = pixels[luminance <= np.percentile(luminance, 35)]
    rgb = np.median(darkest if len(darkest) else pixels, axis=0).astype(np.uint8)
    return (int(rgb[0]), int(rgb[1]), int(rgb[2]), 255)


def eye_angle(source: Image.Image, mask: Image.Image) -> float:
    """Estimate the eyelid angle in radians from dark source pixels inside a user mask."""
    box = mask.getbbox()
    if not box:
        return 0.0
    x0, y0, x1, y1 = box
    rgba = np.asarray(source.crop(box), dtype=np.float64)
    selected = np.asarray(mask.crop(box), dtype=np.uint8) > 0
    selected &= rgba[:, :, 3] > 16
    if selected.sum() < 8:
        return 0.0

    luminance = rgba[:, :, 0] * 0.2126 + rgba[:, :, 1] * 0.7152 + rgba[:, :, 2] * 0.0722
    bright_reference = float(np.percentile(luminance[selected], 85))
    darkness = np.maximum(0.0, bright_reference - luminance)
    darkness[~selected] = 0.0
    xs: list[float] = []
    ys: list[float] = []
    weights: list[float] = []
    for x in range(darkness.shape[1]):
        column = darkness[:, x]
        total = float(column.sum())
        if total <= 0.0:
            continue
        xs.append(float(x))
        ys.append(float(np.dot(np.arange(len(column)), column) / total))
        weights.append(math.sqrt(total))
    if len(xs) < 5 or max(xs) - min(xs) < max(4.0, (x1 - x0) * 0.35):
        return 0.0
    x_values = np.asarray(xs)
    y_values = np.asarray(ys)
    point_weights = np.asarray(weights)
    slope = 0.0
    for _ in range(2):
        weight_sum = float(point_weights.sum())
        if weight_sum <= 0:
            return 0.0
        mean_x = float(np.dot(x_values, point_weights) / weight_sum)
        mean_y = float(np.dot(y_values, point_weights) / weight_sum)
        denominator = float(np.dot(point_weights, (x_values - mean_x) ** 2))
        if denominator <= 1e-6:
            return 0.0
        slope = float(np.dot(point_weights, (x_values - mean_x) * (y_values - mean_y)) / denominator)
        residual = y_values - (mean_y + slope * (x_values - mean_x))
        median_error = float(np.median(np.abs(residual)))
        keep = np.abs(residual) <= max(1.5, median_error * 2.5)
        if keep.all() or keep.sum() < 5:
            break
        x_values, y_values, point_weights = x_values[keep], y_values[keep], point_weights[keep]
    return math.radians(max(-30.0, min(30.0, math.degrees(math.atan(slope)))))


def eye_angles(source: Image.Image, masks: list[Image.Image]) -> list[float]:
    angles = [eye_angle(source, mask) for mask in masks]
    centers = []
    for index, mask in enumerate(masks):
        box = mask.getbbox()
        if box:
            centers.append(((box[0] + box[2]) * 0.5, (box[1] + box[3]) * 0.5, index))
    if len(centers) >= 2:
        centers.sort()
        left, right = centers[0], centers[-1]
        roll = math.atan2(right[1] - left[1], max(1.0, right[0] - left[0]))
        roll = max(math.radians(-30.0), min(math.radians(30.0), roll))
        if abs(roll) >= math.radians(3.0):
            for _, _, index in centers:
                angles[index] = roll * 0.7 + angles[index] * 0.3
    return angles


def closed_eye(source: Image.Image, masks: list[Image.Image]) -> tuple[Image.Image, int, int] | None:
    combined = Image.new("RGBA", source.size)
    angles = eye_angles(source, masks)
    for mask, angle in zip(masks, angles):
        box = mask.getbbox()
        if not box:
            continue
        x0, y0, x1, y1 = box
        width, height = x1 - x0, y1 - y0
        pad = max(2, round(height * 0.2))
        crop_w, crop_h = width + pad * 2, height + pad * 2
        scale = 4
        layer = Image.new("RGBA", (crop_w * scale, crop_h * scale))
        draw = ImageDraw.Draw(layer)
        color = feature_color(source, mask)
        cos_angle, sin_angle = math.cos(angle), math.sin(angle)
        start_x, end_x = pad + width * 0.08, pad + width * 0.92
        center_x = (start_x + end_x) * 0.5
        center_y = pad + height * 0.57
        half = max(1.0, (end_x - start_x) * 0.5)
        amplitude = max(1.0, height * 0.08)
        points = []
        for index in range(33):
            t = index / 32
            x_offset = -half + half * 2.0 * t
            normalized = x_offset / half
            y_offset = amplitude * (1.0 - normalized * normalized)
            x = center_x + x_offset * cos_angle - y_offset * sin_angle
            y = center_y + x_offset * sin_angle + y_offset * cos_angle
            points.append((round(x * scale), round(y * scale)))
        line_width = max(1, round(height * 0.09 * scale))
        draw.line(points, fill=color, width=line_width, joint="curve")
        layer = layer.resize((crop_w, crop_h), Image.Resampling.LANCZOS)
        combined.alpha_composite(layer, (max(0, x0 - pad), max(0, y0 - pad)))
    box = combined.getbbox()
    if not box:
        return None
    return combined.crop(box), box[0], box[1]


def authored_closed_eye(source: Image.Image, masks: list[Image.Image]) -> tuple[Image.Image, int, int] | None:
    """Render the user's authored closed-eye strokes without inferring their curve or angle."""
    combined = Image.new("RGBA", source.size)
    for mask in masks:
        box = mask.getbbox()
        if not box:
            continue
        color = feature_color(source, mask)
        stroke = Image.new("RGBA", source.size, color)
        stroke.putalpha(mask)
        combined.alpha_composite(stroke)
    box = combined.getbbox()
    if not box:
        return None
    return combined.crop(box), box[0], box[1]


def original_eye(source: Image.Image, masks: list[Image.Image]) -> tuple[Image.Image, int, int] | None:
    """Copy the neutral open eyes directly from the fitted source image."""
    combined_mask = Image.new("L", source.size)
    for mask in masks:
        combined_mask = ImageChops.lighter(combined_mask, mask.convert("L"))
    if not combined_mask.getbbox():
        return None
    # A one-pixel expansion and soft edge cover reconstruction seams without
    # noticeably including the nearby eyebrow or hair.
    soft_mask = combined_mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(0.7))
    patch = source.copy()
    patch.putalpha(ImageChops.multiply(source.getchannel("A"), soft_mask))
    box = patch.getbbox()
    if not box:
        return None
    return patch.crop(box), box[0], box[1]


def inferred_eye_masks(info: dict, source_dir: Path, width: int, height: int) -> list[Image.Image]:
    """Use generated eye-layer alpha only as a locator for direct-stroke mode."""
    masks = []
    for record in info.get("layers", []):
        normalized = runtime_name(str(record.get("name", "")))
        if not normalized.startswith(("eyewhite", "irides", "eyelash")):
            continue
        source = source_dir / record["filename"]
        with Image.open(source) as opened:
            alpha = opened.convert("RGBA").getchannel("A")
        placed = Image.new("L", (width, height))
        placed.paste(alpha, (int(record["left"]), int(record["top"])))
        masks.append(placed)
    return masks


def closed_mouth(source: Image.Image, mask: Image.Image) -> tuple[Image.Image, int, int] | None:
    box = mask.getbbox()
    if not box:
        return None
    x0, y0, x1, y1 = box
    source_crop = source.crop(box)
    mask_crop = mask.crop(box)
    rgba = np.asarray(source_crop, dtype=np.uint8).copy()
    selected = np.asarray(mask_crop, dtype=np.uint8) > 0
    luminance = rgba[:, :, 0] * 0.2126 + rgba[:, :, 1] * 0.7152 + rgba[:, :, 2] * 0.0722
    values = luminance[selected]
    if len(values) < 4:
        return None
    threshold = np.percentile(values, 55)
    alpha = np.where(selected & (luminance <= threshold), np.asarray(mask_crop), 0).astype(np.uint8)
    rgba[:, :, 3] = np.minimum(rgba[:, :, 3], alpha)
    feature = Image.fromarray(rgba, "RGBA")
    target_height = max(2, round(feature.height * 0.24))
    feature = feature.resize((feature.width, target_height), Image.Resampling.LANCZOS)
    if not feature.getbbox():
        return None
    return feature, x0, round((y0 + y1 - target_height) * 0.5)


def slightly_open_mouth(source: Image.Image, mask: Image.Image) -> tuple[Image.Image, int, int] | None:
    """Turn a closed mouth line into a restrained open-mouth slit for V1 talking."""
    box = mask.getbbox()
    if not box:
        return None
    x0, y0, x1, y1 = box
    source_crop = source.crop(box)
    mask_crop = mask.crop(box)
    rgba = np.asarray(source_crop, dtype=np.uint8).copy()
    selected = np.asarray(mask_crop, dtype=np.uint8) > 0
    luminance = rgba[:, :, 0] * 0.2126 + rgba[:, :, 1] * 0.7152 + rgba[:, :, 2] * 0.0722
    values = luminance[selected]
    if len(values) < 4:
        return None
    threshold = np.percentile(values, 62)
    alpha = np.where(selected & (luminance <= threshold), np.asarray(mask_crop), 0).astype(np.uint8)
    rgba[:, :, 3] = np.minimum(rgba[:, :, 3], alpha)
    feature = Image.fromarray(rgba, "RGBA")
    visible = feature.getbbox()
    if not visible:
        return None
    feature = feature.crop((0, visible[1], feature.width, visible[3]))
    target_height = max(3, round(max(feature.height * 1.65, (y1 - y0) * 0.42)))
    feature = feature.resize((feature.width, target_height), Image.Resampling.LANCZOS)
    return feature, x0, round((y0 + y1 - target_height) * 0.5)


def manual_expressions(
    source_path: Path | None,
    eye_paths: list[Path],
    eyebrow_paths: list[Path],
    mouth_path: Path | None,
    width: int,
    height: int,
    eye_input_mode: str = "area",
    preserve_original_eyes: bool = False,
    open_eye_masks: list[Image.Image] | None = None,
    mouth_state: str = "closed",
) -> list[dict]:
    if not source_path:
        return []
    with Image.open(source_path) as opened:
        source = fit_to_canvas(opened.convert("RGBA"), width, height, Image.Resampling.LANCZOS)
    eyes = [
        load_mask(path, width, height, binary=eye_input_mode != "closed-stroke")
        for path in eye_paths
        if path
    ]
    result = []
    if preserve_original_eyes:
        opened = original_eye(source, eyes if eye_input_mode == "area" else (open_eye_masks or []))
        if opened:
            image, left, top = opened
            result.append({"name": "eye_open_original", "image": image, "left": left, "top": top,
                           "width": image.width, "height": image.height, "side": None, "fade": "eyeOpen"})
    eyebrows = [load_mask(path, width, height) for path in eyebrow_paths if path]
    eyebrow = original_eye(source, eyebrows)
    if eyebrow:
        image, left, top = eyebrow
        result.append({"name": "eyebrow", "image": image, "left": left, "top": top,
                       "width": image.width, "height": image.height, "side": None, "fade": None})
    eye = authored_closed_eye(source, eyes) if eye_input_mode == "closed-stroke" else closed_eye(source, eyes)
    if eye:
        image, left, top = eye
        result.append({"name": "eye_close", "image": image, "left": left, "top": top, "width": image.width, "height": image.height, "side": None, "fade": "eyeClose"})
    if mouth_path:
        mouth_mask = load_mask(mouth_path, width, height)
        if mouth_state == "closed":
            original = original_eye(source, [mouth_mask])
            opened = slightly_open_mouth(source, mouth_mask)
            if original:
                image, left, top = original
                result.append({"name": "mouth_close", "image": image, "left": left, "top": top, "width": image.width, "height": image.height, "side": None, "fade": "mouthClose"})
            if opened:
                image, left, top = opened
                result.append({"name": "mouth_open", "image": image, "left": left, "top": top, "width": image.width, "height": image.height, "side": None, "fade": "mouthOpen"})
        else:
            original = original_eye(source, [mouth_mask])
            mouth = closed_mouth(source, mouth_mask)
            if original:
                image, left, top = original
                result.append({"name": "mouth_open", "image": image, "left": left, "top": top, "width": image.width, "height": image.height, "side": None, "fade": "mouthOpen"})
            if mouth:
                image, left, top = mouth
                result.append({"name": "mouth_close", "image": image, "left": left, "top": top, "width": image.width, "height": image.height, "side": None, "fade": "mouthClose"})
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("layers_json", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--node", default=shutil.which("node") or "node")
    parser.add_argument("--source-image", type=Path)
    parser.add_argument("--eye-left-mask", type=Path)
    parser.add_argument("--eye-right-mask", type=Path)
    parser.add_argument("--eyebrow-left-mask", type=Path)
    parser.add_argument("--eyebrow-right-mask", type=Path)
    parser.add_argument("--mouth-mask", type=Path)
    parser.add_argument("--eye-left-absent", action="store_true")
    parser.add_argument("--eye-right-absent", action="store_true")
    parser.add_argument("--eye-input-mode", choices=("area", "closed-stroke"), default="area")
    parser.add_argument("--preserve-original-eyes", action="store_true")
    parser.add_argument("--mouth-state", choices=("closed", "slightly-open"), default="closed")
    args = parser.parse_args()

    source_json = args.layers_json.resolve()
    source_dir = source_json.parent
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    info = json.loads(source_json.read_text(encoding="utf-8"))
    width, height = int(info["width"]), int(info["height"])
    composite = Image.new("RGBA", (width, height))
    authored_expressions = manual_expressions(
        args.source_image,
        [path for path in (args.eye_left_mask, args.eye_right_mask) if path],
        [path for path in (args.eyebrow_left_mask, args.eyebrow_right_mask) if path],
        args.mouth_mask,
        width,
        height,
        args.eye_input_mode,
        args.preserve_original_eyes,
        inferred_eye_masks(info, source_dir, width, height),
        args.mouth_state,
    )

    with tempfile.TemporaryDirectory(prefix="rigging-v1-", dir=output_dir) as temp_name:
        temp = Path(temp_name)
        payload_layers = []
        package_layers = []
        layer_images = {}
        neutral_layer_keys = set()
        for index, record in enumerate(info["layers"]):
            source = source_dir / record["filename"]
            normalized = runtime_name(record["name"])
            if normalized == "mouth_open":
                continue
            with Image.open(source) as opened:
                image = opened.convert("RGBA")
            left, top = int(record["left"]), int(record["top"])
            alpha_over(composite, image, left, top)
            raw_name = f"layer_{index:02d}.rgba"
            (temp / raw_name).write_bytes(image.tobytes())
            part_id = file_id(normalized)
            payload_layers.append(
                {
                    "_key": f"part:{part_id}",
                    "name": normalized,
                    "raw": raw_name,
                    "left": left,
                    "top": top,
                    "width": image.width,
                    "height": image.height,
                }
            )
            layer_images[f"part:{part_id}"] = (image, left, top)
            neutral_layer_keys.add(f"part:{part_id}")
            package_layers.append(
                {
                    "id": part_id,
                    "runtimeName": normalized,
                    "sourceLayerName": record["name"],
                    "file": f"layers/{part_id}.png",
                    "left": left,
                    "top": top,
                    "width": image.width,
                    "height": image.height,
                    "depthMedian": record.get("depth_median"),
                    "source": source,
                }
            )

        for index, expression in enumerate(authored_expressions):
            image = expression["image"]
            neutral_mouth = (
                args.mouth_state == "closed" and expression["name"] == "mouth_close"
            ) or (
                args.mouth_state == "slightly-open" and expression["name"] == "mouth_open"
            )
            if expression["name"] in ("eye_open_original", "eyebrow") or neutral_mouth:
                alpha_over(composite, image, int(expression["left"]), int(expression["top"]))
            raw_name = f"expression_{index:02d}.rgba"
            (temp / raw_name).write_bytes(image.tobytes())
            payload_layers.append(
                {
                    "_key": f"expression:{expression['name']}",
                    "name": expression["name"],
                    "raw": raw_name,
                    "left": expression["left"],
                    "top": expression["top"],
                    "width": image.width,
                    "height": image.height,
                }
            )
            expression_key = f"expression:{expression['name']}"
            layer_images[expression_key] = (image, int(expression["left"]), int(expression["top"]))
            if expression["name"] in ("eye_open_original", "eyebrow") or neutral_mouth:
                neutral_layer_keys.add(expression_key)

        authored_records = [{"id": item["name"]} for item in authored_expressions]
        initial_order = default_layer_order(package_layers, authored_records)
        order_index = {key: index for index, key in enumerate(initial_order)}
        payload_layers.sort(key=lambda item: order_index.get(item["_key"], len(order_index)))
        composite = Image.new("RGBA", (width, height))
        for layer_key in initial_order:
            if layer_key not in neutral_layer_keys:
                continue
            image, left, top = layer_images[layer_key]
            alpha_over(composite, image, left, top)
        for item in payload_layers:
            item.pop("_key", None)

        composite_record = {
            "raw": "composite.rgba",
            "width": width,
            "height": height,
        }
        (temp / composite_record["raw"]).write_bytes(composite.tobytes())
        payload = {
            "width": width,
            "height": height,
            "composite": composite_record,
            "layers": payload_layers,
            "allowGeneric": not bool(authored_expressions),
        }
        payload_path = temp / "payload.json"
        payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        psd_path = output_dir / "character.psd"
        rig_summary_path = temp / "rig-summary.json"
        writer = Path(__file__).with_name("write_psd.js")
        subprocess.run(
            [args.node, str(writer), str(payload_path), str(psd_path), str(rig_summary_path)],
            check=True,
        )
        rig_summary = json.loads(rig_summary_path.read_text(encoding="utf-8"))

        expression_files = []
        if authored_expressions:
            for expression in authored_expressions:
                png_name = expression["name"] + ".png"
                expression["image"].save(output_dir / png_name)
                expression_files.append((expression, output_dir / png_name))
        else:
            for synthetic in rig_summary["synthetic"]:
                raw = (temp / synthetic["raw"]).read_bytes()
                image = Image.frombytes(
                    "RGBA", (int(synthetic["width"]), int(synthetic["height"])), raw
                )
                png_name = synthetic["name"] + ".png"
                image.save(output_dir / png_name)
                expression_files.append((synthetic, output_dir / png_name))

    composite_path = output_dir / "composite.png"
    composite.save(composite_path)
    warnings = filter_absent_eye_warnings(
        [localize_warning(message) for message in rig_summary["warnings"]],
        args.eye_left_absent, args.eye_right_absent,
    )
    manifest = {
        "schemaVersion": 1,
        "status": "needs_review" if rig_summary["warnings"] else "ready",
        "canvas": {"width": width, "height": height, "origin": "top-left"},
        "parts": [
            {key: value for key, value in part.items() if key != "source"}
            for part in package_layers
        ],
        "expressions": [
            {
                "id": synthetic["name"],
                "file": f"expressions/{path.name}",
                "left": synthetic["left"],
                "top": synthetic["top"],
                "width": synthetic["width"],
                "height": synthetic["height"],
                "side": synthetic.get("side"),
                "fade": synthetic.get("fade"),
            }
            for synthetic, path in expression_files
        ],
        "anchors": rig_summary["anchors"],
        "warnings": warnings,
        "synthetic": rig_summary["synth"],
        "expressionSource": (
            "user_closed_eye_stroke"
            if authored_expressions and args.eye_input_mode == "closed-stroke"
            else "user_mask_derived"
            if authored_expressions
            else "generic_fallback"
        ),
        "originalEyePreserved": any(item["name"] == "eye_open_original" for item in authored_expressions),
        "originalEyebrowsPreserved": any(item["name"] == "eyebrow" for item in authored_expressions),
        "sourceMouthState": args.mouth_state,
        "originalMouthPreserved": any(item["name"] == "mouth_open" for item in authored_expressions)
        if args.mouth_state == "slightly-open"
        else any(item["name"] == "mouth_close" for item in authored_expressions),
    }
    manifest["layerOrder"] = default_layer_order(manifest["parts"], manifest["expressions"])
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    unity_guide = output_dir / "UNITY_IMPORT.md"
    unity_guide.write_text(
        """# Unity 2D Animation import

1. `layers/`와 `expressions/`의 PNG를 Unity 프로젝트의 `Assets` 아래에 복사합니다.
2. 각 PNG의 Texture Type을 `Sprite (2D and UI)`로, Mesh Type을 `Full Rect`로 설정합니다.
3. Pivot은 캔버스 좌상단 기준 `manifest.json`의 `left`, `top`, `width`, `height`를 사용해 맞춥니다.
4. 자동 배치를 쓰려면 ZIP의 `Unity/Runtime`과 `Unity/Editor`를 프로젝트 `Assets/RiggingV1` 아래에 복사합니다.
5. Unity 메뉴 `Tools > Sprite Lab > Import Rigging V1 ZIP`에서 원본 ZIP을 선택합니다.
6. 생성된 Prefab은 눈 깜박임, 입 open/close, 앞·뒤 머리카락 회전을 미리 설정합니다.
7. 더 자연스러운 변형은 Unity 2D Animation의 뼈·메시·웨이트를 수동으로 추가합니다.
8. `manifest.json`의 `status`가 `needs_review`면 경계, 빈 영역, 누락 파츠를 먼저 확인합니다.

V1 자동 결과는 리깅 초안입니다. 손·발·장비가 겹치거나 측면 얼굴인 입력은 수동 보정이 필요할 수 있습니다.
""",
        encoding="utf-8",
    )

    zip_path = output_dir / "character-unity-parts.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(psd_path, "character.psd")
        archive.write(composite_path, "composite.png")
        archive.write(manifest_path, "manifest.json")
        archive.write(unity_guide, "UNITY_IMPORT.md")
        for part in package_layers:
            archive.write(part["source"], part["file"])
        for _, path in expression_files:
            archive.write(path, f"expressions/{path.name}")
        unity_root = Path(__file__).resolve().parent.parent / "unity-package"
        if unity_root.is_dir():
            for unity_file in sorted(unity_root.rglob("*.cs")):
                archive.write(unity_file, "Unity/" + unity_file.relative_to(unity_root).as_posix())

    print(
        json.dumps(
            {
                "psd": str(psd_path),
                "zip": str(zip_path),
                "layers": len(package_layers),
                "expressions": len(expression_files),
                "warnings": warnings,
                "synth": rig_summary["synth"],
            },
            ensure_ascii=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
