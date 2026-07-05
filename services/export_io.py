from __future__ import annotations

import re
import time
from pathlib import Path

from .task_queue import TtsTask


INVALID_FILENAME_RE = re.compile(r'[<>:"/\\|?*\x00-\x1F]')


def safe_filename(value: str, fallback: str = "tts") -> str:
    value = INVALID_FILENAME_RE.sub("_", value).strip(" .")
    value = re.sub(r"\s+", "_", value)
    return value[:120] or fallback


def render_template(template: str, task: TtsTask, ext: str) -> str:
    date_value = time.strftime("%Y%m%d")
    index_value = str(task.subtitle_index or task.short_id)
    voice_value = safe_filename(task.voice, "voice")
    stem = template or "{index}-{voice}-{date}"
    stem = stem.replace("{index}", index_value)
    stem = stem.replace("{voice}", voice_value)
    stem = stem.replace("{date}", date_value)
    stem = safe_filename(stem, f"{index_value}-{voice_value}-{date_value}")
    return f"{stem}.{ext.lstrip('.')}"


def _srt_time(value: str | None) -> str:
    if not value:
        return "00:00:00,000"
    return value.replace(".", ",")


def _vtt_time(value: str | None) -> str:
    if not value:
        return "00:00:00.000"
    return value.replace(",", ".")


def write_exports(task: TtsTask, output_dir: str | Path, template: str, formats: list[str]) -> dict[str, str]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    selected = set(formats or [])

    if ".txt" in selected:
        path = root / render_template(template, task, "txt")
        path.write_text(task.text + "\n", encoding="utf-8")
        written["txt"] = str(path)

    if ".srt" in selected:
        path = root / render_template(template, task, "srt")
        start = _srt_time(task.start)
        end = _srt_time(task.end) if task.end else "00:00:05,000"
        path.write_text(f"1\n{start} --> {end}\n{task.text}\n", encoding="utf-8")
        written["srt"] = str(path)

    if ".vtt" in selected:
        path = root / render_template(template, task, "vtt")
        start = _vtt_time(task.start)
        end = _vtt_time(task.end) if task.end else "00:00:05.000"
        path.write_text(f"WEBVTT\n\n{start} --> {end}\n{task.text}\n", encoding="utf-8")
        written["vtt"] = str(path)

    return written

