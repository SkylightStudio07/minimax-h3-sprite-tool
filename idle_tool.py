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


ROOT = Path(__file__).resolve().parent
COMFY_ROOT = ROOT / "ComfyUI"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
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
    "text_encoder": COMFY_ROOT / "models" / "text_encoders" / "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
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


def prepare_reference_image(image_bytes: bytes, width: int, height: int) -> bytes:
    """Fit the source without distortion onto the exact H3 canvas size."""
    source = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    scale = min(width / source.width, height / source.height)
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
    "idle": "gentle breathing, subtle blinking, slight hair and clothing sway, feet remain planted",
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


def animation_prompt(user_prompt: str, animation_type: str, loop: bool, facing: str = "preserve") -> str:
    animation_type = animation_type if animation_type in ANIMATION_DEFAULTS else "custom"
    detail = user_prompt.strip() or ANIMATION_DEFAULTS[animation_type]
    cycle = (
        "The motion is rhythmic and the final pose, position and silhouette match the opening pose for a seamless loop."
        if loop else
        "Perform the action once with a clear readable progression and a distinct final pose. Do not repeat the action."
    )
    facing_prompt = FACING_PROMPTS.get(facing, FACING_PROMPTS["preserve"])
    return (
        f"Game character {animation_type} animation. Use <Picture 1> as the exact character and design reference. "
        "Locked static camera, fixed framing and fixed scale; keep the complete character visible with safety margin. "
        "Preserve face, anatomy, costume, equipment, colors, silhouette and background consistently in every frame. "
        f"{facing_prompt} Motion: {detail}. {cycle} "
        "No camera motion, no zoom, no pan, no cut, no scene change, no morphing, no extra limbs or duplicated equipment. "
        "Audio: silence."
    )


def build_workflow(image_name: str, prompt: str, seconds: float, width: int, height: int, seed: int,
                   animation_type: str = "idle", loop: bool = True, facing: str = "preserve") -> dict:
    video_inputs = {
        "clip": ["3", 0], "vae": ["4", 0], "first_frame": ["1", 0],
        "prompt": animation_prompt(prompt, animation_type, loop, facing),
        "width": width, "height": height, "length": frame_length(seconds),
    }
    # A matching final reference strongly biases cyclic actions toward a closed loop.
    # One-shot actions intentionally omit it so they can end in a different pose.
    if loop:
        video_inputs["last_frame"] = ["1", 0]
    return {
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


def make_sprite_sheet(video_path: Path, output_path: Path, count: int, loop: bool = True) -> None:
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


def stabilize_video(source_path: Path, output_path: Path) -> dict:
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
        prepared_bytes = prepare_reference_image(image_bytes, width, height)
        result_dir = RESULT_ROOT / job_id
        result_dir.mkdir(parents=True, exist_ok=True)
        (result_dir / "reference_prepared.png").write_bytes(prepared_bytes)
        image_name = upload_image(prepared_bytes, payload.get("filename", "reference.png"))
        seed = int(payload.get("seed") or random.randrange(0, 2**63))
        animation_type = str(payload.get("animationType", "idle"))
        loop = bool(payload.get("loop", animation_type in {"idle", "walk", "run", "jump"}))
        facing = str(payload.get("facing", "preserve"))
        prompt = str(payload.get("prompt", ""))
        if had_transparency:
            prompt += ", perfectly uniform neutral gray background, identical in every frame, no lighting or background changes"
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
        )
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
                stabilize_video(raw_video_path, video_path)
            except Exception as error:
                stabilization_warning = str(error)
                shutil.copy2(raw_video_path, video_path)
        else:
            shutil.copy2(raw_video_path, video_path)
        update_job(job_id, state="packing", message="프레임을 골라 스프라이트 시트로 패킹 중")
        sheet_path = result_dir / f"{animation_type}_sprite_sheet.png"
        make_sprite_sheet(video_path, sheet_path, int(payload.get("frameCount", 8)), loop)
        update_job(
            job_id,
            state="complete",
            message="완료",
            video=f"/outputs/results/{job_id}/{animation_type}.mp4",
            rawVideo=f"/outputs/results/{job_id}/{animation_type}_raw.mp4",
            spriteSheet=f"/outputs/results/{job_id}/{animation_type}_sprite_sheet.png",
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
