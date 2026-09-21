"""YuE2 instrumental BGM runner isolated from the web server environment."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from collections import deque


ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = ROOT / "vendor" / "YuE"
VENV_PYTHON = ROOT / ".venv-yue2" / "Scripts" / "python.exe"
RUNTIME_ROOT = Path(os.environ.get("YUE2_RUNTIME", ROOT / "yue2-runtime")).resolve()
MODEL_ROOT = RUNTIME_ROOT / "models" / "YuE2-3B"
VAE_ROOT = RUNTIME_ROOT / "models" / "YuE2-Vae"
RESULT_ROOT = ROOT / "outputs" / "music"
DRIVER = ROOT / "tools" / "run_yue2_job.py"
NAR_QUERY_CHUNK_SIZE = int(os.environ.get("YUE2_NAR_QUERY_CHUNK_SIZE", "1024"))

# Replaced by team_server so progress is persisted in the shared queue.
update_job = lambda *_args, **_kwargs: None


def _model_ready(folder: Path) -> bool:
    return (folder / "config.json").is_file() and any(folder.glob("*.safetensors"))


def status_payload() -> dict:
    source_ready = (SOURCE_ROOT / "src" / "yue2" / "pipeline.py").is_file()
    runtime_ready = VENV_PYTHON.is_file() and DRIVER.is_file()
    models_ready = _model_ready(MODEL_ROOT) and _model_ready(VAE_ROOT)
    return {
        "sourceReady": source_ready,
        "runtimeReady": runtime_ready,
        "modelsReady": models_ready,
        "ready": source_ready and runtime_ready and models_ready,
        "profile": f"RTX 5060 Ti 16GB · FP8 AR · CPU offload · NAR chunk {NAR_QUERY_CHUNK_SIZE}",
    }


def run_job(job_id: str, payload: dict) -> None:
    if not status_payload()["ready"]:
        raise RuntimeError("YuE2 런타임 또는 모델이 준비되지 않았습니다. setup_yue2.bat을 확인하세요.")
    folder = (RESULT_ROOT / job_id).resolve()
    if not folder.is_relative_to(RESULT_ROOT.resolve()):
        raise RuntimeError("BGM 결과 경로를 만들 수 없습니다.")
    folder.mkdir(parents=True, exist_ok=False)
    request_path = folder / "request.json"
    request_path.write_text(json.dumps({
        "id": job_id,
        "style": payload["resolvedPrompt"],
        "lyrics": "",
        "cot": payload.get("cot", "full"),
        "seed": payload["seed"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    update_job(job_id, state="generating", message="YuE2가 인스트루멘털 BGM을 생성하는 중")
    command = [
        str(VENV_PYTHON), str(DRIVER),
        "--request", str(request_path),
        "--output", str(folder),
        "--model", str(MODEL_ROOT),
        "--vae", str(VAE_ROOT),
        "--budget", "16",
        "--quantization", "fp8",
        "--offload-ar",
        "--nar-query-chunk-size", str(NAR_QUERY_CHUNK_SIZE),
    ]
    process = subprocess.Popen(
        command,
        cwd=SOURCE_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    recent = deque(maxlen=30)
    assert process.stdout is not None
    for raw_line in process.stdout:
        line = raw_line.strip()
        if not line:
            continue
        recent.append(line)
        if line.startswith("[YuE2]"):
            update_job(job_id, state="generating", message=line.removeprefix("[YuE2]").strip())
    return_code = process.wait()
    if return_code:
        detail = "\n".join(recent).strip()[-3000:] or "YuE2 실행 실패"
        raise RuntimeError(detail)
    audio = folder / "audio.flac"
    if not audio.is_file():
        raise RuntimeError("YuE2가 오디오 파일을 만들지 못했습니다.")
    metadata = {}
    result_path = folder / "result.json"
    if result_path.is_file():
        metadata = json.loads(result_path.read_text(encoding="utf-8"))
    base = f"/outputs/music/{job_id}"
    result = {
        "state": "complete",
        "message": "BGM 생성 완료",
        "audio": base + "/audio.flac",
        "duration": metadata.get("audio_seconds"),
        "resolvedPrompt": payload["resolvedPrompt"],
    }
    if (folder / "score.abc").is_file():
        result["score"] = base + "/score.abc"
    update_job(job_id, **result)
