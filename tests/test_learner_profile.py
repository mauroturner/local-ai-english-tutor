"""The learner's name and pronouns: setting, validation and use in every prompt."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from test_ollama_chat import FakeSession, answer

from english_tutor.adapters.ollama_chat import OllamaTutorModel
from english_tutor.config import ConfigError
from english_tutor.domain.learner import LearnerProfile, profile_block
from english_tutor.domain.models import MistakeRecord, Severity, Turn
from english_tutor.domain.practice_prompts import (
    PRACTICE_SYSTEM_PROMPT,
    build_practice_system_prompt,
)
from english_tutor.i18n import en, es
from english_tutor.settings.model import (
    RESTART_FIELDS,
    UserSettings,
    learner_profile,
    parse_field,
    parse_settings,
)
from english_tutor.settings.registry import Category, Control, by_category


def test_defaults_are_mauro_and_he_him():
    settings = UserSettings()
    assert (settings.learner_name, settings.learner_pronouns) == ("Mauro", "he")
    assert learner_profile(settings) == LearnerProfile("Mauro", "he")


def test_name_is_trimmed_and_may_be_empty():
    assert parse_field("learner_name", "  Ana   María ") == "Ana María"
    assert parse_field("learner_name", "") == ""
    assert parse_field("learner_name", "O'Brien-Núñez") == "O'Brien-Núñez"


@pytest.mark.parametrize("bad", ["x" * 41, 'Ann"', "Bo{b}", "Tab\tname", "a\nb", "<tag>"])
def test_name_rejects_long_or_unsafe_text(bad):
    with pytest.raises(ConfigError):
        parse_field("learner_name", bad)


def test_bad_stored_name_falls_back_alone():
    settings, warnings = parse_settings({"learner_name": "x" * 99, "learner_pronouns": "she"})
    assert settings.learner_name == "Mauro" and settings.learner_pronouns == "she"
    assert len(warnings) == 1


def test_pronouns_accept_only_the_three_choices():
    assert parse_field("learner_pronouns", "They") == "they"
    with pytest.raises(ConfigError):
        parse_field("learner_pronouns", "him")


def test_rows_live_in_general_and_apply_without_restart():
    specs = {s.key: s for s in by_category(Category.GENERAL)}
    assert specs["learner_name"].control is Control.TEXT
    assert specs["learner_pronouns"].options == ("he", "she", "they")
    assert not {"learner_name", "learner_pronouns"} & RESTART_FIELDS
    for table in (en.STRINGS, es.STRINGS):
        for value in ("he", "she", "they"):
            assert f"option.learner_pronouns.{value}" in table


def test_profile_block_names_the_learner_and_pronouns():
    block = profile_block(LearnerProfile("Mauro", "he"))
    assert '"Mauro"' in block and "he/him" in block
    empty = profile_block(LearnerProfile("", "they"))
    assert "do not use or invent one" in empty and "they/them" in empty


def target() -> MistakeRecord:
    now = datetime(2026, 11, 12)
    return MistakeRecord("k", "I go", "I went", "Past tense.", Severity.MAJOR, 1, now, now, ())


def test_practice_prompt_ends_with_the_profile():
    prompt = build_practice_system_prompt(target(), LearnerProfile("Lu", "she"))
    assert prompt.startswith(PRACTICE_SYSTEM_PROMPT + "\n")
    assert prompt.endswith(profile_block(LearnerProfile("Lu", "she")))


def _system_prompt(session: FakeSession) -> str:
    return session.posts[-1]["json"]["messages"][0]["content"]


def test_every_model_call_reads_the_current_profile():
    current = [LearnerProfile("Mauro", "he")]
    reply = json.dumps({"reply": "Hi!", "errors": []})
    session = FakeSession(post=answer(reply))
    tutor = OllamaTutorModel(
        "http://x:1", "m", 9, 0.1, session=session, profile=lambda: current[0]
    )

    tutor.reply([], "hello")
    assert '"Mauro"' in _system_prompt(session)

    current[0] = LearnerProfile("Sam", "they")  # what Save does
    tutor.reply([], "hello")
    assert '"Sam"' in _system_prompt(session) and "they/them" in _system_prompt(session)

    session._post = answer(json.dumps({"summary": "s", "strengths": [], "focus_areas": []}))
    tutor.feedback([Turn(1, "hi", "ok", (), None)])
    assert '"Sam"' in _system_prompt(session)

    verdict = {"target_used": "correct", "feedback": "f", "next_prompt": "q"}
    session._post = answer(json.dumps(verdict))
    tutor.practice(target(), [], "I went")
    assert '"Sam"' in _system_prompt(session)


def test_settings_window_accepts_an_empty_name_but_not_other_empty_texts():
    from english_tutor.settings.draft import SettingsDraft

    draft = SettingsDraft(UserSettings(), UserSettings(), frozenset())
    assert draft.set("learner_name", "  ") is None
    assert draft.to_settings().learner_name == ""
    assert draft.set("ollama_model", "") == "This value cannot be empty."
