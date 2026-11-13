"""Pure rules that fold corrections and practice results into a mistake history."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from datetime import datetime

from .corrections import normalize
from .models import Correction, MistakeRecord, PracticeOutcome, Severity
from .review_schedule import first_review, schedule

MAX_EXAMPLES = 3


def mistake_key(original: str, corrected: str) -> str:
    """Stable identity of a mistake: the normalized original/corrected pair."""
    return f"{normalize(original)} => {normalize(corrected)}"


def add_corrections(
    records: Mapping[str, MistakeRecord],
    corrections: Iterable[Correction],
    sentence: str,
    now: datetime,
) -> dict[str, MistakeRecord]:
    """Return a copy of ``records`` with every correction of ``sentence`` counted.

    A repeated mistake keeps ``first_seen``, takes the latest display text and
    non-empty explanation, never loses a MAJOR severity, and remembers the
    raw sentence (the last ``MAX_EXAMPLES`` distinct ones). Making a mistake
    again starts its review schedule over (see ``review_schedule``).
    """
    result = dict(records)
    for item in corrections:
        key = mistake_key(item.original, item.corrected)
        old = result.get(key)
        if old is None:
            result[key] = MistakeRecord(
                key, item.original, item.corrected, item.explanation, item.severity,
                1, now, now, (sentence,), category=item.category,
                review=first_review(now.date()),
            )
            continue
        severity = Severity.MAJOR if Severity.MAJOR in (old.severity, item.severity) else old.severity
        examples = tuple(e for e in old.examples if e != sentence) + (sentence,)
        result[key] = replace(
            old,
            original=item.original,
            corrected=item.corrected,
            explanation=item.explanation or old.explanation,
            severity=severity,
            count=old.count + 1,
            last_seen=now,
            examples=examples[-MAX_EXAMPLES:],
            category=item.category or old.category,
            review=first_review(now.date()),
        )
    return result


def add_practice(
    records: Mapping[str, MistakeRecord],
    key: str,
    outcome: PracticeOutcome,
    now: datetime,
) -> dict[str, MistakeRecord]:
    """Return a copy of ``records`` with one practice attempt recorded.

    ``NOT_USED`` is not an attempt. Practising does not change ``last_seen``
    (that date means "last made this mistake in conversation"); ``now`` sets
    the day the review schedule moves from.
    """
    result = dict(records)
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


def rank(records: Mapping[str, MistakeRecord]) -> tuple[MistakeRecord, ...]:
    """Most frequent first; ties go to the most recently seen."""
    return tuple(sorted(records.values(), key=lambda r: (-r.count, -r.last_seen.timestamp())))
