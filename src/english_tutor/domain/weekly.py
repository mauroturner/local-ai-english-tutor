"""The weekly review: a short list of what to practise after a week of conversations (pure)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import date, timedelta

from .models import MistakeRecord
from .review_schedule import is_due

WEEK_DAYS = 7
LIMIT = 5


def weekly_selection(
    records: Sequence[MistakeRecord], today: date, limit: int = LIMIT
) -> tuple[MistakeRecord, ...]:
    """Up to ``limit`` items worth practising now.

    First the mistakes and pauses seen in the last seven days, those of the
    week's most frequent categories first (then due ones, then the most repeated);
    anything else that is due today fills the remaining places.
    """
    first_day = today - timedelta(days=WEEK_DAYS - 1)
    week = [r for r in records if first_day <= r.last_seen.date() <= today]
    weight: Counter[str] = Counter()
    for item in week:
        if item.category:
            weight[item.category] += item.count

    def rank(item: MistakeRecord) -> tuple[int, bool, int, str]:
        return (-weight.get(item.category or "", 0), not is_due(item.review, today), -item.count, item.key)

    chosen = sorted(week, key=rank)[:limit]
    taken = {r.key for r in chosen}
    due = sorted(
        (r for r in records if r.key not in taken and is_due(r.review, today)),
        key=lambda r: (-r.count, r.key),
    )
    return tuple([*chosen, *due][:limit])


def next_in(
    selection: Sequence[MistakeRecord], after: str | None = None
) -> MistakeRecord | None:
    """The item after ``after`` in ``selection`` (wrapping round), or the first one."""
    if not selection:
        return None
    keys = [r.key for r in selection]
    if after in keys:
        return selection[(keys.index(after) + 1) % len(selection)]
    return selection[0]
