"""UserSettings parsing, validation, env mapping and URL checks (pure, no I/O)."""

from __future__ import annotations

import dataclasses

import pytest

from english_tutor.settings.model import (
    ENV_VARS,
    RESTART_FIELDS,
    UserSettings,
    locked_fields,
    parse_settings,
    settings_env,
    to_json_dict,
    validate_ollama_url,
)


def test_defaults_match_the_plan():
    s = UserSettings()
    assert (s.language, s.appearance_mode, s.ui_scale, s.chat_font_size) == ("en", "system", 1.0, 13)
    assert (s.density, s.tts_enabled, s.notify_report) == ("comfortable", True, True)
    assert (s.cue_record_start, s.cue_record_stop, s.cue_error) == (True, True, True)
    assert (s.data_dir, s.export_dir, s.ptt_key) == ("", "", "v")
    assert s.shortcut_end_session == "Ctrl+E"
    assert s.shortcut_settings == "Ctrl+,"
    assert s.shortcut_chat_tab == "Ctrl+1"
    assert s.shortcut_mistakes_tab == "Ctrl+2"
    assert (s.whisper_device, s.whisper_model) == ("auto", "large-v3")
    assert s.ollama_url == "http://localhost:11434"
    assert s.ollama_model == "llama3:8b-instruct-q4_K_M"
    assert s.log_level == "INFO"


def test_empty_mapping_gives_defaults_without_warnings():
    assert parse_settings({}) == (UserSettings(), ())


def test_round_trip_through_json_dict():
    custom = dataclasses.replace(
        UserSettings(),
        language="es",
        appearance_mode="dark",
        ui_scale=1.25,
        chat_font_size=16,
        tts_enabled=False,
        ptt_key="right ctrl",
        log_level="DEBUG",
    )
    parsed, warnings = parse_settings(to_json_dict(custom))
    assert parsed == custom
    assert warnings == ()


def test_unknown_keys_are_ignored():
    parsed, warnings = parse_settings({"future_option": 1, "language": "es"})
    assert parsed.language == "es"
    assert warnings == ()


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("language", "fr"),
        ("appearance_mode", "purple"),
        ("ui_scale", 3.0),
        ("ui_scale", "big"),
        ("chat_font_size", 99),
        ("chat_font_size", "abc"),
        ("chat_font_size", True),
        ("density", "tiny"),
        ("tts_enabled", "maybe"),
        ("cue_error", 5),
        ("whisper_device", "tpu"),
        ("log_level", "LOUD"),
        ("ollama_url", "ftp://host"),
        ("ptt_key", ["v"]),
        ("shortcut_end_session", 7),
    ],
)
def test_each_invalid_field_falls_back_alone_with_a_warning(field, bad):
    default = getattr(UserSettings(), field)
    others = {"language": "es", "chat_font_size": 15}
    others.pop(field, None)
    parsed, warnings = parse_settings({**others, field: bad})
    assert getattr(parsed, field) == default
    assert len(warnings) == 1
    assert field in warnings[0]
    for name, value in others.items():
        assert getattr(parsed, name) == value


def test_choice_values_are_case_insensitive_and_normalised():
    parsed, warnings = parse_settings({"whisper_device": "CPU", "log_level": "debug"})
    assert (parsed.whisper_device, parsed.log_level) == ("cpu", "DEBUG")
    assert warnings == ()


def test_string_forms_are_accepted_for_numbers_and_bools():
    raw = {"chat_font_size": "14", "tts_enabled": "off", "ui_scale": "1.1"}
    parsed, warnings = parse_settings(raw)
    assert (parsed.chat_font_size, parsed.tts_enabled, parsed.ui_scale) == (14, False, 1.1)
    assert warnings == ()


def test_blank_string_uses_the_default_silently():
    parsed, warnings = parse_settings({"ollama_model": "   "})
    assert parsed.ollama_model == UserSettings().ollama_model
    assert warnings == ()


def test_ollama_url_is_stripped_of_a_trailing_slash():
    parsed, _ = parse_settings({"ollama_url": " http://host:1234/ "})
    assert parsed.ollama_url == "http://host:1234"


# ----------------------------------------------------------------- env mapping
def test_env_vars_map_the_documented_fields():
    assert ENV_VARS == {
        "tts_enabled": "TUTOR_TTS",
        "data_dir": "TUTOR_DATA_DIR",
        "ptt_key": "TUTOR_PTT_KEY",
        "whisper_device": "TUTOR_WHISPER_DEVICE",
        "whisper_model": "TUTOR_WHISPER_MODEL",
        "ollama_url": "TUTOR_OLLAMA_URL",
        "ollama_model": "TUTOR_OLLAMA_MODEL",
        "log_level": "TUTOR_LOG_LEVEL",
    }


def test_restart_fields_are_known_settings():
    names = {f.name for f in dataclasses.fields(UserSettings)}
    assert RESTART_FIELDS <= names
    assert {"language", "density", "ptt_key", "ollama_url"} <= RESTART_FIELDS
    assert "appearance_mode" not in RESTART_FIELDS


def test_locked_fields_are_the_non_empty_env_vars():
    env = {"TUTOR_PTT_KEY": "f9", "TUTOR_TTS": "  ", "TUTOR_LOG_LEVEL": "debug", "OTHER": "x"}
    assert locked_fields(env) == frozenset({"ptt_key", "log_level"})
    assert locked_fields({}) == frozenset()


def test_settings_env_formats_values_and_omits_an_empty_data_dir():
    env = settings_env(dataclasses.replace(UserSettings(), tts_enabled=False))
    assert env["TUTOR_TTS"] == "0"
    assert env["TUTOR_PTT_KEY"] == "v"
    assert env["TUTOR_OLLAMA_URL"] == "http://localhost:11434"
    assert "TUTOR_DATA_DIR" not in env
    assert settings_env(UserSettings())["TUTOR_TTS"] == "1"
    with_dir = settings_env(dataclasses.replace(UserSettings(), data_dir="D:\\tutor"))
    assert with_dir["TUTOR_DATA_DIR"] == "D:\\tutor"
    assert all(isinstance(v, str) for v in env.values())


# ------------------------------------------------------------- URL validation
@pytest.mark.parametrize(
    "url", ["http://localhost:11434", "https://127.0.0.1:8080/api", "http://[::1]:11434"]
)
def test_local_urls_are_valid_without_warning(url):
    assert validate_ollama_url(url) == (None, None)


def test_remote_host_is_a_warning_not_an_error():
    error, warning = validate_ollama_url("http://192.168.1.20:11434")
    assert error is None
    assert warning and "192.168.1.20" in warning


@pytest.mark.parametrize(
    "url",
    ["", "   ", "localhost:11434", "ftp://localhost", "http://", "http://host?x=1", "http://host:99999"],
)
def test_bad_urls_return_an_error(url):
    error, warning = validate_ollama_url(url)
    assert error
    assert warning is None
