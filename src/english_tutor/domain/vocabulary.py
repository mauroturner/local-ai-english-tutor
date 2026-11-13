"""The learner's personal word list: phrases to learn, with meaning, example and a review date (pure)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime

from .corrections import normalize
from .models import MistakeRecord, PracticeOutcome, ReviewState, Severity
from .review_schedule import first_review, schedule

MAX_PHRASE = 80
MAX_MEANING = 120
MAX_EXAMPLE = 160
MAX_ENTRIES = 500

_SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class PhraseSuggestion:
    """A phrase proposed for the word list (by the model, from a reply or from Spanish)."""

    phrase: str
    meaning: str = ""
    example: str = ""


@dataclass(frozen=True)
class VocabEntry:
    """One saved phrase."""

    key: str
    phrase: str
    meaning: str
    example: str
    added: datetime
    review: ReviewState | None = None
    practice_attempts: int = 0
    practice_successes: int = 0


def _clean(text: str, limit: int) -> str:
    """One line of printable text, without double quotes (it goes into prompts), bounded."""
    printable = "".join(c for c in str(text) if c.isprintable() or c.isspace())
    return _SPACE.sub(" ", printable).strip().replace('"', "'")[:limit].strip()


def clean_suggestion(suggestion: PhraseSuggestion) -> PhraseSuggestion | None:
    """The suggestion made safe to store; None when there is no phrase left."""
    phrase = _clean(suggestion.phrase, MAX_PHRASE)
    if not normalize(phrase):
        return None
    return PhraseSuggestion(
        phrase, _clean(suggestion.meaning, MAX_MEANING), _clean(suggestion.example, MAX_EXAMPLE)
    )


def add_entry(
    entries: Mapping[str, VocabEntry], suggestion: PhraseSuggestion, now: datetime
) -> dict[str, VocabEntry]:
    """A copy of ``entries`` with the suggestion added.

    A phrase already in the list keeps its date, schedule and score and only takes
    a newer non-empty meaning or example. A new phrase is due tomorrow. The list is
    bounded: when full, a new phrase is ignored.
    """
    cleaned = clean_suggestion(suggestion)
    result = dict(entries)
    if cleaned is None:
        return result
    key = normalize(cleaned.phrase)
    old = result.get(key)
    if old is not None:
        result[key] = replace(
            old, meaning=cleaned.meaning or old.meaning, example=cleaned.example or old.example
        )
    elif len(result) < MAX_ENTRIES:
        result[key] = VocabEntry(
            key, cleaned.phrase, cleaned.meaning, cleaned.example, now, first_review(now.date())
        )
    return result


def remove_entry(entries: Mapping[str, VocabEntry], key: str) -> dict[str, VocabEntry]:
    """A copy of ``entries`` without ``key``."""
    return {k: v for k, v in entries.items() if k != key}


def practice_entry(
    entries: Mapping[str, VocabEntry], key: str, outcome: PracticeOutcome, now: datetime
) -> dict[str, VocabEntry]:
    """A copy of ``entries`` with one practice answer recorded (``NOT_USED`` changes nothing)."""
    result = dict(entries)
    old = result.get(key)
    if old is None or outcome is PracticeOutcome.NOT_USED:
        return result
    won = 1 if outcome is PracticeOutcome.CORRECT else 0
    result[key] = replace(
        old,
        practice_attempts=old.practice_attempts + 1,
        practice_successes=old.practice_successes + won,
        review=schedule(old.review, outcome, now.date()),
    )
    return result


def as_target(entry: VocabEntry) -> MistakeRecord:
    """The entry as a practice target, so the existing drill can run on it."""
    return MistakeRecord(
        key=entry.key,
        original=entry.meaning,
        corrected=entry.phrase,
        explanation=entry.example,
        severity=Severity.VOCABULARY,
        count=1,
        first_seen=entry.added,
        last_seen=entry.added,
        examples=(),
        practice_attempts=entry.practice_attempts,
        practice_successes=entry.practice_successes,
        review=entry.review,
    )
