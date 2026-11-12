"""Settings registry: coverage of UserSettings, i18n keys and accent-blind search."""

from __future__ import annotations

import dataclasses

import pytest

from english_tutor.i18n import en, es
from english_tutor.settings.model import ENV_VARS, RESTART_FIELDS, UserSettings, parse_field
from english_tutor.settings.registry import (
    ACTION_KEYS,
    REGISTRY,
    Category,
    Control,
    SettingSpec,
    by_category,
    option_label_key,
    search,
)

FIELDS = {f.name for f in dataclasses.fields(UserSettings)}


def spanish(key: str) -> str:
    return es.STRINGS[key]


def english(key: str) -> str:
    return en.STRINGS[key]


def keys_of(result) -> set[str]:
    return {spec.key for specs in result.values() for spec in specs}


def test_enums_have_the_documented_members():
    assert [c.name for c in Category] == [
        "GENERAL", "APPEARANCE", "AUDIO", "STORAGE", "SHORTCUTS", "ADVANCED",
    ]  # fmt: skip
    assert {c.name for c in Control} == {
        "SWITCH", "CHOICE", "SLIDER", "TEXT", "COMBO", "PATH", "KEY", "SHORTCUT", "ACTION",
    }


def test_every_user_setting_has_exactly_one_spec():
    setting_specs = [s.key for s in REGISTRY if s.key in FIELDS]
    assert sorted(setting_specs) == sorted(FIELDS)


def test_every_other_spec_is_a_known_action():
    assert ACTION_KEYS == frozenset({
        "open_data_folder", "export_report", "export_mistakes", "clear_logs", "clear_mistakes",
        "test_connection", "open_logs_folder", "restore_defaults", "autostart",
    })  # fmt: skip
    extra = {s.key for s in REGISTRY} - FIELDS
    assert extra == ACTION_KEYS
    assert all(s.control is Control.ACTION for s in REGISTRY if s.key in ACTION_KEYS)
    assert not any(s.control is Control.ACTION for s in REGISTRY if s.key in FIELDS)


def test_spec_keys_are_unique():
    keys = [s.key for s in REGISTRY]
    assert len(keys) == len(set(keys))


def test_restart_and_env_metadata_match_the_model():
    for spec in REGISTRY:
        if spec.key in FIELDS:
            assert spec.restart == (spec.key in RESTART_FIELDS), spec.key
            assert spec.env_var == ENV_VARS.get(spec.key), spec.key
        else:
            assert spec.restart is False and spec.env_var is None, spec.key


def test_every_label_help_and_category_key_exists_in_both_languages():
    for spec in REGISTRY:
        for key in (spec.label, spec.help):
            assert key in en.STRINGS and key in es.STRINGS, key
    for category in Category:
        assert f"category.{category.value}" in en.STRINGS
        assert f"category.{category.value}" in es.STRINGS


def test_option_labels_exist_for_choices_shown_by_name():
    for key in ("language", "appearance_mode", "density", "whisper_device"):
        spec = next(s for s in REGISTRY if s.key == key)
        assert spec.options
        for value in spec.options:
            assert option_label_key(key, value) in en.STRINGS
            assert option_label_key(key, value) in es.STRINGS


def test_choice_options_are_accepted_by_the_model():
    for spec in REGISTRY:
        if spec.key in FIELDS and spec.control in (Control.CHOICE, Control.COMBO, Control.SLIDER):
            for value in spec.options:
                parse_field(spec.key, value)
        if spec.control is Control.CHOICE:
            assert spec.options, spec.key


def test_every_category_has_specs_in_registry_order():
    seen: list[SettingSpec] = []
    for category in Category:
        specs = by_category(category)
        assert specs, category
        assert all(s.category is category for s in specs)
        seen.extend(specs)
    assert seen == [s for c in Category for s in REGISTRY if s.category is c]
    assert len(seen) == len(REGISTRY)


def test_destructive_actions_are_marked_dangerous():
    danger = {s.key for s in REGISTRY if s.danger}
    assert {"clear_logs", "clear_mistakes"} <= danger
    assert "export_report" not in danger


def test_keywords_are_lowercase_strings():
    for spec in REGISTRY:
        assert all(k == k.lower() and k for k in spec.keywords), spec.key


# ----------------------------------------------------------------------- search
def test_blank_query_returns_everything_grouped_in_category_order():
    for query in ("", "   "):
        result = search(query, english)
        assert keys_of(result) == {s.key for s in REGISTRY}
        assert list(result) == list(Category)


def test_search_matches_label_case_insensitively():
    assert "appearance_mode" in keys_of(search("THEME", english))


def test_search_ignores_accents_in_query_and_text():
    for query in ("tamano", "tamaño", "TAMAÑO"):
        assert "chat_font_size" in keys_of(search(query, spanish)), query


def test_search_matches_the_english_label_under_another_language():
    assert "ptt_key" in keys_of(search("push-to-talk", spanish))


def test_search_matches_keywords_and_help_text():
    assert "notify_report" in keys_of(search("toast", english))
    assert "whisper_device" in keys_of(search("gpu", english))
    assert "clear_logs" in keys_of(search("permanently", english))  # only in the help text


def test_search_requires_every_word_to_match():
    assert "appearance_mode" in keys_of(search("dark mode", english))
    assert search("dark zzzzz", english) == {}


def test_search_groups_by_category_and_skips_empty_ones():
    result = search("log", english)
    assert list(result) == [Category.STORAGE, Category.ADVANCED]
    for category, specs in result.items():
        assert all(spec.category is category for spec in specs)
    assert {"clear_logs"} <= {s.key for s in result[Category.STORAGE]}
    assert {"log_level", "open_logs_folder"} <= {s.key for s in result[Category.ADVANCED]}


def test_search_with_no_match_is_empty():
    assert search("qqqqqq", english) == {}


@pytest.mark.parametrize("query", ["a", "e", "o"])
def test_single_letter_queries_do_not_crash(query):
    assert search(query, spanish)
