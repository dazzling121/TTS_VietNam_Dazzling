from __future__ import annotations

import gc
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any


KOKORO_CODE_ROOT = Path(os.environ.get("TTS_STUDIO_KOKORO_CODE_ROOT") or r"E:\Kokoro\Kokoro-Vietnamese-code\src")
KOKORO_MODEL_ROOT = Path(os.environ.get("TTS_STUDIO_KOKORO_MODEL_ROOT", r"E:\Kokoro\Kokoro-Vietnamese"))
KOKORO_MODEL = KOKORO_MODEL_ROOT / "kokoro_vi.pth"
KOKORO_CONFIG = KOKORO_MODEL_ROOT / "config.json"

if KOKORO_CODE_ROOT.exists() and str(KOKORO_CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(KOKORO_CODE_ROOT))

_tts = None
_loaded_voice: str | None = None
_runtime_note = ""


def _send(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _error(request_id: str | None, message: str, exc: BaseException | None = None) -> dict[str, Any]:
    details = traceback.format_exc(limit=8) if exc else ""
    return {
        "id": request_id,
        "ok": False,
        "status": message,
        "details": details,
    }


def _empty_cuda_cache() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _unload() -> None:
    global _tts, _loaded_voice
    _tts = None
    _loaded_voice = None
    gc.collect()
    _empty_cuda_cache()


def _voicepack_path(voice: str) -> Path:
    from kokoro_vietnamese.core import VOICES

    return KOKORO_MODEL_ROOT / VOICES[voice]["filename"]


def _ensure_model(voice: str, device: str) -> None:
    global _tts, _loaded_voice, _runtime_note
    if _tts is not None and _loaded_voice == voice:
        return

    _unload()

    from kokoro_vietnamese import KokoroVietnamese

    kwargs = {
        "device": device,
        "voice": voice,
        "model_path": str(KOKORO_MODEL),
        "voicepack_path": str(_voicepack_path(voice)),
        "config_path": str(KOKORO_CONFIG),
    }
    try:
        _tts = KokoroVietnamese(**kwargs)
        _runtime_note = ""
    except Exception as exc:
        if device != "cuda":
            raise
        kwargs["device"] = "cpu"
        _tts = KokoroVietnamese(**kwargs)
        _runtime_note = f"GPU runtime unavailable; fell back to CPU. Original error: {exc}"
    _loaded_voice = voice


def list_voices(request_id: str | None) -> dict[str, Any]:
    from kokoro_vietnamese.core import DEFAULT_VOICE, VOICES

    voices = [
        {
            "id": name,
            "label": str(info.get("label") or name),
        }
        for name, info in sorted(VOICES.items())
    ]
    return {
        "id": request_id,
        "ok": True,
        "voices": voices,
        "default_voice": DEFAULT_VOICE,
        "sample_rate": 24000,
        "status": "Kokoro worker ready.",
    }


def synthesize(request_id: str | None, payload: dict[str, Any]) -> dict[str, Any]:
    text = str(payload.get("text") or "").strip()
    if not text:
        return _error(request_id, "Text is empty.")

    voice = str(payload.get("voice") or "diem_trinh")
    device = str(payload.get("device") or "cuda")
    output_path = Path(str(payload.get("output_path") or "")).expanduser()
    if not output_path:
        return _error(request_id, "Missing output_path.")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    speed = float(payload.get("speed") or 1.0)
    crossfade_ms = int(float(payload.get("crossfade_ms") or 50))
    volume = float(payload.get("volume") or 1.0)
    normalize_audio = bool(payload.get("normalize_audio"))

    try:
        _ensure_model(voice, device)
        assert _tts is not None
        audio, phonemes = _tts.synthesize(
            text,
            speed=speed,
            crossfade_ms=crossfade_ms,
        )
        if len(audio) == 0:
            return _error(request_id, "Kokoro generated empty audio.")

        if normalize_audio:
            import numpy as np

            peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
            if peak > 0:
                audio = audio * (0.95 / peak)
        if volume != 1.0:
            import numpy as np

            audio = np.clip(audio * volume, -1.0, 1.0)

        import soundfile as sf
        from kokoro_vietnamese.core import SAMPLE_RATE

        sf.write(str(output_path), audio, SAMPLE_RATE)
        return {
            "id": request_id,
            "ok": True,
            "audio_path": str(output_path),
            "sample_rate": SAMPLE_RATE,
            "status": f"Kokoro generated audio with voice '{voice}'.",
            "details": "\n".join(part for part in (phonemes, _runtime_note) if part),
        }
    except Exception as exc:
        return _error(request_id, f"Kokoro error: {exc}", exc)


def handle(message: dict[str, Any]) -> dict[str, Any]:
    request_id = message.get("id")
    command = message.get("command")
    payload = message.get("payload") or {}

    try:
        if command == "list_voices":
            return list_voices(request_id)
        if command == "synthesize":
            return synthesize(request_id, payload)
        if command == "shutdown":
            _unload()
            return {
                "id": request_id,
                "ok": True,
                "status": "Kokoro worker stopped.",
                "details": "",
            }
        return _error(request_id, f"Unknown command: {command}")
    except Exception as exc:
        return _error(request_id, f"Worker error: {exc}", exc)


def main() -> int:
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            message = json.loads(raw)
        except json.JSONDecodeError as exc:
            _send(_error(None, f"Invalid JSON: {exc}", exc))
            continue

        response = handle(message)
        _send(response)
        if message.get("command") == "shutdown":
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
