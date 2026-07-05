from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(?P<end>\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})"
)
TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class SubtitleSegment:
    index: int
    start: str
    end: str
    text: str


def read_text_file(path: str | Path) -> str:
    file_path = Path(path)
    for encoding in ("utf-8-sig", "utf-8", "cp1258"):
        try:
            return file_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return file_path.read_text(encoding="utf-8", errors="replace")


def clean_script(text: str) -> str:
    cleaned_lines: list[str] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = TAG_RE.sub("", raw_line).strip()
        if not line:
            continue
        if TIMESTAMP_RE.search(line):
            continue
        if line.isdigit():
            continue
        line = re.sub(r"\s+", " ", line)
        line = re.sub(r"\s+([,.!?;:])", r"\1", line)
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def parse_subtitle(path: str | Path) -> list[SubtitleSegment]:
    file_path = Path(path)
    text = read_text_file(file_path)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"^\ufeff?WEBVTT.*?(?:\n\n|\Z)", "", normalized, flags=re.IGNORECASE | re.DOTALL)
    blocks = re.split(r"\n\s*\n", normalized.strip())
    segments: list[SubtitleSegment] = []

    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue

        timestamp_index = None
        timestamp_match = None
        for idx, line in enumerate(lines):
            timestamp_match = TIMESTAMP_RE.search(line)
            if timestamp_match:
                timestamp_index = idx
                break
        if timestamp_index is None or timestamp_match is None:
            continue

        text_lines = lines[timestamp_index + 1 :]
        segment_text = clean_script("\n".join(text_lines)).replace("\n", " ").strip()
        if not segment_text:
            continue

        segments.append(
            SubtitleSegment(
                index=len(segments) + 1,
                start=timestamp_match.group("start"),
                end=timestamp_match.group("end"),
                text=segment_text,
            )
        )

    return segments

