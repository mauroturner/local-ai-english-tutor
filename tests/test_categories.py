"""Mistake categories: parsing, counting, and how they travel through the app."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from english_tutor.adapters.ollama_parsing import parse_tutor_reply
from english_tutor.application.report import make_report
from english_tutor.domain.categories import (
    FLUENCY,
    MODEL_CATEGORIES,
    category_label,
    count_categories,
    parse_category,
)
from english_tutor.domain.formatting import category_line, format_report
from english_tutor.domain.hesitation import as_corrections
from english_tutor.domain.models import Correction, Hesitation, SessionReport, Severity, Turn
from english_tutor.domain.mistakes import add_corrections

NOW = datetime(2026, 11, 13, 10, 0, 0)


def fix(category, original="I go", corrected="I went") -> Correction:
    return Correction(original, corrected, "why", Severity.MAJOR, category)


@pytest.mark.parametrize("name", MODEL_CATEGORIES)
def test_every_model_category_is_accepted(name):
    assert parse_category(name) == name


@pytest.mark.parametrize(
    "value, expected",
    [
        ("Verb Tense", "verb_tense"), (" word-order ", "word_order"), ("PREPOSITIONS", "prepositions"),
        ("spelling", "other"), ("fluency", "other"), ("", "other"), (None, "other"), (7, "other"),
    ],
)
def test_unknown_values_become_other(value, expected):
    assert parse_category(value) == expected


def test_labels_are_plain_english():
    assert category_label("false_friend") == "false friend"


def test_counting_ignores_unlabelled_other_and_fluency_and_sorts_by_count_then_name():
    items = [fix("articles"), fix("prepositions"), fix("articles"), fix("other"), fix(None),
             fix(FLUENCY), fix("agreement")]
    assert count_categories(items) == (("articles", 2), ("agreement", 1), ("prepositions", 1))


def test_the_parser_reads_the_category_and_maps_unknown_ones():
    raw = (
        '{"reply": "ok", "errors": ['
        '{"original": "a", "corrected": "b", "explanation": "x", "severity": "major", "category": "Verb tense"},'
        '{"original": "c", "corrected": "d", "explanation": "x", "severity": "minor", "category": "banana"},'
        '{"original": "e", "corrected": "f", "explanation": "x", "severity": "minor"}]}'
    )
    reply = parse_tutor_reply(raw)
    assert [c.category for c in reply.corrections] == ["verb_tense", "other", "other"]


def test_pauses_are_labelled_fluency():
    (item,) = as_corrections([Hesitation("how's", "everything", 1.7)])
    assert item.category == FLUENCY


def test_the_history_keeps_the_category_and_a_repeat_without_one_does_not_erase_it():
    first = add_corrections({}, [fix("verb_tense")], "I go home", NOW)
    again = add_corrections(first, [replace(fix(None))], "I go out", NOW)
    assert again["i go => i went"].category == "verb_tense"
    relabelled = add_corrections(again, [fix("word_choice")], "I go up", NOW)
    assert relabelled["i go => i went"].category == "word_choice"


def turn(*corrections) -> Turn:
    return Turn(1, "text", "ok", tuple(corrections), None)


class _Tutor:
    def feedback(self, turns):
        raise RuntimeError("no model")


def test_the_report_counts_every_occurrence_by_category():
    turns = (
        turn(fix("prepositions"), fix("articles", "a apple", "an apple")),
        turn(fix("prepositions")),
    )
    report = make_report(_Tutor(), turns)
    assert report.categories == (("prepositions", 2), ("articles", 1))


def test_the_report_text_shows_the_top_three():
    report = SessionReport(
        1, (), (), None,
        categories=(("a_b", 4), ("c", 3), ("d", 2), ("e", 1)),
    )
    assert category_line(report) == "Most frequent: a b (4), c (3), d (2)"
    assert "Most frequent: a b (4)" in format_report(report)


def test_the_report_text_is_unchanged_without_categories():
    report = SessionReport(1, (), (), None)
    assert category_line(report) == ""
    assert "Most frequent" not in format_report(report)


def test_present_categories_follow_the_canonical_order():
    from english_tutor.domain.categories import present_categories

    items = [fix("word_order"), fix(None), fix("articles"), fix(FLUENCY), fix("articles")]
    assert present_categories(items) == ("articles", "word_order", FLUENCY)


def test_filtering_by_category():
    from english_tutor.domain.categories import filter_by_category

    items = [fix("articles"), fix("plural"), fix(None)]
    assert filter_by_category(items, None) == tuple(items)
    assert filter_by_category(items, "plural") == (items[1],)
    assert filter_by_category(items, "pronoun") == ()
