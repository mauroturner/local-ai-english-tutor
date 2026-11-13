"""The weekly review selection."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from english_tutor.domain.models import MistakeRecord, ReviewState, Severity
from english_tutor.domain.weekly import LIMIT, next_in, weekly_selection

TODAY = date(2026, 11, 13)


def item(key, days_ago=0, count=1, category=None, due_in=None, severity=Severity.MAJOR):
    seen = datetime.combine(TODAY - timedelta(days=days_ago), datetime.min.time())
    review = None if due_in is None else ReviewState(TODAY + timedelta(days=due_in))
    return MistakeRecord(
        key, key, key + "!", "", severity, count, seen, seen, (), category=category, review=review
    )


def keys(selection):
    return [r.key for r in selection]


def test_items_of_the_busiest_category_come_first():
    records = [
        item("a", category="articles", count=1, due_in=5),
        item("b", category="plural", count=3, due_in=5),
        item("c", category="plural", count=2, due_in=5),
    ]
    assert keys(weekly_selection(records, TODAY)) == ["b", "c", "a"]


def test_inside_a_category_due_items_then_repeated_ones_come_first():
    records = [
        item("late", category="articles", count=9, due_in=3),
        item("due", category="articles", count=1, due_in=-1),
        item("often", category="articles", count=5, due_in=3),
    ]
    assert keys(weekly_selection(records, TODAY)) == ["due", "late", "often"]  # then by repeats


def test_old_mistakes_are_left_out_unless_they_are_due():
    records = [item("old", days_ago=9, due_in=4), item("old_due", days_ago=9, due_in=-2),
               item("fresh", days_ago=2, due_in=4)]
    assert keys(weekly_selection(records, TODAY)) == ["fresh", "old_due"]


def test_pauses_are_part_of_the_week():
    pause = item("how's … everything", severity=Severity.HESITATION, due_in=2)
    assert keys(weekly_selection([pause], TODAY)) == [pause.key]


def test_the_list_is_capped():
    records = [item(f"k{i}", count=i + 1, due_in=2) for i in range(12)]
    assert len(weekly_selection(records, TODAY)) == LIMIT
    assert len(weekly_selection(records, TODAY, limit=2)) == 2


def test_nothing_to_review():
    assert weekly_selection([], TODAY) == ()
    assert weekly_selection([item("later", days_ago=20, due_in=9)], TODAY) == ()


def test_the_review_walks_through_the_selection_and_wraps():
    selection = weekly_selection([item("a", count=3), item("b", count=2), item("c", count=1)], TODAY)
    assert keys(selection) == ["a", "b", "c"]
    assert next_in(selection).key == "a"
    assert next_in(selection, "a").key == "b"
    assert next_in(selection, "c").key == "a"
    assert next_in(selection, "unknown").key == "a"
    assert next_in(()) is None
