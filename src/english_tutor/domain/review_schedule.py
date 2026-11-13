"""Spaced repetition: when a mistake should be practised again.

Every mistake sits on a ladder of growing gaps. A correct practice answer
climbs one step (the next review is further away); a wrong one, or making the
mistake again in conversation, goes back to the first step.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, timedelta

from .models import MistakeRecord, PracticeOutcome, ReviewState

LADDER_DAYS = (1, 3, 7, 14, 30)
"""Days until the next review at each step."""


def first_review(today: date) -> ReviewState:
    """The schedule of a mistake just made: due tomorrow."""
    return ReviewState(today + timedelta(days=LADDER_DAYS[0]), 0)


def schedule(
    review: ReviewState | None, outcome: PracticeOutcome, today: date
) -> ReviewState | None:
    """The schedule after one practice answer.

    ``NOT_USED`` is not an answer and changes nothing. A mistake that had no
    schedule yet (stored before spaced repetition existed) starts at step 0.
    """
    if outcome is PracticeOutcome.NOT_USED:
        return review
    if outcome is PracticeOutcome.INCORRECT:
        return first_review(today)
    step = min((review.step if review else 0) + 1, len(LADDER_DAYS) - 1)
    return ReviewState(today + timedelta(days=LADDER_DAYS[step]), step)


def is_due(review: ReviewState | None, today: date) -> bool:
    """Whether the review is due today or overdue; an unscheduled mistake always is."""
    return review is None or review.due <= today


def _due_date(record: MistakeRecord, today: date) -> date:
    return today if record.review is None else min(record.review.due, today)


def due_items(records: Iterable[MistakeRecord], today: date) -> tuple[MistakeRecord, ...]:
    """The mistakes due today, most overdue first (ties keep the given order)."""
    due = [r for r in records if is_due(r.review, today)]
    return tuple(sorted(due, key=lambda r: _due_date(r, today)))


def due_first(records: Sequence[MistakeRecord], today: date) -> tuple[MistakeRecord, ...]:
    """``records`` with the due ones moved to the front, the rest in the given order."""
    due = due_items(records, today)
    due_keys = {r.key for r in due}
    return due + tuple(r for r in records if r.key not in due_keys)


def next_due(
    records: Iterable[MistakeRecord], today: date, after: str | None = None
) -> MistakeRecord | None:
    """The mistake to review next, preferring one other than ``after`` (the last practised)."""
    due = due_items(records, today)
    return next((r for r in due if r.key != after), due[0] if due else None)
