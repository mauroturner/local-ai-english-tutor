"""Applying settings that take effect without a restart."""

from __future__ import annotations

from collections.abc import Callable, Iterable

import customtkinter as ctk

from ...settings.model import UserSettings
from .. import theme

LIVE_KEYS = ("appearance_mode", "ui_scale", "chat_font_size", "log_level")
PREVIEW_KEYS = ("appearance_mode", "chat_font_size")
"""Settings shown immediately while editing and reverted by Cancel."""


def apply_live(
    changed: Iterable[str], settings: UserSettings, apply_log_level: Callable[[str], None]
) -> None:
    """Apply the live settings among ``changed`` using the values in ``settings``."""
    keys = set(changed)
    if "appearance_mode" in keys:
        ctk.set_appearance_mode(settings.appearance_mode)
    if "ui_scale" in keys:
        ctk.set_widget_scaling(settings.ui_scale)
    if "chat_font_size" in keys:
        theme.set_chat_font_size(settings.chat_font_size)
    if "log_level" in keys:
        apply_log_level(settings.log_level)
