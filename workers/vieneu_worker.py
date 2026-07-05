from __future__ import annotations

import gc
import importlib.resources as resources
import json
import os
import sys
import traceback
import unicodedata
from pathlib import Path
from typing import Any


VIENEU_ROOT = Path(os.environ.get("TTS_STUDIO_VIENEU_CODE_ROOT") or r"E:\TTS\VieNeu-TTS")
VIENEU_SRC = VIENEU_ROOT / "src"
VIENEU_ASSETS = VIENEU_SRC / "vieneu" / "assets"
VIENEU_VOICES = VIENEU_ASSETS / "voices_v3_turbo.json"
VIENEU_MODEL_ROOT = os.environ.get("TTS_STUDIO_VIENEU_MODEL_ROOT") or ""

for path in (VIENEU_SRC, VIENEU_ROOT):
    if path.exists() and str(path) not in sys.path:
        sys.path.insert(0, str(path))

_tts = None
_runtime_note = ""


FALLBACK_VOICES = {
    "default_voice": "Ngọc Lan",
    "presets": {
        "Bình An": {"description": "nam, giọng điềm đạm"},
        "Gia Bảo": {"description": "nam, giọng mượt mà"},
        "Mỹ Duyên": {"description": "nữ, giọng mượt mà"},
        "Ngọc Lan": {"description": "nữ, giọng dịu dàng"},
        "Ngọc Linh": {"description": "nữ, giọng tươi sáng"},
        "Thái Sơn": {"description": "nam, giọng chắc khỏe"},
        "Trúc Ly": {"description": "nữ, giọng trẻ trung"},
        "Trọng Hữu": {"description": "nam, giọng uyên bác"},
        "Xuân Vĩnh": {"description": "nam, giọng vui tươi"},
        "Đức Trí": {"description": "nam, giọng rõ ràng"},
    },
}


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
    global _tts
    try:
        if _tts is not None and hasattr(_tts, "close"):
            _tts.close()
    except Exception:
        pass
    _tts = None
    gc.collect()
    _empty_cuda_cache()


def _load_voices_data() -> dict[str, Any]:
    if VIENEU_VOICES.exists():
        return json.loads(VIENEU_VOICES.read_text(encoding="utf-8"))
    try:
        package_file = resources.files("vieneu").joinpath("assets", "voices_v3_turbo.json")
        return json.loads(package_file.read_text(encoding="utf-8"))
    except Exception:
        return FALLBACK_VOICES


def _ensure_model(device: str) -> None:
    global _tts, _runtime_note
    if _tts is not None:
        return

    from vieneu import Vieneu

    kwargs: dict[str, Any] = {
        "mode": "v3turbo",
        "device": device,
        "backend": "pytorch" if device == "cuda" else "onnx",
    }
    if VIENEU_MODEL_ROOT:
        model_root = Path(VIENEU_MODEL_ROOT)
        if model_root.is_dir() and any(model_root.iterdir()):
            kwargs["backbone_repo"] = str(model_root)
            for onnx_name in ("onnx_update", "onnx"):
                onnx_dir = model_root / onnx_name
                if (onnx_dir / "config.json").exists() and (onnx_dir / "tokenizer.json").exists():
                    kwargs["onnx_dir"] = str(onnx_dir)
                    kwargs["onnx_subfolder"] = onnx_name
                    break

    try:
        _tts = Vieneu(**kwargs)
        _runtime_note = ""
    except Exception as exc:
        if device != "cuda":
            raise
        fallback_kwargs = dict(kwargs)
        fallback_kwargs["device"] = "cpu"
        fallback_kwargs["backend"] = "onnx"
        _tts = Vieneu(**fallback_kwargs)
        _runtime_note = f"GPU runtime unavailable; fell back to CPU/ONNX. Original error: {exc}"


def list_voices(request_id: str | None) -> dict[str, Any]:
    default_voice = None
    voices: list[dict[str, str]] = []
    try:
        data = _load_voices_data()
        default_voice = data.get("default_voice")
        for name, info in sorted((data.get("presets") or {}).items()):
            desc = str(info.get("description") or "").strip()
            label = f"{name} - {desc}" if desc else name
            voices.append({"id": name, "label": label})
    except Exception as exc:
        return _error(request_id, f"Could not read VieNeu voices: {exc}", exc)

    return {
        "id": request_id,
        "ok": True,
        "voices": voices,
        "default_voice": default_voice,
        "sample_rate": 48000,
        "status": "VieNeu worker ready.",
    }


def encode_reference(request_id: str | None, payload: dict[str, Any]) -> dict[str, Any]:
    ref_audio = payload.get("ref_audio") or None
    if not ref_audio:
        return _error(request_id, "Missing ref_audio.")

    ref_path = Path(str(ref_audio)).expanduser()
    if not ref_path.exists():
        return _error(request_id, f"Reference audio not found: {ref_path}")

    output_path = Path(str(payload.get("output_path") or "")).expanduser()
    if not output_path:
        return _error(request_id, "Missing output_path.")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    device = str(payload.get("device") or "cuda")
    try:
        _ensure_model(device)
        assert _tts is not None

        import numpy as np

        codes = _tts.encode_reference(str(ref_path))
        np.save(str(output_path), codes)
        return {
            "id": request_id,
            "ok": True,
            "codes_path": str(output_path),
            "codes_shape": list(codes.shape),
            "sample_rate": int(getattr(_tts, "sample_rate", 48000)),
            "status": f"Encoded reference voice: {ref_path.name}",
            "details": "; ".join(
                part
                for part in (
                    f"backend={getattr(_tts, 'backend', 'unknown')}, codes_shape={tuple(codes.shape)}",
                    _runtime_note,
                )
                if part
            ),
        }
    except Exception as exc:
        return _error(request_id, f"VieNeu reference encode error: {exc}", exc)


def synthesize(request_id: str | None, payload: dict[str, Any]) -> dict[str, Any]:
    text = str(payload.get("text") or "").strip()
    if not text:
        return _error(request_id, "Text is empty.")

    output_path = Path(str(payload.get("output_path") or "")).expanduser()
    if not output_path:
        return _error(request_id, "Missing output_path.")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    device = str(payload.get("device") or "cuda")
    voice = payload.get("voice") or None
    if isinstance(voice, str):
        voice = unicodedata.normalize("NFC", voice)
    emotion = unicodedata.normalize("NFC", str(payload.get("emotion") or "natural"))
    temperature = float(payload.get("temperature") or 0.8)
    ref_audio = payload.get("ref_audio") or None
    ref_codes_path = payload.get("ref_codes_path") or None
    volume = float(payload.get("volume") or 1.0)
    normalize_audio = bool(payload.get("normalize_audio"))

    try:
        _ensure_model(device)
        assert _tts is not None

        infer_kwargs: dict[str, Any] = {
            "text": text,
            "emotion": emotion,
            "temperature": temperature,
            "apply_watermark": False,
        }

        if ref_codes_path:
            import numpy as np

            codes_path = Path(str(ref_codes_path)).expanduser()
            if not codes_path.exists():
                return _error(request_id, f"Reference codes not found: {codes_path}")
            infer_kwargs["ref_codes"] = np.load(str(codes_path), allow_pickle=False)
        elif ref_audio:
            infer_kwargs["ref_audio"] = str(ref_audio)
        elif voice:
            infer_kwargs["voice"] = str(voice)

        audio = _tts.infer(**infer_kwargs)
        if len(audio) == 0:
            return _error(request_id, "VieNeu generated empty audio.")

        if normalize_audio:
            import numpy as np

            peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
            if peak > 0:
                audio = audio * (0.95 / peak)
        if volume != 1.0:
            import numpy as np

            audio = np.clip(audio * volume, -1.0, 1.0)

        _tts.save(audio, output_path)
        return {
            "id": request_id,
            "ok": True,
            "audio_path": str(output_path),
            "sample_rate": int(getattr(_tts, "sample_rate", 48000)),
            "status": f"VieNeu generated audio with voice '{voice or 'default'}'.",
            "details": "; ".join(
                part
                for part in (
                    f"backend={getattr(_tts, 'backend', 'unknown')}, emotion={emotion}, temperature={temperature}",
                    _runtime_note,
                )
                if part
            ),
        }
    except Exception as exc:
        return _error(request_id, f"VieNeu error: {exc}", exc)


def handle(message: dict[str, Any]) -> dict[str, Any]:
    request_id = message.get("id")
    command = message.get("command")
    payload = message.get("payload") or {}

    try:
        if command == "list_voices":
            return list_voices(request_id)
        if command == "encode_reference":
            return encode_reference(request_id, payload)
        if command == "synthesize":
            return synthesize(request_id, payload)
        if command == "shutdown":
            _unload()
            return {
                "id": request_id,
                "ok": True,
                "status": "VieNeu worker stopped.",
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
