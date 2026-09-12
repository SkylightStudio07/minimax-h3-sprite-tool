"""See-through layer separation and Anime2.5DRig packaging for the team server."""

from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time

from PIL import Image
import requests


ROOT = Path(__file__).resolve().parent


def _default_home() -> Path:
    configured = os.environ.get("RIGGING_HOME")
    if configured:
        return Path(configured).resolve()
    for candidate in (ROOT.parent, ROOT.parent / "111"):
        if (candidate / "runtime" / "ComfyUI" / "main.py").is_file():
            return candidate.resolve()
    return (ROOT.parent / "111").resolve()


RIGGING_HOME = _default_home()
COMFY_ROOT = RIGGING_HOME / "runtime" / "ComfyUI"
PYTHON = RIGGING_HOME / "runtime" / ".venv" / "Scripts" / "python.exe"
MODEL_ROOT = RIGGING_HOME / "models"
INPUT_ROOT = RIGGING_HOME / "input"
COMFY_OUTPUT = RIGGING_HOME / "outputs" / "comfy"
USER_ROOT = RIGGING_HOME / "runtime" / "comfy-user"
RESULT_ROOT = ROOT / "outputs" / "rigging"
PACKAGER = ROOT / "tools" / "build_rig_package.py"
COMFY_URL = os.environ.get("RIGGING_COMFY_URL", "http://127.0.0.1:8190")
LAYER_MODEL = "layerdifforg/seethroughv0.0.2_layerdiff3d"
DEPTH_MODEL = "layerdifforg/seethroughv0.0.1_marigold"


def _model_path(repo_id: str) -> Path:
    return MODEL_ROOT / "SeeThrough" / Path(repo_id)


def comfy_ready() -> bool:
    try:
        return requests.get(f"{COMFY_URL}/system_stats", timeout=2).ok
    except requests.RequestException:
        return False


def status_payload() -> dict:
    files_ready = all(
        (
            PYTHON.is_file(),
            (COMFY_ROOT / "main.py").is_file(),
            _model_path(LAYER_MODEL).is_dir(),
            _model_path(DEPTH_MODEL).is_dir(),
            PACKAGER.is_file(),
            (ROOT / "vendor" / "Anime2.5DRig" / "lib" / "rigger.js").is_file(),
        )
    )
    return {"comfy": comfy_ready(), "modelsReady": files_ready, "port": 8190}


def start_comfy() -> subprocess.Popen | None:
    if comfy_ready():
        return None
    missing = [
        path
        for path in (PYTHON, COMFY_ROOT / "main.py", _model_path(LAYER_MODEL), _model_path(DEPTH_MODEL))
        if not path.exists()
    ]
    if missing:
        raise RuntimeError("리깅 런타임 파일이 없습니다: " + ", ".join(map(str, missing)))
    INPUT_ROOT.mkdir(parents=True, exist_ok=True)
    COMFY_OUTPUT.mkdir(parents=True, exist_ok=True)
    USER_ROOT.mkdir(parents=True, exist_ok=True)
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        [
            str(PYTHON),
            str(COMFY_ROOT / "main.py"),
            "--listen",
            "127.0.0.1",
            "--port",
            "8190",
            "--disable-auto-launch",
            "--models-directory",
            str(MODEL_ROOT),
            "--input-directory",
            str(INPUT_ROOT),
            "--output-directory",
            str(COMFY_OUTPUT),
            "--user-directory",
            str(USER_ROOT),
        ],
        cwd=COMFY_ROOT,
        creationflags=creationflags,
    )
    for _ in range(120):
        if comfy_ready():
            return process
        if process.poll() is not None:
            raise RuntimeError("리깅 ComfyUI가 시작 중 종료되었습니다.")
        time.sleep(1)
    process.terminate()
    raise TimeoutError("리깅 ComfyUI 시작 시간이 초과되었습니다.")


def workflow(image_name: str, prefix: str, resolution: int, steps: int, seed: int) -> dict:
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "2": {
            "class_type": "SeeThrough_LoadLayerDiffModel",
            "inputs": {
                "model": LAYER_MODEL,
                "vae_ckpt": "",
                "unet_ckpt": "",
                "quant_mode": "none",
                "cache_tag_embeds": True,
                "group_offload": False,
                "auto_download": False,
            },
        },
        "3": {
            "class_type": "SeeThrough_GenerateLayers",
            "inputs": {
                "image": ["1", 0],
                "layerdiff_model": ["2", 0],
                "seed": seed,
                "resolution": resolution,
                "num_inference_steps": steps,
            },
        },
        "4": {
            "class_type": "SeeThrough_LoadDepthModel",
            "inputs": {
                "model": DEPTH_MODEL,
                "quant_mode": "none",
                "cache_tag_embeds": True,
                "group_offload": False,
                "auto_download": False,
            },
        },
        "5": {
            "class_type": "SeeThrough_GenerateDepth",
            "inputs": {
                "layers": ["3", 0],
                "depth_model": ["4", 0],
                "seed": seed,
                "resolution_depth": 720,
            },
        },
        "6": {
            "class_type": "SeeThrough_PostProcess",
            "inputs": {"layers_depth": ["5", 0], "tblr_split": True, "use_lama": False},
        },
        "7": {
            "class_type": "SeeThrough_SavePSD",
            "inputs": {"parts": ["6", 0], "filename_prefix": prefix},
        },
        "8": {
            "class_type": "SaveImage",
            "inputs": {"images": ["6", 1], "filename_prefix": prefix + "_preview"},
        },
    }


def _write_input(job_id: str, image_data: str) -> Path:
    try:
        raw = base64.b64decode(image_data.split(",")[-1], validate=True)
        with Image.open(io.BytesIO(raw)) as opened:
            opened.load()
            image = opened.convert("RGBA")
    except Exception as error:
        raise ValueError("리깅 입력 이미지를 읽을 수 없습니다.") from error
    if image.width * image.height > 24_000_000:
        raise ValueError("리깅 입력은 24MP 이하여야 합니다.")
    INPUT_ROOT.mkdir(parents=True, exist_ok=True)
    path = INPUT_ROOT / f"rigging_{job_id}.png"
    image.save(path)
    return path


def _write_mask(job_id: str, name: str, image_data: str) -> Path:
    try:
        raw = base64.b64decode(image_data.split(",")[-1], validate=True)
        with Image.open(io.BytesIO(raw)) as opened:
            opened.load()
            mask = opened.convert("RGBA")
    except Exception as error:
        raise ValueError(name + " 마스크를 읽을 수 없습니다.") from error
    path = INPUT_ROOT / f"rigging_{job_id}_{name}.png"
    mask.save(path)
    return path


def _wait_for_prompt(prompt_id: str, timeout: int = 3600) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = requests.get(f"{COMFY_URL}/history/{prompt_id}", timeout=30)
        response.raise_for_status()
        record = response.json().get(prompt_id)
        if record:
            status = record.get("status", {})
            if status.get("status_str") == "error":
                messages = status.get("messages", [])
                raise RuntimeError("See-through 처리 실패: " + json.dumps(messages, ensure_ascii=False)[-1000:])
            return record
        time.sleep(4)
    raise TimeoutError("레이어 분리 시간이 60분을 초과했습니다.")


def _latest_layers(prefix: str) -> Path:
    candidates = sorted(COMFY_OUTPUT.glob(prefix + "*_layers.json"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise RuntimeError("See-through 레이어 목록이 생성되지 않았습니다.")
    return candidates[-1]


def update_job(job_id: str, **changes) -> None:
    """Replaced by team_server while a queued job is running."""


def run_job(job_id: str, payload: dict) -> None:
    source = None
    mask_paths = {}
    try:
        update_job(job_id, state="uploading", message="리깅 입력 이미지를 준비하는 중")
        source = _write_input(job_id, payload["imageData"])
        for key, name in (("eyeLeftMask", "eye_left"), ("eyeRightMask", "eye_right"), ("mouthMask", "mouth")):
            if payload.get(key):
                mask_paths[name] = _write_mask(job_id, name, payload[key])
        resolution = int(payload.get("resolution", 1024))
        steps = int(payload.get("steps", 30))
        seed = int(payload.get("seed") or secrets.randbelow(2**31))
        prefix = f"rigging_{job_id}"
        update_job(job_id, state="separating", message="See-through가 얼굴·눈·입·머리카락 레이어를 분리하는 중")
        response = requests.post(
            f"{COMFY_URL}/prompt",
            json={"prompt": workflow(source.name, prefix, resolution, steps, seed)},
            timeout=60,
        )
        response.raise_for_status()
        prompt_id = response.json()["prompt_id"]
        update_job(job_id, state="separating", message="레이어와 깊이 정보를 생성하는 중", promptId=prompt_id)
        record = _wait_for_prompt(prompt_id)

        update_job(job_id, state="packing", message="PSD와 Unity PNG 패키지를 만드는 중")
        result_dir = RESULT_ROOT / job_id
        result_dir.mkdir(parents=True, exist_ok=True)
        layers_json = _latest_layers(prefix)
        package_command = [
                str(PYTHON),
                str(PACKAGER),
                str(layers_json),
                "--output-dir",
                str(result_dir),
                "--source-image",
                str(source),
            ]
        for name, option in (("eye_left", "--eye-left-mask"), ("eye_right", "--eye-right-mask"), ("mouth", "--mouth-mask")):
            if name in mask_paths:
                package_command.extend((option, str(mask_paths[name])))
        completed = subprocess.run(
            package_command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode:
            raise RuntimeError("Unity 패키지 생성 실패: " + completed.stderr[-1000:])

        preview_records = record.get("outputs", {}).get("8", {}).get("images", [])
        if preview_records:
            preview_source = COMFY_OUTPUT / preview_records[-1]["filename"]
            if preview_source.is_file():
                shutil.copy2(preview_source, result_dir / "preview.png")
        manifest = json.loads((result_dir / "manifest.json").read_text(encoding="utf-8"))
        base = f"/outputs/rigging/{job_id}"
        result = {
            "state": "complete",
            "message": "레이어 초안 생성 완료 · 경계와 누락 파츠를 검수하세요.",
            "qualityStatus": manifest["status"],
            "partCount": len(manifest["parts"]),
            "expressionCount": len(manifest["expressions"]),
            "warnings": manifest["warnings"],
            "expressionSource": manifest.get("expressionSource"),
            "psd": base + "/character.psd",
            "package": base + "/character-unity-parts.zip",
            "composite": base + "/composite.png",
            "preview": base + "/preview.png" if (result_dir / "preview.png").is_file() else None,
            "manifest": base + "/manifest.json",
            "player": f"/rigging-player/index.html?model={base}/character.psd",
        }
        update_job(job_id, **result)
    except Exception as error:
        update_job(job_id, state="error", message=str(error))
        raise
    finally:
        if source:
            source.unlink(missing_ok=True)
        for mask_path in mask_paths.values():
            mask_path.unlink(missing_ok=True)
