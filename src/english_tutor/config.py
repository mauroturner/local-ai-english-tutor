"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    """An environment variable has an invalid value."""


@dataclass(frozen=True)
class AppConfig:
    """Immutable settings for the whole application."""

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:8b-instruct-q4_K_M"
    ollama_timeout_s: float = 120.0
    llm_temperature: float = 0.5
    history_exchanges: int = 6
    whisper_model: str = "large-v3"
    whisper_device: str = "auto"
    whisper_compute_type: str = "float16"
    whisper_cpu_compute_type: str = "int8"
    whisper_beam_size: int = 5
    tts_enabled: bool = True
    piper_exe: Path | None = None
    piper_voice: Path = Path("piper/voices/en_US-lessac-medium.onnx")
    ptt_key: str = "v"
    log_level: str = "INFO"


def _int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


def _non_negative(env: Mapping[str, str], name: str, default: int) -> int:
    value = _int(env, name, default)
    if value < 0:
        raise ConfigError(f"{name} must be 0 or greater, got {value}")
    return value


def _float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc


def _bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ConfigError(f"{name} must be a boolean (1/0, true/false), got {raw!r}")


def _str(env: Mapping[str, str], name: str, default: str) -> str:
    raw = env.get(name)
    return raw.strip() if raw is not None and raw.strip() else default


def default_project_root() -> Path:
    """Repository root when running from source, else the current directory."""
    candidate = Path(__file__).resolve().parents[2]
    return candidate if (candidate / "pyproject.toml").exists() else Path.cwd()


def resolve_piper_exe(env: Mapping[str, str], root: Path) -> Path | None:
    """Find the Piper binary.

    Order: TUTOR_PIPER_EXE, <root>/piper/piper.exe,
    <root>/english_teacher/piper/piper.exe, <cwd>/piper/piper.exe.
    """
    explicit = env.get("TUTOR_PIPER_EXE", "").strip()
    if explicit:
        path = Path(explicit)
        return path if path.is_file() else None
    candidates = (
        root / "piper" / "piper.exe",
        root / "english_teacher" / "piper" / "piper.exe",
        Path.cwd() / "piper" / "piper.exe",
    )
    return next((c for c in candidates if c.is_file()), None)


def load_config(
    env: Mapping[str, str] | None = None, project_root: Path | None = None
) -> AppConfig:
    """Build an AppConfig from ``env`` (defaults to ``os.environ``)."""
    env = os.environ if env is None else env
    root = project_root if project_root is not None else default_project_root()
    exe = resolve_piper_exe(env, root)
    piper_dir = exe.parent if exe is not None else root / "piper"
    voice_raw = env.get("TUTOR_PIPER_VOICE", "").strip()
    voice = Path(voice_raw) if voice_raw else piper_dir / "voices" / "en_US-lessac-medium.onnx"
    return AppConfig(
        ollama_url=_str(env, "TUTOR_OLLAMA_URL", "http://localhost:11434").rstrip("/"),
        ollama_model=_str(env, "TUTOR_OLLAMA_MODEL", "llama3:8b-instruct-q4_K_M"),
        ollama_timeout_s=_float(env, "TUTOR_OLLAMA_TIMEOUT", 120.0),
        llm_temperature=_float(env, "TUTOR_LLM_TEMPERATURE", 0.5),
        history_exchanges=_non_negative(env, "TUTOR_HISTORY_EXCHANGES", 6),
        whisper_model=_str(env, "TUTOR_WHISPER_MODEL", "large-v3"),
        whisper_device=_str(env, "TUTOR_WHISPER_DEVICE", "auto").lower(),
        whisper_compute_type=_str(env, "TUTOR_WHISPER_COMPUTE_TYPE", "float16"),
        whisper_cpu_compute_type=_str(env, "TUTOR_WHISPER_CPU_COMPUTE_TYPE", "int8"),
        whisper_beam_size=_int(env, "TUTOR_WHISPER_BEAM_SIZE", 5),
        tts_enabled=_bool(env, "TUTOR_TTS", True),
        piper_exe=exe,
        piper_voice=voice,
        ptt_key=_str(env, "TUTOR_PTT_KEY", "v"),
        log_level=_str(env, "TUTOR_LOG_LEVEL", "INFO").upper(),
    )
