from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import gradio as gr

from services.export_io import render_template, write_exports
from services.gpu_status import get_gpu_status
from services.google_tts import (
    AI_MODEL_CHOICES as GOOGLE_AI_MODEL_CHOICES,
    AI_MODEL_CLOUD_VOICE as GOOGLE_AI_MODEL_CLOUD_VOICE,
    DEFAULT_CHUNK_CHAR_LIMIT as GOOGLE_DEFAULT_CHUNK_CHAR_LIMIT,
    DEFAULT_LANGUAGE_CODE as GOOGLE_DEFAULT_LANGUAGE_CODE,
    FALLBACK_VOICES as GOOGLE_FALLBACK_VOICES,
    GOOGLE_OUTPUT_DIR,
    GoogleTtsError,
    clear_google_cache,
    credential_status as google_credential_status,
    fetch_google_voices,
    generate_google_tts as synthesize_google_tts,
    load_google_settings,
    save_google_settings,
    voice_choices as google_voice_choices,
    voice_table_rows as google_voice_table_rows,
)
from services.subtitle_io import clean_script, parse_subtitle
from services.text_cleaner import TtsCleanResult, clean_text_for_tts
from services.task_queue import (
    STATUS_DONE,
    STATUS_ERROR,
    STATUS_PROCESSING,
    STATUS_WAITING,
    TASK_HEADERS,
    TaskStore,
    TtsTask,
    make_settings,
)
from ui_styles import APP_CSS


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "outputs"
LOG_DIR = ROOT / "logs"
USER_VOICE_DIR = ROOT / "voices" / "user_clones"
CLONE_OUTPUT_DIR = OUTPUT_DIR / "clones"
CLONE_DEBUG_LOG = LOG_DIR / "clone_debug.log"
MODEL_CONFIG_PATH = ROOT / "model_paths.json"


def _default_model_root() -> Path:
    configured = os.environ.get("TTS_STUDIO_MODEL_ROOT")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "TTS" / "Models"


def _legacy_path(windows_path: str, relative_fallback: str) -> Path:
    path = Path(windows_path)
    if path.exists():
        return path
    return ROOT / relative_fallback


DEFAULT_MODEL_ROOT = _default_model_root()
RUNTIME_DIR = ROOT / "runtimes"
RUNTIME_LOG = LOG_DIR / "runtime_bootstrap.log"
KOKORO_HF_REPO = "contextboxai/Kokoro-Vietnamese"
VIENEU_HF_REPO = "pnnbao-ump/VieNeu-TTS-v3-Turbo"
KOKORO_SOURCE_URL = "https://github.com/iamdinhthuan/Kokoro-Vietnamese/archive/refs/heads/main.zip"

RUNTIME_IMPORTS = {
    "kokoro": "kokoro_vietnamese",
    "vieneu": "vieneu",
}

RUNTIME_PACKAGES = {
    "kokoro": [KOKORO_SOURCE_URL],
    "vieneu": ["vieneu>=3.0.12"],
}

BOOTSTRAP_LOCK = threading.RLock()

NAV_CHOICES = [
    "Tổng quan",
    "Tạo giọng đọc",
    "TTS Google",
    "Kho giọng",
    "Thiết lập",
    "Donate",
    "Cài đặt",
]

CREATE_MODE_CHOICES = ["Text to Speech", "Clone Voice"]

VOICE_LIBRARY_HEADERS = ["Loại", "Engine", "ID", "Tên", "Trạng thái", "Ghi chú"]
GOOGLE_VOICE_HEADERS = ["Voice", "Ngôn ngữ", "Giới tính", "Dòng", "Tần số mẫu", "Nhóm quota"]


@dataclass(frozen=True)
class EngineConfig:
    key: str
    label: str
    python: Path
    worker: Path
    cwd: Path


ENGINES = {
    "kokoro": EngineConfig(
        key="kokoro",
        label="Kokoro Vietnamese",
        python=_legacy_path(r"E:\Kokoro\.venv-kokoro-vi\Scripts\python.exe", "runtimes/kokoro/.venv/Scripts/python.exe"),
        worker=ROOT / "workers" / "kokoro_worker.py",
        cwd=_legacy_path(r"E:\Kokoro", "runtimes/kokoro"),
    ),
    "vieneu": EngineConfig(
        key="vieneu",
        label="VieNeu-TTS v3 Turbo",
        python=_legacy_path(r"E:\TTS\VieNeu-TTS\.venv\Scripts\python.exe", "runtimes/vieneu/.venv/Scripts/python.exe"),
        worker=ROOT / "workers" / "vieneu_worker.py",
        cwd=_legacy_path(r"E:\TTS\VieNeu-TTS", "runtimes/vieneu"),
    ),
}

KOKORO_MODEL_ROOT = DEFAULT_MODEL_ROOT / "Kokoro-Vietnamese"
KOKORO_VOICES_JSON = KOKORO_MODEL_ROOT / "voices.json"
KOKORO_VOICEPACK_DIR = KOKORO_MODEL_ROOT / "voicepacks"
VIENEU_VOICES_JSON = _legacy_path(r"E:\TTS\VieNeu-TTS\src\vieneu\assets\voices_v3_turbo.json", "runtimes/vieneu/.venv/Lib/site-packages/vieneu/assets/voices_v3_turbo.json")

PRESETS = {
    "Tự nhiên": {"speed": 1.0, "pitch": 0.0, "volume": 1.0, "emotion": "natural", "temperature": 0.8},
    "Review sản phẩm": {"speed": 1.03, "pitch": 0.0, "volume": 1.0, "emotion": "natural", "temperature": 0.75},
    "Kể chuyện": {"speed": 0.95, "pitch": -0.05, "volume": 1.0, "emotion": "storytelling", "temperature": 0.72},
    "Tin tức": {"speed": 1.05, "pitch": 0.0, "volume": 1.0, "emotion": "natural", "temperature": 0.7},
    "Quảng cáo": {"speed": 1.08, "pitch": 0.05, "volume": 1.05, "emotion": "happy", "temperature": 0.86},
    "Chậm rãi": {"speed": 0.88, "pitch": -0.05, "volume": 1.0, "emotion": "natural", "temperature": 0.68},
}

DEFAULT_FILENAME_TEMPLATE = "{index}-{voice}-{date}"
DEFAULT_OUTPUT_FORMATS = [".txt"]
DEFAULT_NORMALIZE_AUDIO = True


def _default_model_config() -> dict[str, Any]:
    return {
        "model_root": str(DEFAULT_MODEL_ROOT),
        "recommended_model": "kokoro",
        "models": {
            "kokoro": {"path": str(KOKORO_MODEL_ROOT), "repo": KOKORO_HF_REPO},
            "vieneu": {"path": str(DEFAULT_MODEL_ROOT / "VieNeu-TTS-v3-Turbo"), "repo": VIENEU_HF_REPO},
        },
    }


def load_model_config() -> dict[str, Any]:
    config = _default_model_config()
    if MODEL_CONFIG_PATH.exists():
        try:
            saved = json.loads(MODEL_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                config.update({k: v for k, v in saved.items() if k != "models"})
                saved_models = saved.get("models")
                if isinstance(saved_models, dict):
                    for key, value in saved_models.items():
                        if isinstance(value, dict):
                            config.setdefault("models", {}).setdefault(key, {}).update(value)
        except Exception:
            pass
    return config


def save_model_config(config: dict[str, Any]) -> None:
    MODEL_CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def configured_model_path(engine_key: str) -> Path:
    config = load_model_config()
    path = ((config.get("models") or {}).get(engine_key) or {}).get("path")
    if path:
        return Path(str(path))
    return Path(str(config.get("model_root") or DEFAULT_MODEL_ROOT)) / ("Kokoro-Vietnamese" if engine_key == "kokoro" else "VieNeu-TTS-v3-Turbo")


def remember_model_path(engine_key: str, path: Path, model_root: str | None = None) -> None:
    config = load_model_config()
    if model_root:
        config["model_root"] = str(Path(model_root).expanduser())
    config.setdefault("models", {}).setdefault(engine_key, {})["path"] = str(path)
    config["models"][engine_key]["repo"] = KOKORO_HF_REPO if engine_key == "kokoro" else VIENEU_HF_REPO
    save_model_config(config)


def model_target_path(engine_key: str, model_root: str | None) -> Path:
    root = Path((model_root or "").strip() or load_model_config().get("model_root") or DEFAULT_MODEL_ROOT).expanduser()
    return root / ("Kokoro-Vietnamese" if engine_key == "kokoro" else "VieNeu-TTS-v3-Turbo")


def _path_has_contents(path: Path) -> bool:
    try:
        return path.is_dir() and any(path.iterdir())
    except Exception:
        return False


def _runtime_venv_dir(engine_key: str) -> Path:
    return RUNTIME_DIR / engine_key / ".venv"


def _runtime_python(engine_key: str) -> Path:
    if os.name == "nt":
        return _runtime_venv_dir(engine_key) / "Scripts" / "python.exe"
    return _runtime_venv_dir(engine_key) / "bin" / "python"


def _effective_python(engine_key: str) -> Path:
    configured = ENGINES[engine_key].python
    if configured.exists():
        return configured
    return _runtime_python(engine_key)


def _effective_cwd(engine_key: str) -> Path:
    configured = ENGINES[engine_key].cwd
    return configured if configured.exists() else ROOT


def _runtime_log(message: str) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with RUNTIME_LOG.open("a", encoding="utf-8", errors="replace") as handle:
            handle.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception:
        pass


def _run_runtime_command(args: list[str], timeout: int = 7200) -> tuple[bool, str]:
    display = " ".join(args)
    _runtime_log(f"RUN {display}")
    try:
        completed = subprocess.run(
            args,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except Exception as exc:
        message = f"Command failed to start: {exc}"
        _runtime_log(message)
        return False, message

    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    if completed.returncode != 0:
        message = output or f"Command exited with code {completed.returncode}"
        _runtime_log(f"FAIL {display}\n{message[-4000:]}")
        return False, message
    if output:
        _runtime_log(f"OK {display}\n{output[-2000:]}")
    else:
        _runtime_log(f"OK {display}")
    return True, output


def _runtime_import_ok(python: Path, module: str) -> tuple[bool, str]:
    return _run_runtime_command([str(python), "-c", f"import {module}; print('OK {module}')"], timeout=120)


def ensure_engine_runtime(engine_key: str) -> tuple[Path, str]:
    if engine_key not in ENGINES:
        raise WorkerError(f"Unknown engine: {engine_key}")

    configured = ENGINES[engine_key].python
    if configured.exists():
        return configured, f"Using existing runtime: {configured}"

    with BOOTSTRAP_LOCK:
        python = _runtime_python(engine_key)
        venv_dir = _runtime_venv_dir(engine_key)
        messages: list[str] = []
        created_venv = False

        if not python.exists():
            venv_dir.parent.mkdir(parents=True, exist_ok=True)
            messages.append(f"Creating runtime venv: {venv_dir}")
            ok, output = _run_runtime_command([sys.executable, "-m", "venv", str(venv_dir)], timeout=900)
            if not ok:
                raise WorkerError(f"Could not create runtime for {ENGINES[engine_key].label}: {output}")
            created_venv = True

        module = RUNTIME_IMPORTS[engine_key]
        import_ok, import_output = _runtime_import_ok(python, module)
        if not import_ok:
            ok, output = _run_runtime_command([str(python), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], timeout=1800)
            if not ok:
                raise WorkerError(f"Could not upgrade pip for {ENGINES[engine_key].label}: {output}")
            packages = RUNTIME_PACKAGES[engine_key]
            messages.append(f"Installing runtime package: {' '.join(packages)}")
            ok, output = _run_runtime_command([str(python), "-m", "pip", "install", "--upgrade", *packages], timeout=7200)
            if not ok:
                raise WorkerError(f"Could not install runtime for {ENGINES[engine_key].label}: {output}")
            import_ok, import_output = _runtime_import_ok(python, module)
            if not import_ok:
                raise WorkerError(f"Runtime installed but import failed for {module}: {import_output}")
        else:
            messages.append(f"Runtime package already installed: {module}")
            if created_venv:
                messages.append("Runtime venv was created with package already available.")

        messages.append(f"Runtime ready: {python}")
        return python, "\n".join(messages)


def model_path_rows() -> list[list[str]]:
    kokoro_root = configured_model_path("kokoro")
    vieneu_root = configured_model_path("vieneu")
    rows = [
        [
            "Kokoro Vietnamese",
            str(kokoro_root),
            "Sẵn sàng" if (kokoro_root / "kokoro_vi.pth").exists() and (kokoro_root / "config.json").exists() else "Cần tải/kiểm tra",
            "Cần kokoro_vi.pth, config.json và voicepacks/*.pt",
        ],
        [
            "VieNeu-TTS v3 Turbo",
            str(vieneu_root),
            "Sẵn sàng" if _path_has_contents(vieneu_root) else "Cần tải/kiểm tra",
            "SDK v3 Turbo; CPU ONNX hoặc GPU PyTorch, hỗ trợ clone ref_audio/ref_codes",
        ],
    ]
    return rows


class WorkerError(RuntimeError):
    pass


class WorkerClient:
    def __init__(self, config: EngineConfig) -> None:
        self.config = config
        self.process: subprocess.Popen[str] | None = None
        self.responses: queue.Queue[dict[str, Any]] = queue.Queue()
        self.lock = threading.RLock()
        self.stderr_file = None
        self.raw_stdout_file = None
        self.reader: threading.Thread | None = None

    def start(self) -> None:
        if self.process is not None and self.process.poll() is None:
            return

        python, runtime_message = ensure_engine_runtime(self.config.key)
        _runtime_log(f"{self.config.label}: {runtime_message}")
        if not python.exists():
            raise WorkerError(f"Python not found: {python}")
        if not self.config.worker.exists():
            raise WorkerError(f"Worker not found: {self.config.worker}")

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONUTF8"] = "1"
        env["TTS_STUDIO_KOKORO_MODEL_ROOT"] = str(configured_model_path("kokoro"))
        env["TTS_STUDIO_VIENEU_MODEL_ROOT"] = str(configured_model_path("vieneu"))
        kokoro_code_root = Path(r"E:\Kokoro\Kokoro-Vietnamese-code\src")
        vieneu_code_root = Path(r"E:\TTS\VieNeu-TTS")
        env["TTS_STUDIO_KOKORO_CODE_ROOT"] = str(kokoro_code_root if kokoro_code_root.exists() else ROOT / "runtimes" / "kokoro")
        env["TTS_STUDIO_VIENEU_CODE_ROOT"] = str(vieneu_code_root if vieneu_code_root.exists() else ROOT / "runtimes" / "vieneu")

        err_path = LOG_DIR / f"{self.config.key}_worker.err.log"
        raw_path = LOG_DIR / f"{self.config.key}_worker.stdout.log"
        self.stderr_file = err_path.open("a", encoding="utf-8", errors="replace")
        self.raw_stdout_file = raw_path.open("a", encoding="utf-8", errors="replace")

        self.process = subprocess.Popen(
            [str(python), str(self.config.worker)],
            cwd=str(_effective_cwd(self.config.key)),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.stderr_file,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
        )
        self.reader = threading.Thread(target=self._read_stdout, daemon=True)
        self.reader.start()

    def _read_stdout(self) -> None:
        assert self.process is not None
        assert self.process.stdout is not None
        for line in self.process.stdout:
            raw = line.rstrip("\r\n")
            if self.raw_stdout_file:
                self.raw_stdout_file.write(raw + "\n")
                self.raw_stdout_file.flush()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            self.responses.put(data)

    def request(self, command: str, payload: dict[str, Any] | None = None, timeout: float = 600) -> dict[str, Any]:
        with self.lock:
            self.start()
            assert self.process is not None
            assert self.process.stdin is not None

            if self.process.poll() is not None:
                raise WorkerError(f"{self.config.label} worker exited with code {self.process.returncode}.")

            request_id = uuid.uuid4().hex
            message = {
                "id": request_id,
                "command": command,
                "payload": payload or {},
            }
            self.process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
            self.process.stdin.flush()

            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise WorkerError(f"{self.config.label} worker exited with code {self.process.returncode}.")
                try:
                    response = self.responses.get(timeout=0.2)
                except queue.Empty:
                    continue
                if response.get("id") == request_id:
                    return response

            raise WorkerError(f"{self.config.label} worker timed out while running '{command}'.")

    def stop(self, timeout: float = 45) -> str:
        with self.lock:
            status = "Worker was not running."
            if self.process is not None and self.process.poll() is None:
                try:
                    response = self.request("shutdown", timeout=timeout)
                    status = str(response.get("status") or "Worker stopped.")
                except Exception as exc:
                    status = f"Forced worker stop: {exc}"
                    try:
                        self.process.terminate()
                        self.process.wait(timeout=10)
                    except Exception:
                        try:
                            self.process.kill()
                        except Exception:
                            pass
            self._close_files()
            return status

    def _close_files(self) -> None:
        for handle_name in ("stderr_file", "raw_stdout_file"):
            handle = getattr(self, handle_name, None)
            if handle:
                try:
                    handle.close()
                except Exception:
                    pass
                setattr(self, handle_name, None)


class EngineManager:
    def __init__(self) -> None:
        self.active_key: str | None = None
        self.active_client: WorkerClient | None = None
        self.lock = threading.RLock()

    def ensure(self, engine_key: str) -> WorkerClient:
        with self.lock:
            if engine_key not in ENGINES:
                raise WorkerError(f"Unknown engine: {engine_key}")
            if self.active_key != engine_key:
                self.unload()
                self.active_key = engine_key
                self.active_client = WorkerClient(ENGINES[engine_key])
            assert self.active_client is not None
            self.active_client.start()
            return self.active_client

    def list_voices(self, engine_key: str) -> dict[str, Any]:
        with self.lock:
            return self.ensure(engine_key).request("list_voices", timeout=90)

    def synthesize(self, engine_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            return self.ensure(engine_key).request("synthesize", payload, timeout=1200)

    def encode_reference(self, engine_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            return self.ensure(engine_key).request("encode_reference", payload, timeout=1200)

    def unload(self) -> str:
        with self.lock:
            if self.active_client is None:
                self.active_key = None
                return "No worker is loaded."
            status = self.active_client.stop()
            self.active_client = None
            self.active_key = None
            return status

    def status(self) -> str:
        with self.lock:
            if not self.active_client or not self.active_client.process:
                return "No active engine."
            proc = self.active_client.process
            state = "running" if proc.poll() is None else f"exited({proc.returncode})"
            label = ENGINES[self.active_key].label if self.active_key else "unknown"
            return f"Active: {label} | PID: {proc.pid} | {state}"


manager = EngineManager()
store = TaskStore()


def _safe_filename(value: str, fallback: str = "voice") -> str:
    normalized = re.sub(r"[^\w\-.]+", "-", (value or "").strip(), flags=re.UNICODE)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-.")
    return normalized or fallback


def _clone_debug_timestamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _clone_debug_write(run_id: str, stage: str, message: str, **fields: Any) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "time": _clone_debug_timestamp(),
            "run_id": run_id,
            "stage": stage,
            "message": message,
            **fields,
        }
        with CLONE_DEBUG_LOG.open("a", encoding="utf-8", errors="replace") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def _clone_debug_format(lines: list[str]) -> str:
    visible_lines = lines[-80:]
    return "\n".join(visible_lines + ["", f"Log file: {CLONE_DEBUG_LOG}"])


def _clone_debug_append(lines: list[str], run_id: str, stage: str, message: str, **fields: Any) -> None:
    timestamp = time.strftime("%H:%M:%S")
    lines.append(f"[{timestamp}] {stage}: {message}")
    _clone_debug_write(run_id, stage, message, **fields)


def _run_capture(args: list[str], timeout: float = 10) -> str:
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except Exception:
        return ""
    return (completed.stdout or "").strip()


def _total_ram_gb() -> float | None:
    try:
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))  # type: ignore[attr-defined]
        return round(status.ullTotalPhys / (1024**3), 1)
    except Exception:
        return None


def _query_gpus() -> list[dict[str, Any]]:
    raw = _run_capture(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.used,driver_version",
            "--format=csv,noheader,nounits",
        ],
        timeout=8,
    )
    gpus: list[dict[str, Any]] = []
    for line in raw.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 4:
            continue
        try:
            total_mb = int(float(parts[1]))
            used_mb = int(float(parts[2]))
        except ValueError:
            total_mb = 0
            used_mb = 0
        gpus.append(
            {
                "name": parts[0],
                "memory_total_mb": total_mb,
                "memory_used_mb": used_mb,
                "driver": parts[3],
            }
        )
    return gpus


def _resolve_device(device_mode: str | None) -> str:
    mode = (device_mode or "GPU").strip().lower()
    if mode == "cpu":
        return "cpu"
    if mode == "auto":
        return "cuda" if _query_gpus() else "cpu"
    return "cuda"


def _engine_runtime_rows() -> list[list[str]]:
    return [
        [
            config.label,
            str(config.python),
            "OK" if config.python.exists() else "Thiếu Python venv",
            str(config.cwd),
        ]
        for config in ENGINES.values()
    ]


def _model_status_rows() -> list[list[str]]:
    kokoro_root = configured_model_path("kokoro")
    kokoro_model = kokoro_root / "kokoro_vi.pth"
    kokoro_config = kokoro_root / "config.json"
    kokoro_voicepacks = kokoro_root / "voicepacks"
    vieneu_root = configured_model_path("vieneu")
    vieneu_assets = _vieneu_voice_json_path()
    rows = [
        ["Kokoro model", str(kokoro_model), "Đã có" if kokoro_model.exists() else "Cần tải"],
        ["Kokoro config", str(kokoro_config), "Đã có" if kokoro_config.exists() else "Cần tải"],
        ["Kokoro voicepacks", str(kokoro_voicepacks), "Đã có" if kokoro_voicepacks.exists() else "Cần tải"],
        ["VieNeu model path", str(vieneu_root), "Đã có" if _path_has_contents(vieneu_root) else "Cần tải"],
        ["VieNeu voices", str(vieneu_assets), "Đã có" if vieneu_assets.exists() else "Cần runtime"],
    ]
    return rows


def _engine_runtime_rows() -> list[list[str]]:
    rows = []
    for key, config in ENGINES.items():
        python = _effective_python(key)
        source = "venv gốc" if config.python.exists() else "runtime tự động"
        rows.append(
            [
                config.label,
                str(python),
                "OK" if python.exists() else "Sẽ tự tạo khi load",
                f"{source} · cwd: {_effective_cwd(key)}",
            ]
        )
    return rows


def _read_text_if_exists(path: Path, limit: int = 12000) -> str:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        pass
    return ""


def _vieneu_voice_json_candidates() -> list[Path]:
    candidates = [
        VIENEU_VOICES_JSON,
        Path(r"E:\TTS\VieNeu-TTS\src\vieneu\assets\voices_v3_turbo.json"),
        _runtime_venv_dir("vieneu") / "Lib" / "site-packages" / "vieneu" / "assets" / "voices_v3_turbo.json",
        _runtime_venv_dir("vieneu") / "lib" / "python3.12" / "site-packages" / "vieneu" / "assets" / "voices_v3_turbo.json",
        _runtime_venv_dir("vieneu") / "lib" / "python3.11" / "site-packages" / "vieneu" / "assets" / "voices_v3_turbo.json",
        _runtime_venv_dir("vieneu") / "lib" / "python3.10" / "site-packages" / "vieneu" / "assets" / "voices_v3_turbo.json",
    ]
    return [path for index, path in enumerate(candidates) if path not in candidates[:index]]


def _vieneu_voice_json_path() -> Path:
    for path in _vieneu_voice_json_candidates():
        if path.exists():
            return path
    return _vieneu_voice_json_candidates()[0]


def _model_readme_notes() -> dict[str, list[str]]:
    kokoro_text = "\n".join(
        text
        for text in (
            _read_text_if_exists(configured_model_path("kokoro") / "README.md"),
            _read_text_if_exists(Path(r"E:\Kokoro\Kokoro-Vietnamese-code\README.md")),
            _read_text_if_exists(ROOT / "runtimes" / "kokoro" / "README.md"),
        )
        if text
    )
    vieneu_text = "\n".join(
        text
        for text in (
            _read_text_if_exists(Path(r"E:\TTS\VieNeu-TTS\README.vi.md")),
            _read_text_if_exists(Path(r"E:\TTS\VieNeu-TTS\README.md")),
            _read_text_if_exists(configured_model_path("vieneu") / "README.md"),
            _read_text_if_exists(ROOT / "runtimes" / "vieneu" / "README.md"),
        )
        if text
    )
    kokoro_notes = [
        "Kokoro README nêu các file cần có: kokoro_vi.pth, kokoro_vi.onnx, kokoro_vi_voicepack.pt, config.json và voicepacks/*.pt.",
        "Kokoro hỗ trợ PyTorch inference với --device cuda và ONNX Runtime với --device cpu/cuda.",
    ]
    vieneu_notes = [
        "VieNeu README nêu SDK mặc định dùng v3 Turbo 48 kHz.",
        "VieNeu v3 Turbo chạy CPU bằng ONNX không cần torch, còn CUDA dùng PyTorch.",
        "VieNeu hỗ trợ clone giọng tức thì từ audio mẫu 3-5 giây và có thể encode_reference để tái dùng ref_codes.",
    ]
    if "voicepacks/*.pt" not in kokoro_text:
        kokoro_notes.append("Không đọc thấy README model Kokoro đầy đủ tại đường dẫn đang nhớ; dùng ghi chú mặc định của dự án.")
    if "v3 Turbo" not in vieneu_text and "v3turbo" not in vieneu_text:
        vieneu_notes.append("Không đọc thấy README VieNeu đầy đủ; dùng ghi chú mặc định của dự án.")
    return {"kokoro": kokoro_notes, "vieneu": vieneu_notes}


def _recommended_model_key(gpus: list[dict[str, Any]], ram_gb: float | None) -> tuple[str, str, str]:
    best_vram = max((gpu["memory_total_mb"] for gpu in gpus), default=0)
    if best_vram >= 6000:
        return (
            "vieneu",
            "GPU có từ khoảng 6 GB VRAM trở lên: ưu tiên VieNeu-TTS v3 Turbo GPU để có clone voice và preset 48 kHz.",
            "GPU",
        )
    if best_vram >= 3500:
        return (
            "kokoro",
            "GPU khoảng 4 GB VRAM: ưu tiên Kokoro Vietnamese cho TTS preset nhẹ hơn; dùng VieNeu khi cần clone và nên chia câu ngắn.",
            "GPU",
        )
    if gpus:
        return (
            "kokoro",
            "GPU VRAM thấp: ưu tiên Kokoro hoặc chạy VieNeu CPU/ONNX khi cần clone, tránh giữ nhiều worker.",
            "CPU/GPU ngắn",
        )
    if ram_gb and ram_gb >= 16:
        return (
            "vieneu",
            "Không thấy NVIDIA GPU nhưng RAM đủ: ưu tiên VieNeu-TTS v3 Turbo CPU/ONNX theo README, đặc biệt nếu cần clone voice.",
            "CPU",
        )
    return (
        "kokoro",
        "Máy không có NVIDIA GPU/RAM thấp: ưu tiên Kokoro Vietnamese vì nhẹ và đơn giản hơn cho TTS preset.",
        "CPU",
    )


def _build_system_recommendation(gpus: list[dict[str, Any]], ram_gb: float | None) -> tuple[str, str]:
    recommended, reason, device_mode_tip = _recommended_model_key(gpus, ram_gb)
    notes = _model_readme_notes()
    config = load_model_config()
    config["recommended_model"] = recommended
    save_model_config(config)
    label = ENGINES[recommended].label
    recommendation = f"""
### Model tối ưu nhất cho cấu hình hiện tại

**{label}**

{reason}

Thiết bị nên dùng: **{device_mode_tip}**.

Người dùng vẫn có thể tải cả **Kokoro Vietnamese** và **VieNeu-TTS v3 Turbo**. Khuyến nghị trên chỉ chọn model tối ưu nhất để bắt đầu.

### Căn cứ từ README

**Kokoro Vietnamese**
- {notes["kokoro"][0]}
- {notes["kokoro"][1]}

**VieNeu-TTS**
- {notes["vieneu"][0]}
- {notes["vieneu"][1]}
- {notes["vieneu"][2]}

### Trạng thái worker

{manager.status()}
"""
    return recommended, recommendation.strip()


def scan_system_profile():
    gpus = _query_gpus()
    ram_gb = _total_ram_gb()
    cpu_name = platform.processor() or platform.machine() or "Không rõ"
    rows = [
        ["Hệ điều hành", platform.platform(), "Windows local app"],
        ["CPU", f"{cpu_name} · {os.cpu_count() or '?'} luồng", "CPU dùng được, phù hợp khi thiếu VRAM"],
        ["RAM", f"{ram_gb} GB" if ram_gb else "Không đọc được", "Từ 16 GB trở lên chạy queue ổn hơn"],
    ]
    if gpus:
        for index, gpu in enumerate(gpus, start=1):
            total_gb = gpu["memory_total_mb"] / 1024
            used_gb = gpu["memory_used_mb"] / 1024
            rows.append(
                [
                    f"GPU {index}",
                    f"{gpu['name']} · {total_gb:.1f} GB VRAM · dùng {used_gb:.1f} GB · driver {gpu['driver']}",
                    "Ưu tiên GPU, chỉ load một engine tại một thời điểm",
                ]
            )
    else:
        rows.append(["GPU", "Không thấy NVIDIA GPU qua nvidia-smi", "Chọn CPU hoặc cài driver/CUDA phù hợp"])

    for name, path, state in _model_status_rows():
        rows.append([name, path, state])

    recommended, recommendation = _build_system_recommendation(gpus, ram_gb)
    return rows, recommendation, gr.update(value=recommended), model_path_rows()


def _download_python(engine_key: str) -> Path:
    configured = ENGINES[engine_key].python
    if configured.exists():
        return configured
    return Path(sys.executable)


def _model_repo(engine_key: str) -> str:
    return KOKORO_HF_REPO if engine_key == "kokoro" else VIENEU_HF_REPO


def _model_ready(engine_key: str, target: Path) -> bool:
    if engine_key == "kokoro":
        return (target / "kokoro_vi.pth").exists() and (target / "config.json").exists()
    return _path_has_contents(target)


def _download_hf_snapshot(engine_key: str, target: Path) -> tuple[bool, str]:
    target.mkdir(parents=True, exist_ok=True)
    python = _download_python(engine_key)
    repo = _model_repo(engine_key)
    script = (
        "from huggingface_hub import snapshot_download\n"
        "import sys\n"
        "repo=sys.argv[1]\n"
        "target=sys.argv[2]\n"
        "try:\n"
        "    snapshot_download(repo_id=repo, local_dir=target, local_dir_use_symlinks=False, resume_download=True)\n"
        "except TypeError:\n"
        "    snapshot_download(repo_id=repo, local_dir=target)\n"
        "print('DONE ' + repo + ' -> ' + target)\n"
    )
    try:
        completed = subprocess.run(
            [str(python), "-c", script, repo, str(target)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=7200,
            check=False,
        )
    except Exception as exc:
        return False, f"Không chạy được downloader: {exc}"
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    if completed.returncode != 0:
        return False, output or f"Downloader exited with code {completed.returncode}"
    return True, output or f"Đã tải {repo}"


def _download_log(lines: list[str]) -> str:
    return "\n".join(lines[-120:])


def _load_model_after_download(engine_key: str):
    ensure_engine_runtime(engine_key)
    manager.unload()
    return on_engine_change(engine_key)


def download_models_flow(selected_model: str, model_save_root: str, download_both: bool = False):
    config = load_model_config()
    selected = selected_model or str(config.get("recommended_model") or "kokoro")
    keys = ["kokoro", "vieneu"] if download_both else [selected]
    lines = [
        f"[{time.strftime('%H:%M:%S')}] Bắt đầu tải model.",
        f"Thư mục lưu: {(model_save_root or config.get('model_root') or DEFAULT_MODEL_ROOT)}",
        f"Model: {'cả 2 model' if download_both else ENGINES[selected].label}",
    ]
    yield model_path_rows(), _download_log(lines), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), _download_log(lines)

    for key in keys:
        target = model_target_path(key, model_save_root)
        remember_model_path(key, target, model_save_root)
        lines.append(f"[{time.strftime('%H:%M:%S')}] Chuẩn bị {ENGINES[key].label}: {target}")
        yield model_path_rows(), _download_log(lines), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), _download_log(lines)

        if _model_ready(key, target):
            lines.append(f"[{time.strftime('%H:%M:%S')}] Đã có sẵn, bỏ qua tải lại: {ENGINES[key].label}")
            yield model_path_rows(), _download_log(lines), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), _download_log(lines)
            continue

        lines.append(f"[{time.strftime('%H:%M:%S')}] Đang tải từ Hugging Face: {_model_repo(key)}")
        lines.append("Quá trình này có thể mất vài phút tùy tốc độ mạng và dung lượng model.")
        yield model_path_rows(), _download_log(lines), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), _download_log(lines)

        ok, message = _download_hf_snapshot(key, target)
        if not ok:
            lines.append(f"[{time.strftime('%H:%M:%S')}] Tải thất bại: {ENGINES[key].label}")
            lines.append(message)
            yield model_path_rows(), _download_log(lines), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), _download_log(lines)
            return
        lines.append(f"[{time.strftime('%H:%M:%S')}] Tải xong: {ENGINES[key].label}")
        if message:
            lines.append(message[-1800:])
        yield model_path_rows(), _download_log(lines), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), _download_log(lines)

    model_to_load = selected
    lines.append(f"[{time.strftime('%H:%M:%S')}] Đang chuẩn bị runtime: {ENGINES[model_to_load].label}")
    yield model_path_rows(), _download_log(lines), gr.update(value=model_to_load), gr.update(), gr.update(), gr.update(), gr.update(), _download_log(lines)

    try:
        runtime_python, runtime_message = ensure_engine_runtime(model_to_load)
        lines.append(f"[{time.strftime('%H:%M:%S')}] Runtime sẵn sàng: {runtime_python}")
        if runtime_message:
            lines.append(runtime_message[-1200:])
    except Exception as exc:
        lines.append(f"[{time.strftime('%H:%M:%S')}] Chuẩn bị runtime thất bại: {exc}")
        yield model_path_rows(), _download_log(lines), gr.update(value=model_to_load), gr.update(), gr.update(), gr.update(), gr.update(), _download_log(lines)
        return
    lines.append(f"[{time.strftime('%H:%M:%S')}] Đang load/chạy model: {ENGINES[model_to_load].label}")
    yield model_path_rows(), _download_log(lines), gr.update(value=model_to_load), gr.update(), gr.update(), gr.update(), gr.update(), _download_log(lines)

    try:
        voice_update, ref_update, emotion_update, temperature_update, create_status = _load_model_after_download(model_to_load)
        lines.append(f"[{time.strftime('%H:%M:%S')}] Load xong: {create_status}")
        yield (
            model_path_rows(),
            _download_log(lines),
            gr.update(value=model_to_load),
            voice_update,
            ref_update,
            emotion_update,
            temperature_update,
            create_status,
        )
    except Exception as exc:
        lines.append(f"[{time.strftime('%H:%M:%S')}] Load model thất bại: {exc}")
        yield model_path_rows(), _download_log(lines), gr.update(value=model_to_load), gr.update(), gr.update(), gr.update(), gr.update(), _download_log(lines)


def download_selected_model(selected_model: str, model_save_root: str):
    yield from download_models_flow(selected_model, model_save_root, download_both=False)


def download_all_models(selected_model: str, model_save_root: str):
    yield from download_models_flow(selected_model, model_save_root, download_both=True)


def load_selected_model_from_overview(selected_model: str, model_save_root: str):
    key = selected_model or str(load_model_config().get("recommended_model") or "kokoro")
    typed_target = model_target_path(key, model_save_root)
    remembered_target = configured_model_path(key)
    target = typed_target if _model_ready(key, typed_target) else remembered_target
    remember_model_path(key, target, model_save_root)
    try:
        voice_update, ref_update, emotion_update, temperature_update, create_status = _load_model_after_download(key)
        log = f"Đã ghi nhớ đường dẫn: {target}\nĐã load/chạy {ENGINES[key].label}.\n{create_status}"
        return model_path_rows(), log, gr.update(value=key), voice_update, ref_update, emotion_update, temperature_update, create_status
    except Exception as exc:
        log = f"Đã ghi nhớ đường dẫn: {target}\nLoad model thất bại: {exc}"
        return model_path_rows(), log, gr.update(value=key), gr.update(), gr.update(), gr.update(), gr.update(), log


def open_model_root(model_save_root: str):
    root = Path((model_save_root or "").strip() or load_model_config().get("model_root") or DEFAULT_MODEL_ROOT)
    return open_local_folder(str(root))


def _clone_profile_path(profile_id: str) -> Path:
    return USER_VOICE_DIR / f"{_safe_filename(profile_id)}.json"


def _load_clone_profiles(engine_key: str | None = None) -> list[dict[str, Any]]:
    USER_VOICE_DIR.mkdir(parents=True, exist_ok=True)
    profiles: list[dict[str, Any]] = []
    for path in sorted(USER_VOICE_DIR.glob("*.json")):
        try:
            profile = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if engine_key and profile.get("engine") != engine_key:
            continue
        profile["_path"] = str(path)
        profiles.append(profile)
    return profiles


def _voice_name_from_id(voice_id: str) -> str:
    words = re.split(r"[_\-\s]+", voice_id.strip())
    return " ".join(part[:1].upper() + part[1:] for part in words if part)


def _voice_rows_from_local_files(engine_key: str) -> tuple[list[list[str]], str]:
    config = ENGINES[engine_key]
    rows: list[list[str]] = []

    if engine_key == "kokoro":
        kokoro_root = configured_model_path("kokoro")
        kokoro_voices_json = kokoro_root / "voices.json"
        kokoro_voicepack_dir = kokoro_root / "voicepacks"
        if kokoro_voices_json.exists():
            try:
                data = json.loads(kokoro_voices_json.read_text(encoding="utf-8"))
                for voice_id, info in sorted(data.items()):
                    filename = str(info.get("filename") or f"voicepacks/{voice_id}.pt")
                    voice_path = kokoro_root / filename
                    status = "Sẵn sàng" if voice_path.exists() else "Thiếu file"
                    rows.append(
                        [
                            "Giọng có sẵn",
                            config.label,
                            str(voice_id),
                            str(info.get("label") or _voice_name_from_id(str(voice_id))),
                            status,
                            f"Local voicepack: {voice_path.name}",
                        ]
                    )
            except Exception as exc:
                rows.append(["Giọng có sẵn", config.label, "", "", "Lỗi", f"Không đọc được voices.json: {exc}"])
        elif kokoro_voicepack_dir.exists():
            for path in sorted(kokoro_voicepack_dir.glob("*.pt")):
                rows.append(
                    [
                        "Giọng có sẵn",
                        config.label,
                        path.stem,
                        _voice_name_from_id(path.stem),
                        "Sẵn sàng",
                        f"Local voicepack: {path.name}",
                    ]
                )

    if engine_key == "vieneu":
        vieneu_voices_json = _vieneu_voice_json_path()
        if vieneu_voices_json.exists():
            try:
                data = json.loads(vieneu_voices_json.read_text(encoding="utf-8"))
                default_voice = str(data.get("default_voice") or "")
                presets = data.get("presets") or {}
                for voice_id, info in sorted(presets.items()):
                    desc = str(info.get("description") or "").strip()
                    note_parts = ["Preset v3 Turbo"]
                    if desc:
                        note_parts.append(desc)
                    if str(voice_id) == default_voice:
                        note_parts.append("mặc định")
                    rows.append(
                        [
                            "Giọng có sẵn",
                            config.label,
                            str(voice_id),
                            str(voice_id),
                            "Sẵn sàng",
                            " · ".join(note_parts),
                        ]
                    )
            except Exception as exc:
                rows.append(["Giọng có sẵn", config.label, "", "", "Lỗi", f"Không đọc được voices_v3_turbo.json: {exc}"])
        else:
            rows.append(["Giọng có sẵn", config.label, "", "", "Thiếu file", str(VIENEU_VOICES_JSON)])

    if not rows:
        rows.append(["Giọng có sẵn", config.label, "", "", "Chưa tìm thấy", "Kiểm tra runtime/model trong Cài đặt."])
    return rows, f"{config.label}: {len(rows)} giọng local"


def _clone_profile_rows(include_empty: bool = True) -> tuple[list[list[str]], str]:
    rows: list[list[str]] = []
    profiles = _load_clone_profiles()
    for profile in profiles:
        engine_label = ENGINES.get(str(profile.get("engine")), ENGINES["kokoro"]).label
        if profile.get("ref_codes_path"):
            mode = "Clone ref codes"
        elif profile.get("ref_audio"):
            mode = "Clone ref audio"
        else:
            mode = "Clone preset"
        preview = Path(str(profile.get("preview_audio") or "")).name
        rows.append(
            [
                "Clone người dùng",
                engine_label,
                str(profile.get("id") or ""),
                str(profile.get("name") or ""),
                "Sẵn sàng",
                f"{mode} · preview: {preview or 'chưa có'}",
            ]
        )
    if include_empty and not rows:
        rows.append(
            [
                "Clone người dùng",
                "TTS Studio",
                "",
                "Chưa có clone",
                "Chưa có",
                "Mở Tạo giọng đọc > Clone Voice để tạo và lưu profile mới.",
            ]
        )
    return rows, f"Clone người dùng: {len(profiles)}"


def voice_library_snapshot():
    rows: list[list[str]] = []
    messages: list[str] = []
    for key in ENGINES:
        local_rows, message = _voice_rows_from_local_files(key)
        rows.extend(local_rows)
        messages.append(message)
    clone_rows, clone_message = _clone_profile_rows(include_empty=True)
    rows.extend(clone_rows)
    messages.append(clone_message)
    return rows, "\n".join(messages)


def _clone_profile_by_value(value: str | None) -> dict[str, Any] | None:
    if not value or not str(value).startswith("clone:"):
        return None
    profile_id = str(value).split(":", 1)[1]
    path = _clone_profile_path(profile_id)
    if not path.exists():
        return None
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    profile["_path"] = str(path)
    return profile


def _clone_voice_choices(engine_key: str) -> list[tuple[str, str]]:
    choices = []
    for profile in _load_clone_profiles(engine_key):
        label = profile.get("name") or profile.get("id")
        source = profile.get("source_voice") or "custom"
        choices.append((f"Clone: {label} · {source}", f"clone:{profile.get('id')}"))
    return choices


def _choices_with_clones(engine_key: str) -> tuple[list[tuple[str, str]], str | None, dict[str, Any]]:
    response = manager.list_voices(engine_key)
    choices, value = _choices_from_response(response)
    choices.extend(_clone_voice_choices(engine_key))
    if value is None and choices:
        value = choices[0][1]
    return choices, value, response


def _builtin_voice_choices(engine_key: str) -> tuple[list[tuple[str, str]], str | None, str]:
    response = manager.list_voices(engine_key)
    choices, value = _choices_from_response(response)
    return choices, value, str(response.get("status") or "Engine ready.")


def refresh_voice_library():
    rows: list[list[str]] = []
    messages: list[str] = []
    for key, config in ENGINES.items():
        try:
            choices, _value, message = _builtin_voice_choices(key)
            for label, voice_id in choices:
                rows.append(["Giọng có sẵn", config.label, voice_id, label, "Sẵn sàng", "Preset gốc từ worker"])
            messages.append(f"{config.label}: {len(choices)} giọng từ worker · {message}")
        except Exception as exc:
            local_rows, local_message = _voice_rows_from_local_files(key)
            rows.extend(local_rows)
            messages.append(f"{config.label}: worker lỗi ({exc}); dùng fallback local. {local_message}")

    clone_rows, clone_message = _clone_profile_rows(include_empty=True)
    rows.extend(clone_rows)
    messages.append(clone_message)
    return rows, "\n".join(messages)


def open_local_folder(folder: str):
    path = Path(folder)
    try:
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))  # type: ignore[attr-defined]
        return f"Đã mở: {path}"
    except Exception as exc:
        return f"Không mở được thư mục: {exc}"


def _file_path(file_value: Any) -> str | None:
    if not file_value:
        return None
    if isinstance(file_value, str):
        return file_value
    if isinstance(file_value, dict):
        return file_value.get("path") or file_value.get("name")
    return getattr(file_value, "name", None) or getattr(file_value, "path", None)


def _choices_from_response(response: dict[str, Any]) -> tuple[list[tuple[str, str]], str | None]:
    if not response.get("ok"):
        raise WorkerError(str(response.get("status") or "Failed to list voices."))
    choices = [(str(v.get("label") or v.get("id")), str(v.get("id"))) for v in response.get("voices", [])]
    default_voice = response.get("default_voice")
    if default_voice and any(value == default_voice for _, value in choices):
        value = str(default_voice)
    elif choices:
        value = choices[0][1]
    else:
        value = None
    return choices, value


def _queue_summary() -> str:
    counts = store.counts()
    return f"{counts['tasks']} tác vụ · {counts['waiting']} đang chờ · {counts['done']} đã xong · {counts['error']} lỗi"


def _char_meter(text: str = "") -> str:
    current_chars = len(text or "")
    current_words = len((text or "").split())
    return f"{current_chars:,} ký tự · {current_words:,} từ"


def _task_updates(filter_mode: str = "Tất cả task", selected_id: str | None = None):
    choices = store.choices()
    valid_ids = {value for _, value in choices}
    value = selected_id if selected_id in valid_ids else (choices[0][1] if choices else None)
    return (
        gr.update(value=store.rows(filter_mode)),
        gr.update(choices=choices, value=value),
        _queue_summary(),
    )


def _status_with_gpu(message: str) -> str:
    _, details = get_gpu_status()
    return f"{message}\n{manager.status()}\n{details}"


def _output_audio_path(task: TtsTask, template: str) -> Path:
    path = OUTPUT_DIR / render_template(template, task, "wav")
    if path.exists():
        path = path.with_name(f"{path.stem}-{task.short_id}{path.suffix}")
    return path


def _payload_for_task(task: TtsTask, output_path: Path) -> dict[str, Any]:
    settings = task.settings
    clone_profile = _clone_profile_by_value(task.voice)
    voice = task.voice
    ref_audio = settings.get("ref_audio")
    ref_codes_path = settings.get("ref_codes_path")
    if clone_profile:
        source_voice = str(clone_profile.get("source_voice") or "").strip()
        voice = source_voice or None
        if clone_profile.get("ref_codes_path"):
            ref_codes_path = str(clone_profile.get("ref_codes_path"))
            ref_audio = None
        elif clone_profile.get("ref_audio"):
            ref_audio = str(clone_profile.get("ref_audio"))

    payload: dict[str, Any] = {
        "text": task.text,
        "voice": voice,
        "output_path": str(output_path),
        "device": _resolve_device(str(settings.get("device") or "GPU")),
        "volume": float(settings.get("volume", 1.0)),
        "normalize_audio": bool(settings.get("normalize_audio", False)),
    }
    if task.engine == "kokoro":
        payload.update(
            {
                "speed": float(settings.get("speed", 1.0)),
                "crossfade_ms": int(settings.get("crossfade_ms", 50)),
            }
        )
    else:
        payload.update(
            {
                "emotion": settings.get("emotion", "natural"),
                "temperature": float(settings.get("temperature", 0.8)),
                "ref_audio": ref_audio,
                "ref_codes_path": ref_codes_path,
            }
        )
    return payload


def _synthesize_task(task: TtsTask, template: str, output_formats: list[str]) -> tuple[str | None, str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    task.status = STATUS_PROCESSING
    task.error = ""
    task.details = ""
    output_path = _output_audio_path(task, template)
    response = manager.synthesize(task.engine, _payload_for_task(task, output_path))
    if not response.get("ok"):
        task.status = STATUS_ERROR
        task.error = str(response.get("status") or "Generation failed.")
        task.details = str(response.get("details") or "")
        return None, task.error

    task.status = STATUS_DONE
    task.audio_path = str(response.get("audio_path") or output_path)
    task.details = str(response.get("details") or "")
    task.error = ""
    task.exports = write_exports(task, OUTPUT_DIR, template, output_formats)
    return task.audio_path, str(response.get("status") or "Done")


def refresh_gpu():
    badge, details = get_gpu_status()
    return f"<div class='gpu-badge'>{badge}</div>", details


def on_engine_change(engine_key: str):
    try:
        choices, value, response = _choices_with_clones(engine_key)
        return (
            gr.update(choices=choices, value=value),
            gr.update(visible=engine_key == "vieneu"),
            gr.update(visible=engine_key == "vieneu"),
            gr.update(visible=engine_key == "vieneu"),
            _status_with_gpu(str(response.get("status") or "Engine ready.")),
        )
    except Exception as exc:
        return (
            gr.update(choices=[], value=None),
            gr.update(visible=engine_key == "vieneu"),
            gr.update(visible=engine_key == "vieneu"),
            gr.update(visible=engine_key == "vieneu"),
            f"Error: {exc}",
        )


def apply_preset(preset: str):
    values = PRESETS.get(preset, PRESETS["Tự nhiên"])
    return (
        values["speed"],
        values["pitch"],
        values["volume"],
        values["emotion"],
        values["temperature"],
        f"Preset: {preset}",
    )


def clean_textbox(text: str):
    cleaned = clean_script(text or "")
    return cleaned, _char_meter(cleaned), "Script cleaned."


def clear_textbox():
    return "", _char_meter(""), "Content cleared."


def clear_direct_text():
    return "", _char_meter(""), "", "Đã xóa nội dung."


def _plain_clean_result(text: str) -> TtsCleanResult:
    cleaned = (text or "").strip()
    return TtsCleanResult(original=text or "", cleaned=cleaned, warnings=[], transformations=[])


def generate_direct_tts(
    text: str,
    engine: str,
    voice: str,
    preset: str,
    speed: float,
    crossfade_ms: float,
    emotion: str,
    temperature: float,
    pitch: float,
    volume: float,
    device_mode: str,
    ref_audio: Any,
    clean_enabled: bool,
):
    clean_result = clean_text_for_tts(text or "") if clean_enabled else _plain_clean_result(text or "")
    cleaned = clean_result.cleaned.strip()
    if not cleaned:
        return None, cleaned, "", "Không có nội dung để tạo giọng đọc."
    if not voice:
        return None, cleaned, "", "Cần chọn giọng đọc trước khi tạo audio."

    settings = make_settings(
        speed=speed,
        crossfade_ms=crossfade_ms,
        emotion=emotion,
        temperature=temperature,
        pitch=pitch,
        volume=volume,
        normalize_audio=DEFAULT_NORMALIZE_AUDIO,
    )
    settings["device"] = device_mode
    settings["ref_audio"] = _file_path(ref_audio)
    task = TtsTask(
        id=uuid.uuid4().hex,
        text=cleaned,
        engine=engine,
        voice=voice,
        preset=preset,
        settings=settings,
        source="Direct",
    )

    audio_path, status = _synthesize_task(task, DEFAULT_FILENAME_TEMPLATE, DEFAULT_OUTPUT_FORMATS)
    notes: list[str] = []
    if clean_result.transformations:
        notes.append("Đã làm sạch: " + ", ".join(dict.fromkeys(clean_result.transformations)))
    if clean_result.warnings:
        notes.append("Lưu ý: " + " ".join(clean_result.warnings))
    if task.details:
        notes.append(task.details)
    detail_text = "\n\n".join(notes)
    if task.error:
        return None, cleaned, detail_text, task.error
    return audio_path, cleaned, detail_text, status


def open_direct_audio(audio_path: str | None):
    if not audio_path:
        return "Chưa có file audio để mở."
    path = Path(audio_path)
    target = path if path.exists() else OUTPUT_DIR
    try:
        os.startfile(str(target))  # type: ignore[attr-defined]
        return f"Đã mở: {target}"
    except Exception as exc:
        return f"Không mở được file: {exc}"


def add_current_task(
    text: str,
    engine: str,
    voice: str,
    preset: str,
    speed: float,
    crossfade_ms: float,
    emotion: str,
    temperature: float,
    pitch: float,
    volume: float,
    normalize_audio: bool,
    device_mode: str,
    ref_audio: Any,
    filter_mode: str,
):
    text = clean_script(text or "")
    if not text:
        table, selector, summary = _task_updates(filter_mode)
        return table, selector, summary, _char_meter(text), "No text to add."

    settings = make_settings(
        speed=speed,
        crossfade_ms=crossfade_ms,
        emotion=emotion,
        temperature=temperature,
        pitch=pitch,
        volume=volume,
        normalize_audio=normalize_audio,
    )
    settings["device"] = device_mode
    settings["ref_audio"] = _file_path(ref_audio)
    task = store.add(text=text, engine=engine, voice=voice, preset=preset, settings=settings)
    table, selector, summary = _task_updates(filter_mode, task.id)
    return table, selector, summary, _char_meter(text), f"Added task {task.short_id}."


def import_subtitle_tasks(
    subtitle_file: Any,
    engine: str,
    voice: str,
    preset: str,
    speed: float,
    crossfade_ms: float,
    emotion: str,
    temperature: float,
    pitch: float,
    volume: float,
    normalize_audio: bool,
    device_mode: str,
    ref_audio: Any,
    filter_mode: str,
):
    path = _file_path(subtitle_file)
    if not path:
        table, selector, summary = _task_updates(filter_mode)
        return table, selector, summary, "No subtitle file selected."

    segments = parse_subtitle(path)
    if not segments:
        table, selector, summary = _task_updates(filter_mode)
        return table, selector, summary, "No subtitle segments found."

    settings = make_settings(
        speed=speed,
        crossfade_ms=crossfade_ms,
        emotion=emotion,
        temperature=temperature,
        pitch=pitch,
        volume=volume,
        normalize_audio=normalize_audio,
    )
    settings["device"] = device_mode
    settings["ref_audio"] = _file_path(ref_audio)
    last_id = None
    for segment in segments:
        task = store.add(
            text=segment.text,
            engine=engine,
            voice=voice,
            preset=preset,
            settings=settings,
            source=Path(path).name,
            subtitle_index=segment.index,
            start=segment.start,
            end=segment.end,
        )
        last_id = task.id

    table, selector, summary = _task_updates(filter_mode, last_id)
    return table, selector, summary, f"Imported {len(segments)} subtitle tasks."


def on_filter_change(filter_mode: str, selected_task: str | None):
    return _task_updates(filter_mode, selected_task)


def listen_task(task_id: str | None):
    task = store.get(task_id)
    if not task or not task.audio_path:
        return None, "", "No generated audio for this task."
    return task.audio_path, task.details, f"Loaded audio: {Path(task.audio_path).name}"


def open_task_file(task_id: str | None):
    task = store.get(task_id)
    path = Path(task.audio_path) if task and task.audio_path else OUTPUT_DIR
    target = path if path.exists() else OUTPUT_DIR
    try:
        os.startfile(str(target))  # type: ignore[attr-defined]
        return f"Opened: {target}"
    except Exception as exc:
        return f"Open failed: {exc}"


def delete_task(task_id: str | None, filter_mode: str):
    deleted = store.delete(task_id)
    table, selector, summary = _task_updates(filter_mode)
    message = "Task deleted." if deleted else "No task selected."
    return table, selector, summary, None, "", message


def clear_queue(filter_mode: str):
    store.clear()
    table, selector, summary = _task_updates(filter_mode)
    return table, selector, summary, None, "", "Queue cleared."


def export_selected(task_id: str | None, template: str, output_formats: list[str]):
    task = store.get(task_id)
    if not task:
        return "No task selected."
    task.exports = write_exports(task, OUTPUT_DIR, template, output_formats)
    return "Exported: " + ", ".join(task.exports.values()) if task.exports else "No export format selected."


def regenerate_selected(task_id: str | None, filter_mode: str, template: str, output_formats: list[str]):
    task = store.get(task_id)
    if not task:
        table, selector, summary = _task_updates(filter_mode)
        yield table, selector, summary, None, "", "No task selected."
        return

    task.status = STATUS_WAITING
    table, selector, summary = _task_updates(filter_mode, task.id)
    yield table, selector, summary, task.audio_path, task.details, f"Regenerating {task.short_id}..."

    audio_path, status = _synthesize_task(task, template, output_formats)
    table, selector, summary = _task_updates(filter_mode, task.id)
    yield table, selector, summary, audio_path, task.details, status


def run_queue(filter_mode: str, template: str, output_formats: list[str]):
    tasks = store.waiting()
    if not tasks:
        table, selector, summary = _task_updates(filter_mode)
        yield table, selector, summary, None, "", "No waiting tasks."
        return

    last_audio = None
    last_details = ""
    for task in tasks:
        table, selector, summary = _task_updates(filter_mode, task.id)
        task.status = STATUS_PROCESSING
        yield table, selector, summary, last_audio, last_details, f"Processing task {task.short_id}..."

        audio_path, status = _synthesize_task(task, template, output_formats)
        last_audio = audio_path
        last_details = task.details
        table, selector, summary = _task_updates(filter_mode, task.id)
        yield table, selector, summary, last_audio, last_details, status

    yield (*_task_updates(filter_mode), last_audio, last_details, "Queue finished.")


def unload_engine():
    return None, "", manager.unload()


def switch_page(page: str):
    return tuple(gr.update(visible=page == choice) for choice in NAV_CHOICES)


def switch_to_create_page():
    return (gr.update(value="Tạo giọng đọc"), *switch_page("Tạo giọng đọc"))


def switch_create_mode(mode: str):
    return (
        gr.update(visible=mode == "Text to Speech"),
        gr.update(visible=mode == "Clone Voice"),
    )


def on_clone_engine_change(engine_key: str):
    try:
        choices, value, message = _builtin_voice_choices(engine_key)
        return (
            gr.update(choices=choices, value=value),
            gr.update(visible=engine_key == "vieneu"),
            gr.update(visible=engine_key == "vieneu"),
            gr.update(visible=engine_key == "vieneu"),
            message,
        )
    except Exception as exc:
        return (
            gr.update(choices=[], value=None),
            gr.update(visible=engine_key == "vieneu"),
            gr.update(visible=engine_key == "vieneu"),
            gr.update(visible=engine_key == "vieneu"),
            f"Lỗi tải giọng clone: {exc}",
        )


def create_clone_profile(
    engine_key: str,
    clone_name: str,
    source_voice: str,
    ref_audio: Any,
    sample_text: str,
    speed: float,
    crossfade_ms: float,
    emotion: str,
    temperature: float,
    volume: float,
    normalize_audio: bool,
    device_mode: str,
    current_create_engine: str,
):
    name = (clone_name or "").strip()
    text = clean_script(sample_text or "")
    if not name:
        rows, library_status = refresh_voice_library()
        return None, "Cần nhập tên clone.", rows, library_status, gr.update()
    if engine_key == "kokoro" and not source_voice:
        rows, library_status = refresh_voice_library()
        return None, "Kokoro cần chọn voicepack nền. Kokoro không hỗ trợ clone tức thì từ audio mẫu.", rows, library_status, gr.update()
    if not text:
        rows, library_status = refresh_voice_library()
        return None, "Cần nhập câu test để tạo preview.", rows, library_status, gr.update()

    ref_path = _file_path(ref_audio)
    if engine_key == "vieneu" and not ref_path:
        rows, library_status = refresh_voice_library()
        return None, "VieNeu clone voice cần audio mẫu.", rows, library_status, gr.update()

    profile_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{_safe_filename(name)}"
    profile_dir = USER_VOICE_DIR / profile_id
    profile_dir.mkdir(parents=True, exist_ok=True)
    CLONE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    copied_ref = None
    if ref_path:
        source_path = Path(ref_path)
        suffix = source_path.suffix or ".wav"
        copied_ref = profile_dir / f"reference{suffix}"
        try:
            shutil.copy2(source_path, copied_ref)
        except Exception:
            copied_ref = source_path

    output_path = CLONE_OUTPUT_DIR / f"{profile_id}.wav"
    ref_codes_path = None
    encode_details = ""
    if engine_key == "vieneu" and copied_ref:
        ref_codes_path = profile_dir / "voice_codes.npy"
        try:
            encode_response = manager.encode_reference(
                "vieneu",
                {
                    "ref_audio": str(copied_ref),
                    "output_path": str(ref_codes_path),
                    "device": _resolve_device(device_mode),
                },
            )
            if not encode_response.get("ok"):
                rows, library_status = refresh_voice_library()
                return None, str(encode_response.get("status") or "Mã hóa giọng mẫu thất bại."), rows, library_status, gr.update()
            encode_details = str(encode_response.get("details") or "")
        except Exception as exc:
            rows, library_status = refresh_voice_library()
            return None, f"Mã hóa giọng mẫu thất bại: {exc}", rows, library_status, gr.update()

    payload: dict[str, Any] = {
        "text": text,
        "voice": source_voice if engine_key == "kokoro" else None,
        "output_path": str(output_path),
        "device": _resolve_device(device_mode),
        "volume": float(volume),
        "normalize_audio": bool(normalize_audio),
    }
    if engine_key == "kokoro":
        payload.update({"speed": float(speed), "crossfade_ms": int(float(crossfade_ms))})
    else:
        payload.update(
            {
                "emotion": emotion,
                "temperature": float(temperature),
                "ref_audio": None if ref_codes_path else (str(copied_ref) if copied_ref else None),
                "ref_codes_path": str(ref_codes_path) if ref_codes_path else None,
            }
        )

    try:
        response = manager.synthesize(engine_key, payload)
        if not response.get("ok"):
            rows, library_status = refresh_voice_library()
            return None, str(response.get("status") or "Tạo clone thất bại."), rows, library_status, gr.update()
    except Exception as exc:
        rows, library_status = refresh_voice_library()
        return None, f"Tạo clone thất bại: {exc}", rows, library_status, gr.update()

    profile = {
        "id": profile_id,
        "name": name,
        "engine": engine_key,
        "engine_label": ENGINES[engine_key].label,
        "source_voice": source_voice if engine_key == "kokoro" else "",
        "ref_audio": str(copied_ref) if copied_ref else None,
        "ref_codes_path": str(ref_codes_path) if ref_codes_path else None,
        "preview_audio": str(output_path),
        "sample_text": text,
        "device": device_mode,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "ref_codes" if ref_codes_path else ("ref_audio" if copied_ref else "preset_alias"),
    }
    USER_VOICE_DIR.mkdir(parents=True, exist_ok=True)
    _clone_profile_path(profile_id).write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

    rows, library_status = refresh_voice_library()
    voice_update = gr.update()
    if current_create_engine == engine_key:
        choices, _value, _response = _choices_with_clones(engine_key)
        voice_update = gr.update(choices=choices, value=f"clone:{profile_id}")
    if engine_key == "vieneu":
        message = f"Đã tạo clone '{name}' bằng VieNeu ref codes. Preview: {output_path.name}"
        if encode_details:
            message += f"\n{encode_details}"
    else:
        message = (
            f"Đã lưu profile Kokoro '{name}' từ voicepack '{source_voice}'. "
            f"Kokoro không clone tức thì từ audio mẫu; muốn clone giọng riêng cần tạo voicepack .pt/finetune riêng. "
            f"Preview: {output_path.name}"
        )
    return str(output_path), message, rows, library_status, voice_update


def create_clone_profile_debug(
    engine_key: str,
    clone_name: str,
    source_voice: str,
    ref_audio: Any,
    sample_text: str,
    speed: float,
    crossfade_ms: float,
    emotion: str,
    temperature: float,
    volume: float,
    normalize_audio: bool,
    device_mode: str,
    current_create_engine: str,
):
    run_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    debug_lines: list[str] = []
    engine_label = ENGINES.get(engine_key, ENGINES["vieneu"]).label
    ref_path = _file_path(ref_audio)
    preview_name = (clone_name or "").strip() or "(chưa đặt tên)"
    text_len = len(clean_script(sample_text or ""))

    _clone_debug_append(
        debug_lines,
        run_id,
        "start",
        f"Bắt đầu tạo clone '{preview_name}' bằng {engine_label}.",
        engine=engine_key,
        clone_name=clone_name,
        source_voice=source_voice,
        ref_audio=ref_path,
        device_mode=device_mode,
        text_len=text_len,
        speed=speed,
        crossfade_ms=crossfade_ms,
        emotion=emotion,
        temperature=temperature,
        volume=volume,
        normalize_audio=normalize_audio,
    )
    rows, library_status = voice_library_snapshot()
    yield None, _clone_debug_format(debug_lines), rows, library_status, gr.update()

    _clone_debug_append(debug_lines, run_id, "validate", "Đang kiểm tra tên clone, audio mẫu và câu preview.")
    yield None, _clone_debug_format(debug_lines), rows, library_status, gr.update()

    if engine_key == "vieneu":
        _clone_debug_append(
            debug_lines,
            run_id,
            "vieneu",
            "VieNeu sẽ copy audio mẫu, encode thành voice_codes.npy rồi tạo preview bằng ref codes.",
            expected_log=str(LOG_DIR / "vieneu_worker.err.log"),
        )
    else:
        _clone_debug_append(
            debug_lines,
            run_id,
            "kokoro",
            "Kokoro chỉ dùng voicepack preset; không clone tức thì từ audio mẫu.",
            expected_log=str(LOG_DIR / "kokoro_worker.err.log"),
        )
    yield None, _clone_debug_format(debug_lines), rows, library_status, gr.update()

    try:
        audio_path, message, rows, library_status, voice_update = create_clone_profile(
            engine_key,
            clone_name,
            source_voice,
            ref_audio,
            sample_text,
            speed,
            crossfade_ms,
            emotion,
            temperature,
            volume,
            normalize_audio,
            device_mode,
            current_create_engine,
        )
    except Exception as exc:
        tb = traceback.format_exc(limit=12)
        _clone_debug_append(
            debug_lines,
            run_id,
            "exception",
            f"Lỗi ngoài dự kiến: {exc}",
            traceback=tb,
        )
        rows, library_status = voice_library_snapshot()
        yield None, _clone_debug_format(debug_lines), rows, library_status, gr.update()
        return

    stage = "done" if audio_path else "failed"
    _clone_debug_append(
        debug_lines,
        run_id,
        stage,
        str(message),
        audio_path=audio_path,
        library_status=library_status,
    )
    yield audio_path, _clone_debug_format(debug_lines), rows, library_status, voice_update


def check_runtime_paths():
    rows = []
    for engine, python_path, python_state, cwd in _engine_runtime_rows():
        rows.append([engine, python_path, python_state, cwd])
    for name, path, state in _model_status_rows():
        rows.append([name, path, state, ""])
    return rows, "Đã kiểm tra đường dẫn runtime và model."


def _google_voice_update(voices: list[dict[str, Any]], preferred_voice: str | None = None):
    choices = google_voice_choices(voices)
    values = [value for _label, value in choices]
    value = preferred_voice if preferred_voice in values else (values[0] if values else None)
    return gr.update(choices=choices, value=value, interactive=True)


def refresh_google_voices_ui(credential_path: str, language_code: str, preferred_voice: str | None):
    normalized_language = (language_code or GOOGLE_DEFAULT_LANGUAGE_CODE).strip() or GOOGLE_DEFAULT_LANGUAGE_CODE
    try:
        voices = fetch_google_voices(credential_path, normalized_language)
        if not voices:
            voices = list(GOOGLE_FALLBACK_VOICES)
            status = f"Google Cloud không trả voice cho {normalized_language}. Đang dùng danh sách dự phòng."
        else:
            status = f"Đã tải {len(voices)} voice từ Google Cloud cho {normalized_language}.\n{google_credential_status(credential_path)}"
    except Exception as exc:
        voices = list(GOOGLE_FALLBACK_VOICES)
        status = (
            f"Không tải được danh sách voice từ Google Cloud: {exc}\n"
            "Đang dùng danh sách tiếng Việt dự phòng. Bạn vẫn cần key hợp lệ khi tạo audio."
        )
    return _google_voice_update(voices, preferred_voice), google_voice_table_rows(voices), status


def save_google_private_settings(
    credential_path: str,
    language_code: str,
    voice_name: str,
    ai_model: str,
    max_chars_per_chunk: int,
):
    settings_path = save_google_settings(
        credential_path,
        language_code,
        voice_name,
        ai_model,
        int(max_chars_per_chunk or GOOGLE_DEFAULT_CHUNK_CHAR_LIMIT),
    )
    return (
        f"Đã lưu cấu hình Google TTS vào file riêng tư: {settings_path}\n"
        f"{google_credential_status(credential_path)}\n"
        "File này nằm trong private/ và đã được loại khỏi git."
    )


def clear_google_text():
    return "", "", None, "", "Đã xóa nội dung Google TTS."


def generate_google_direct_tts(
    text: str,
    credential_path: str,
    language_code: str,
    voice_name: str,
    ai_model: str,
    style_instructions: str,
    speaking_rate: float,
    pitch: float,
    max_chars_per_chunk: int,
    clean_enabled: bool,
):
    raw_text = text or ""
    if clean_enabled:
        clean_result = clean_text_for_tts(raw_text)
        text_to_say = clean_result.cleaned
        clean_details = []
        if clean_result.transformations:
            clean_details.append("Biến đổi: " + ", ".join(clean_result.transformations[:12]))
        if clean_result.warnings:
            clean_details.append("Lưu ý: " + " ".join(clean_result.warnings))
        cleaned_preview = text_to_say
    else:
        text_to_say = " ".join(raw_text.split())
        clean_details = ["Không bật bộ làm sạch nâng cao, chỉ chuẩn hóa khoảng trắng."]
        cleaned_preview = text_to_say

    if not text_to_say:
        return None, cleaned_preview, "", "Vui lòng nhập văn bản trước khi tạo audio."

    try:
        result = synthesize_google_tts(
            text=text_to_say,
            language_code=language_code or GOOGLE_DEFAULT_LANGUAGE_CODE,
            voice_name=voice_name,
            speaking_rate=float(speaking_rate),
            pitch=float(pitch),
            credential_path=credential_path,
            style_instructions=style_instructions,
            ai_model=ai_model or GOOGLE_AI_MODEL_CLOUD_VOICE,
            max_chars_per_chunk=int(max_chars_per_chunk or GOOGLE_DEFAULT_CHUNK_CHAR_LIMIT),
        )
        save_google_settings(
            credential_path,
            language_code or GOOGLE_DEFAULT_LANGUAGE_CODE,
            voice_name,
            ai_model or GOOGLE_AI_MODEL_CLOUD_VOICE,
            int(max_chars_per_chunk or GOOGLE_DEFAULT_CHUNK_CHAR_LIMIT),
        )
    except GoogleTtsError as exc:
        return None, cleaned_preview, "\n".join(clean_details), f"Tạo Google TTS thất bại: {exc}"
    except Exception as exc:
        return None, cleaned_preview, "\n".join(clean_details), f"Tạo Google TTS thất bại ngoài dự kiến: {exc}"

    source = "cache" if result.from_cache else "Google API"
    details_lines = [
        f"File: {result.audio_path}",
        f"Voice: {result.voice_name}",
        f"Ngôn ngữ: {result.language_code}",
        f"AI model: {result.ai_model}",
        f"Nguồn: {source}",
        f"Tổng ký tự: {result.total_characters:,}",
        f"Ký tự gọi API lần này: {result.characters_billed:,}",
        f"Số đoạn: {result.chunk_count:,} | tạo mới: {result.chunks_generated:,} | từ cache: {result.chunks_from_cache:,}",
    ]
    if clean_details:
        details_lines.extend(clean_details)
    if result.style_warning:
        details_lines.append("Style: " + result.style_warning)
    elif result.style_applied:
        details_lines.append("Style: đã gửi kèm request Gemini TTS.")
    return str(result.audio_path), cleaned_preview, "\n".join(details_lines), f"Đã tạo Google TTS: {result.audio_path.name}"


def open_google_output_dir():
    return open_local_folder(str(GOOGLE_OUTPUT_DIR))


def clear_google_cache_ui():
    removed = clear_google_cache()
    return f"Đã xóa {removed} file cache Google TTS."


def build_google_tts_header_html() -> str:
    return """
    <section class="google-tts-hero" aria-labelledby="google-tts-title">
      <div>
        <span class="google-kicker">Cloud Text-to-Speech</span>
        <h1 id="google-tts-title">TTS Google</h1>
        <p>
          Trang riêng để dùng Google Cloud Text-to-Speech trong cùng TTS Studio.
          Key, credential và đường dẫn tài khoản được lưu cục bộ trong private/ và không đưa lên git.
        </p>
      </div>
      <div class="google-tts-meter" aria-hidden="true">
        <span></span><span></span><span></span><span></span><span></span>
      </div>
    </section>
    """


def build_sidebar_brand_html() -> str:
    return f"""
    {build_runtime_global_css()}
    <div class="brand">
      <div class="brand-mark">TTS</div>
      <div>
        <div class="brand-title">TTS<br/>Studio</div>
        <div class="brand-subtitle">Local voice suite</div>
      </div>
    </div>
    """


def build_landing_hero_html() -> str:
    return """
    <section class="landing-hero" aria-labelledby="landing-title">
      <div class="landing-scene" aria-hidden="true">
        <div class="signal-grid"></div>
        <div class="signal-panel signal-panel-main">
          <div class="signal-toolbar">
            <span></span><span></span><span></span>
          </div>
          <div class="waveform waveform-a">
            <i style="--h: 46%"></i><i style="--h: 74%"></i><i style="--h: 38%"></i>
            <i style="--h: 86%"></i><i style="--h: 58%"></i><i style="--h: 34%"></i>
            <i style="--h: 92%"></i><i style="--h: 64%"></i><i style="--h: 42%"></i>
            <i style="--h: 80%"></i><i style="--h: 52%"></i><i style="--h: 70%"></i>
          </div>
          <div class="timeline-line"></div>
          <div class="waveform waveform-b">
            <i style="--h: 62%"></i><i style="--h: 30%"></i><i style="--h: 76%"></i>
            <i style="--h: 50%"></i><i style="--h: 90%"></i><i style="--h: 44%"></i>
            <i style="--h: 66%"></i><i style="--h: 36%"></i><i style="--h: 82%"></i>
            <i style="--h: 54%"></i><i style="--h: 72%"></i><i style="--h: 48%"></i>
          </div>
        </div>
        <div class="voice-chip chip-kokoro">Kokoro Vietnamese</div>
        <div class="voice-chip chip-vieneu">VieNeu-TTS v3 Turbo</div>
        <div class="voice-meter">
          <span></span><span></span><span></span><span></span><span></span>
        </div>
      </div>
      <div class="landing-hero-copy">
        <div class="landing-kicker">Local Vietnamese TTS workspace</div>
        <h1 id="landing-title">TTS Studio Unified</h1>
        <p>
          Một landing workspace cho tạo giọng đọc, clone voice, quản lý thư viện giọng
          và xuất file audio ngay trên máy của bạn.
        </p>
        <div class="landing-proof" aria-label="Project highlights">
          <span>2 engine local</span>
          <span>GPU/CPU/Auto</span>
          <span>TXT/SRT/VTT</span>
        </div>
      </div>
    </section>
    """


def build_landing_sections_html() -> str:
    return """
    <section class="landing-section" aria-label="Điểm nổi bật">
      <div class="landing-section-heading">
        <span>Built for voice production</span>
        <h2>Từ văn bản thô đến audio sạch trong một luồng duy nhất.</h2>
      </div>
      <div class="landing-feature-grid">
        <article class="landing-card">
          <div class="landing-card-label">01</div>
          <h3>Tạo giọng đọc trực tiếp</h3>
          <p>Nhập nội dung, làm sạch tiếng Việt, chọn preset và nghe kết quả mà không cần rời màn hình chính.</p>
        </article>
        <article class="landing-card">
          <div class="landing-card-label">02</div>
          <h3>Clone voice có kiểm soát</h3>
          <p>Lưu profile clone riêng, preview nhanh và đồng bộ lại vào kho giọng cho những lần tạo tiếp theo.</p>
        </article>
        <article class="landing-card">
          <div class="landing-card-label">03</div>
          <h3>Tối ưu cho máy local</h3>
          <p>Hai worker tách biệt giúp đổi engine gọn hơn, giữ chính sách một engine đang load để kiểm soát VRAM.</p>
        </article>
      </div>
    </section>

    <section class="landing-workflow" aria-label="Quy trình sử dụng">
      <div class="workflow-copy">
        <span>Production flow</span>
        <h2>Ba bước để có bản đọc hoàn chỉnh.</h2>
      </div>
      <div class="workflow-steps">
        <div class="workflow-step"><strong>1</strong><span>Chọn engine, voice và thiết bị chạy.</span></div>
        <div class="workflow-step"><strong>2</strong><span>Dán script hoặc subtitle, bật làm sạch văn bản.</span></div>
        <div class="workflow-step"><strong>3</strong><span>Xuất WAV cùng TXT, SRT hoặc VTT theo mẫu tên file.</span></div>
      </div>
    </section>
    """


def build_create_studio_header_html() -> str:
    return """
    <section class="create-studio-hero" aria-labelledby="create-studio-title">
      <div class="create-studio-title">
        <div>
          <span class="create-kicker">Voice workspace</span>
          <h1 id="create-studio-title">Tạo giọng đọc</h1>
        </div>
        <div class="create-credit-pill">Text + Clone</div>
      </div>
    </section>
    """


def build_create_editor_intro_html() -> str:
    return """
    <div class="tts-editor-head">
      <div>
        <span class="tts-step-label">Script</span>
        <h2>Text</h2>
      </div>
      <div class="tts-editor-badges" aria-label="Generation profile">
        <span>Vietnamese-ready</span>
        <span>WAV output</span>
      </div>
    </div>
    """


def build_create_result_header_html() -> str:
    return """
    <div class="tts-result-head">
      <div>
        <span class="tts-step-label">Preview</span>
        <h2>Generated audio</h2>
      </div>
      <div class="tts-wave-mini" aria-hidden="true">
        <span></span><span></span><span></span><span></span><span></span><span></span>
      </div>
    </div>
    """


def build_clone_studio_intro_html() -> str:
    return """
    <div class="clone-studio-head">
      <div>
        <span class="tts-step-label">Clone Voice</span>
        <h2>Tạo profile giọng</h2>
      </div>
      <div class="tts-editor-badges" aria-label="Clone profile">
        <span>Reference audio</span>
        <span>Voice library</span>
      </div>
    </div>
    """


def build_clone_result_header_html() -> str:
    return """
    <div class="clone-result-head">
      <div>
        <span class="tts-step-label">Clone Preview</span>
        <h2>Audio kiểm tra</h2>
      </div>
      <div class="tts-wave-mini" aria-hidden="true">
        <span></span><span></span><span></span><span></span><span></span><span></span>
      </div>
    </div>
    """


def build_runtime_global_css() -> str:
    return """
    <style>
      @media (max-width: 720px) {
        body gradio-app .gradio-container {
          padding: 10px !important;
        }

        body gradio-app .gradio-container > .main.app {
          padding: 10px !important;
        }

        body gradio-app .gradio-container > .main.app > .wrap,
        body gradio-app .gradio-container > .main.app > .wrap > .contain,
        body gradio-app .gradio-container > .main.app > .wrap > .contain > .column {
          width: 100% !important;
          max-width: 100% !important;
          min-width: 0 !important;
        }
      }
    </style>
    """


def build_demo() -> gr.Blocks:
    engine_choices = [(config.label, key) for key, config in ENGINES.items()]
    preset_choices = list(PRESETS)
    initial_library_rows, initial_library_status = voice_library_snapshot()
    initial_model_config = load_model_config()
    initial_model_root = str(initial_model_config.get("model_root") or DEFAULT_MODEL_ROOT)
    initial_recommended_model = str(initial_model_config.get("recommended_model") or "kokoro")
    initial_google_settings = load_google_settings()
    initial_google_voices = list(GOOGLE_FALLBACK_VOICES)
    initial_google_voice_choices = google_voice_choices(initial_google_voices)
    initial_google_voice = str(initial_google_settings.get("voice_name") or GOOGLE_FALLBACK_VOICES[0]["name"])

    with gr.Blocks(title="TTS Studio", elem_classes=["studio-root"]) as demo:
        with gr.Row(elem_classes=["studio-shell"]):
            with gr.Column(scale=1, min_width=220, elem_classes=["sidebar"]):
                gr.HTML(build_sidebar_brand_html())
                nav = gr.Radio(NAV_CHOICES, value="Tổng quan", label="", elem_classes=["nav-radio"])

            with gr.Column(scale=4, min_width=340, elem_classes=["main-pane"]):
                with gr.Column(visible=True, elem_classes=["page-block", "landing-page"]) as overview_page:
                    gr.HTML(build_landing_hero_html())
                    with gr.Row(elem_classes=["landing-actions"]):
                        btn_start_create = gr.Button("Bắt đầu tạo giọng đọc", variant="primary", elem_classes=["primary-dark big-action"])
                        btn_scan_system = gr.Button("Quét cấu hình hệ thống", elem_classes=["ghost-button"])
                    gr.HTML(build_landing_sections_html())

                    with gr.Group(elem_classes=["section-card landing-system-card"]):
                        gr.HTML("<div class='section-title'>Kiểm tra cấu hình</div>")
                        system_table = gr.Dataframe(headers=["Mục", "Giá trị", "Đề xuất"], value=[], interactive=False, wrap=True)
                        system_recommendation = gr.Markdown("Bấm quét để đọc CPU/RAM/GPU, trạng thái model và gợi ý chạy CPU/GPU.")

                    with gr.Group(elem_classes=["section-card model-manager-card"]):
                        gr.HTML("<div class='section-title'>Tải và chạy model tối ưu</div>")
                        with gr.Row(elem_classes=["model-manager-row"]):
                            overview_model_choice = gr.Dropdown(
                                engine_choices,
                                value=initial_recommended_model,
                                label="Model đề xuất / muốn tải",
                            )
                            overview_model_root = gr.Textbox(
                                value=initial_model_root,
                                label="Thư mục lưu model",
                                placeholder=str(DEFAULT_MODEL_ROOT),
                            )
                        with gr.Row(elem_classes=["action-row compact-actions"]):
                            btn_download_recommended = gr.Button("Tải model đề xuất", variant="primary", elem_classes=["primary-dark"])
                            btn_download_all_models = gr.Button("Tải cả 2 model", elem_classes=["ghost-button"])
                            btn_load_overview_model = gr.Button("Load / chạy model", elem_classes=["ghost-button"])
                            btn_open_model_root = gr.Button("Mở thư mục model", elem_classes=["ghost-button"])
                        overview_model_paths = gr.Dataframe(
                            headers=["Model", "Đường dẫn đang nhớ", "Trạng thái", "Ghi chú"],
                            value=model_path_rows(),
                            interactive=False,
                            wrap=True,
                        )
                        overview_model_status = gr.Textbox(label="Log tải/chạy model", interactive=False, lines=8)

                with gr.Column(visible=False, elem_classes=["page-block", "create-studio-page"]) as create_page:
                    gr.HTML(build_create_studio_header_html())
                    create_mode = gr.Radio(
                        CREATE_MODE_CHOICES,
                        value="Text to Speech",
                        label="",
                        elem_classes=["create-mode-switch"],
                    )

                    with gr.Row(elem_classes=["create-workbench"]):
                        with gr.Column(scale=7, min_width=430, elem_classes=["create-main-panel"]):
                            with gr.Column(visible=True, elem_classes=["create-mode-panel", "tts-mode-panel"]) as tts_mode_panel:
                                with gr.Group(elem_classes=["section-card direct-card eleven-editor-card"]):
                                    gr.HTML(build_create_editor_intro_html())
                                    content = gr.Textbox(
                                        label="Text",
                                        lines=10,
                                        max_lines=18,
                                        value="Xin chào, đây là bản kiểm tra giao diện TTS Studio hợp nhất.",
                                        placeholder="Nhập nội dung cần tạo giọng đọc...",
                                        show_label=False,
                                        elem_classes=["tts-script-input"],
                                    )
                                    with gr.Row(elem_classes=["inline-options eleven-options"]):
                                        clean_enabled = gr.Checkbox(value=True, label="Tự làm sạch văn bản trước khi đọc", scale=2)
                                        show_cleaned = gr.Checkbox(value=False, label="Xem văn bản đã làm sạch", scale=1)
                                        btn_clear_text = gr.Button("Xóa văn bản", elem_classes=["danger-link"])
                                    cleaned_preview = gr.Textbox(label="Văn bản đã làm sạch", lines=6, interactive=False, visible=False)
                                    char_meter = gr.Markdown(_char_meter(""), elem_classes=["subtle", "tts-char-meter"])
                                    with gr.Row(elem_classes=["action-row tts-generate-bar"]):
                                        btn_generate_direct = gr.Button("Tạo audio", variant="primary", elem_classes=["primary-dark big-action"])
                                        btn_regenerate_direct = gr.Button("Tạo lại", elem_classes=["ghost-button secondary-action"])
                                        btn_open_direct = gr.Button("Mở file", elem_classes=["ghost-button secondary-action"])

                                with gr.Group(elem_classes=["section-card result-card eleven-result-card compact-result-card"]):
                                    gr.HTML(build_create_result_header_html())
                                    audio = gr.Audio(label="Audio", type="filepath", interactive=False)
                                    details = gr.Textbox(label="Chi tiết xử lý", interactive=False, lines=3)

                            with gr.Column(visible=False, elem_classes=["create-mode-panel", "clone-mode-panel"]) as clone_mode_panel:
                                with gr.Group(elem_classes=["section-card clone-studio-card"]):
                                    gr.HTML(build_clone_studio_intro_html())
                                    with gr.Row(elem_classes=["clone-source-row"]):
                                        clone_engine = gr.Dropdown(engine_choices, value="vieneu", label="Engine clone")
                                        clone_source_voice = gr.Dropdown([], label="Giọng nền", allow_custom_value=True)
                                        btn_clone_load = gr.Button("Load giọng", elem_classes=["ghost-button"])
                                    clone_name = gr.Textbox(label="Tên clone", placeholder="VD: giong-doc-review-cua-toi")
                                    clone_ref_audio = gr.Audio(label="Audio mẫu người dùng", type="filepath", visible=True)
                                    clone_text = gr.Textbox(label="Câu test preview", lines=3, value="Xin chào, đây là bản preview cho giọng clone trong TTS Studio.")
                                    with gr.Row(elem_classes=["clone-settings-row"]):
                                        clone_device = gr.Radio(["GPU", "CPU", "Auto"], value="GPU", label="Thiết bị chạy")
                                        clone_speed = gr.Slider(0.75, 1.25, value=1.0, step=0.01, label="Tốc độ")
                                        clone_crossfade = gr.Slider(0, 120, value=50, step=5, label="Crossfade ms")
                                    with gr.Row(elem_classes=["clone-settings-row"]):
                                        clone_emotion = gr.Dropdown(["natural", "happy", "sad", "angry", "surprised", "storytelling"], value="natural", label="Emotion", visible=True)
                                        clone_temperature = gr.Slider(0.2, 1.2, value=0.8, step=0.05, label="Temperature", visible=True)
                                        clone_volume = gr.Slider(0.1, 2.0, value=1.0, step=0.05, label="Âm lượng")
                                    clone_normalize = gr.Checkbox(value=True, label="Chuẩn hóa âm lượng")
                                    with gr.Row(elem_classes=["clone-action-row"]):
                                        btn_create_clone = gr.Button("Tạo clone", variant="primary", elem_classes=["primary-dark big-action"])
                                        btn_open_clone_dir = gr.Button("Mở kho clone", elem_classes=["ghost-button secondary-action"])

                                with gr.Group(elem_classes=["section-card clone-preview-card compact-result-card"]):
                                    gr.HTML(build_clone_result_header_html())
                                    clone_audio = gr.Audio(label="Preview clone", type="filepath")
                                    clone_status = gr.Textbox(label="Debug clone", interactive=False, lines=5)

                        with gr.Column(scale=3, min_width=280, elem_classes=["create-control-panel"]):
                            with gr.Group(elem_classes=["right-section create-voice-section"]):
                                gr.HTML("<div class='section-title'>Giọng đọc</div>")
                                engine = gr.Dropdown(engine_choices, value="kokoro", label="Engine")
                                voice = gr.Dropdown([], label="Chọn giọng đọc", allow_custom_value=True)
                                btn_load = gr.Button("Load giọng", elem_classes=["ghost-button"])
                                ref_audio = gr.Audio(label="Audio mẫu Clone Voice", type="filepath", visible=False)

                            with gr.Group(elem_classes=["right-section create-adjust-section"]):
                                gr.HTML("<div class='section-title'>Điều chỉnh giọng</div><div class='subtle'>Preset nhanh</div>")
                                preset = gr.Radio(preset_choices, value="Tự nhiên", label="", elem_classes=["small-actions"])
                                emotion = gr.Dropdown(["natural", "happy", "sad", "angry", "surprised", "storytelling"], value="natural", label="Emotion", visible=False)
                                device_mode = gr.Radio(["GPU", "CPU", "Auto"], value="GPU", label="Thiết bị chạy")
                                speed = gr.Slider(0.75, 1.25, value=1.0, step=0.01, label="Tốc độ")
                                pitch = gr.Slider(-1.0, 1.0, value=0.0, step=0.05, label="Pitch")
                                volume = gr.Slider(0.1, 2.0, value=1.0, step=0.05, label="Âm lượng")
                                temperature = gr.Slider(0.2, 1.2, value=0.8, step=0.05, label="Temperature", visible=False)
                                crossfade = gr.Slider(0, 120, value=50, step=5, label="Crossfade ms")

                            with gr.Group(elem_classes=["right-section create-status-section"]):
                                gpu_badge, gpu_details = refresh_gpu()
                                gpu_markdown = gr.HTML(gpu_badge)
                                gpu_text = gr.Textbox(value=gpu_details, label="GPU status", interactive=False, lines=1)
                                with gr.Row(elem_classes=["action-row compact-actions"]):
                                    btn_refresh_gpu = gr.Button("Cập nhật GPU", elem_classes=["ghost-button"])
                                    btn_unload = gr.Button("Unload", elem_classes=["ghost-button"])
                                status = gr.Textbox(label="Trạng thái", interactive=False, lines=3)

                with gr.Column(visible=False, elem_classes=["page-block", "google-tts-page"]) as google_page:
                    gr.HTML(build_google_tts_header_html())
                    with gr.Row(elem_classes=["google-tts-workbench"]):
                        with gr.Column(scale=7, min_width=430, elem_classes=["google-main-panel"]):
                            with gr.Group(elem_classes=["section-card google-editor-card"]):
                                gr.HTML(
                                    "<div class='tts-editor-head'><div><span class='tts-step-label'>Google Script</span><h2>Nhập văn bản</h2></div><div class='tts-editor-badges'><span>MP3 output</span><span>Cache local</span></div></div>"
                                )
                                google_content = gr.Textbox(
                                    label="Text",
                                    lines=10,
                                    max_lines=18,
                                    value="Xin chào, đây là bản kiểm tra Google Text-to-Speech trong TTS Studio.",
                                    placeholder="Nhập nội dung cần tạo giọng đọc bằng Google TTS...",
                                    show_label=False,
                                    elem_classes=["tts-script-input"],
                                )
                                with gr.Row(elem_classes=["inline-options eleven-options"]):
                                    google_clean_enabled = gr.Checkbox(value=True, label="Tự làm sạch văn bản trước khi đọc", scale=2)
                                    btn_google_clear = gr.Button("Xóa văn bản", elem_classes=["danger-link"])
                                with gr.Row(elem_classes=["action-row tts-generate-bar"]):
                                    btn_google_generate = gr.Button("Tạo TTS Google", variant="primary", elem_classes=["primary-dark big-action"])
                                    btn_google_open_output = gr.Button("Mở outputs Google", elem_classes=["ghost-button secondary-action"])
                                google_cleaned_preview = gr.Textbox(label="Văn bản đã làm sạch", lines=5, interactive=False)

                            with gr.Group(elem_classes=["section-card google-result-card compact-result-card"]):
                                gr.HTML(
                                    "<div class='tts-result-head'><div><span class='tts-step-label'>Google Preview</span><h2>Audio đầu ra</h2></div><div class='tts-wave-mini' aria-hidden='true'><span></span><span></span><span></span><span></span><span></span><span></span></div></div>"
                                )
                                google_audio = gr.Audio(label="Audio Google", type="filepath", interactive=False)
                                google_details = gr.Textbox(label="Chi tiết xử lý", interactive=False, lines=7)

                        with gr.Column(scale=3, min_width=300, elem_classes=["google-control-panel"]):
                            with gr.Group(elem_classes=["right-section google-private-section"]):
                                gr.HTML("<div class='section-title'>Key riêng tư</div>")
                                google_credential_path = gr.Textbox(
                                    value=str(initial_google_settings.get("credential_path") or ""),
                                    label="Đường dẫn file key JSON",
                                    placeholder="VD: D:\\keys\\google-tts-service-account.json",
                                    type="text",
                                )
                                gr.Markdown("Chỉ lưu đường dẫn trong `private/google_tts_settings.json`. Không lưu nội dung key.")
                                google_language = gr.Textbox(
                                    value=str(initial_google_settings.get("language_code") or GOOGLE_DEFAULT_LANGUAGE_CODE),
                                    label="Mã ngôn ngữ",
                                    placeholder=GOOGLE_DEFAULT_LANGUAGE_CODE,
                                )
                                with gr.Row(elem_classes=["action-row compact-actions"]):
                                    btn_google_save_settings = gr.Button("Lưu riêng tư", variant="primary", elem_classes=["primary-dark"])
                                    btn_google_load_voices = gr.Button("Tải voice", elem_classes=["ghost-button"])

                            with gr.Group(elem_classes=["right-section google-voice-section"]):
                                gr.HTML("<div class='section-title'>Giọng Google</div>")
                                google_voice = gr.Dropdown(
                                    initial_google_voice_choices,
                                    value=initial_google_voice,
                                    label="Voice",
                                    allow_custom_value=True,
                                )
                                google_ai_model = gr.Dropdown(
                                    GOOGLE_AI_MODEL_CHOICES,
                                    value=str(initial_google_settings.get("ai_model") or GOOGLE_AI_MODEL_CLOUD_VOICE),
                                    label="AI model",
                                )
                                google_style = gr.Textbox(
                                    label="Style Instructions",
                                    placeholder="Tùy chọn cho Gemini TTS, ví dụ: đọc ấm áp, rõ ràng, tốc độ vừa phải.",
                                    lines=3,
                                )

                            with gr.Group(elem_classes=["right-section google-tune-section"]):
                                gr.HTML("<div class='section-title'>Điều chỉnh</div>")
                                google_speed = gr.Slider(0.5, 2.0, value=1.0, step=0.05, label="Tốc độ đọc")
                                google_pitch = gr.Slider(-20.0, 20.0, value=0.0, step=0.5, label="Pitch")
                                google_max_chars = gr.Slider(
                                    500,
                                    5000,
                                    value=int(initial_google_settings.get("max_chars_per_chunk") or GOOGLE_DEFAULT_CHUNK_CHAR_LIMIT),
                                    step=100,
                                    label="Ký tự mỗi đoạn",
                                )
                                with gr.Row(elem_classes=["action-row compact-actions"]):
                                    btn_google_clear_cache = gr.Button("Xóa cache", elem_classes=["ghost-button"])
                                google_status = gr.Textbox(
                                    label="Trạng thái Google TTS",
                                    value=google_credential_status(initial_google_settings.get("credential_path") or ""),
                                    interactive=False,
                                    lines=5,
                                )

                    with gr.Group(elem_classes=["section-card google-voice-table-card"]):
                        gr.HTML("<div class='section-title'>Danh sách voice Google</div>")
                        google_voice_table = gr.Dataframe(
                            headers=GOOGLE_VOICE_HEADERS,
                            value=google_voice_table_rows(initial_google_voices),
                            interactive=False,
                            wrap=True,
                        )

                with gr.Column(visible=False, elem_classes=["page-block"]) as library_page:
                    gr.HTML("<div class='page-title'><h1>Kho giọng</h1></div>")
                    with gr.Group(elem_classes=["section-card voice-library-card"]):
                        gr.HTML("<div class='section-title'>Giọng Kokoro, VieNeu và clone người dùng</div>")
                        with gr.Row(elem_classes=["action-row compact-actions"]):
                            btn_refresh_library = gr.Button("Đồng bộ kho giọng", variant="primary", elem_classes=["primary-dark"])
                            btn_open_voice_dir = gr.Button("Mở thư mục clone", elem_classes=["ghost-button"])
                        library_table = gr.Dataframe(
                            headers=VOICE_LIBRARY_HEADERS,
                            value=initial_library_rows,
                            interactive=False,
                            wrap=True,
                            elem_classes=["voice-library-table"],
                        )
                        library_status = gr.Textbox(
                            label="Trạng thái kho giọng",
                            value=initial_library_status,
                            interactive=False,
                            lines=4,
                        )

                with gr.Column(visible=False, elem_classes=["page-block"]) as settings_page:
                    gr.HTML("<div class='page-title'><h1>Thiết lập</h1></div>")
                    with gr.Group(elem_classes=["section-card"]):
                        gr.HTML("<div class='section-title'>Thư mục làm việc</div>")
                        with gr.Row():
                            btn_open_outputs = gr.Button("Mở outputs", elem_classes=["ghost-button"])
                            btn_open_logs = gr.Button("Mở logs", elem_classes=["ghost-button"])
                            btn_open_clones_settings = gr.Button("Mở clones", elem_classes=["ghost-button"])
                            btn_unload_settings = gr.Button("Unload engine", elem_classes=["ghost-button"])
                        settings_status = gr.Textbox(label="Trạng thái thiết lập", interactive=False, lines=4)
                    with gr.Group(elem_classes=["section-card"]):
                        gr.HTML("<div class='section-title'>Runtime</div>")
                        runtime_table = gr.Dataframe(headers=["Hạng mục", "Đường dẫn", "Trạng thái", "Thư mục"], value=[], interactive=False, wrap=True)
                        btn_check_runtime = gr.Button("Kiểm tra runtime/model", elem_classes=["ghost-button"])

                with gr.Column(visible=False, elem_classes=["page-block"]) as donate_page:
                    gr.HTML("<div class='page-title'><h1>Donate</h1></div>")
                    with gr.Group(elem_classes=["section-card"]):
                        gr.HTML("<div class='section-title'>Ủng hộ dự án</div>")
                        gr.Markdown("TTS Studio đang chạy local trên máy của bạn. Phần Donate được giữ riêng để sau này thêm QR, link hoặc ghi chú ủng hộ mà không ảnh hưởng luồng TTS.")
                        gr.Textbox(label="Ghi chú donate", value="Cảm ơn bạn đã dùng và phát triển bộ công cụ TTS local.", lines=3)

                with gr.Column(visible=False, elem_classes=["page-block"]) as config_page:
                    gr.HTML("<div class='page-title'><h1>Cài đặt</h1></div>")
                    with gr.Group(elem_classes=["section-card"]):
                        gr.HTML("<div class='section-title'>Kiểm tra hệ thống</div>")
                        btn_config_scan = gr.Button("Kiểm tra cấu hình", variant="primary", elem_classes=["primary-dark"])
                        config_table = gr.Dataframe(headers=["Hạng mục", "Đường dẫn", "Trạng thái", "Thư mục"], value=[], interactive=False, wrap=True)
                        config_status = gr.Textbox(label="Trạng thái cài đặt", interactive=False, lines=4)

        page_outputs = [overview_page, create_page, google_page, library_page, settings_page, donate_page, config_page]
        nav.change(fn=switch_page, inputs=[nav], outputs=page_outputs, queue=False)
        btn_start_create.click(fn=switch_to_create_page, outputs=[nav, *page_outputs], queue=False)
        btn_scan_system.click(
            fn=scan_system_profile,
            outputs=[system_table, system_recommendation, overview_model_choice, overview_model_paths],
        )

        model_manager_outputs = [
            overview_model_paths,
            overview_model_status,
            engine,
            voice,
            ref_audio,
            emotion,
            temperature,
            status,
        ]
        btn_download_recommended.click(
            fn=download_selected_model,
            inputs=[overview_model_choice, overview_model_root],
            outputs=model_manager_outputs,
        )
        btn_download_all_models.click(
            fn=download_all_models,
            inputs=[overview_model_choice, overview_model_root],
            outputs=model_manager_outputs,
        )
        btn_load_overview_model.click(
            fn=load_selected_model_from_overview,
            inputs=[overview_model_choice, overview_model_root],
            outputs=model_manager_outputs,
        )
        btn_open_model_root.click(fn=open_model_root, inputs=[overview_model_root], outputs=[overview_model_status])

        btn_google_save_settings.click(
            fn=save_google_private_settings,
            inputs=[google_credential_path, google_language, google_voice, google_ai_model, google_max_chars],
            outputs=[google_status],
        )
        btn_google_load_voices.click(
            fn=refresh_google_voices_ui,
            inputs=[google_credential_path, google_language, google_voice],
            outputs=[google_voice, google_voice_table, google_status],
        )
        btn_google_generate.click(
            fn=generate_google_direct_tts,
            inputs=[
                google_content,
                google_credential_path,
                google_language,
                google_voice,
                google_ai_model,
                google_style,
                google_speed,
                google_pitch,
                google_max_chars,
                google_clean_enabled,
            ],
            outputs=[google_audio, google_cleaned_preview, google_details, google_status],
        )
        btn_google_clear.click(
            fn=clear_google_text,
            outputs=[google_content, google_cleaned_preview, google_audio, google_details, google_status],
        )
        btn_google_open_output.click(fn=open_google_output_dir, outputs=[google_status])
        btn_google_clear_cache.click(fn=clear_google_cache_ui, outputs=[google_status])

        create_mode.change(fn=switch_create_mode, inputs=[create_mode], outputs=[tts_mode_panel, clone_mode_panel], queue=False)
        content.change(fn=lambda value: _char_meter(value), inputs=[content], outputs=[char_meter])
        engine.change(fn=on_engine_change, inputs=[engine], outputs=[voice, ref_audio, emotion, temperature, status])
        btn_load.click(fn=on_engine_change, inputs=[engine], outputs=[voice, ref_audio, emotion, temperature, status])
        preset.change(fn=apply_preset, inputs=[preset], outputs=[speed, pitch, volume, emotion, temperature, status])
        show_cleaned.change(fn=lambda enabled: gr.update(visible=enabled), inputs=[show_cleaned], outputs=[cleaned_preview])
        btn_clear_text.click(fn=clear_direct_text, outputs=[content, char_meter, cleaned_preview, status])

        direct_inputs = [
            content,
            engine,
            voice,
            preset,
            speed,
            crossfade,
            emotion,
            temperature,
            pitch,
            volume,
            device_mode,
            ref_audio,
            clean_enabled,
        ]
        btn_generate_direct.click(fn=generate_direct_tts, inputs=direct_inputs, outputs=[audio, cleaned_preview, details, status])
        btn_regenerate_direct.click(fn=generate_direct_tts, inputs=direct_inputs, outputs=[audio, cleaned_preview, details, status])
        btn_open_direct.click(fn=open_direct_audio, inputs=[audio], outputs=[status])
        btn_refresh_gpu.click(fn=refresh_gpu, outputs=[gpu_markdown, gpu_text])
        btn_unload.click(fn=unload_engine, outputs=[audio, details, status])

        clone_engine.change(fn=on_clone_engine_change, inputs=[clone_engine], outputs=[clone_source_voice, clone_ref_audio, clone_emotion, clone_temperature, clone_status])
        btn_clone_load.click(fn=on_clone_engine_change, inputs=[clone_engine], outputs=[clone_source_voice, clone_ref_audio, clone_emotion, clone_temperature, clone_status])
        btn_create_clone.click(
            fn=create_clone_profile_debug,
            inputs=[
                clone_engine,
                clone_name,
                clone_source_voice,
                clone_ref_audio,
                clone_text,
                clone_speed,
                clone_crossfade,
                clone_emotion,
                clone_temperature,
                clone_volume,
                clone_normalize,
                clone_device,
                engine,
            ],
            outputs=[clone_audio, clone_status, library_table, library_status, voice],
        )
        btn_open_clone_dir.click(fn=lambda: open_local_folder(str(USER_VOICE_DIR)), outputs=[clone_status])
        btn_refresh_library.click(fn=refresh_voice_library, outputs=[library_table, library_status])
        btn_open_voice_dir.click(fn=lambda: open_local_folder(str(USER_VOICE_DIR)), outputs=[library_status])

        btn_open_outputs.click(fn=lambda: open_local_folder(str(OUTPUT_DIR)), outputs=[settings_status])
        btn_open_logs.click(fn=lambda: open_local_folder(str(LOG_DIR)), outputs=[settings_status])
        btn_open_clones_settings.click(fn=lambda: open_local_folder(str(USER_VOICE_DIR)), outputs=[settings_status])
        btn_unload_settings.click(fn=lambda: manager.unload(), outputs=[settings_status])
        btn_check_runtime.click(fn=check_runtime_paths, outputs=[runtime_table, settings_status])
        btn_config_scan.click(fn=check_runtime_paths, outputs=[config_table, config_status])

        demo.load(fn=on_engine_change, inputs=[engine], outputs=[voice, ref_audio, emotion, temperature, status])
        demo.load(fn=on_clone_engine_change, inputs=[clone_engine], outputs=[clone_source_voice, clone_ref_audio, clone_emotion, clone_temperature, clone_status])
        demo.load(fn=voice_library_snapshot, outputs=[library_table, library_status], queue=False)
    return demo


def main() -> int:
    parser = argparse.ArgumentParser(description="TTS Studio unified Kokoro/VieNeu TTS UI")
    parser.add_argument("--server-name", default="127.0.0.1")
    parser.add_argument("--server-port", type=int, default=7870)
    parser.add_argument("--share", action="store_true")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    demo = build_demo()
    demo.queue(default_concurrency_limit=1).launch(
        server_name=args.server_name,
        server_port=args.server_port,
        share=args.share,
        css=APP_CSS,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        manager.unload()
