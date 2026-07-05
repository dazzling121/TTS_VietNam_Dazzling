from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field


@dataclass
class TtsCleanResult:
    original: str
    cleaned: str
    warnings: list[str] = field(default_factory=list)
    transformations: list[str] = field(default_factory=list)


_DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
_SCALES = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ", "triệu tỷ"]
_MONTHS = {
    1: "tháng một",
    2: "tháng hai",
    3: "tháng ba",
    4: "tháng tư",
    5: "tháng năm",
    6: "tháng sáu",
    7: "tháng bảy",
    8: "tháng tám",
    9: "tháng chín",
    10: "tháng mười",
    11: "tháng mười một",
    12: "tháng mười hai",
}
_ABBREVIATIONS = {
    "TP.HCM": "thành phố hồ chí minh",
    "TP HCM": "thành phố hồ chí minh",
    "TPHCM": "thành phố hồ chí minh",
    "HN": "hà nội",
    "VN": "việt nam",
    "VND": "việt nam đồng",
    "USD": "đô la Mỹ",
    "AI": "trí tuệ nhân tạo",
    "TTS": "tê tê ét",
    "GPU": "gi pi diu",
    "CPU": "xi pi diu",
    "RAM": "ram",
    "VRAM": "vê ram",
    "API": "ây pi ai",
    "URL": "đường dẫn",
}
_UNITS = {
    "kg": "ki lô gam",
    "g": "gam",
    "km": "ki lô mét",
    "m": "mét",
    "cm": "xen ti mét",
    "mm": "mi li mét",
    "gb": "ghi ga bai",
    "mb": "mê ga bai",
    "kb": "ki lô bai",
    "hz": "héc",
    "khz": "ki lô héc",
    "mhz": "mê ga héc",
    "ghz": "ghi ga héc",
    "w": "oát",
    "kw": "ki lô oát",
}
_CURRENCY_UNITS = {
    "đ": "đồng",
    "₫": "đồng",
    "đồng": "đồng",
    "dong": "đồng",
    "vnd": "đồng",
    "usd": "đô la Mỹ",
    "$": "đô la Mỹ",
}

_TAG_RE = re.compile(r"<[^>]+>")
_TIMESTAMP_RE = re.compile(r"\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}\s*-->\s*\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}")
_URL_RE = re.compile(r"\b(?:https?://|www\.)\S+", flags=re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", flags=re.IGNORECASE)
_DATE_RE = re.compile(r"\b(?:(?:ngày|ngay)\s+)?(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", flags=re.IGNORECASE)
_TIME_RE = re.compile(r"\b(\d{1,2})[:h](\d{2})(?:[:](\d{2}))?\b", flags=re.IGNORECASE)
_CURRENCY_RE = re.compile(r"(?<!\w)([$]?)(\d[\d.,]*)(?:\s*)(đ|₫|đồng|dong|vnd|usd|\$)(?!\w)", flags=re.IGNORECASE)
_PERCENT_RE = re.compile(r"(?<!\w)(\d[\d.,]*)\s*%")
_UNIT_RE = re.compile(r"(?<!\w)(\d[\d.,]*)\s*(kg|km|cm|mm|gb|mb|kb|ghz|mhz|khz|hz|kw|g|m|w)\b", flags=re.IGNORECASE)
_NUMBER_RE = re.compile(r"(?<![\w/.-])\d[\d.,]*(?![\w/.-])")


def _spell_under_1000(number: int, force_hundreds: bool = False) -> str:
    if number <= 0:
        return "không" if not force_hundreds else "không trăm"

    hundreds = number // 100
    remainder = number % 100
    parts: list[str] = []

    if hundreds:
        parts.extend([_DIGITS[hundreds], "trăm"])
    elif force_hundreds and remainder:
        parts.extend(["không", "trăm"])

    tens = remainder // 10
    ones = remainder % 10
    if tens == 0:
        if ones:
            if hundreds or force_hundreds:
                parts.append("lẻ")
            parts.append(_DIGITS[ones])
    elif tens == 1:
        parts.append("mười")
        if ones == 5:
            parts.append("lăm")
        elif ones:
            parts.append(_DIGITS[ones])
    else:
        parts.extend([_DIGITS[tens], "mươi"])
        if ones == 1:
            parts.append("mốt")
        elif ones == 4:
            parts.append("tư")
        elif ones == 5:
            parts.append("lăm")
        elif ones:
            parts.append(_DIGITS[ones])

    return " ".join(parts)


def _spell_integer(number: int) -> str:
    if number == 0:
        return "không"
    if number < 0:
        return "âm " + _spell_integer(abs(number))

    groups: list[int] = []
    while number:
        groups.append(number % 1000)
        number //= 1000

    spoken: list[str] = []
    for index in range(len(groups) - 1, -1, -1):
        group = groups[index]
        if group == 0:
            continue
        force_hundreds = bool(spoken and group < 100)
        words = _spell_under_1000(group, force_hundreds=force_hundreds)
        scale = _SCALES[index] if index < len(_SCALES) else ""
        spoken.append(f"{words} {scale}".strip())
    return " ".join(spoken)


def _looks_like_thousand_number(value: str) -> bool:
    return bool(re.fullmatch(r"\d{1,3}([.,]\d{3})+", value))


def _spell_number_text(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if _looks_like_thousand_number(value):
        return _spell_integer(int(re.sub(r"[.,]", "", value)))
    if "," in value or "." in value:
        sep = "," if "," in value else "."
        left, right = value.split(sep, 1)
        if right and len(right) <= 3:
            left_words = _spell_integer(int(re.sub(r"\D", "", left) or "0"))
            right_words = " ".join(_DIGITS[int(ch)] for ch in right if ch.isdigit())
            return f"{left_words} phẩy {right_words}".strip()
    return _spell_integer(int(re.sub(r"\D", "", value) or "0"))


def _replace_with_log(pattern: re.Pattern[str], text: str, repl, log: list[str]) -> str:
    changed = False

    def _inner(match: re.Match[str]) -> str:
        nonlocal changed
        changed = True
        return repl(match)

    result = pattern.sub(_inner, text)
    if changed:
        log.append(pattern.pattern)
    return result


def _normalize_dates(text: str, transformations: list[str]) -> str:
    def repl(match: re.Match[str]) -> str:
        day = int(match.group(1))
        month = int(match.group(2))
        year_raw = match.group(3)
        year = int(year_raw) + 2000 if len(year_raw) == 2 else int(year_raw)
        month_words = _MONTHS.get(month, f"tháng {_spell_integer(month)}")
        return f"ngày {_spell_integer(day)} {month_words} năm {_spell_integer(year)}"

    return _replace_with_log(_DATE_RE, text, repl, transformations)


def _normalize_times(text: str, transformations: list[str]) -> str:
    def repl(match: re.Match[str]) -> str:
        hour = int(match.group(1))
        minute = int(match.group(2))
        second = int(match.group(3)) if match.group(3) else None
        spoken = f"{_spell_integer(hour)} giờ"
        if minute:
            spoken += f" {_spell_integer(minute)} phút"
        if second:
            spoken += f" {_spell_integer(second)} giây"
        return spoken

    return _replace_with_log(_TIME_RE, text, repl, transformations)


def _normalize_currency(text: str, transformations: list[str]) -> str:
    def repl(match: re.Match[str]) -> str:
        prefix = match.group(1)
        amount = match.group(2)
        suffix = (match.group(3) or prefix).lower()
        unit = _CURRENCY_UNITS.get(suffix, "đồng")
        return f"{_spell_number_text(amount)} {unit}"

    return _replace_with_log(_CURRENCY_RE, text, repl, transformations)


def _normalize_percent_units_numbers(text: str, transformations: list[str]) -> str:
    text = _replace_with_log(_PERCENT_RE, text, lambda m: f"{_spell_number_text(m.group(1))} phần trăm", transformations)
    text = _replace_with_log(
        _UNIT_RE,
        text,
        lambda m: f"{_spell_number_text(m.group(1))} {_UNITS.get(m.group(2).lower(), m.group(2))}",
        transformations,
    )
    return _replace_with_log(_NUMBER_RE, text, lambda m: _spell_number_text(m.group(0)), transformations)


def _normalize_abbreviations(text: str, transformations: list[str]) -> str:
    for source, target in sorted(_ABBREVIATIONS.items(), key=lambda item: len(item[0]), reverse=True):
        pattern = re.compile(rf"(?<!\w){re.escape(source)}(?!\w)", flags=re.IGNORECASE)
        if pattern.search(text):
            text = pattern.sub(target, text)
            transformations.append(f"abbrev:{source}")
    return text


def clean_text_for_tts(text: str) -> TtsCleanResult:
    original = text or ""
    warnings: list[str] = []
    transformations: list[str] = []

    cleaned = unicodedata.normalize("NFC", original)
    cleaned = html.unescape(cleaned)
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"[\u200b-\u200f\ufeff]", "", cleaned)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", cleaned)

    if _URL_RE.search(cleaned):
        warnings.append("Đã rút gọn URL thành 'đường dẫn'.")
        cleaned = _URL_RE.sub(" đường dẫn ", cleaned)
    if _EMAIL_RE.search(cleaned):
        warnings.append("Đã rút gọn email thành 'địa chỉ email'.")
        cleaned = _EMAIL_RE.sub(" địa chỉ email ", cleaned)

    lines: list[str] = []
    for raw_line in cleaned.split("\n"):
        line = _TAG_RE.sub("", raw_line).strip()
        if not line:
            continue
        if _TIMESTAMP_RE.search(line):
            transformations.append("subtitle_timestamp")
            continue
        if line.isdigit() and len(line) < 5:
            transformations.append("subtitle_index")
            continue
        lines.append(line)
    cleaned = "\n".join(lines)

    cleaned = _normalize_abbreviations(cleaned, transformations)
    cleaned = _normalize_dates(cleaned, transformations)
    cleaned = _normalize_times(cleaned, transformations)
    cleaned = _normalize_currency(cleaned, transformations)
    cleaned = _normalize_percent_units_numbers(cleaned, transformations)

    cleaned = cleaned.replace("“", '"').replace("”", '"').replace("’", "'")
    cleaned = re.sub(r"[•·●]", ". ", cleaned)
    cleaned = re.sub(r"[-–—]{2,}", ", ", cleaned)
    cleaned = re.sub(r"([!?]){2,}", r"\1", cleaned)
    cleaned = re.sub(r"\s+([,.!?;:])", r"\1", cleaned)
    cleaned = re.sub(r"([,.!?;:])(?=\S)", r"\1 ", cleaned)
    cleaned = re.sub(r"([!?])(?:\s*\1)+", r"\1", cleaned)
    cleaned = re.sub(r"\.{3,}", "…", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    if cleaned and cleaned[-1] not in ".!?…":
        cleaned += "."
        transformations.append("final_punctuation")
    if not cleaned:
        warnings.append("Văn bản trống sau khi làm sạch.")

    return TtsCleanResult(
        original=original,
        cleaned=cleaned,
        warnings=warnings,
        transformations=transformations,
    )
