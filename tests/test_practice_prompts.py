"""Practice prompt building, reply parsing and the Ollama practice call."""

from __future__ import annotations

import json
from datetime import datetime

from test_ollama_chat import FakeSession, answer, model

from english_tutor.adapters.ollama_parsing import FALLBACK_PROMPT, parse_practice_reply
from english_tutor.domain.models import ChatMessage, MistakeRecord, PracticeOutcome, Severity
from english_tutor.domain.practice_prompts import (
    PRACTICE_SCHEMA,
    PRACTICE_START,
    PRACTICE_SYSTEM_PROMPT,
    build_practice_system_prompt,
)

WHEN = datetime(2026, 11, 12, 9, 0, 0)


def target(original="I go", corrected="I went", explanation="Use the past tense.") -> MistakeRecord:
    return MistakeRecord(
        "k", original, corrected, explanation, Severity.MAJOR, 1, WHEN, WHEN, ("I go home",)
    )


def test_constants():
    assert PRACTICE_START == "START"
    assert PRACTICE_SCHEMA["required"] == ["target_used", "feedback", "next_prompt"]
    assert PRACTICE_SCHEMA["properties"]["target_used"]["enum"] == [
        "correct",
        "incorrect",
        "not_used",
    ]
    assert PRACTICE_SYSTEM_PROMPT.startswith("You are Alex, a friendly English tutor running")
    assert "Spoken English only: no lists, no emojis, no markdown." in PRACTICE_SYSTEM_PROMPT


def test_prompt_contains_the_target_block():
    prompt = build_practice_system_prompt(target())
    assert prompt.startswith(PRACTICE_SYSTEM_PROMPT + "\n")
    assert (
        'TARGET:\n- The learner said: "I go"\n- Correct form: "I went"\n'
        "- Rule: Use the past tense.\n\nLEARNER:\n"
    ) in prompt


def test_target_fields_are_cleaned():
    messy = target('He said  "no"\n  twice', "x" * 500, "Rule:\n\tspaced   out")
    prompt = build_practice_system_prompt(messy)
    block = prompt.split("TARGET:\n")[1].split("\n\nLEARNER:")[0]
    assert "He said 'no' twice" in block
    assert '"x' + "x" * 199 + '"' in block
    assert "x" * 201 not in block
    assert "Rule: Rule: spaced out" in block
    assert block.count('"') == 4  # only the template's own quotes survive


def test_prompt_with_braces_in_fields_does_not_break():
    assert "{oops}" in build_practice_system_prompt(target("say {oops}", "ok"))


def test_parse_valid_reply():
    raw = json.dumps(
        {"target_used": "correct", "feedback": " Great! ", "next_prompt": " Where did you go? "}
    )
    reply = parse_practice_reply(raw)
    assert reply.outcome is PracticeOutcome.CORRECT
    assert (reply.feedback, reply.next_prompt) == ("Great!", "Where did you go?")
    assert reply.parsed_ok


def test_parse_each_outcome():
    for value in PracticeOutcome:
        raw = json.dumps({"target_used": value.value, "feedback": "f", "next_prompt": "p"})
        assert parse_practice_reply(raw).outcome is value


def test_parse_invalid_json_uses_the_raw_text_as_the_prompt():
    reply = parse_practice_reply("  What did you eat?  ")
    assert reply.outcome is PracticeOutcome.NOT_USED
    assert reply.feedback == ""
    assert reply.next_prompt == "What did you eat?"
    assert not reply.parsed_ok


def test_parse_empty_text_uses_the_fallback_prompt():
    reply = parse_practice_reply("   ")
    assert reply.next_prompt == FALLBACK_PROMPT and not reply.parsed_ok


def test_parse_unknown_outcome_is_not_used():
    raw = json.dumps({"target_used": "maybe", "feedback": "f", "next_prompt": "p"})
    reply = parse_practice_reply(raw)
    assert reply.outcome is PracticeOutcome.NOT_USED
    assert reply.parsed_ok


def test_parse_missing_next_prompt_gets_the_fallback():
    reply = parse_practice_reply(json.dumps({"target_used": "correct", "feedback": "Well done"}))
    assert reply.next_prompt == FALLBACK_PROMPT
    assert reply.outcome is PracticeOutcome.CORRECT


def test_parse_json_without_any_expected_field_is_unparsed():
    assert not parse_practice_reply(json.dumps({"hello": 1})).parsed_ok


def test_parse_json_inside_prose():
    raw = 'Sure! {"target_used": "incorrect", "feedback": "f", "next_prompt": "p"} bye'
    assert parse_practice_reply(raw).outcome is PracticeOutcome.INCORRECT


def test_ollama_practice_payload():
    content = json.dumps({"target_used": "correct", "feedback": "f", "next_prompt": "p"})
    session = FakeSession(post=answer(content))
    history = [ChatMessage("user", "START"), ChatMessage("assistant", "Let's go.")]
    result = model(session).practice(target(), history, "I went home")

    payload = session.posts[0]["json"]
    assert payload["format"] == PRACTICE_SCHEMA
    assert payload["messages"] == [
        {"role": "system", "content": build_practice_system_prompt(target())},
        {"role": "user", "content": "START"},
        {"role": "assistant", "content": "Let's go."},
        {"role": "user", "content": "I went home"},
    ]
    assert result.outcome is PracticeOutcome.CORRECT


def test_ollama_practice_never_raises_on_garbage():
    result = model(FakeSession(post=answer("not json at all"))).practice(target(), [], "START")
    assert not result.parsed_ok
    assert result.next_prompt == "not json at all"
