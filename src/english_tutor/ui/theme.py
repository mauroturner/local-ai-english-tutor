"""Colours, spacing and fonts shared by the UI widgets.

Every colour is a ``(light, dark)`` pair, which customtkinter resolves for the
active appearance mode. Importing this module does not need a Tk root; the
shared body font is created lazily by ``body_font``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

COLOR_THEME = "blue"

# --------------------------------------------------------------------- colours
TEXT = ("gray10", "gray90")
MUTED_TEXT = ("gray35", "gray65")
CHAT_BG = ("white", "gray14")
TUTOR_BUBBLE = ("#E3F2FD", "#1E3A5F")
USER_BUBBLE = ("#F5F5F5", "#2B2B2B")
CORRECTION_BUBBLE = ("#FFF3CD", "#4A3F12")
NOTICE_TEXT = ("#B26A00", "#FFB74D")
REPORT_BG = ("#EDE7F6", "#2E2748")
PRACTICE_OK = ("#E8F5E9", "#1B3A22")
PRACTICE_RETRY = ("#FDECEA", "#4A2220")
BADGE_MAJOR = ("#D32F2F", "#C62828")
BADGE_MINOR = ("#B26A00", "#9A5B00")
BADGE_PAUSE = ("#1565C0", "#1E5AA8")
HOVER = ("gray85", "gray25")
TOOLTIP_BG = ("gray20", "gray85")
TOOLTIP_TEXT = ("gray95", "gray10")
SIDEBAR_BG = ("gray92", "gray16")
SELECTED = ("gray80", "gray28")
ROW_BG = ("gray95", "gray19")
PILL_BG = ("#FFE0B2", "#5D3A00")
PILL_TEXT = ("#8A4B00", "#FFCC80")
ERROR_TEXT = ("#C62828", "#EF9A9A")
OK_TEXT = ("#2E7D32", "#81C784")
CHIP_GREEN = ("#2E7D32", "#2E7D32")
CHIP_RED = ("#C62828", "#D32F2F")
CHIP_AMBER = ("#B26A00", "#B26A00")

COLOR_NAMES = (
    "TEXT", "MUTED_TEXT", "CHAT_BG", "TUTOR_BUBBLE", "USER_BUBBLE", "CORRECTION_BUBBLE",
    "NOTICE_TEXT", "REPORT_BG", "PRACTICE_OK", "PRACTICE_RETRY", "BADGE_MAJOR", "BADGE_MINOR",
    "BADGE_PAUSE", "HOVER", "TOOLTIP_BG", "TOOLTIP_TEXT", "SIDEBAR_BG", "SELECTED", "ROW_BG",
    "PILL_BG",    "PILL_TEXT", "ERROR_TEXT", "OK_TEXT", "CHIP_GREEN", "CHIP_RED", "CHIP_AMBER",
)  # fmt: skip

# --------------------------------------------------------------------- spacing
SPACE_XS, SPACE_S, SPACE_M, SPACE_L, SPACE_XL = 4, 8, 12, 16, 24


@dataclass(frozen=True)
class Spacing:
    """Spacing scale in pixels for one interface density."""

    xs: int
    s: int
    m: int
    l: int  # noqa: E741 - mirrors SPACE_L
    xl: int


def spacing(density: str) -> Spacing:
    """The scale for ``comfortable`` (default) or ``compact``."""
    if density == "compact":
        return Spacing(2, 5, 8, 11, 16)
    return Spacing(SPACE_XS, SPACE_S, SPACE_M, SPACE_L, SPACE_XL)


# ----------------------------------------------------------------------- fonts
FAMILY = "Segoe UI"
FONT_TITLE = (FAMILY, 20, "bold")
FONT_HEADING = (FAMILY, 14, "bold")
FONT_BODY = (FAMILY, 13)
FONT_HINT = (FAMILY, 11)
DEFAULT_CHAT_FONT_SIZE = 13
BUBBLE_WRAP = 450

_body_font: Any = None


def body_font() -> Any:
    """The shared chat font; changing its size restyles every bubble at once.

    Created on first use, so a Tk root must already exist.
    """
    global _body_font
    if _body_font is None:
        import customtkinter as ctk

        _body_font = ctk.CTkFont(family=FAMILY, size=DEFAULT_CHAT_FONT_SIZE)
    return _body_font


def set_chat_font_size(size: int) -> None:
    """Resize the chat font live."""
    body_font().configure(size=size)


def apply_appearance(mode: str, scale: float) -> None:
    """Set light/dark/system mode and the widget scale; call before the root exists."""
    import customtkinter as ctk

    ctk.set_appearance_mode(mode)
    ctk.set_widget_scaling(scale)
