"""The settings the user can change, with validation and the TUTOR_* mapping.

Precedence is defaults < settings.json < ``TUTOR_*`` environment variables.
``parse_settings`` validates the stored values, ``settings_env`` turns them into
overrides for ``config.load_config`` and ``locked_fields`` says which settings an
environment variable currently pins.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from ..config import PARSERS, ConfigError, check_between


@dataclass(frozen=True)
class UserSettings:
    """Every user setting with its default (see docs/configuration.md)."""

    language: str = "en"
    appearance_mode: str = "system"
    ui_scale: float = 1.0
    chat_font_size: int = 13
    density: str = "comfortable"
    tts_enabled: bool = True
    cue_record_start: bool = True
    cue_record_stop: bool = True
    cue_error: bool = True
    notify_report: bool = True
    data_dir: str = ""
    export_dir: str = ""
    ptt_key: str = "v"
    shortcut_end_session: str = "Ctrl+E"
    shortcut_settings: str = "Ctrl+,"
    shortcut_chat_tab: str = "Ctrl+1"
    shortcut_mistakes_tab: str = "Ctrl+2"
    whisper_device: str = "auto"
    whisper_model: str = "large-v3"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:8b-instruct-q4_K_M"
    log_level: str = "INFO"


ENV_VARS: dict[str, str] = {
    "tts_enabled": "TUTOR_TTS",
    "data_dir": "TUTOR_DATA_DIR",
    "ptt_key": "TUTOR_PTT_KEY",
    "whisper_device": "TUTOR_WHISPER_DEVICE",
    "whisper_model": "TUTOR_WHISPER_MODEL",
    "ollama_url": "TUTOR_OLLAMA_URL",
    "ollama_model": "TUTOR_OLLAMA_MODEL",
    "log_level": "TUTOR_LOG_LEVEL",
}
"""Settings that a ``TUTOR_*`` variable can override (field -> variable)."""

RESTART_FIELDS: frozenset[str] = frozenset(
    {
        "language",
        "density",
        "tts_enabled",
        "data_dir",
        "ptt_key",
        "whisper_device",
        "whisper_model",
        "ollama_url",
        "ollama_model",
    }
)
"""Settings that only take effect after the app restarts."""

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_SCALES = (0.8, 0.9, 1.0, 1.1, 1.25, 1.5)


@dataclass(frozen=True)
class _Rule:
    kind: str  # key of config.PARSERS
    options: tuple[Any, ...] = ()  # allowed values (after normalisation); empty = any
    lower: bool = False
    upper: bool = False
    bounds: tuple[int, int] | None = None


_RULES: dict[str, _Rule] = {
    "language": _Rule("str", ("en", "es"), lower=True),
    "appearance_mode": _Rule("str", ("system", "light", "dark"), lower=True),
    "ui_scale": _Rule("float", _SCALES),
    "chat_font_size": _Rule("int", bounds=(10, 22)),
    "density": _Rule("str", ("comfortable", "compact"), lower=True),
    "whisper_device": _Rule("str", ("auto", "cuda", "cpu"), lower=True),
    "log_level": _Rule("str", ("DEBUG", "INFO", "WARNING", "ERROR"), upper=True),
}


def _as_text(name: str, raw: Any, kind: str) -> str:
    """Turn a JSON value into the string form the shared parsers expect."""
    if kind == "bool" and isinstance(raw, bool):
        return "1" if raw else "0"
    if kind == "int" and isinstance(raw, int) and not isinstance(raw, bool):
        return str(raw)
    if kind == "float" and isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return repr(float(raw))
    if isinstance(raw, str):
        return raw
    raise ConfigError(f"{name} has the wrong type, got {raw!r}")


def _parse_field(name: str, raw: Any, default: Any) -> Any:
    rule = _RULES.get(name) or _Rule("bool" if isinstance(default, bool) else "str")
    text = _as_text(name, raw, rule.kind)
    value = PARSERS[rule.kind]({name: text}, name, default)
    if isinstance(value, str):
        value = value.lower() if rule.lower else value.upper() if rule.upper else value
    if rule.options and value not in rule.options:
        choices = ", ".join(str(o) for o in rule.options)
        raise ConfigError(f"{name} must be one of {choices}, got {raw!r}")
    if rule.bounds is not None:
        check_between(name, value, *rule.bounds)
    if name == "ollama_url":
        value = _checked_url(name, value)
    return value


def _checked_url(name: str, value: str) -> str:
    error, _ = validate_ollama_url(value)
    if error:
        raise ConfigError(f"{name}: {error}")
    return value.rstrip("/")


def parse_settings(raw: Mapping[str, Any]) -> tuple[UserSettings, tuple[str, ...]]:
    """Validate stored values; each bad field falls back alone, with a warning.

    Unknown keys are ignored so files written by a newer version still load.
    """
    defaults = UserSettings()
    values: dict[str, Any] = {}
    warnings: list[str] = []
    for field in dataclasses.fields(UserSettings):
        if field.name not in raw:
            continue
        default = getattr(defaults, field.name)
        try:
            values[field.name] = _parse_field(field.name, raw[field.name], default)
        except ConfigError as exc:
            warnings.append(f"Ignored invalid setting: {exc}; using {default!r}.")
    return dataclasses.replace(defaults, **values), tuple(warnings)


def to_json_dict(settings: UserSettings) -> dict[str, Any]:
    """The plain mapping stored in settings.json."""
    return dataclasses.asdict(settings)


def locked_fields(env: Mapping[str, str]) -> frozenset[str]:
    """Settings currently pinned by a non-empty ``TUTOR_*`` variable."""
    return frozenset(f for f, var in ENV_VARS.items() if env.get(var, "").strip())


def settings_env(settings: UserSettings) -> dict[str, str]:
    """The saved values as ``TUTOR_*`` overrides for ``config.load_config``."""
    out: dict[str, str] = {}
    for field, var in ENV_VARS.items():
        value = getattr(settings, field)
        if isinstance(value, bool):
            out[var] = "1" if value else "0"
        elif value != "":
            out[var] = str(value)
    return out


def validate_ollama_url(text: str) -> tuple[str | None, str | None]:
    """Check an Ollama base URL; returns ``(error, warning)``.

    Only ``http``/``https`` URLs with a host and no query or fragment are valid.
    A host other than localhost is allowed but gets a warning, because the app
    is designed to keep everything on this machine.
    """
    url = text.strip()
    if not url:
        return "Enter a URL such as http://localhost:11434.", None
    try:
        parts = urlsplit(url)
        host = parts.hostname
        parts.port  # noqa: B018 - raises ValueError for an invalid port
    except ValueError:
        return "That is not a valid URL.", None
    if parts.scheme not in ("http", "https"):
        return "The URL must start with http:// or https://.", None
    if not host:
        return "The URL must include a host name.", None
    if parts.query or parts.fragment:
        return "The URL must not contain a query or fragment.", None
    if host.lower() not in _LOCAL_HOSTS:
        return None, f"{host} is not on this computer; your speech text will be sent there."
    return None, None
