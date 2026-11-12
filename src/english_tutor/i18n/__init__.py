"""Interface language: text lookup, regional date/time formats, status translation.

Pure and stdlib-only. The language is process-wide and set once at start-up
(``set_language``). Report text, error details and conversation logs are never
translated; the tutor itself always speaks English.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time

from . import en, es

_CATALOGS: dict[str, dict[str, str]] = {"en": en.STRINGS, "es": es.STRINGS}
_MONTHS: dict[str, tuple[str, ...]] = {
    "en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
    "es": ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"),
}
_STATUS_EXACT: dict[str, str] = {
    "Initializing...": "status.initializing",
    "Ready": "status.ready",
    "Loading speech model...": "status.loading",
    "Listening...": "status.listening",
    "Transcribing...": "status.transcribing",
    "Thinking...": "status.thinking",
    "Speaking...": "status.speaking",
    "Preparing practice...": "status.preparing_practice",
    "Checking your answer...": "status.checking_answer",
    "Writing feedback...": "status.writing_feedback",
    "Too short or too quiet, try again": "status.too_short",
    "Didn't catch that, try again": "status.not_caught",
}
_STATUS_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^Ready: hold (?P<key>.+)$"), "status.ready_hold"),
    (re.compile(r"^Practice: hold (?P<key>.+) to answer$"), "status.practice_hold"),
)

_language = "en"


def set_language(language: str) -> None:
    """Choose the interface language; anything unsupported means English."""
    global _language
    _language = language if language in _CATALOGS else "en"


def current_language() -> str:
    """The active language code (``en`` or ``es``)."""
    return _language


def t(key: str, /, **values: object) -> str:
    """Look up ``key`` in the active language, then English, then return the key.

    ``values`` fill ``{placeholders}``; a missing value leaves the text as is.
    """
    text = _CATALOGS[_language].get(key) or en.STRINGS.get(key)
    if text is None:
        return key
    if not values:
        return text
    try:
        return text.format(**values)
    except (KeyError, IndexError, ValueError):
        return text


def format_date(value: date | datetime) -> str:
    """``Nov 12, 2026`` in English, ``12 nov 2026`` in Spanish."""
    month = _MONTHS[_language][value.month - 1]
    if _language == "es":
        return f"{value.day} {month} {value.year}"
    return f"{month} {value.day}, {value.year}"


def format_time(value: datetime | time) -> str:
    """``2:05 PM`` in English, ``14:05`` in Spanish."""
    if _language == "es":
        return f"{value.hour:02d}:{value.minute:02d}"
    suffix = "PM" if value.hour >= 12 else "AM"
    return f"{value.hour % 12 or 12}:{value.minute:02d} {suffix}"


def translate_status(message: str) -> str:
    """Translate a known session status message; anything else passes through."""
    key = _STATUS_EXACT.get(message)
    if key is not None:
        return t(key)
    for pattern, pattern_key in _STATUS_PATTERNS:
        match = pattern.match(message)
        if match:
            return t(pattern_key, key=match.group("key"))
    return message
