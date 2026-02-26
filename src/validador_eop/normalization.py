from __future__ import annotations

import re
import unicodedata


EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def normalize_key(value: str | None) -> str:
    if value is None:
        return ""
    cleaned = " ".join(str(value).strip().split())
    cleaned = strip_accents(cleaned)
    return cleaned.upper()


def normalize_email(value: str | None) -> str:
    return normalize_key(value).lower()


def is_valid_email(value: str | None) -> bool:
    if value is None:
        return False
    return bool(EMAIL_REGEX.match(value.strip()))


def normalize_state(value: str | None) -> str:
    text = normalize_key(value)
    if text in {"", "ACTIVO", "ACTIVE", "1"}:
        return "ACTIVO"
    if text in {"INACTIVO", "NO ACTIVO", "0", "INACTIVE"}:
        return "INACTIVO"
    return text
