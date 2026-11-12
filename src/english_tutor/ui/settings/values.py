"""Pure display helpers for the Settings rows (no Tk)."""

from __future__ import annotations

from collections.abc import Sequence

from ...i18n import en, t
from ...settings.registry import option_label_key


def format_scale(value: float) -> str:
    """``1.25`` -> ``125%``."""
    return f"{round(float(value) * 100)}%"


def index_of_nearest(options: Sequence[float], value: float) -> int:
    """Index of the option closest to ``value`` (for slider positions)."""
    return min(range(len(options)), key=lambda i: abs(options[i] - value))


def option_labels(key: str, options: Sequence[str]) -> list[str]:
    """Displayed names of the options of choice setting ``key`` in the active language.

    Options without a translation (for example log levels) are shown as they are.
    """
    labels = []
    for value in options:
        label_key = option_label_key(key, value)
        labels.append(t(label_key) if label_key in en.STRINGS else value)
    return labels


def value_for_label(key: str, options: Sequence[str], label: str) -> str | None:
    """The option whose displayed name is ``label`` (None if there is none)."""
    for value, shown in zip(options, option_labels(key, options), strict=True):
        if shown == label:
            return value
    return None
