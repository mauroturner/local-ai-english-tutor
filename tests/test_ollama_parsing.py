"""Tolerant parsing of model output."""

from __future__ import annotations

import json

from english_tutor.adapters.ollama_parsing import (
    FALLBACK_REPLY,
    parse_feedback,
    parse_tutor_reply,
)
from english_tutor.domain.models import Severity

VALID = {
    "reply": "Nice! What did you do?",
    "errors": [
        {"original": "I go", "corrected": "I went", "explanation": "Past.", "severity": "major"},
        {"original": "the Paris", "corrected": "Paris", "explanation": "No the.", "severity": "minor"},
    ],
}


def test_valid_json():
    reply = parse_tutor_reply(json.dumps(VALID))
    assert reply.parsed_ok
    assert reply.reply == "Nice! What did you do?"
    assert [c.severity for c in reply.corrections] == [Severity.MAJOR, Severity.MINOR]


def test_json_wrapped_in_prose():
    raw = "Sure! Here you go: " + json.dumps(VALID) + " Hope that helps {not json}"
    reply = parse_tutor_reply(raw)
    assert reply.parsed_ok and len(reply.corrections) == 2


def test_braces_inside_strings_do_not_break_extraction():
    payload = {"reply": "Use {braces} wisely?", "errors": []}
    reply = parse_tutor_reply("noise " + json.dumps(payload))
    assert reply.parsed_ok and reply.reply == "Use {braces} wisely?"


def test_malformed_falls_back_to_raw_text():
    reply = parse_tutor_reply('  {"reply": "oops", ')
    assert not reply.parsed_ok
    assert reply.reply == '{"reply": "oops",'
    assert reply.corrections == ()


def test_plain_text_becomes_reply():
    reply = parse_tutor_reply("Just chatting, how are you?")
    assert not reply.parsed_ok and reply.reply == "Just chatting, how are you?"


def test_empty_input_uses_fallback_text():
    assert parse_tutor_reply("   ").reply == FALLBACK_REPLY


def test_bad_severity_item_is_skipped_others_kept():
    data = dict(VALID)
    data["errors"] = [
        {"original": "a b", "corrected": "a", "explanation": "x", "severity": "huge"},
        VALID["errors"][0],
    ]
    reply = parse_tutor_reply(json.dumps(data))
    assert [c.original for c in reply.corrections] == ["I go"]


def test_item_with_missing_keys_is_skipped():
    data = {"reply": "Hi?", "errors": [{"original": "x"}, "junk", None]}
    reply = parse_tutor_reply(json.dumps(data))
    assert reply.parsed_ok and reply.corrections == ()


def test_missing_reply_key_falls_back():
    reply = parse_tutor_reply(json.dumps({"errors": []}))
    assert not reply.parsed_ok


def test_severity_is_case_insensitive():
    data = {"reply": "Hi?", "errors": [dict(VALID["errors"][0], severity="MAJOR")]}
    assert parse_tutor_reply(json.dumps(data)).corrections[0].severity is Severity.MAJOR


def test_parse_feedback_valid_and_fallback():
    ok = parse_feedback(json.dumps({"summary": "Good.", "strengths": ["a"], "focus_areas": ["b"]}))
    assert ok.summary == "Good." and ok.strengths == ("a",) and ok.focus_areas == ("b",)
    bad = parse_feedback("Plain words only")
    assert bad.summary == "Plain words only" and bad.strengths == ()
