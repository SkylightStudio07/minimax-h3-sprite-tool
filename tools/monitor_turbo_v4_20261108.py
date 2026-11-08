"""Observe the serialized Turbo v4 comparison queue without touching its prompts."""
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import av
import psutil
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/turbo-v4-comparison-20261108"
COMFY = "http://127.0.0.1:8189"
LOG = OUT / "monitor.log"
STDERR = ROOT / "logs/comfy.stderr.log"
STATE = OUT / "monitor-state.json"


def log(message):
    line = f"{datetime.now().astimezone().isoformat(timespec='seconds')} {message}"
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)


def save_progress(obj):
    path = OUT / "progress.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def validate_video(path):
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        meta = {"width": stream.width, "height": stream.height,
                "fps": float(stream.average_rate), "frames": stream.frames}
    expected = {"width": 768, "height": 768, "fps": 24.0, "frames": 73}
    if meta != expected:
        raise RuntimeError(f"Unexpected video metadata: {meta}")
    return meta


def resource_sample():
    free_gb = psutil.virtual_memory().available / 1024**3
    try:
        line = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used,memory.free,utilization.gpu", "--format=csv,noheader,nounits"],
            text=True, timeout=5).strip().splitlines()[0]
        used, free, util = [int(v.strip()) for v in line.split(",")]
        return {"time": time.time(), "ramAvailableGB": free_gb,
                "gpuMemoryUsedMB": used, "gpuMemoryFreeMB": free, "gpuUtilizationPct": util}
    except Exception as exc:
        return {"time": time.time(), "ramAvailableGB": free_gb,
                "gpuStatsUnavailable": str(exc)}


def tqdm_seconds(start_offset, end_offset=None):
    """Read a completed 8-step tqdm duration from this job's log segment."""
    if not STDERR.exists():
        return None, None
    with STDERR.open("rb") as f:
        f.seek(start_offset)
        raw = f.read() if end_offset is None else f.read(max(0, end_offset - start_offset))
    segment = raw.decode("utf-8", errors="replace").replace("\r", "\n")
    matches = re.findall(r"(?:100%\|[^\n]*?\|\s*)?8/8\s*\[([^\]]+)\]", segment)
    if not matches:
        return None, None
    m = re.match(r"\s*(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)\s*<", matches[-1])
    if not m:
        return None, None
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2))
    seconds = float(m.group(3))
    return hours * 3600 + minutes * 60 + seconds, "ComfyUI tqdm final 8/8 elapsed duration from logs/comfy.stderr.log"


def main():
    log("monitor started")
    peak_used = 0
    job_min_ram = None
    last_job = None
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"stderrOffsets": {}}
    # The first prompt was already executing before monitor start. Its initial 0/8
    # marker is recoverable because this comparison had not run earlier.
    if "turbo-v4-idle" not in state["stderrOffsets"] and STDERR.exists():
        with STDERR.open("rb") as f:
            data = f.read()
        hits = list(re.finditer(rb"0%\|[^\r\n]*\|\s*0/8\s*\[", data))
        if hits:
            state["stderrOffsets"]["turbo-v4-idle"] = hits[-1].start()
            STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    while True:
        sample = resource_sample()
        if "gpuMemoryUsedMB" in sample:
            peak_used = max(peak_used, sample["gpuMemoryUsedMB"])
        active = None
        for folder in sorted(OUT.iterdir()):
            pending = folder / "pending.json" if folder.is_dir() else None
            result = folder / "result.json" if folder.is_dir() else None
            if pending and pending.exists() and (not result or not result.exists()):
                active = (folder, json.loads(pending.read_text(encoding="utf-8")))
                break

        if active is None:
            progress_path = OUT / "progress.json"
            progress = json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else {}
            if progress.get("phase") == "complete":
                log("all jobs complete; monitor exiting")
                return
            if sample["ramAvailableGB"] < 2:
                log(f"queue empty; RAM {sample['ramAvailableGB']:.2f} GB, waiting")
                time.sleep(20)
                continue
            log(f"queue empty; RAM {sample['ramAvailableGB']:.2f} GB, requesting next serialized job")
            # Record a byte offset before submitting the next prompt, so each
            # job's tqdm timing comes only from its own log segment.
            if STDERR.exists():
                state["nextStderrOffset"] = STDERR.stat().st_size
                STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(ROOT / "tools/compare_turbo_v4_20261108.py"), "next"],
                                  cwd=ROOT, capture_output=True, text=True, timeout=90)
            output = (proc.stdout + proc.stderr).strip().replace("\n", " | ")
            log(f"next exit={proc.returncode}: {output}")
            if proc.returncode == 0:
                try:
                    progress = json.loads((OUT / "progress.json").read_text(encoding="utf-8"))
                    next_id = progress.get("active")
                    if next_id and "nextStderrOffset" in state:
                        state["stderrOffsets"][next_id] = state.pop("nextStderrOffset")
                        STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
                except Exception as exc:
                    log(f"could not associate stderr offset: {exc}")
            if proc.returncode:
                if "RAM below 2 GB" in output:
                    time.sleep(20)
                    continue
                save_progress({"phase": "error", "message": output})
                log("next failed; stopping without retry")
                return
            time.sleep(2)
            continue

        folder, record = active
        if folder.name != last_job:
            last_job = folder.name
            job_min_ram = sample["ramAvailableGB"]
        else:
            job_min_ram = min(job_min_ram, sample["ramAvailableGB"])
        pid = record["promptId"]
        try:
            history = requests.get(f"{COMFY}/history/{pid}", timeout=10).json()
        except Exception as exc:
            log(f"history unavailable for {folder.name}: {exc}")
            time.sleep(10)
            continue
        entry = history.get(pid)
        if not entry:
            queue = requests.get(f"{COMFY}/queue", timeout=10).json()
            running = queue.get("queue_running", [])
            pending_queue = queue.get("queue_pending", [])
            if any(len(x) > 1 and x[1] == pid for x in running + pending_queue):
                log(f"{folder.name} still queued/running; RAM={sample['ramAvailableGB']:.2f}GB GPU={sample.get('gpuUtilizationPct','?')}%")
                time.sleep(10)
                continue
            log(f"prompt missing from history and queue: {pid}; stopping for review")
            save_progress({"phase": "error", "active": folder.name, "promptId": pid,
                           "message": "prompt absent from history and queue"})
            return

        status = entry.get("status", {})
        messages = status.get("messages", [])
        if any("execution_error" in str(m) for m in messages) or entry.get("outputs") is None:
            log(f"ComfyUI execution error for {folder.name}; no automatic retry")
            save_progress({"phase": "error", "active": folder.name, "promptId": pid,
                           "status": status, "messages": messages})
            return
        if not status.get("completed"):
            log(f"{folder.name} running; RAM={sample['ramAvailableGB']:.2f}GB GPU={sample.get('gpuUtilizationPct','?')}%")
            time.sleep(10)
            continue

        source = Path(record["output"])
        deadline = time.time() + 30
        while (not source.exists() or source.stat().st_size == 0) and time.time() < deadline:
            time.sleep(2)
        if not source.exists() or source.stat().st_size == 0:
            log(f"successful history but output file missing: {source}")
            save_progress({"phase": "error", "active": folder.name, "promptId": pid,
                           "message": "output missing after successful history"})
            return
        meta = validate_video(source)
        target = folder / "raw.mp4"
        shutil.copy2(source, target)
        validate_video(target)
        now = time.time()
        sampling_seconds, sampling_source = tqdm_seconds(state["stderrOffsets"].get(folder.name, 0))
        result = {"status": "complete", "id": record["id"], "promptId": pid,
                  "submittedEpoch": record["submittedEpoch"], "completedEpoch": now,
                  "elapsedSeconds": now - record["submittedEpoch"],
                  "samplingSeconds": sampling_seconds, "samplingMeasurementSource": sampling_source,
                  "video": meta, "source": str(source), "memory": {"minAvailableGB": job_min_ram,
                  "peakGpuMemoryUsedMB": peak_used}, "historyStatus": status}
        result_path = folder / "result.json"
        tmp = result_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(result_path)
        timing_text = f"sampling={sampling_seconds:.1f}s via tqdm" if sampling_seconds is not None else "sampling timing unavailable"
        log(f"completed {folder.name}: {result['elapsedSeconds']:.1f}s elapsed, {timing_text}, video verified")
        save_progress({"phase": "job_complete", "completed": folder.name,
                       "elapsedSeconds": result["elapsedSeconds"], "memorySample": sample})
        # Build is updated by the owner to display unknown sampling time safely.
        time.sleep(2)


if __name__ == "__main__":
    main()
