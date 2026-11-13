"""Spaced repetition: the review ladder and which mistakes are due."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest

from english_tutor.domain.mistakes import add_corrections, add_practice
from english_tutor.domain.models import (
    Correction,
    MistakeRecord,
    PracticeOutcome,
    ReviewState,
    Severity,
)
from english_tutor.domain.review_schedule import (
    LADDER_DAYS,
    due_first,
    due_items,
    first_review,
    is_due,
    next_due,
    schedule,
)

TODAY = date(2026, 11, 13)
NOW = datetime(2026, 11, 13, 10, 0, 0)


def record(key="a => b", review=None, count=1) -> MistakeRecord:
    return MistakeRecord(
        key, "a", "b", "", Severity.MAJOR, count, NOW, NOW, ("a",), review=review
    )


def test_a_new_mistake_is_due_tomorrow():
    assert first_review(TODAY) == ReviewState(TODAY + timedelta(days=1), 0)


@pytest.mark.parametrize("step", range(len(LADDER_DAYS) - 1))
def test_a_correct_answer_climbs_one_step(step):
    after = schedule(ReviewState(TODAY, step), PracticeOutcome.CORRECT, TODAY)
    assert after == ReviewState(TODAY + timedelta(days=LADDER_DAYS[step + 1]), step + 1)


def test_the_top_step_stays_at_the_longest_interval():
    top = len(LADDER_DAYS) - 1
    after = schedule(ReviewState(TODAY, top), PracticeOutcome.CORRECT, TODAY)
    assert after == ReviewState(TODAY + timedelta(days=LADDER_DAYS[-1]), top)


def test_a_wrong_answer_goes_back_to_the_first_step():
    after = schedule(ReviewState(TODAY, 3), PracticeOutcome.INCORRECT, TODAY)
    assert after == ReviewState(TODAY + timedelta(days=LADDER_DAYS[0]), 0)


def test_not_using_the_phrase_changes_nothing():
    state = ReviewState(TODAY, 2)
    assert schedule(state, PracticeOutcome.NOT_USED, TODAY) == state
    assert schedule(None, PracticeOutcome.NOT_USED, TODAY) is None


def test_an_unscheduled_mistake_is_scheduled_by_its_first_answer():
    assert schedule(None, PracticeOutcome.CORRECT, TODAY) == ReviewState(
        TODAY + timedelta(days=LADDER_DAYS[1]), 1
    )
    assert schedule(None, PracticeOutcome.INCORRECT, TODAY) == first_review(TODAY)


def test_due_means_today_or_earlier_and_unscheduled_counts_as_due():
    assert is_due(ReviewState(TODAY, 0), TODAY)
    assert is_due(ReviewState(TODAY - timedelta(days=5), 0), TODAY)
    assert not is_due(ReviewState(TODAY + timedelta(days=1), 0), TODAY)
    assert is_due(None, TODAY)


def test_due_items_most_overdue_first_keeping_the_given_order_on_ties():
    late = record("late", ReviewState(TODAY - timedelta(days=4)))
    today = record("today", ReviewState(TODAY))
    unscheduled = record("old")
    later = record("later", ReviewState(TODAY + timedelta(days=2)))
    assert [r.key for r in due_items([today, later, unscheduled, late], TODAY)] == [
        "late", "today", "old",
    ]


def test_due_first_puts_due_items_ahead_without_reordering_the_rest():
    a = record("a", ReviewState(TODAY + timedelta(days=3)))
    b = record("b", ReviewState(TODAY))
    c = record("c", ReviewState(TODAY + timedelta(days=1)))
    d = record("d", ReviewState(TODAY - timedelta(days=1)))
    assert [r.key for r in due_first([a, b, c, d], TODAY)] == ["d", "b", "a", "c"]


def test_next_due_skips_the_item_just_practised():
    first = record("first", ReviewState(TODAY - timedelta(days=2)))
    second = record("second", ReviewState(TODAY))
    assert next_due([first, second], TODAY).key == "first"
    assert next_due([first, second], TODAY, after="first").key == "second"
    assert next_due([first], TODAY, after="first").key == "first"  # nothing else is due
    assert next_due([record("x", ReviewState(TODAY + timedelta(days=9)))], TODAY) is None


# ---- how the mistake history feeds the schedule -----------------------------------


def fix(original="I go", corrected="I went") -> Correction:
    return Correction(original, corrected, "Past.", Severity.MAJOR)


def test_a_new_mistake_gets_its_first_review():
    result = add_corrections({}, [fix()], "I go home", NOW)
    assert result["i go => i went"].review == first_review(TODAY)


def test_a_repeated_mistake_starts_the_ladder_again():
    climbed = replace(
        add_corrections({}, [fix()], "I go home", NOW)["i go => i went"],
        review=ReviewState(TODAY + timedelta(days=14), 3),
    )
    again = add_corrections({climbed.key: climbed}, [fix()], "I go out", NOW)
    assert again[climbed.key].review == first_review(TODAY)
    assert again[climbed.key].count == 2


def test_practice_moves_the_schedule_by_outcome():
    start = add_corrections({}, [fix()], "I go home", NOW)
    key = "i go => i went"
    right = add_practice(start, key, PracticeOutcome.CORRECT, NOW)
    assert right[key].review == ReviewState(TODAY + timedelta(days=LADDER_DAYS[1]), 1)
    wrong = add_practice(right, key, PracticeOutcome.INCORRECT, NOW)
    assert wrong[key].review == first_review(TODAY)
    unused = add_practice(wrong, key, PracticeOutcome.NOT_USED, NOW)
    assert unused[key].review == wrong[key].review
