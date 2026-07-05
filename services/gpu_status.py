from __future__ import annotations

import subprocess


def get_gpu_status() -> tuple[str, str]:
    command = [
        "nvidia-smi",
        "--query-gpu=name,memory.used,memory.total,utilization.gpu",
        "--format=csv,noheader",
    ]
    try:
        output = subprocess.check_output(command, text=True, encoding="utf-8", errors="replace", timeout=8)
    except Exception as exc:
        return "GPU: unavailable", f"nvidia-smi error: {exc}"

    first_line = output.strip().splitlines()[0] if output.strip() else ""
    if not first_line:
        return "GPU: unavailable", "No GPU returned by nvidia-smi."

    parts = [part.strip() for part in first_line.split(",")]
    if len(parts) < 4:
        return f"GPU: {first_line}", first_line

    name, used, total, util = parts[:4]
    short_name = name.replace("NVIDIA GeForce ", "").replace("NVIDIA ", "")
    return f"GPU: {short_name}", f"{name} | VRAM {used}/{total} | Util {util}"

