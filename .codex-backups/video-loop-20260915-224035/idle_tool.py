from __future__ import annotations

import base64
import io
import json
import mimetypes
import os
import random
import shutil
import subprocess
import threading
import time
import uuid
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import av
import numpy as np
import requests
from PIL import Image
from scipy import ndimage
from subject_prompts import SUBJECT_DEFAULTS, subject_constraints


ROOT = Path(__file__).resolve().parent
AMD_BACKEND = os.environ.get("SPRITE_BACKEND", "nvidia") == "amd"
COMFY_ROOT = ROOT / ("ComfyUI-amd" if AMD_BACKEND else "ComfyUI")
PYTHON = ROOT / (".venv-amd" if AMD_BACKEND else ".venv") / "Scripts" / "python.exe"
WEB_ROOT = ROOT / "web"
OUTPUT_ROOT = ROOT / "outputs"
COMFY_OUTPUT = OUTPUT_ROOT / "comfy"
RESULT_ROOT = OUTPUT_ROOT / "results"
LOG_ROOT = ROOT / "logs"
LICENSE_MARKER = ROOT / "MINIMAX_H3_LICENSE_APPROVED.txt"
COMFY_URL = "http://127.0.0.1:8189"
TOOL_HOST = "127.0.0.1"
TOOL_PORT = 7866

MODEL_FILES = {
    "diffusion": COMFY_ROOT / "models" / "diffusion_models" / "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
    "text_encoder": COMFY_ROOT / "models" / "text_encoders" / ("qwen3vl_32b_minimax_h3_int8_convrot.safetensors" if AMD_BACKEND else "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"),
    "video_vae": COMFY_ROOT / "models" / "vae" / "minimax_h3_video_vae_fp16.safetensors",
    "audio_vae": COMFY_ROOT / "models" / "vae" / "minimax_h3_audio_vae_fp32.safetensors",
    "turbo_lora": COMFY_ROOT / "models" / "loras" / "minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors",
}

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


def comfy_online() -> bool:
    try:
        return requests.get(f"{COMFY_URL}/system_stats", timeout=2).ok
    except requests.RequestException:
        return False


def start_comfy() -> subprocess.Popen | None:
    if comfy_online():
        return None
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    COMFY_OUTPUT.mkdir(parents=True, exist_ok=True)
    stdout = (LOG_ROOT / "comfy.stdout.log").open("a", encoding="utf-8")
    stderr = (LOG_ROOT / "comfy.stderr.log").open("a", encoding="utf-8")
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        [
            str(PYTHON),
            str(COMFY_ROOT / "main.py"),
            "--listen", "127.0.0.1",
            "--port", "8189",
            "--disable-smart-memory",
            "--disable-pinned-memory",
            "--output-directory", str(COMFY_OUTPUT),
        ],
        cwd=COMFY_ROOT,
        stdout=stdout,
        stderr=stderr,
        creationflags=creationflags,
    )
    for _ in range(120):
        if comfy_online():
            return process
        if process.poll() is not None:
            raise RuntimeError(f"ComfyUI exited. Check {LOG_ROOT / 'comfy.stderr.log'}")
        time.sleep(1)
    raise TimeoutError("ComfyUI did not become ready within 120 seconds.")


def status_payload() -> dict:
    model_status = {
        name: {
            "ready": path.exists(),
            "path": str(path),
            "gb": round(path.stat().st_size / 1_000_000_000, 2) if path.exists() else 0,
        }
        for name, path in MODEL_FILES.items()
    }
    return {
        "comfy": comfy_online(),
        "licenseConfirmed": LICENSE_MARKER.exists(),
        "modelsReady": all(item["ready"] for item in model_status.values()),
        "models": model_status,
    }


def upload_image(image_bytes: bytes, filename: str) -> str:
    safe_name = f"h3_idle_{uuid.uuid4().hex[:10]}_{Path(filename).name}"
    response = requests.post(
        f"{COMFY_URL}/upload/image",
        files={"image": (safe_name, image_bytes, "image/png")},
        data={"type": "input", "overwrite": "false"},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("name", safe_name)


def prepare_reference_image(image_bytes: bytes, width: int, height: int, motion_padding: int = 0) -> bytes:
    """Fit the source without distortion onto the exact H3 canvas size."""
    source = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    if type(motion_padding) is not int or motion_padding not in (0,10,20,30):
        raise ValueError('동작 여백은 0, 10, 20, 30% 중 선택하세요.')
    scale = min(width / source.width, height / source.height) * (1-motion_padding/100)
    resized_size = (
        max(1, round(source.width * scale)),
        max(1, round(source.height * scale)),
    )
    resized = source.resize(resized_size, Image.Resampling.LANCZOS)
    if source.getchannel("A").getextrema()[0] < 255:
        # H3 encodes RGB and otherwise interprets transparent pixels as black.
        # A deliberate neutral matte is more stable and easier to remove later.
        canvas = Image.new("RGBA", (width, height), (128, 128, 128, 255))
        canvas.alpha_composite(resized, ((width - resized.width) // 2, (height - resized.height) // 2))
    else:
        rgb = np.asarray(source.convert("RGB"))
        border = np.concatenate((rgb[:8].reshape(-1, 3), rgb[-8:].reshape(-1, 3), rgb[:, :8].reshape(-1, 3), rgb[:, -8:].reshape(-1, 3)))
        fill = tuple(int(value) for value in np.median(border, axis=0)) + (255,)
        canvas = Image.new("RGBA", (width, height), fill)
        canvas.alpha_composite(resized, ((width - resized.width) // 2, (height - resized.height) // 2))
    output = io.BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()


def frame_length(seconds: float) -> int:
    frames = max(5, round(seconds * 24))
    return frames + (5 - frames % 17) % 17


ANIMATION_DEFAULTS = {
    "idle": "one very slow shallow breathing cycle, barely perceptible movement of the upper torso, tiny secondary movement at hair tips and clothing hems, feet stay at their original screen coordinates",
    "walk": "walk cycle in place, alternating steps, natural arm swing, consistent rhythm",
    "run": "run cycle in place, energetic alternating strides and arm swing",
    "attack": "one clear weapon attack, readable anticipation, strike and follow-through",
    "cast": "one clear magic casting action, hands gather energy and release it forward",
    "hit": "brief impact reaction, recoil backward and regain balance",
    "death": "lose balance and fall into a clearly readable defeated pose",
    "jump": "crouch, jump upward and land back in the starting position",
    "custom": "one clear game character animation",
}


FACING_PROMPTS = {
    "preserve": "Maintain the exact facing direction, head angle, torso orientation and camera-relative view from <Picture 1> throughout every frame. Never rotate toward or away from the camera.",
    "right": "Strict screen-right-facing side profile throughout every frame. Head, eyes, torso, hips, feet and weapon remain oriented to screen right. The action and projectile travel only toward screen right. Never face the camera.",
    "left": "Strict screen-left-facing side profile throughout every frame. Head, eyes, torso, hips, feet and weapon remain oriented to screen left. The action and projectile travel only toward screen left. Never face the camera.",
    "front": "Maintain a strict front-facing view throughout every frame. Never turn into a side or rear view.",
    "back": "Maintain a strict rear-facing view throughout every frame. Never turn toward the camera.",
}


MOTION_PROMPTS = {
    'low': 'Use restrained but visible movement with small joint excursions and minimal secondary motion.',
    'normal': 'Use clearly visible, natural movement readable at game-sprite scale, with moderate joint excursions and delayed follow-through of hair tips and clothing hems.',
    'high': 'Use pronounced, controlled movement with larger joint excursions and clear anticipation and follow-through; keep the entire character and equipment inside the canvas.',
}
ANIMATION_DEFAULTS['idle'] = 'one slow breathing cycle with a visible rise and fall of the shoulders and chest, a small lateral weight shift through the hips, hair tips and clothing hems follow the body with a slight delay, both feet remain planted at their original screen coordinates'

LEGACY_IDLE_PROMPTS = {
    ANIMATION_DEFAULTS['idle'],
    'one very slow shallow breathing cycle, barely perceptible movement of the upper torso, tiny secondary movement at hair tips and clothing hems, feet stay at their original screen coordinates',
    'gentle breathing, subtle blinking, slight hair and clothing sway, feet remain planted',
}
ANIMATION_DEFAULTS['idle'] = 'continuous rhythmic breathing with a visible rise and fall of the shoulders and chest, ongoing small lateral weight shifts through the hips, hair tips and clothing hems follow the body with a slight delay throughout the clip, both feet remain planted at their original screen coordinates'
PROMPT_REVISION = 'sprite-motion-v6-subject-types'
DEFAULT_NEGATIVE = 'scenery, textured background, changing background'


def guidance_options(payload):
    enabled = payload.get('negativeEnabled', False)
    if not isinstance(enabled, bool):
        raise ValueError('네거티브 사용 여부는 체크박스로 선택하세요.')
    if not enabled:
        return False, '', 1.0
    negative = payload.get('negativePrompt', DEFAULT_NEGATIVE)
    cfg = payload.get('cfgScale', 1.5)
    if not isinstance(negative, str) or not negative.strip() or len(negative)>2000:
        raise ValueError('네거티브 프롬프트는 1~2000자로 입력하세요.')
    if isinstance(cfg,bool) or not isinstance(cfg,(int,float)) or not 1.1<=cfg<=2.0:
        raise ValueError('실험 CFG는 1.1~2.0 사이여야 합니다.')
    return True, negative.strip(), float(cfg)


def animation_prompt(user_prompt: str, animation_type: str, loop: bool, facing: str = "preserve",
                     seconds: float = 5, flat_background: bool = False, blink_mode: str = 'none',
                     motion_strength: str = 'normal', subject_type: str = 'human') -> str:
    if subject_type not in ('human', *SUBJECT_DEFAULTS):
        raise ValueError('잘못된 대상 유형입니다.')
    if motion_strength not in MOTION_PROMPTS:
        raise ValueError('잘못된 움직임 강도입니다.')
    animation_type = animation_type if animation_type in ANIMATION_DEFAULTS else "custom"
    defaults = ANIMATION_DEFAULTS if subject_type == 'human' else SUBJECT_DEFAULTS[subject_type]
    detail = user_prompt.strip() or defaults[animation_type]
    if subject_type == 'human' and animation_type == 'idle' and detail in LEGACY_IDLE_PROMPTS:
        # Old browser tabs may still submit the former default verbatim.
        detail = ANIMATION_DEFAULTS['idle']
    # Keep timestamps consistent with ComfyUI's 17k+5 frame grid.
    duration = frame_length(seconds) / 24
    alignment = f'<Picture 1> supplies the complete opening image of [Shot 1] at 0.00 seconds.'
    if loop:
        alignment += f' <Picture 2> supplies its closing image at {duration:.2f} seconds; both images show the same composition.'
    cycle = (f'The movement eases out from the opening pose, develops through a readable motion arc, and settles back into the pose in <Picture 2> by {duration:.2f} seconds. '
             'The closing character scale and placement match the opening for a seamless loop.' if loop else
             'The action happens once: readable preparation, execution, then a settled final pose. The viewpoint stays unchanged.')
    if animation_type == 'idle':
        cycle = (f'This is a continuous idle motion already in progress at 0.00 seconds and still in progress at {duration:.2f} seconds. '
                 'Maintain an even breathing rhythm and consistent motion amplitude throughout the entire clip, including its final two seconds. '
                 'Motion flows through the ending without a finishing gesture, slowdown, or held resting pose. ')
        if loop:
            cycle += ('The closing pose matches <Picture 2> at the same phase of the ongoing motion as the opening; '
                      'movement direction and speed connect smoothly across the loop boundary. '
                      'The closing character scale and placement match the opening for a seamless loop.')
    facing_prompt = FACING_PROMPTS.get(facing, FACING_PROMPTS["preserve"])
    background = (
        'The character is a separate illustrated element over a perfectly flat, uniform medium-gray color field matching the input matte. '
        'This gray field fills every exposed area around and between the moving limbs, with the same color and brightness from edge to edge in every frame. '
        'It is a featureless two-dimensional color layer, not a physical location. '
        if flat_background else
        'The background already visible in the opening image stays unchanged in layout, colors and brightness; only the character animates. '
    )
    eyes = ('The eyelids and visible eye shapes stay exactly as drawn in the opening image throughout the clip; gaze stays fixed. '
            'No blinking or repeated facial expressions. ' if blink_mode == 'none' else
            'Allow at most one brief natural blink near the middle of the clip; otherwise retain the opening eye shape and gaze. ')
    anatomy = 'The opening character size, screen placement, head-to-body proportions, costume, equipment, linework and painted shading are retained. '
    constraints = facing_prompt + ' ' + eyes + 'The mouth keeps its original shape without speaking. '
    motion = MOTION_PROMPTS[motion_strength]
    if subject_type != 'human':
        anatomy = 'The original subject scale, composition, silhouette, component proportions, linework and painted shading are retained. '
        constraints, motion = subject_constraints(subject_type, facing, motion_strength, blink_mode, animation_type)
        cycle = cycle.replace('breathing rhythm', 'motion rhythm')
        background = background.replace('moving limbs', 'moving parts')
    return (alignment + '\n\n'
        'integrated_multimodal_description: [Shot 1] A single continuous game-sprite animation retaining the exact illustration style of the input. '
        + anatomy + 'The camera holds a static shot throughout: identical framing and magnification, with the full character remaining inside the original canvas. '
        + background + 'The colors and shading painted on the character remain stable; illumination does not change. '
        + constraints
        + f'Subject movement only: {detail}. ' + motion + ' ' + cycle
        + '\n\noverall_soundscape: N/A\n\nnon_diegetic_music: N/A')


def build_workflow(image_name: str, prompt: str, seconds: float, width: int, height: int, seed: int,
                   animation_type: str = "idle", loop: bool = True, facing: str = "preserve",
                   flat_background: bool = False, blink_mode: str = 'none',
                   negative_enabled: bool = False, negative_prompt: str = DEFAULT_NEGATIVE,
                   cfg_scale: float = 1.5, sampling_mode: str = 'quality', motion_strength: str = 'normal',
                   subject_type: str = 'human') -> dict:
    if sampling_mode not in ('quality','turbo'):
        raise ValueError('잘못된 생성 모드입니다.')
    negative_enabled, negative_prompt, cfg_scale = guidance_options({
        'negativeEnabled': negative_enabled, 'negativePrompt': negative_prompt, 'cfgScale': cfg_scale})
    video_inputs = {
        "clip": ["3", 0], "vae": ["4", 0], "first_frame": ["1", 0],
        "prompt": animation_prompt(prompt, animation_type, loop, facing, seconds, flat_background, blink_mode, motion_strength, subject_type),
        "width": width, "height": height, "length": frame_length(seconds),
    }
    # A matching final reference strongly biases cyclic actions toward a closed loop.
    # One-shot actions intentionally omit it so they can end in a different pose.
    if loop:
        video_inputs["last_frame"] = ["1", 0]
    workflow = {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "2": {"class_type": "UNETLoader", "inputs": {
            "unet_name": MODEL_FILES["diffusion"].name, "weight_dtype": "default"}},
        "3": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": MODEL_FILES["text_encoder"].name, "type": "minimax", "device": "default"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": MODEL_FILES["video_vae"].name}},
        "5": {"class_type": "VAELoader", "inputs": {"vae_name": MODEL_FILES["audio_vae"].name}},
        "6": {"class_type": "MiniMaxH3ImageToVideo", "inputs": video_inputs},
        "7": {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["2", 0], "lora_name": MODEL_FILES["turbo_lora"].name, "strength_model": 1.0}},
        "8": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "9": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "10": {"class_type": "BasicScheduler", "inputs": {
            "model": ["7", 0], "scheduler": "simple", "steps": 4, "denoise": 1.0}},
        "11": {"class_type": "BasicGuider", "inputs": {"model": ["7", 0], "conditioning": ["6", 0]}},
        "12": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["8", 0], "guider": ["11", 0], "sampler": ["9", 0],
            "sigmas": ["10", 0], "latent_image": ["6", 1]}},
        "13": {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["4", 0]}},
        "14": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["12", 0], "vae": ["5", 0]}},
        "15": {"class_type": "CreateVideo", "inputs": {
            "images": ["13", 0], "audio": ["14", 0], "fps": 24.0, "bit_depth": 8, "color_space": "sRGB"}},
        "16": {"class_type": "SaveVideo", "inputs": {
            "video": ["15", 0], "filename_prefix": "h3_idle/idle", "format": "mp4", "codec": {"codec": "h264"}}},
    }
    if negative_enabled:
        # Both branches must retain identical image order, keyframes and AV geometry.
        negative_inputs = dict(video_inputs)
        alignment = video_inputs['prompt'].split('\n\n',1)[0]
        negative_inputs['prompt'] = (alignment + '\n\nintegrated_multimodal_description: [Shot 1] '
            + negative_prompt + '\n\noverall_soundscape: N/A\n\nnon_diegetic_music: N/A')
        workflow['17'] = {'class_type': 'MiniMaxH3ImageToVideo', 'inputs': negative_inputs}
        workflow['11'] = {'class_type': 'CFGGuider', 'inputs': {
            'model': ['7',0], 'positive': ['6',0], 'negative': ['17',0], 'cfg': cfg_scale}}
    if sampling_mode == 'quality':
        workflow.pop('7')
        workflow['10']['inputs']['model'] = ['2',0]
        workflow['10']['inputs']['steps'] = 20
        workflow['11']['inputs']['model'] = ['2',0]
    return workflow


def find_saved_video(history: dict) -> Path:
    output = history.get("outputs", {}).get("16", {})

    def walk(value):
        if isinstance(value, dict):
            if "filename" in value and str(value["filename"]).lower().endswith((".mp4", ".webm", ".mkv")):
                yield value
            for child in value.values():
                yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)

    match = next(walk(output), None)
    if not match:
        raise RuntimeError("ComfyUI completed but did not report a saved video.")
    path = COMFY_OUTPUT / match.get("subfolder", "") / match["filename"]
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def remove_flat_background(image: Image.Image, tolerance: int = 24) -> Image.Image:
    """Remove only border-connected colors close to the median border color."""
    rgba = np.array(image.convert("RGBA"))
    rgb = rgba[:, :, :3].astype(np.float32)
    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]))
    color = np.median(border, axis=0)
    distance = np.max(np.abs(rgb - color), axis=2)
    candidate = distance <= tolerance
    seed = np.zeros(candidate.shape, dtype=bool)
    seed[0] = candidate[0]
    seed[-1] = candidate[-1]
    seed[:, 0] = candidate[:, 0]
    seed[:, -1] = candidate[:, -1]
    background = ndimage.binary_propagation(seed, mask=candidate)
    rgba[background, 3] = 0
    return Image.fromarray(rgba)


def video_thumbnail(video_path: Path) -> bytes:
    """Decode only the first frame; no model inference or full-video loading."""
    with av.open(str(video_path)) as container:
        frame = next(container.decode(video=0), None)
        if frame is None:
            raise ValueError("Video contains no frames.")
        preview = frame.to_image().convert("RGB")
        preview.thumbnail((480, 480), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        preview.save(buffer, format="JPEG", quality=82)
        return buffer.getvalue()


def make_sprite_sheet(video_path: Path, output_path: Path, count: int, loop: bool = True,
                      transparent_path: Path | None = None, tolerance: int = 24) -> None:
    container = av.open(str(video_path))
    frames = [frame.to_image().convert("RGBA") for frame in container.decode(video=0)]
    container.close()
    if not frames:
        raise RuntimeError("No frames were decoded from the generated video.")
    count = max(2, min(count, len(frames)))
    # Looping clips omit the duplicated closing pose; one-shot actions retain their ending pose.
    final_index = len(frames) - (2 if loop and len(frames) > 2 else 1)
    indices = [round(i * final_index / (count - 1)) for i in range(count)]
    selected = [frames[index] for index in indices]
    cell_w = max(image.width for image in selected)
    cell_h = max(image.height for image in selected)
    columns = min(count, 8)
    rows = (count + columns - 1) // columns
    sheet = Image.new("RGBA", (cell_w * columns, cell_h * rows), (0, 0, 0, 0))
    for index, image in enumerate(selected):
        x = (index % columns) * cell_w + (cell_w - image.width) // 2
        y = (index // columns) * cell_h + (cell_h - image.height) // 2
        sheet.alpha_composite(image, (x, y))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, optimize=True)
    if transparent_path is not None:
        transparent = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
        for index, image in enumerate(selected):
            transparent.alpha_composite(remove_flat_background(image, tolerance),
                                        ((index % columns) * cell_w, (index // columns) * cell_h))
        transparent.save(transparent_path, optimize=True)


def _subject_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    """Find a colorful/light/dark character on a mostly neutral background."""
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    border = np.concatenate((rgb[:8].reshape(-1, 3), rgb[-8:].reshape(-1, 3), rgb[:, :8].reshape(-1, 3), rgb[:, -8:].reshape(-1, 3)))
    background = np.median(border, axis=0)
    color_distance = np.linalg.norm(rgb - background, axis=2)
    mask = color_distance > 38
    mask = ndimage.binary_opening(mask, iterations=1)
    mask = ndimage.binary_dilation(mask, iterations=max(3, min(image.size) // 70))
    mask = ndimage.binary_closing(mask, iterations=4)
    labels, total = ndimage.label(mask)
    objects = ndimage.find_objects(labels)
    candidates = []
    image_area = image.width * image.height
    for label_id, slices in enumerate(objects, start=1):
        if slices is None:
            continue
        ys, xs = slices
        area = int(np.count_nonzero(labels[ys, xs] == label_id))
        center_x = (xs.start + xs.stop) / 2
        center_y = (ys.start + ys.stop) / 2
        if area >= image_area * 0.0004 and image.width * 0.08 < center_x < image.width * 0.92 and image.height * 0.05 < center_y < image.height * 0.95:
            candidates.append((xs.start, ys.start, xs.stop, ys.stop, area))
    if not candidates:
        return (0, 0, image.width, image.height)
    # Keep the main component and nearby detailed pieces such as separated feet or hair.
    main = max(candidates, key=lambda item: item[4])
    mx = (main[0] + main[2]) / 2
    my = (main[1] + main[3]) / 2
    keep = [item for item in candidates if abs((item[0] + item[2]) / 2 - mx) < image.width * 0.33 and abs((item[1] + item[3]) / 2 - my) < image.height * 0.43]
    return (
        min(item[0] for item in keep),
        min(item[1] for item in keep),
        max(item[2] for item in keep),
        max(item[3] for item in keep),
    )


def stabilize_video(source_path: Path, output_path: Path, preserve_padding: bool = False) -> dict:
    """Normalize subject center and scale across frames without changing duration."""
    container = av.open(str(source_path))
    stream = container.streams.video[0]
    fps = stream.average_rate or 24
    frames = [frame.to_image().convert("RGB") for frame in container.decode(video=0)]
    container.close()
    if not frames:
        raise RuntimeError("No frames were decoded from the generated video.")
    boxes = np.asarray([_subject_bbox(frame) for frame in frames], dtype=np.float64)
    centers = np.column_stack(((boxes[:, 0] + boxes[:, 2]) / 2, (boxes[:, 1] + boxes[:, 3]) / 2))
    sizes = np.column_stack((boxes[:, 2] - boxes[:, 0], boxes[:, 3] - boxes[:, 1]))
    valid = (sizes[:, 0] < frames[0].width * 0.995) & (sizes[:, 1] < frames[0].height * 0.995)
    if not np.any(valid):
        raise RuntimeError("Could not isolate a character for stabilization.")
    target_center = np.median(centers[valid], axis=0)
    target_size = np.median(sizes[valid], axis=0)
    # Fill a useful sprite cell while retaining roughly 11% vertical safety margin.
    occupancy_scale = min(1.6, max(0.65, frames[0].height * 0.78 / max(target_size[1], 1)))
    if preserve_padding:
        occupancy_scale = min(1.0, occupancy_scale)
    target_size *= occupancy_scale
    stabilized = []
    # Use one transform for the whole clip: this preserves intended breathing/bobbing
    # and, importantly, does not introduce a new discontinuity at the loop seam.
    scale = float(occupancy_scale)
    center = target_center
    for frame in frames:
        inverse = 1.0 / scale
        transform = (
            inverse, 0.0, center[0] - target_center[0] * inverse,
            0.0, inverse, center[1] - target_center[1] * inverse,
        )
        corners = np.asarray(frame)[np.r_[:8, -8:]][:, np.r_[:8, -8:]].reshape(-1, 3)
        background = tuple(int(value) for value in np.median(corners, axis=0))
        stabilized.append(frame.transform(frame.size, Image.Transform.AFFINE, transform, resample=Image.Resampling.BICUBIC, fillcolor=background))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output = av.open(str(output_path), mode="w")
    output_stream = output.add_stream("libx264", rate=fps)
    output_stream.width, output_stream.height = stabilized[0].size
    output_stream.pix_fmt = "yuv420p"
    output_stream.options = {"crf": "18", "preset": "medium"}
    for image in stabilized:
        for packet in output_stream.encode(av.VideoFrame.from_image(image)):
            output.mux(packet)
    for packet in output_stream.encode():
        output.mux(packet)
    output.close()
    return {
        "frames": len(stabilized),
        "targetCenter": [round(float(value), 1) for value in target_center],
        "targetSize": [round(float(value), 1) for value in target_size],
        "scale": round(scale, 2),
    }


def update_job(job_id: str, **changes) -> None:
    with JOBS_LOCK:
        JOBS[job_id].update(changes)


def run_job(job_id: str, payload: dict) -> None:
    try:
        update_job(job_id, state="uploading", message="기준 이미지를 ComfyUI로 전송 중")
        encoded = payload["imageData"].split(",", 1)[-1]
        image_bytes = base64.b64decode(encoded, validate=True)
        source_image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        had_transparency = source_image.getchannel("A").getextrema()[0] < 255
        width = int(payload.get("width", 864))
        height = int(payload.get("height", 480))
        if width % 32 or height % 32 or width < 256 or height < 256:
            raise ValueError("해상도의 가로·세로는 256 이상이며 32의 배수여야 합니다.")
        motion_padding = payload.get('motionPadding',10)
        prepared_bytes = prepare_reference_image(image_bytes, width, height, motion_padding)
        result_dir = RESULT_ROOT / job_id
        result_dir.mkdir(parents=True, exist_ok=True)
        (result_dir / "reference_prepared.png").write_bytes(prepared_bytes)
        image_name = upload_image(prepared_bytes, payload.get("filename", "reference.png"))
        seed = int(payload.get("seed") or random.randrange(0, 2**63))
        animation_type = str(payload.get("animationType", "idle"))
        loop = bool(payload.get("loop", animation_type in {"idle", "walk", "run", "jump"}))
        facing = str(payload.get("facing", "preserve"))
        prompt = str(payload.get("prompt", ""))
        workflow = build_workflow(
            image_name,
            prompt,
            float(payload.get("duration", 5)),
            width,
            height,
            seed,
            animation_type,
            loop,
            facing,
            flat_background=had_transparency,
            blink_mode=payload.get('blinkMode','none'),
            motion_strength=payload.get('motionStrength','normal'),
            subject_type=payload.get('subjectType','human'),
            negative_enabled=payload.get('negativeEnabled',False),
            negative_prompt=payload.get('negativePrompt',DEFAULT_NEGATIVE),
            cfg_scale=payload.get('cfgScale',1.5),
            sampling_mode=payload.get('samplingMode','quality'),
        )
        # Local audit record for reproducible comparisons; never part of the public gallery.
        (result_dir / 'generation_prompt.json').write_text(json.dumps({
            'revision': PROMPT_REVISION, 'seed': seed, 'prompt': workflow['6']['inputs']['prompt'],
            'width': width, 'height': height, 'length': workflow['6']['inputs']['length'],
            'flatBackground': had_transparency, 'blinkMode': payload.get('blinkMode','none'),
            'motionPadding': motion_padding,
            'motionStrength': payload.get('motionStrength','normal'),
            'subjectType': payload.get('subjectType','human'),
            'negativeEnabled': '17' in workflow,
            'samplingMode': payload.get('samplingMode','quality'),
            'steps': workflow['10']['inputs']['steps'],
            'negativePrompt': workflow.get('17',{}).get('inputs',{}).get('prompt'),
            'cfgScale': workflow['11']['inputs'].get('cfg',1.0),
        },ensure_ascii=False,indent=2),encoding='utf-8')
        response = requests.post(f"{COMFY_URL}/prompt", json={"prompt": workflow}, timeout=60)
        if not response.ok:
            raise RuntimeError(f"ComfyUI rejected workflow: {response.text[:2000]}")
        prompt_id = response.json()["prompt_id"]
        update_job(job_id, state="generating", message=f"MiniMax H3가 {animation_type} 영상을 생성 중", promptId=prompt_id)
        deadline = time.time() + 4 * 60 * 60
        history = None
        while time.time() < deadline:
            result = requests.get(f"{COMFY_URL}/history/{prompt_id}", timeout=30).json()
            if prompt_id in result:
                history = result[prompt_id]
                break
            time.sleep(3)
        if history is None:
            raise TimeoutError("Generation exceeded four hours.")
        status = history.get("status", {})
        if status.get("status_str") == "error" or not status.get("completed", True):
            raise RuntimeError(f"ComfyUI generation failed: {json.dumps(status, ensure_ascii=False)[:2000]}")
        source_video = find_saved_video(history)
        raw_video_path = result_dir / f"{animation_type}_raw.mp4"
        video_path = result_dir / f"{animation_type}.mp4"
        shutil.copy2(source_video, raw_video_path)
        stabilization_warning = None
        if payload.get("stabilize", True):
            update_job(job_id, state="stabilizing", message="캐릭터 크기와 프레이밍을 정규화하는 중")
            try:
                stabilize_video(raw_video_path, video_path, preserve_padding=motion_padding>0)
            except Exception as error:
                stabilization_warning = str(error)
                shutil.copy2(raw_video_path, video_path)
        else:
            shutil.copy2(raw_video_path, video_path)
        update_job(job_id, state="packing", message="프레임을 골라 스프라이트 시트로 패킹 중")
        sheet_path = result_dir / f"{animation_type}_sprite_sheet.png"
        transparent_path = result_dir / f"{animation_type}_transparent.png" if payload.get("removeBackground", False) else None
        make_sprite_sheet(video_path, sheet_path, int(payload.get("frameCount", 8)), loop,
                          transparent_path, int(payload.get("backgroundTolerance", 24)))
        update_job(
            job_id,
            state="complete",
            message="완료",
            video=f"/outputs/results/{job_id}/{animation_type}.mp4",
            rawVideo=f"/outputs/results/{job_id}/{animation_type}_raw.mp4",
            spriteSheet=f"/outputs/results/{job_id}/{animation_type}_sprite_sheet.png",
            transparentSheet=f"/outputs/results/{job_id}/{animation_type}_transparent.png" if transparent_path else None,
            seed=seed,
            animationType=animation_type,
            loop=loop,
            facing=facing,
            warning=stabilization_warning,
        )
    except Exception as error:
        update_job(job_id, state="error", message=str(error))


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def send_json(self, payload: dict, status=HTTPStatus.OK):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/api/status":
            self.send_json(status_payload())
            return
        if path.startswith("/api/jobs/"):
            job_id = path.rsplit("/", 1)[-1]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            self.send_json(job or {"error": "job not found"}, HTTPStatus.OK if job else HTTPStatus.NOT_FOUND)
            return
        if path.startswith("/outputs/"):
            target = (ROOT / path.lstrip("/")).resolve()
            if not str(target).startswith(str(OUTPUT_ROOT.resolve())) or not target.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            data = target.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        target = WEB_ROOT / ("index.html" if path == "/" else path.lstrip("/"))
        if target.is_file() and str(target.resolve()).startswith(str(WEB_ROOT.resolve())):
            data = target.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "text/plain")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        if urlparse(self.path).path != "/api/generate":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        current = status_payload()
        if not current["licenseConfirmed"]:
            self.send_json({"error": "MiniMax H3 별도 라이선스 확인이 필요합니다."}, HTTPStatus.FORBIDDEN)
            return
        if not current["modelsReady"]:
            self.send_json({"error": "MiniMax H3 모델 파일이 아직 모두 준비되지 않았습니다."}, HTTPStatus.CONFLICT)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 30 * 1024 * 1024:
            self.send_json({"error": "잘못된 요청 크기입니다."}, HTTPStatus.BAD_REQUEST)
            return
        try:
            payload = json.loads(self.rfile.read(length))
            if not payload.get("imageData"):
                raise ValueError("기준 이미지를 선택하세요.")
            job_id = uuid.uuid4().hex
            with JOBS_LOCK:
                JOBS[job_id] = {"id": job_id, "state": "queued", "message": "대기 중"}
            threading.Thread(target=run_job, args=(job_id, payload), daemon=True).start()
            self.send_json({"jobId": job_id}, HTTPStatus.ACCEPTED)
        except Exception as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    process = start_comfy()
    server = ThreadingHTTPServer((TOOL_HOST, TOOL_PORT), Handler)
    url = f"http://{TOOL_HOST}:{TOOL_PORT}"
    print(f"MiniMax H3 Idle Tool: {url}")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if process is not None and process.poll() is None:
            process.terminate()


if __name__ == "__main__":
    main()
