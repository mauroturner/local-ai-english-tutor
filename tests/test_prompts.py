"""Prompt schemas and report message builder."""

from __future__ import annotations

from conftest import major, minor

from english_tutor.domain.models import Turn
from english_tutor.domain.prompts import (
    REPORT_SCHEMA,
    TURN_SCHEMA,
    TURN_SYSTEM_PROMPT,
    build_report_user_message,
)


def test_turn_schema_required_fields_and_severity_enum():
    assert TURN_SCHEMA["required"] == ["reply", "errors", "natural"]
    item = TURN_SCHEMA["properties"]["errors"]["items"]
    assert item["required"] == ["original", "corrected", "explanation", "severity", "category"]
    assert item["properties"]["severity"]["enum"] == ["major", "minor"]


def test_turn_schema_offers_every_model_category_and_never_fluency():
    from english_tutor.domain.categories import MODEL_CATEGORIES

    item = TURN_SCHEMA["properties"]["errors"]["items"]
    assert item["properties"]["category"]["enum"] == list(MODEL_CATEGORIES)
    assert "fluency" not in item["properties"]["category"]["enum"]
    assert all(name in TURN_SYSTEM_PROMPT for name in MODEL_CATEGORIES)


def test_report_schema_required_fields():
    assert REPORT_SCHEMA["required"] == ["summary", "strengths", "focus_areas", "memory"]


def test_turn_prompt_keeps_corrections_out_of_reply_and_allows_empty_errors():
    assert "Never talk about the learner's mistakes" in TURN_SYSTEM_PROMPT
    assert "return an empty list" in TURN_SYSTEM_PROMPT


def test_report_message_with_no_errors():
    turns = [Turn(1, "Hello there", "Hi!", (), None)]
    assert build_report_user_message(turns) == (
        "Learner said:\n1. Hello there\n\nRecorded errors:\nnone\n\nLong pauses:\nnone"
    )


def test_report_message_lists_all_errors():
    turns = [
        Turn(1, "yesterday I go", "ok", (major("I go", "I went", "Past."),), None),
        Turn(2, "the Paris", "ok", (minor("the Paris", "Paris", "No the."),), None),
    ]
    assert build_report_user_message(turns) == (
        "Learner said:\n1. yesterday I go\n2. the Paris\n\n"
        'Recorded errors:\n- [major] "I go" -> "I went": Past.\n'
        '- [minor] "the Paris" -> "Paris": No the.\n\nLong pauses:\nnone'
    )


def test_report_message_uses_last_40_turns():
    turns = [Turn(i, f"said {i}", "r", (), None) for i in range(1, 51)]
    message = build_report_user_message(turns)
    assert "said 10\n" not in message
    assert "1. said 11\n" in message and "40. said 50" in message
