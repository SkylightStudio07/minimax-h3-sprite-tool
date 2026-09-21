"""Run one YuE2 request in the dedicated YuE2 virtual environment."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from yue2 import YuE2Pipeline
from instrumental_abc import mute_vocal_abc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--vae", required=True)
    parser.add_argument("--budget", type=float, default=16)
    parser.add_argument("--quantization", choices=("none", "fp8"), default="fp8")
    parser.add_argument("--offload-ar", action="store_true")
    parser.add_argument("--nar-query-chunk-size", type=int, default=1024)
    parser.add_argument("--instrumental", action="store_true")
    args = parser.parse_args()
    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    output = Path(args.output)
    with YuE2Pipeline.from_pretrained(
        args.model,
        vae=args.vae,
        device="cuda",
        memory_budget_gib=args.budget,
        quantization=args.quantization,
        offload_ar=args.offload_ar,
        nar_query_chunk_size=args.nar_query_chunk_size,
        local_files_only=True,
    ) as pipeline:
        original_abc = None
        if args.instrumental:
            if request.get("cot", "full") == "off":
                raise ValueError("Instrumental Vocal muting requires cot=full or melody")
            plan = pipeline.plan(**request)
            if plan.truncated:
                raise RuntimeError("YuE2 ABC plan was truncated before instrumental conversion")
            original_abc = plan.abc
            muted = mute_vocal_abc(original_abc)
            request["abc"] = muted.abc
            print(
                f"[YuE2] Instrumental score ready: muted {muted.muted_notes} notes "
                f"across {muted.vocal_lines} Vocal blocks",
                flush=True,
            )
        song = pipeline(**request)
        if original_abc is not None:
            (output / "score.original.abc").write_text(original_abc, encoding="utf-8")
        song.save_artifacts(output)
        if any(song.truncated.values()):
            raise RuntimeError(f"YuE2 output was truncated: {song.truncated}")


if __name__ == "__main__":
    main()
