from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GOOGLE_OUTPUT_DIR = ROOT / "outputs" / "google"
GOOGLE_CACHE_DIR = ROOT / "cache" / "google_tts"
GOOGLE_PRIVATE_DIR = ROOT / "private"
GOOGLE_SETTINGS_PATH = GOOGLE_PRIVATE_DIR / "google_tts_settings.json"
DEFAULT_PRIVATE_KEY_FILE = GOOGLE_PRIVATE_DIR / "google_tts_key.json"

DEFAULT_LANGUAGE_CODE = "vi-VN"
DEFAULT_CHUNK_CHAR_LIMIT = 2_000
AI_MODEL_CLOUD_VOICE = "cloud_voice"
AI_MODEL_CHOICES = [
    ("Cloud voice hiện tại", AI_MODEL_CLOUD_VOICE),
    ("Gemini 2.5 Flash TTS", "gemini-2.5-flash-tts"),
    ("Gemini 2.5 Flash Lite Preview", "gemini-2.5-flash-lite-preview-tts"),
    ("Gemini 2.5 Pro TTS", "gemini-2.5-pro-tts"),
    ("Gemini 3.1 Flash Preview", "gemini-3.1-flash-tts-preview"),
]

VOICE_TIER_STANDARD = "standard_wavenet"
VOICE_TIER_ADVANCED = "neural2_chirp_studio"
VOICE_TIER_LABELS = {
    VOICE_TIER_STANDARD: "Standard / WaveNet",
    VOICE_TIER_ADVANCED: "Neural2 / Chirp / Studio / Polyglot",
}

CHIRP3_CODE_NAMES = frozenset(
    {
        "achernar",
        "achird",
        "algenib",
        "algieba",
        "alnilam",
        "aoede",
        "autonoe",
        "betelgeuse",
        "callirrhoe",
        "charon",
        "despina",
        "enceladus",
        "erinome",
        "fenrir",
        "gacrux",
        "iapetus",
        "kore",
        "laomedeia",
        "leda",
        "orus",
        "puck",
        "pulcherrima",
        "rasalgethi",
        "rigel",
        "sadachbia",
        "sadaltager",
        "schedar",
        "sulafat",
        "umbriel",
        "vindemiatrix",
        "zephyr",
        "zubenelgenubi",
    }
)
PREMIUM_VOICE_KEYWORDS = frozenset({"neural2", "chirp", "studio", "polyglot"} | CHIRP3_CODE_NAMES)

FALLBACK_VOICES = [
    {
        "name": "vi-VN-Neural2-D",
        "language_codes": [DEFAULT_LANGUAGE_CODE],
        "gender": "MALE",
        "natural_sample_rate_hertz": 24000,
        "model_family": "Neural2",
    },
    {
        "name": "vi-VN-Neural2-A",
        "language_codes": [DEFAULT_LANGUAGE_CODE],
        "gender": "FEMALE",
        "natural_sample_rate_hertz": 24000,
        "model_family": "Neural2",
    },
    {
        "name": "vi-VN-Standard-A",
        "language_codes": [DEFAULT_LANGUAGE_CODE],
        "gender": "FEMALE",
        "natural_sample_rate_hertz": 24000,
        "model_family": "Standard",
    },
]


class GoogleTtsError(RuntimeError):
    pass


@dataclass(frozen=True)
class GoogleTtsResult:
    audio_path: Path
    cache_audio_path: Path
    from_cache: bool
    characters_billed: int
    total_characters: int
    chunk_count: int
    chunks_generated: int
    chunks_from_cache: int
    clean_text: str
    voice_name: str
    language_code: str
    ai_model: str
    style_applied: bool | None = None
    style_warning: str | None = None


def ensure_google_dirs() -> None:
    GOOGLE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    GOOGLE_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def clean_google_text(text: str) -> str:
    return " ".join((text or "").split())


def load_google_settings() -> dict[str, Any]:
    settings: dict[str, Any] = {
        "credential_path": "",
        "language_code": DEFAULT_LANGUAGE_CODE,
        "voice_name": FALLBACK_VOICES[0]["name"],
        "ai_model": AI_MODEL_CLOUD_VOICE,
        "max_chars_per_chunk": DEFAULT_CHUNK_CHAR_LIMIT,
    }
    if GOOGLE_SETTINGS_PATH.exists():
        try:
            saved = json.loads(GOOGLE_SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                for key in settings:
                    if key in saved:
                        settings[key] = saved[key]
        except Exception:
            pass
    if not settings.get("credential_path"):
        env_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
        if env_path:
            settings["credential_path"] = env_path
    return settings


def save_google_settings(
    credential_path: str,
    language_code: str,
    voice_name: str,
    ai_model: str,
    max_chars_per_chunk: int,
) -> Path:
    GOOGLE_PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    settings = {
        "credential_path": (credential_path or "").strip(),
        "language_code": (language_code or DEFAULT_LANGUAGE_CODE).strip() or DEFAULT_LANGUAGE_CODE,
        "voice_name": (voice_name or "").strip() or FALLBACK_VOICES[0]["name"],
        "ai_model": (ai_model or AI_MODEL_CLOUD_VOICE).strip() or AI_MODEL_CLOUD_VOICE,
        "max_chars_per_chunk": max(200, int(max_chars_per_chunk or DEFAULT_CHUNK_CHAR_LIMIT)),
    }
    GOOGLE_SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    return GOOGLE_SETTINGS_PATH


def credential_status(credential_path: str | os.PathLike[str] | None = None) -> str:
    selected = (str(credential_path or "").strip())
    if selected:
        path = _resolve_candidate_path(selected)
        if path.is_file():
            return f"Đã tìm thấy file key: {path}"
        return f"Chưa tìm thấy file key: {path}"
    env_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if env_path:
        path = _resolve_candidate_path(env_path)
        if path.is_file():
            return f"Đang dùng GOOGLE_APPLICATION_CREDENTIALS: {path}"
        return f"GOOGLE_APPLICATION_CREDENTIALS đang trỏ tới file không tồn tại: {path}"
    if DEFAULT_PRIVATE_KEY_FILE.is_file():
        return f"Đang dùng key riêng trong private: {DEFAULT_PRIVATE_KEY_FILE}"
    return "Chưa có key. Chọn file JSON service account hoặc đặt GOOGLE_APPLICATION_CREDENTIALS."


def _resolve_candidate_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path


def _resolve_credentials_file(credential_path: str | os.PathLike[str] | None = None) -> Path | None:
    selected = str(credential_path or "").strip()
    if selected:
        candidate = _resolve_candidate_path(selected)
        if candidate.is_file():
            return candidate.resolve()
        raise GoogleTtsError(f"Không tìm thấy file key Google: {candidate}")

    env_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if env_path:
        candidate = _resolve_candidate_path(env_path)
        if candidate.is_file():
            return candidate.resolve()
        raise GoogleTtsError(f"GOOGLE_APPLICATION_CREDENTIALS trỏ tới file không tồn tại: {candidate}")

    if DEFAULT_PRIVATE_KEY_FILE.is_file():
        return DEFAULT_PRIVATE_KEY_FILE.resolve()
    return None


def _load_texttospeech_module() -> Any:
    try:
        from google.cloud import texttospeech_v1beta1 as texttospeech
    except ImportError as exc:
        raise GoogleTtsError(
            "Thiếu thư viện google-cloud-texttospeech. Hãy chạy lại START_HERE hoặc cài: "
            "pip install google-cloud-texttospeech"
        ) from exc
    return texttospeech


def _create_client(credential_path: str | os.PathLike[str] | None = None) -> tuple[Any, Any]:
    texttospeech = _load_texttospeech_module()
    key_file = _resolve_credentials_file(credential_path)
    try:
        if key_file:
            from google.oauth2 import service_account

            credentials = service_account.Credentials.from_service_account_file(str(key_file))
            if getattr(credentials, "requires_scopes", False):
                credentials = credentials.with_scopes(["https://www.googleapis.com/auth/cloud-platform"])
            return texttospeech, texttospeech.TextToSpeechClient(credentials=credentials)
        return texttospeech, texttospeech.TextToSpeechClient()
    except Exception as exc:
        raise GoogleTtsError(
            "Không tạo được Google Text-to-Speech client. Kiểm tra file key, quyền service account, "
            f"API Text-to-Speech và billing. Chi tiết: {exc}"
        ) from exc


def infer_model_family(voice_name: str) -> str:
    voice_lower = voice_name.lower()
    if "chirp3" in voice_lower or "chirp" in voice_lower:
        return "Chirp"
    if "neural2" in voice_lower:
        return "Neural2"
    if "studio" in voice_lower:
        return "Studio"
    if "wavenet" in voice_lower:
        return "WaveNet"
    if "standard" in voice_lower:
        return "Standard"
    return "Google"


def get_voice_tier(voice_name: str) -> str:
    voice_lower = (voice_name or "").lower()
    if any(keyword in voice_lower for keyword in PREMIUM_VOICE_KEYWORDS):
        return VOICE_TIER_ADVANCED
    return VOICE_TIER_STANDARD


def _voice_gender_name(texttospeech: Any, gender_value: Any) -> str:
    try:
        return texttospeech.SsmlVoiceGender(gender_value).name
    except Exception:
        return str(gender_value or "UNKNOWN")


def fetch_google_voices(
    credential_path: str | os.PathLike[str] | None = None,
    language_code: str = DEFAULT_LANGUAGE_CODE,
) -> list[dict[str, Any]]:
    texttospeech, client = _create_client(credential_path)
    normalized_language = (language_code or DEFAULT_LANGUAGE_CODE).strip() or DEFAULT_LANGUAGE_CODE
    try:
        response = client.list_voices(request={"language_code": normalized_language})
    except Exception as exc:
        raise GoogleTtsError(f"Không tải được danh sách voice Google: {exc}") from exc

    voices: list[dict[str, Any]] = []
    for voice in response.voices:
        voices.append(
            {
                "name": voice.name,
                "language_codes": list(voice.language_codes),
                "gender": _voice_gender_name(texttospeech, voice.ssml_gender),
                "natural_sample_rate_hertz": int(voice.natural_sample_rate_hertz or 0),
                "model_family": infer_model_family(voice.name),
            }
        )
    return sorted(voices, key=lambda item: item["name"])


def voice_table_rows(voices: list[dict[str, Any]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for voice in voices:
        name = str(voice.get("name") or "")
        rows.append(
            [
                name,
                ", ".join(str(code) for code in voice.get("language_codes", [])),
                str(voice.get("gender") or "UNKNOWN"),
                str(voice.get("model_family") or infer_model_family(name)),
                f"{int(voice.get('natural_sample_rate_hertz') or 0):,} Hz",
                VOICE_TIER_LABELS[get_voice_tier(name)],
            ]
        )
    return rows


def voice_choice_label(voice: dict[str, Any]) -> str:
    name = str(voice.get("name") or "")
    gender = str(voice.get("gender") or "UNKNOWN")
    family = str(voice.get("model_family") or infer_model_family(name))
    sample_rate = int(voice.get("natural_sample_rate_hertz") or 0)
    suffix = f" - {gender} - {family}"
    if sample_rate:
        suffix += f" - {sample_rate:,} Hz"
    return f"{name}{suffix}"


def voice_choices(voices: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [(voice_choice_label(voice), str(voice.get("name") or "")) for voice in voices if voice.get("name")]


def normalize_ai_model(ai_model: str | None = None) -> str:
    normalized = clean_google_text(ai_model or "")
    if not normalized or normalized == AI_MODEL_CLOUD_VOICE:
        return AI_MODEL_CLOUD_VOICE
    return normalized


def is_gemini_model(ai_model: str | None = None) -> bool:
    return normalize_ai_model(ai_model).startswith("gemini-")


def gemini_speaker_from_voice_name(voice_name: str) -> str:
    parts = [part for part in voice_name.split("-") if part]
    candidate = parts[-1] if parts else voice_name
    if candidate.lower() in CHIRP3_CODE_NAMES:
        return candidate
    if voice_name.lower() in CHIRP3_CODE_NAMES:
        return voice_name
    raise GoogleTtsError(
        "Gemini TTS cần voice Chirp3-HD có speaker như Aoede, Kore hoặc Achernar. "
        "Hãy chọn voice dạng vi-VN-Chirp3-HD-*."
    )


def split_text_into_chunks(text: str, max_chars: int = DEFAULT_CHUNK_CHAR_LIMIT) -> list[str]:
    normalized_text = clean_google_text(text)
    if not normalized_text:
        return []

    max_chars = max(int(max_chars or DEFAULT_CHUNK_CHAR_LIMIT), 200)
    if len(normalized_text) <= max_chars:
        return [normalized_text]

    sentence_parts = re.findall(r"[^.!?。！？]+[.!?。！？]*", normalized_text)
    if not sentence_parts:
        sentence_parts = [normalized_text]

    chunks: list[str] = []
    current = ""

    def flush_current() -> None:
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for raw_part in sentence_parts:
        sentence = raw_part.strip()
        if not sentence:
            continue

        while len(sentence) > max_chars:
            split_at = sentence.rfind(" ", 0, max_chars + 1)
            if split_at < max_chars // 2:
                split_at = max_chars
            part = sentence[:split_at].strip()
            sentence = sentence[split_at:].strip()

            if current and len(current) + len(part) + 1 > max_chars:
                flush_current()
            current = f"{current} {part}".strip()
            flush_current()

        if current and len(current) + len(sentence) + 1 > max_chars:
            flush_current()
        current = f"{current} {sentence}".strip()

    flush_current()
    return chunks


def _make_cache_key(
    text: str,
    language_code: str,
    voice_name: str,
    speaking_rate: float,
    pitch: float,
    style_instructions: str,
    ai_model: str,
) -> str:
    payload = {
        "text": text,
        "language_code": language_code,
        "voice_name": voice_name,
        "speaking_rate": round(float(speaking_rate), 2),
        "pitch": round(float(pitch), 2),
        "style_instructions": style_instructions,
        "ai_model": normalize_ai_model(ai_model),
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _metadata_path(cache_key: str) -> Path:
    return GOOGLE_CACHE_DIR / f"{cache_key}.json"


def _load_metadata(cache_key: str) -> dict[str, Any]:
    path = _metadata_path(cache_key)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_metadata(cache_key: str, metadata: dict[str, Any]) -> None:
    _metadata_path(cache_key).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_filename(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_value = re.sub(r"[^A-Za-z0-9._-]+", "-", ascii_value).strip("-._")
    return ascii_value or "google-tts"


def _synthesize_audio_content(
    client: Any,
    texttospeech: Any,
    text: str,
    language_code: str,
    voice_name: str,
    speaking_rate: float,
    pitch: float,
    style_instructions: str,
    ai_model: str,
) -> tuple[bytes, bool, str | None]:
    normalized_style = clean_google_text(style_instructions)
    normalized_ai_model = normalize_ai_model(ai_model)
    gemini_mode = is_gemini_model(normalized_ai_model)
    effective_voice_name = gemini_speaker_from_voice_name(voice_name) if gemini_mode else voice_name
    style_warning: str | None = None

    synthesis_input = texttospeech.SynthesisInput(text=text)
    if normalized_style:
        if gemini_mode:
            try:
                synthesis_input = texttospeech.SynthesisInput(text=text, prompt=normalized_style)
            except Exception:
                style_warning = "Phiên bản thư viện hiện tại chưa hỗ trợ prompt cho Gemini TTS."
        else:
            style_warning = "Style Instructions chỉ áp dụng cho Gemini TTS; Cloud voice sẽ bỏ qua phần này."

    voice_kwargs: dict[str, Any] = {"language_code": language_code, "name": effective_voice_name}
    if gemini_mode:
        voice_kwargs["model_name"] = normalized_ai_model

    voice = texttospeech.VoiceSelectionParams(**voice_kwargs)
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=float(speaking_rate),
        pitch=float(pitch),
    )

    try:
        response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
        return response.audio_content, bool(normalized_style and gemini_mode and not style_warning), style_warning
    except Exception as exc:
        if normalized_style and gemini_mode:
            try:
                response = client.synthesize_speech(
                    input=texttospeech.SynthesisInput(text=text),
                    voice=voice,
                    audio_config=audio_config,
                )
                warning = (
                    "Google không nhận Style Instructions cho request này, app đã tạo audio bằng text thường. "
                    f"Chi tiết style lỗi: {exc}"
                )
                return response.audio_content, False, warning
            except Exception as fallback_exc:
                raise GoogleTtsError(
                    "Google TTS lỗi với Style Instructions và fallback text thường cũng lỗi. "
                    f"Chi tiết: {fallback_exc}"
                ) from fallback_exc
        raise GoogleTtsError(f"Google Text-to-Speech API lỗi: {exc}") from exc


def _copy_cache_to_output(cache_audio_path: Path, voice_name: str) -> Path:
    GOOGLE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_path = GOOGLE_OUTPUT_DIR / f"google-tts-{timestamp}-{_safe_filename(voice_name)}.mp3"
    shutil.copy2(cache_audio_path, output_path)
    return output_path


def generate_google_tts(
    text: str,
    language_code: str,
    voice_name: str,
    speaking_rate: float,
    pitch: float,
    credential_path: str | os.PathLike[str] | None = None,
    style_instructions: str = "",
    ai_model: str | None = None,
    max_chars_per_chunk: int = DEFAULT_CHUNK_CHAR_LIMIT,
) -> GoogleTtsResult:
    ensure_google_dirs()
    normalized_text = clean_google_text(text)
    normalized_style = clean_google_text(style_instructions)
    normalized_language = (language_code or DEFAULT_LANGUAGE_CODE).strip() or DEFAULT_LANGUAGE_CODE
    normalized_voice = (voice_name or "").strip()
    normalized_ai_model = normalize_ai_model(ai_model)
    if not normalized_text:
        raise GoogleTtsError("Vui lòng nhập văn bản trước khi tạo audio.")
    if not normalized_voice:
        raise GoogleTtsError("Vui lòng chọn hoặc nhập tên voice Google.")

    final_cache_key = _make_cache_key(
        normalized_text,
        normalized_language,
        normalized_voice,
        speaking_rate,
        pitch,
        normalized_style,
        normalized_ai_model,
    )
    final_cache_audio = GOOGLE_CACHE_DIR / f"{final_cache_key}.mp3"
    if final_cache_audio.exists():
        metadata = _load_metadata(final_cache_key)
        output_path = _copy_cache_to_output(final_cache_audio, normalized_voice)
        return GoogleTtsResult(
            audio_path=output_path,
            cache_audio_path=final_cache_audio,
            from_cache=True,
            characters_billed=0,
            total_characters=int(metadata.get("total_characters", len(normalized_text))),
            chunk_count=int(metadata.get("chunk_count", 1)),
            chunks_generated=0,
            chunks_from_cache=int(metadata.get("chunk_count", 1)),
            clean_text=normalized_text,
            voice_name=normalized_voice,
            language_code=normalized_language,
            ai_model=normalized_ai_model,
            style_applied=metadata.get("style_applied"),
            style_warning=metadata.get("style_warning"),
        )

    chunks = split_text_into_chunks(normalized_text, max_chars_per_chunk)
    if not chunks:
        raise GoogleTtsError("Vui lòng nhập văn bản trước khi tạo audio.")

    texttospeech, client = _create_client(credential_path)
    chunk_files: list[Path] = []
    characters_billed = 0
    chunks_generated = 0
    chunks_from_cache = 0
    style_warning: str | None = None
    style_applied_values: list[bool] = []

    for chunk in chunks:
        chunk_cache_key = _make_cache_key(
            chunk,
            normalized_language,
            normalized_voice,
            speaking_rate,
            pitch,
            normalized_style,
            normalized_ai_model,
        )
        chunk_metadata_key = f"sub_{chunk_cache_key}"
        chunk_path = GOOGLE_CACHE_DIR / f"{chunk_metadata_key}.mp3"

        if chunk_path.exists():
            chunks_from_cache += 1
            metadata = _load_metadata(chunk_metadata_key)
            if metadata.get("style_warning") and not style_warning:
                style_warning = str(metadata["style_warning"])
            if metadata.get("style_applied") is not None:
                style_applied_values.append(bool(metadata["style_applied"]))
            chunk_files.append(chunk_path)
            continue

        audio_content, chunk_style_applied, chunk_style_warning = _synthesize_audio_content(
            client=client,
            texttospeech=texttospeech,
            text=chunk,
            language_code=normalized_language,
            voice_name=normalized_voice,
            speaking_rate=speaking_rate,
            pitch=pitch,
            style_instructions=normalized_style,
            ai_model=normalized_ai_model,
        )
        chunk_path.write_bytes(audio_content)
        _save_metadata(
            chunk_metadata_key,
            {
                "language_code": normalized_language,
                "voice_name": normalized_voice,
                "ai_model": normalized_ai_model,
                "voice_tier": get_voice_tier(normalized_voice),
                "speaking_rate": float(speaking_rate),
                "pitch": float(pitch),
                "characters_billed": len(chunk),
                "total_characters": len(chunk),
                "style_instructions": normalized_style,
                "style_applied": chunk_style_applied,
                "style_warning": chunk_style_warning,
            },
        )
        chunk_files.append(chunk_path)
        characters_billed += len(chunk)
        chunks_generated += 1
        style_applied_values.append(chunk_style_applied)
        if chunk_style_warning and not style_warning:
            style_warning = chunk_style_warning

    with final_cache_audio.open("wb") as final_file:
        for chunk_path in chunk_files:
            final_file.write(chunk_path.read_bytes())

    style_applied: bool | None
    if normalized_style:
        style_applied = bool(style_applied_values) and all(style_applied_values)
    else:
        style_applied = False

    _save_metadata(
        final_cache_key,
        {
            "language_code": normalized_language,
            "voice_name": normalized_voice,
            "ai_model": normalized_ai_model,
            "voice_tier": get_voice_tier(normalized_voice),
            "speaking_rate": float(speaking_rate),
            "pitch": float(pitch),
            "characters_billed": characters_billed,
            "total_characters": len(normalized_text),
            "chunk_count": len(chunks),
            "chunks_generated": chunks_generated,
            "chunks_from_cache": chunks_from_cache,
            "style_instructions": normalized_style,
            "style_applied": style_applied,
            "style_warning": style_warning,
        },
    )
    output_path = _copy_cache_to_output(final_cache_audio, normalized_voice)
    return GoogleTtsResult(
        audio_path=output_path,
        cache_audio_path=final_cache_audio,
        from_cache=False,
        characters_billed=characters_billed,
        total_characters=len(normalized_text),
        chunk_count=len(chunks),
        chunks_generated=chunks_generated,
        chunks_from_cache=chunks_from_cache,
        clean_text=normalized_text,
        voice_name=normalized_voice,
        language_code=normalized_language,
        ai_model=normalized_ai_model,
        style_applied=style_applied,
        style_warning=style_warning,
    )


def clear_google_cache() -> int:
    if not GOOGLE_CACHE_DIR.exists():
        return 0
    removed = 0
    for path in list(GOOGLE_CACHE_DIR.glob("*.mp3")) + list(GOOGLE_CACHE_DIR.glob("*.json")):
        try:
            path.unlink()
            removed += 1
        except Exception:
            pass
    return removed
