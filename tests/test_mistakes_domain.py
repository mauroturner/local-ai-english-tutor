"""Pure rules that group corrections into a persistent mistake history."""

from __future__ import annotations

from datetime import datetime, timedelta

from conftest import major, minor

from english_tutor.domain.mistakes import (
    MAX_EXAMPLES,
    add_corrections,
    add_practice,
    mistake_key,
    rank,
)
from english_tutor.domain.models import PracticeOutcome, Severity

T0 = datetime(2026, 11, 12, 10, 0, 0)


def test_key_normalizes_case_punctuation_and_spaces():
    assert mistake_key("I  Go!", "I went.") == "i go => i went"
    assert mistake_key("i go", "I WENT") == "i go => i went"


def test_first_occurrence_creates_a_record():
    records = add_corrections({}, [major("I go", "I went", "Past tense.")], "I go home", T0)
    record = records["i go => i went"]
    assert record.key == "i go => i went"
    assert (record.original, record.corrected) == ("I go", "I went")
    assert record.explanation == "Past tense."
    assert record.severity is Severity.MAJOR
    assert record.count == 1
    assert record.first_seen == record.last_seen == T0
    assert record.examples == ("I go home",)
    assert (record.practice_attempts, record.practice_successes) == (0, 0)


def test_input_mapping_is_not_mutated():
    original = add_corrections({}, [major("I go", "I went")], "I go", T0)
    snapshot = dict(original)
    add_corrections(original, [major("I go", "I went")], "again I go", T0)
    assert original == snapshot


def test_repeat_increments_count_and_keeps_first_seen():
    first = add_corrections({}, [major("I go", "I went")], "I go home", T0)
    later = T0 + timedelta(days=1)
    second = add_corrections(first, [major("i go", "I went!")], "yesterday i go out", later)
    record = second["i go => i went"]
    assert record.count == 2
    assert record.first_seen == T0 and record.last_seen == later
    assert (record.original, record.corrected) == ("i go", "I went!")  # latest display text


def test_examples_are_bounded_and_deduped_keeping_the_latest():
    records: dict = {}
    for sentence in ["s1 I go", "s2 I go", "s3 I go", "s4 I go", "s2 I go"]:
        records = add_corrections(records, [major("I go", "I went")], sentence, T0)
    examples = records["i go => i went"].examples
    assert MAX_EXAMPLES == 3
    assert examples == ("s3 I go", "s4 I go", "s2 I go")


def test_major_wins_over_minor_and_never_downgrades():
    records = add_corrections({}, [minor("a apple", "an apple")], "a apple", T0)
    assert records["a apple => an apple"].severity is Severity.MINOR
    records = add_corrections(records, [major("a apple", "an apple")], "a apple", T0)
    assert records["a apple => an apple"].severity is Severity.MAJOR
    records = add_corrections(records, [minor("a apple", "an apple")], "a apple", T0)
    assert records["a apple => an apple"].severity is Severity.MAJOR


def test_latest_non_empty_explanation_wins():
    records = add_corrections({}, [major("I go", "I went", "old")], "I go", T0)
    records = add_corrections(records, [major("I go", "I went", "new")], "I go", T0)
    assert records["i go => i went"].explanation == "new"
    records = add_corrections(records, [major("I go", "I went", "")], "I go", T0)
    assert records["i go => i went"].explanation == "new"


def test_several_corrections_in_one_turn():
    records = add_corrections(
        {}, [major("I go", "I went"), minor("a apple", "an apple")], "I go a apple", T0
    )
    assert set(records) == {"i go => i went", "a apple => an apple"}


def test_rank_orders_by_count_then_recency():
    records: dict = {}
    records = add_corrections(records, [major("a b", "a c")], "x", T0)
    records = add_corrections(records, [major("d e", "d f")], "x", T0 + timedelta(hours=1))
    for _ in range(2):
        records = add_corrections(records, [major("g h", "g i")], "x", T0 - timedelta(hours=5))
    order = [r.key for r in rank(records)]
    assert order == ["g h => g i", "d e => d f", "a b => a c"]


def test_practice_stats_ignore_not_used():
    records = add_corrections({}, [major("I go", "I went")], "I go", T0)
    key = "i go => i went"
    records = add_practice(records, key, PracticeOutcome.CORRECT, T0)
    records = add_practice(records, key, PracticeOutcome.INCORRECT, T0)
    records = add_practice(records, key, PracticeOutcome.NOT_USED, T0)
    assert (records[key].practice_attempts, records[key].practice_successes) == (2, 1)


def test_practice_for_unknown_key_changes_nothing():
    records = add_corrections({}, [major("I go", "I went")], "I go", T0)
    assert add_practice(records, "nope", PracticeOutcome.CORRECT, T0) == records
