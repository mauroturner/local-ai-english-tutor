"""Pure rules that decide which corrections are real and which one is shown live."""

from __future__ import annotations

import re
from collections.abc import Iterable

from .models import Correction, Severity

_PUNCT_RE = re.compile(r"[^\w\s']", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Lowercase, drop punctuation (keeping apostrophes) and collapse spaces."""
    lowered = text.lower().replace("’", "'")
    return _SPACE_RE.sub(" ", _PUNCT_RE.sub(" ", lowered)).strip()


def is_cosmetic(correction: Correction) -> bool:
    """True when the correction only changes case or punctuation."""
    return normalize(correction.original) == normalize(correction.corrected)


def filter_corrections(
    transcript: str, corrections: Iterable[Correction]
) -> tuple[Correction, ...]:
    """Drop empty, cosmetic-only and invented corrections.

    A correction is invented when its ``original`` text does not appear in the
    transcript the learner actually produced.
    """
    haystack = f" {normalize(transcript)} "
    kept: list[Correction] = []
    for item in corrections:
        original = normalize(item.original)
        if not original or not normalize(item.corrected):
            continue
        if is_cosmetic(item) or f" {original} " not in haystack:
            continue
        kept.append(item)
    return tuple(kept)


def dedupe(corrections: Iterable[Correction]) -> tuple[Correction, ...]:
    """Remove repeated corrections (same original and corrected text)."""
    seen: set[tuple[str, str]] = set()
    unique: list[Correction] = []
    for item in corrections:
        key = (normalize(item.original), normalize(item.corrected))
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return tuple(unique)


def pick_live(
    corrections: Iterable[Correction],
) -> tuple[Correction | None, tuple[Correction, ...]]:
    """Choose at most one major correction to show live.

    Returns ``(live, rest)``. ``rest`` holds every other correction, which is
    recorded silently for the end-of-session report.
    """
    items = tuple(corrections)
    live = next((c for c in items if c.severity is Severity.MAJOR), None)
    rest = tuple(c for c in items if c is not live)
    return live, rest


def spoken_line(correction: Correction) -> str:
    """Short sentence read aloud before the tutor reply."""
    return (
        f"Quick tip: instead of '{correction.original}', "
        f"say '{correction.corrected}'."
    )


def compose_speech(reply: str, live: Correction | None) -> str:
    """Text read aloud for a turn: the live tip (if any), then the tutor's reply."""
    return f"{spoken_line(live)} {reply}" if live is not None else reply
