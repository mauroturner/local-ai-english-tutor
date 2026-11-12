"""SettingsDraft: validated edits, dirty/restart tracking, defaults, locked fields."""

from __future__ import annotations

import dataclasses

import pytest

from english_tutor.settings.draft import SettingsDraft
from english_tutor.settings.model import UserSettings


def make(locked=(), stored=None, effective=None) -> SettingsDraft:
    effective = effective or UserSettings()
    return SettingsDraft(stored or effective, effective, frozenset(locked))


def test_fresh_draft_is_clean():
    draft = make()
    assert draft.dirty_keys == ()
    assert draft.restart_keys == ()
    assert draft.errors == {}
    assert not draft.has_errors
    assert draft.to_settings() == UserSettings()
    assert draft.value("chat_font_size") == 13


def test_valid_edit_marks_the_key_dirty_and_back_again_clears_it():
    draft = make()
    assert draft.set("chat_font_size", 16) is None
    assert draft.value("chat_font_size") == 16
    assert draft.dirty_keys == ("chat_font_size",)
    assert draft.to_settings().chat_font_size == 16
    draft.set("chat_font_size", 13)
    assert draft.dirty_keys == ()


def test_values_arrive_as_widgets_give_them():
    draft = make()
    assert draft.set("tts_enabled", False) is None
    assert draft.set("ui_scale", 1.25) is None
    assert draft.set("appearance_mode", "dark") is None
    assert draft.set("chat_font_size", "15") is None
    s = draft.to_settings()
    assert (s.tts_enabled, s.ui_scale, s.appearance_mode, s.chat_font_size) == (
        False, 1.25, "dark", 15,
    )  # fmt: skip


def test_invalid_edit_reports_an_error_keeps_the_last_good_value_and_stays_dirty():
    draft = make()
    message = draft.set("chat_font_size", 99)
    assert message and "between" in message
    assert draft.errors == {"chat_font_size": message}
    assert draft.has_errors
    assert draft.value("chat_font_size") == 13
    assert draft.dirty_keys == ("chat_font_size",)
    assert draft.set("chat_font_size", 14) is None
    assert draft.errors == {}
    assert draft.dirty_keys == ("chat_font_size",)


@pytest.mark.parametrize(
    ("key", "bad"),
    [("ui_scale", 1.3), ("language", "fr"), ("whisper_device", "tpu"), ("log_level", "LOUD")],
)
def test_each_model_rule_is_enforced(key, bad):
    draft = make()
    assert draft.set(key, bad)
    assert key in draft.errors


def test_blank_required_text_is_an_error_but_blank_optional_paths_are_fine():
    draft = make()
    assert draft.set("ollama_model", "   ")
    assert "ollama_model" in draft.errors
    assert draft.set("export_dir", "") is None
    assert draft.set("data_dir", "  ") is None


def test_ollama_url_is_validated_with_a_warning_for_remote_hosts():
    draft = make()
    assert draft.set("ollama_url", "ftp://x")
    assert "ollama_url" in draft.errors
    assert draft.set("ollama_url", "http://192.168.0.5:11434") is None
    assert "192.168.0.5" in draft.warnings["ollama_url"]
    draft.set("ollama_url", "http://localhost:11434")
    assert "ollama_url" not in draft.warnings


def test_restart_keys_list_only_changed_restart_settings_in_field_order():
    draft = make()
    draft.set("ptt_key", "f9")
    draft.set("language", "es")
    draft.set("appearance_mode", "dark")
    assert draft.dirty_keys == ("language", "appearance_mode", "ptt_key")
    assert draft.restart_keys == ("language", "ptt_key")


def test_locked_fields_cannot_be_edited():
    effective = dataclasses.replace(UserSettings(), ptt_key="right ctrl")
    draft = make(locked={"ptt_key"}, stored=UserSettings(ptt_key="f9"), effective=effective)
    message = draft.set("ptt_key", "x")
    assert message
    assert "ptt_key" not in draft.errors
    assert draft.value("ptt_key") == "right ctrl"
    assert draft.dirty_keys == ()
    assert draft.is_locked("ptt_key") and not draft.is_locked("language")


def test_to_settings_gives_locked_fields_their_stored_value():
    effective = dataclasses.replace(UserSettings(), ptt_key="right ctrl", language="es")
    draft = make(locked={"ptt_key"}, stored=UserSettings(ptt_key="f9"), effective=effective)
    result = draft.to_settings()
    assert result.ptt_key == "f9"
    assert result.language == "es"


def test_reset_to_defaults_keeps_locked_fields():
    effective = dataclasses.replace(
        UserSettings(), language="es", ptt_key="right ctrl", chat_font_size=18
    )
    draft = make(locked={"ptt_key"}, effective=effective)
    draft.set("chat_font_size", 99)  # an error pending: reset clears it
    draft.reset_to_defaults()
    assert draft.errors == {}
    assert draft.value("language") == "en"
    assert draft.value("chat_font_size") == 13
    assert draft.value("ptt_key") == "right ctrl"
    assert draft.dirty_keys == ("language", "chat_font_size")


def test_shortcuts_are_validated_and_stored_in_canonical_form():
    draft = make()
    assert draft.set("shortcut_settings", "ctrl+shift+p") is None
    assert draft.value("shortcut_settings") == "Ctrl+Shift+P"
    assert draft.set("shortcut_settings", "banana")
    assert "shortcut_settings" in draft.errors


def test_blocking_shortcut_conflicts_become_errors_on_every_involved_action():
    draft = make()
    assert draft.set("shortcut_chat_tab", "Ctrl+E") is None
    assert set(draft.errors) == {"shortcut_chat_tab", "shortcut_end_session"}
    assert draft.has_errors
    draft.set("shortcut_chat_tab", "Ctrl+1")
    assert draft.errors == {}
    draft.set("shortcut_settings", "Ctrl+C")  # reserved
    assert set(draft.errors) == {"shortcut_settings"}
    draft.set("shortcut_settings", "X")  # no Ctrl/Alt
    assert set(draft.errors) == {"shortcut_settings"}


def test_invalid_shortcut_loaded_from_a_file_is_reported():
    stored = dataclasses.replace(UserSettings(), shortcut_settings="nonsense")
    assert set(make(stored=stored, effective=stored).errors) == {"shortcut_settings"}


def test_ptt_overlap_is_a_warning_not_an_error():
    draft = make()
    draft.set("ptt_key", "e")
    assert draft.errors == {}
    assert "shortcut_end_session" in draft.warnings
    assert "ptt_key" in draft.warnings
    draft.set("ptt_key", "v")
    assert "shortcut_end_session" not in draft.warnings


def test_unknown_keys_are_rejected():
    draft = make()
    with pytest.raises(KeyError):
        draft.set("no_such_setting", 1)
    with pytest.raises(KeyError):
        draft.value("no_such_setting")
