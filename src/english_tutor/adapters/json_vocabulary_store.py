"""The personal word list stored in ``data/vocabulary.json``."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ..domain.corrections import normalize
from ..domain.models import ReviewState
from ..domain.vocabulary import (
    MAX_ENTRIES,
    PhraseSuggestion,
    VocabEntry,
    clean_suggestion,
)
from .json_document import VersionedJsonList

logger = logging.getLogger(__name__)


class JsonVocabularyStore:
    """Reads and writes ``{"version": 1, "words": [...]}``; see ``VersionedJsonList``."""

    def __init__(self, path: Path, clock: Callable[[], datetime] = datetime.now) -> None:
        self._file = VersionedJsonList(path, "words", "word list", clock)

    def load(self) -> list[VocabEntry]:
        """The saved phrases; bad entries are skipped. Raises StorageError if unusable."""
        entries: dict[str, VocabEntry] = {}
        for raw in self._file.read():
            try:
                entry = _parse(raw)
            except (KeyError, TypeError, ValueError, AttributeError) as exc:
                logger.warning("Skipping a bad word list entry: %r", exc)
                continue
            entries.setdefault(entry.key, entry)
        return list(entries.values())[:MAX_ENTRIES]

    def save(self, entries: Sequence[VocabEntry]) -> None:
        """Replace the stored phrases; raises StorageError on failure."""
        self._file.write([_to_dict(e) for e in entries])


def _to_dict(entry: VocabEntry) -> dict[str, Any]:
    data: dict[str, Any] = {
        "phrase": entry.phrase,
        "meaning": entry.meaning,
        "example": entry.example,
        "added": entry.added.isoformat(timespec="seconds"),
        "practice": {"attempts": entry.practice_attempts, "successes": entry.practice_successes},
    }
    if entry.review is not None:
        data["review"] = {"due": entry.review.due.isoformat(), "step": entry.review.step}
    return data


def _parse_review(raw: Any) -> ReviewState | None:
    if not isinstance(raw, dict):
        return None
    try:
        step = int(raw.get("step", 0))
        return ReviewState(date.fromisoformat(raw["due"]), step) if step >= 0 else None
    except (KeyError, TypeError, ValueError):
        return None


def _parse(raw: Any) -> VocabEntry:
    cleaned = clean_suggestion(
        PhraseSuggestion(str(raw["phrase"]), str(raw.get("meaning", "")), str(raw.get("example", "")))
    )
    if cleaned is None:
        raise ValueError("empty phrase")
    practice = raw.get("practice") or {}
    return VocabEntry(
        key=normalize(cleaned.phrase),
        phrase=cleaned.phrase,
        meaning=cleaned.meaning,
        example=cleaned.example,
        added=datetime.fromisoformat(raw["added"]),
        review=_parse_review(raw.get("review")),
        practice_attempts=max(0, int(practice.get("attempts", 0))),
        practice_successes=max(0, int(practice.get("successes", 0))),
    )
