"""Description of every row of the Settings window, plus accent-blind search (pure).

Each ``SettingSpec`` names its label and help as i18n keys; the window builds its
pages from ``REGISTRY`` so adding a setting means adding one spec and its texts.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from ..i18n import en
from .model import ENV_VARS, RESTART_FIELDS


class Category(Enum):
    """Sidebar sections, in display order."""

    GENERAL = "general"
    APPEARANCE = "appearance"
    AUDIO = "audio"
    STORAGE = "storage"
    SHORTCUTS = "shortcuts"
    ADVANCED = "advanced"


class Control(Enum):
    """Kind of widget a row uses."""

    SWITCH = "switch"
    CHOICE = "choice"
    SLIDER = "slider"
    TEXT = "text"
    COMBO = "combo"
    PATH = "path"
    KEY = "key"
    SHORTCUT = "shortcut"
    ACTION = "action"


@dataclass(frozen=True)
class SettingSpec:
    """One row: a ``UserSettings`` field or an action button."""

    key: str
    category: Category
    label: str  # i18n key
    help: str  # i18n key
    control: Control
    options: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    restart: bool = False
    env_var: str | None = None
    danger: bool = False


ACTION_KEYS = frozenset({
    "open_data_folder", "export_report", "export_mistakes", "clear_logs", "clear_mistakes",
    "test_connection", "open_logs_folder", "restore_defaults", "autostart",
})  # fmt: skip

TOGGLE_ACTIONS = frozenset({"autostart"})
"""Action rows drawn as an on/off switch (their state lives outside settings.json)."""

SearchResult = dict[Category, tuple[SettingSpec, ...]]


def option_label_key(key: str, value: str) -> str:
    """i18n key for the displayed name of ``value`` in the choice setting ``key``."""
    return f"option.{key}.{value}"


def _setting(
    key: str, category: Category, control: Control, keywords: tuple[str, ...],
    options: tuple[str, ...] = (),
) -> SettingSpec:  # fmt: skip
    return SettingSpec(
        key, category, f"setting.{key}.label", f"setting.{key}.help", control, options, keywords,
        restart=key in RESTART_FIELDS, env_var=ENV_VARS.get(key),
    )  # fmt: skip


def _action(
    key: str, category: Category, keywords: tuple[str, ...], danger: bool = False
) -> SettingSpec:
    return SettingSpec(
        key, category, f"setting.{key}.label", f"setting.{key}.help", Control.ACTION,
        keywords=keywords, danger=danger,
    )  # fmt: skip


_G, _A, _AU, _S, _SC, _AD = (
    Category.GENERAL, Category.APPEARANCE, Category.AUDIO,
    Category.STORAGE, Category.SHORTCUTS, Category.ADVANCED,
)  # fmt: skip
_SWITCH, _PATH, _SHORTCUT = Control.SWITCH, Control.PATH, Control.SHORTCUT
_SCALES = ("0.8", "0.9", "1.0", "1.1", "1.25", "1.5")
_WHISPER_MODELS = ("tiny", "base", "small", "medium", "large-v3", "distil-large-v3")
_CUE_WORDS = ("beep", "sound", "alert", "sonido", "pitido")
_PATH_WORDS = ("folder", "path", "directory", "carpeta", "ruta")
_KEY_WORDS = ("hotkey", "keyboard", "tecla", "atajo")

REGISTRY: tuple[SettingSpec, ...] = (
    # General
    _setting("language", _G, Control.CHOICE, ("locale", "region", "date", "time", "format",
             "idioma", "espanol", "spanish"), ("en", "es")),
    _setting("learner_name", _G, Control.TEXT, ("name", "nombre", "profile", "perfil", "me")),
    _setting("learner_pronouns", _G, Control.CHOICE, ("pronoun", "pronombre", "gender", "genero",
             "he", "she", "they", "profile", "perfil"), ("he", "she", "they")),
    _setting("track_pauses", _G, _SWITCH, ("hesitation", "fluency", "silence", "pause", "pausa",
             "fluidez", "silencio", "practice", "practicar")),
    _setting("suggest_natural", _G, _SWITCH, ("native", "natural", "rephrase", "phrasing", "style",
             "nativo", "frase", "sugerir")),
    _action("autostart", _G, ("startup", "boot", "sign in", "registry", "inicio", "windows")),
    # Appearance
    _setting("appearance_mode", _A, Control.CHOICE, ("dark mode", "light", "night", "theme",
             "oscuro", "claro", "modo", "system"), ("system", "light", "dark")),
    _setting("ui_scale", _A, Control.SLIDER, ("zoom", "size", "dpi", "escala"), _SCALES),
    _setting("chat_font_size", _A, Control.SLIDER, ("font", "text size", "letra", "fuente")),
    _setting("density", _A, Control.CHOICE, ("spacing", "padding", "compact", "densidad"),
             ("comfortable", "compact")),
    # Audio and notifications
    _setting("tts_enabled", _AU, _SWITCH, ("voice", "speech", "piper", "mute", "voz")),
    _setting("cue_record_start", _AU, _SWITCH, _CUE_WORDS),
    _setting("cue_record_stop", _AU, _SWITCH, _CUE_WORDS),
    _setting("cue_error", _AU, _SWITCH, _CUE_WORDS),
    _setting("notify_report", _AU, _SWITCH, ("toast", "popup", "notification", "alert", "aviso",
             "notificacion")),
    # Storage
    _setting("data_dir", _S, _PATH, _PATH_WORDS),
    _setting("export_dir", _S, _PATH, _PATH_WORDS + ("export", "exportar")),
    _action("open_data_folder", _S, ("explorer", "files", "archivos")),
    _action("export_report", _S, ("save", "download", "markdown", "exportar", "informe")),
    _action("export_mistakes", _S, ("save", "download", "csv", "exportar", "errores")),
    _action("clear_logs", _S, ("delete", "remove", "privacy", "cache", "temp", "borrar",
            "limpiar"), danger=True),
    _action("clear_mistakes", _S, ("delete", "remove", "privacy", "wipe", "borrar", "limpiar"),
            danger=True),
    # Shortcuts
    _setting("ptt_key", _SC, Control.KEY, _KEY_WORDS + ("push to talk", "microphone")),
    _setting("shortcut_end_session", _SC, _SHORTCUT, _KEY_WORDS),
    _setting("shortcut_settings", _SC, _SHORTCUT, _KEY_WORDS),
    _setting("shortcut_chat_tab", _SC, _SHORTCUT, _KEY_WORDS),
    _setting("shortcut_mistakes_tab", _SC, _SHORTCUT, _KEY_WORDS),
    # Advanced
    _setting("whisper_device", _AD, Control.CHOICE, ("gpu", "cuda", "cpu", "hardware",
             "acceleration", "aceleracion"), ("auto", "cuda", "cpu")),
    _setting("whisper_model", _AD, Control.COMBO, ("whisper", "stt", "recognition",
             "transcription", "modelo"), _WHISPER_MODELS),
    _setting("ollama_url", _AD, Control.TEXT, ("server", "host", "port", "localhost", "api")),
    _setting("ollama_model", _AD, Control.TEXT, ("llm", "llama", "model", "ai")),
    _action("test_connection", _AD, ("ping", "check", "network", "probar")),
    _setting("log_level", _AD, Control.CHOICE, ("debug", "verbose", "errors", "support",
             "soporte"), ("DEBUG", "INFO", "WARNING", "ERROR")),
    _action("open_logs_folder", _AD, ("troubleshooting", "support", "diagnostics", "soporte")),
    _action("restore_defaults", _AD, ("reset", "factory", "default", "restablecer")),
)


def by_category(category: Category) -> tuple[SettingSpec, ...]:
    """The specs of one section, in display order."""
    return tuple(spec for spec in REGISTRY if spec.category is category)


def _fold(text: str) -> str:
    """Lower-case and strip accents so ``Tamaño`` matches ``tamano``."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def search(query: str, translate: Callable[[str], str]) -> SearchResult:
    """Find specs whose texts contain every word of ``query``, grouped by category.

    Searched: the translated label and help, the English label, and the keywords.
    A blank query returns everything. Categories without matches are omitted.
    """
    words = _fold(query).split()
    result: SearchResult = {}
    for category in Category:
        found = tuple(
            spec for spec in by_category(category) if _matches(spec, words, translate)
        )
        if found:
            result[category] = found
    return result


def _matches(spec: SettingSpec, words: list[str], translate: Callable[[str], str]) -> bool:
    if not words:
        return True
    haystack = _fold(
        " ".join((
            translate(spec.label), translate(spec.help), en.STRINGS.get(spec.label, ""),
            *spec.keywords,
        ))
    )  # fmt: skip
    return all(word in haystack for word in words)
