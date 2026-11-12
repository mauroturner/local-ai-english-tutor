"""Precedence defaults < settings.json < TUTOR_* and the settings file location."""

from __future__ import annotations

import dataclasses

import pytest

from english_tutor.config import (
    PARSERS,
    ConfigError,
    check_between,
    load_config,
    resolve_settings_path,
)
from english_tutor.settings.model import UserSettings, settings_env


def test_overrides_replace_defaults(tmp_path):
    cfg = load_config({}, tmp_path, overrides={"TUTOR_PTT_KEY": "f9", "TUTOR_TTS": "0"})
    assert cfg.ptt_key == "f9"
    assert cfg.tts_enabled is False


def test_env_beats_overrides(tmp_path):
    env = {"TUTOR_PTT_KEY": "right ctrl"}
    overrides = {"TUTOR_PTT_KEY": "f9", "TUTOR_WHISPER_MODEL": "small"}
    cfg = load_config(env, tmp_path, overrides=overrides)
    assert cfg.ptt_key == "right ctrl"
    assert cfg.whisper_model == "small"


def test_blank_env_does_not_hide_an_override(tmp_path):
    cfg = load_config({"TUTOR_PTT_KEY": "   "}, tmp_path, overrides={"TUTOR_PTT_KEY": "f9"})
    assert cfg.ptt_key == "f9"


def test_without_overrides_behaviour_is_unchanged(tmp_path):
    assert load_config({}, tmp_path) == load_config({}, tmp_path, overrides=None)
    assert load_config({}, tmp_path) == load_config({}, tmp_path, overrides={})


def test_invalid_env_still_raises_with_overrides(tmp_path):
    with pytest.raises(ConfigError, match="TUTOR_TTS"):
        load_config({"TUTOR_TTS": "maybe"}, tmp_path, overrides={"TUTOR_TTS": "1"})


def test_settings_env_round_trips_into_the_config(tmp_path):
    s = dataclasses.replace(
        UserSettings(),
        ptt_key="f9",
        whisper_device="cpu",
        data_dir=str(tmp_path / "d"),
        ollama_url="http://h:1",
    )
    cfg = load_config({}, tmp_path, overrides=settings_env(s))
    assert (cfg.ptt_key, cfg.whisper_device, cfg.ollama_url) == ("f9", "cpu", "http://h:1")
    assert cfg.data_dir == tmp_path / "d"


def test_parsers_are_the_shared_config_parsers():
    assert PARSERS["int"]({"X": "4"}, "X", 1) == 4
    assert PARSERS["bool"]({"X": "off"}, "X", True) is False
    assert PARSERS["str"]({}, "X", "d") == "d"
    with pytest.raises(ConfigError, match="X must be an integer"):
        PARSERS["int"]({"X": "no"}, "X", 1)


def test_check_between():
    assert check_between("size", 10, 10, 22) == 10
    with pytest.raises(ConfigError, match="size must be between 10 and 22, got 23"):
        check_between("size", 23, 10, 22)
    with pytest.raises(ConfigError):
        check_between("size", 9, 10, 22)


def test_settings_path_defaults_to_the_data_folder(tmp_path):
    assert resolve_settings_path({}, tmp_path) == tmp_path / "data" / "settings.json"


def test_settings_path_follows_tutor_data_dir(tmp_path):
    env = {"TUTOR_DATA_DIR": str(tmp_path / "mine")}
    assert resolve_settings_path(env, tmp_path) == tmp_path / "mine" / "settings.json"


def test_settings_file_variable_wins(tmp_path):
    env = {"TUTOR_DATA_DIR": str(tmp_path / "mine"), "TUTOR_SETTINGS_FILE": str(tmp_path / "x.json")}
    assert resolve_settings_path(env, tmp_path) == tmp_path / "x.json"
    blank = {"TUTOR_SETTINGS_FILE": "  "}
    assert resolve_settings_path(blank, tmp_path) == tmp_path / "data" / "settings.json"
