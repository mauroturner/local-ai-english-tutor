"""Explanations of corrections in Spanish: a rule of the turn prompt only."""

from __future__ import annotations

import dataclasses

import pytest

from english_tutor.adapters.ollama_chat import OllamaTutorModel
from english_tutor.domain.learner import LearnerProfile, explanation_rule, profile_block
from english_tutor.domain.prompts import TURN_SYSTEM_PROMPT
from english_tutor.settings.model import RESTART_FIELDS, UserSettings, learner_profile, parse_settings
from english_tutor.settings.registry import Category, Control, by_category


def test_english_needs_no_extra_rule():
    assert explanation_rule(LearnerProfile()) == ""


def test_spanish_asks_for_spanish_explanations_only():
    rule = explanation_rule(LearnerProfile(explain_in="es"))
    assert '"explanation"' in rule and "Spanish" in rule and "English" in rule


def test_an_unknown_language_is_treated_as_english():
    assert explanation_rule(LearnerProfile(explain_in="fr")) == ""


def test_the_learner_block_is_the_same_in_both_languages():
    assert profile_block(LearnerProfile(explain_in="es")) == profile_block(LearnerProfile())


class Http:
    def __init__(self):
        self.prompts = []

    def post(self, url, json, timeout):
        self.prompts.append(json["messages"][0]["content"])
        raise RuntimeError("stop here")


def sent_prompt(profile):
    http = Http()
    tutor = OllamaTutorModel("http://x", "m", 1.0, 0.3, session=http, profile=lambda: profile)
    with pytest.raises(Exception):  # noqa: B017 - the fake server only records the request
        tutor.reply([], "hello")
    return http.prompts[0]


def test_the_turn_prompt_carries_the_rule_only_for_spanish():
    english = sent_prompt(LearnerProfile())
    spanish = sent_prompt(LearnerProfile(explain_in="es"))
    assert "EXPLANATION LANGUAGE" not in english
    assert spanish.startswith(english) and spanish.endswith(explanation_rule(LearnerProfile(explain_in="es")))
    assert TURN_SYSTEM_PROMPT.rstrip("\n") in spanish


def test_the_setting_defaults_to_english_applies_live_and_reaches_the_profile():
    assert UserSettings().explain_language == "en"
    spec = {s.key: s for s in by_category(Category.GENERAL)}["explain_language"]
    assert spec.control is Control.CHOICE and spec.options == ("en", "es")
    assert "explain_language" not in RESTART_FIELDS
    assert learner_profile(dataclasses.replace(UserSettings(), explain_language="es")).explain_in == "es"


def test_a_bad_value_falls_back_to_english():
    settings, warnings = parse_settings({"explain_language": "klingon"})
    assert settings.explain_language == "en" and warnings
