from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


STATUS_WAITING = "Chờ"
STATUS_PROCESSING = "Đang xử lý"
STATUS_DONE = "Đã xong"
STATUS_ERROR = "Lỗi"

TASK_HEADERS = [
    "ID",
    "Trạng thái",
    "Engine",
    "Giọng",
    "Ký tự",
    "Nguồn",
    "File",
    "Lỗi",
    "Nội dung",
]


@dataclass
class TtsTask:
    id: str
    text: str
    engine: str
    voice: str
    preset: str
    settings: dict[str, Any] = field(default_factory=dict)
    source: str = "Manual"
    subtitle_index: int | None = None
    start: str | None = None
    end: str | None = None
    status: str = STATUS_WAITING
    audio_path: str | None = None
    exports: dict[str, str] = field(default_factory=dict)
    details: str = ""
    error: str = ""
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))

    @property
    def chars(self) -> int:
        return len(self.text)

    @property
    def short_id(self) -> str:
        return self.id[:8]

    def label(self) -> str:
        preview = " ".join(self.text.split())[:56]
        return f"{self.short_id} · {self.status} · {preview}"

    def row(self) -> list[Any]:
        file_name = Path(self.audio_path).name if self.audio_path else ""
        return [
            self.short_id,
            self.status,
            self.engine,
            self.voice,
            self.chars,
            self.source,
            file_name,
            self.error[:80],
            " ".join(self.text.split())[:96],
        ]


class TaskStore:
    def __init__(self) -> None:
        self._tasks: list[TtsTask] = []
        self._lock = threading.RLock()

    def add(
        self,
        *,
        text: str,
        engine: str,
        voice: str,
        preset: str,
        settings: dict[str, Any],
        source: str = "Manual",
        subtitle_index: int | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> TtsTask:
        task = TtsTask(
            id=uuid.uuid4().hex,
            text=text.strip(),
            engine=engine,
            voice=voice,
            preset=preset,
            settings=dict(settings),
            source=source,
            subtitle_index=subtitle_index,
            start=start,
            end=end,
        )
        with self._lock:
            self._tasks.append(task)
        return task

    def add_many(self, tasks: list[TtsTask]) -> None:
        with self._lock:
            self._tasks.extend(tasks)

    def all(self) -> list[TtsTask]:
        with self._lock:
            return list(self._tasks)

    def get(self, task_id: str | None) -> TtsTask | None:
        if not task_id:
            return None
        with self._lock:
            for task in self._tasks:
                if task.id == task_id:
                    return task
        return None

    def delete(self, task_id: str | None) -> bool:
        if not task_id:
            return False
        with self._lock:
            before = len(self._tasks)
            self._tasks = [task for task in self._tasks if task.id != task_id]
            return len(self._tasks) != before

    def clear(self) -> None:
        with self._lock:
            self._tasks.clear()

    def waiting(self) -> list[TtsTask]:
        with self._lock:
            return [task for task in self._tasks if task.status in {STATUS_WAITING, STATUS_ERROR}]

    def counts(self) -> dict[str, int]:
        with self._lock:
            total_chars = sum(task.chars for task in self._tasks)
            return {
                "tasks": len(self._tasks),
                "chars": total_chars,
                "waiting": sum(task.status == STATUS_WAITING for task in self._tasks),
                "done": sum(task.status == STATUS_DONE for task in self._tasks),
                "error": sum(task.status == STATUS_ERROR for task in self._tasks),
            }

    def rows(self, filter_mode: str = "Tất cả task") -> list[list[Any]]:
        tasks = self.all()
        if filter_mode == "Đang chờ":
            tasks = [task for task in tasks if task.status == STATUS_WAITING]
        elif filter_mode == "Đã xong":
            tasks = [task for task in tasks if task.status == STATUS_DONE]
        elif filter_mode == "Lỗi":
            tasks = [task for task in tasks if task.status == STATUS_ERROR]
        return [task.row() for task in tasks]

    def choices(self) -> list[tuple[str, str]]:
        return [(task.label(), task.id) for task in self.all()]


def make_settings(
    *,
    speed: float,
    crossfade_ms: float,
    emotion: str,
    temperature: float,
    pitch: float,
    volume: float,
    normalize_audio: bool,
) -> dict[str, Any]:
    return {
        "speed": float(speed),
        "crossfade_ms": int(float(crossfade_ms)),
        "emotion": emotion,
        "temperature": float(temperature),
        "pitch": float(pitch),
        "volume": float(volume),
        "normalize_audio": bool(normalize_audio),
    }

