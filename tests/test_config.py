"""Configuration loading and Piper resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from english_tutor.config import ConfigError, key_label, load_config, resolve_piper_exe


def make_exe(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def test_defaults(tmp_path):
    cfg = load_config({}, tmp_path)
    assert cfg.ollama_url == "http://localhost:11434"
    assert cfg.ollama_model == "llama3:8b-instruct-q4_K_M"
    assert cfg.ollama_timeout_s == 120
    assert cfg.llm_temperature == 0.5
    assert cfg.history_exchanges == 6
    assert cfg.whisper_model == "large-v3"
    assert cfg.whisper_device == "auto"
    assert cfg.whisper_compute_type == "float16"
    assert cfg.whisper_cpu_compute_type == "int8"
    assert cfg.whisper_beam_size == 5
    assert cfg.tts_enabled is True
    assert cfg.ptt_key == "v"
    assert cfg.ptt_label == "V"
    assert cfg.log_level == "INFO"
    assert cfg.piper_exe is None
    assert cfg.data_dir == tmp_path / "data"


def test_env_overrides(tmp_path):
    env = {
        "TUTOR_OLLAMA_URL": "http://h:1/",
        "TUTOR_OLLAMA_MODEL": "qwen",
        "TUTOR_OLLAMA_TIMEOUT": "30",
        "TUTOR_LLM_TEMPERATURE": "0.2",
        "TUTOR_HISTORY_EXCHANGES": "3",
        "TUTOR_WHISPER_MODEL": "small",
        "TUTOR_WHISPER_DEVICE": "CPU",
        "TUTOR_WHISPER_BEAM_SIZE": "1",
        "TUTOR_TTS": "0",
        "TUTOR_PTT_KEY": "f9",
        "TUTOR_LOG_LEVEL": "debug",
    }
    cfg = load_config(env, tmp_path)
    assert cfg.ollama_url == "http://h:1"
    assert cfg.ollama_model == "qwen"
    assert cfg.ollama_timeout_s == 30
    assert cfg.llm_temperature == 0.2
    assert cfg.history_exchanges == 3
    assert cfg.whisper_model == "small"
    assert cfg.whisper_device == "cpu"
    assert cfg.whisper_beam_size == 1
    assert cfg.tts_enabled is False
    assert cfg.ptt_key == "f9"
    assert cfg.log_level == "DEBUG"


@pytest.mark.parametrize(
    "name,value",
    [
        ("TUTOR_HISTORY_EXCHANGES", "many"),
        ("TUTOR_WHISPER_BEAM_SIZE", "1.5"),
        ("TUTOR_OLLAMA_TIMEOUT", "soon"),
        ("TUTOR_TTS", "maybe"),
    ],
)
def test_bad_values_raise_config_error_naming_variable(tmp_path, name, value):
    with pytest.raises(ConfigError, match=name):
        load_config({name: value}, tmp_path)


@pytest.mark.parametrize(
    "name,value",
    [
        ("TUTOR_OLLAMA_TIMEOUT", "0"),
        ("TUTOR_OLLAMA_TIMEOUT", "-1"),
        ("TUTOR_OLLAMA_TIMEOUT", "nan"),
        ("TUTOR_OLLAMA_TIMEOUT", "inf"),
        ("TUTOR_LLM_TEMPERATURE", "-0.1"),
        ("TUTOR_LLM_TEMPERATURE", "nan"),
        ("TUTOR_WHISPER_BEAM_SIZE", "0"),
    ],
)
def test_out_of_range_values_raise_config_error_naming_variable(tmp_path, name, value):
    with pytest.raises(ConfigError, match=name):
        load_config({name: value}, tmp_path)


def test_range_edges_are_accepted(tmp_path):
    cfg = load_config(
        {
            "TUTOR_LLM_TEMPERATURE": "0",
            "TUTOR_WHISPER_BEAM_SIZE": "1",
            "TUTOR_OLLAMA_TIMEOUT": "0.5",
            "TUTOR_HISTORY_EXCHANGES": "0",
        },
        tmp_path,
    )
    assert cfg.llm_temperature == 0
    assert cfg.whisper_beam_size == 1
    assert cfg.ollama_timeout_s == 0.5
    assert cfg.history_exchanges == 0


@pytest.mark.parametrize(
    "key,label",
    [("right ctrl", "Right Ctrl"), ("v", "V"), ("f9", "F9"), ("left  alt", "Left Alt")],
)
def test_key_label(key, label):
    assert key_label(key) == label


def test_ptt_label_follows_configured_key(tmp_path):
    assert load_config({"TUTOR_PTT_KEY": "f9"}, tmp_path).ptt_label == "F9"


def test_data_dir_override(tmp_path):
    cfg = load_config({"TUTOR_DATA_DIR": str(tmp_path / "elsewhere")}, tmp_path)
    assert cfg.data_dir == tmp_path / "elsewhere"


def test_piper_explicit_env_wins(tmp_path):
    explicit = make_exe(tmp_path / "custom" / "p.exe")
    make_exe(tmp_path / "piper" / "piper.exe")
    assert resolve_piper_exe({"TUTOR_PIPER_EXE": str(explicit)}, tmp_path) == explicit


def test_piper_explicit_missing_file_is_not_silently_replaced(tmp_path):
    make_exe(tmp_path / "piper" / "piper.exe")
    assert resolve_piper_exe({"TUTOR_PIPER_EXE": str(tmp_path / "nope.exe")}, tmp_path) is None


def test_piper_recommended_location_before_legacy(tmp_path):
    recommended = make_exe(tmp_path / "piper" / "piper.exe")
    make_exe(tmp_path / "english_teacher" / "piper" / "piper.exe")
    assert resolve_piper_exe({}, tmp_path) == recommended


def test_piper_legacy_location(tmp_path):
    legacy = make_exe(tmp_path / "english_teacher" / "piper" / "piper.exe")
    assert resolve_piper_exe({}, tmp_path) == legacy


def test_piper_cwd_fallback(tmp_path, monkeypatch):
    root, cwd = tmp_path / "root", tmp_path / "cwd"
    root.mkdir()
    found = make_exe(cwd / "piper" / "piper.exe")
    monkeypatch.chdir(cwd)
    assert resolve_piper_exe({}, root).resolve() == found.resolve()


def test_piper_not_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert resolve_piper_exe({}, tmp_path) is None


def test_voice_defaults_next_to_exe_and_can_be_overridden(tmp_path):
    exe = make_exe(tmp_path / "piper" / "piper.exe")
    cfg = load_config({}, tmp_path)
    assert cfg.piper_exe == exe
    assert cfg.piper_voice == exe.parent / "voices" / "en_US-lessac-medium.onnx"
    custom = load_config({"TUTOR_PIPER_VOICE": "x/voice.onnx"}, tmp_path)
    assert custom.piper_voice == Path("x/voice.onnx")
