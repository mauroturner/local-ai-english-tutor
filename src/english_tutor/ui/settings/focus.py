"""Best-effort keyboard focus for customtkinter controls that ignore Tab by default."""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

_FOCUS_COLOR = "#3B8ED0"


def enable_keyboard(widget: Any, activate: Callable[[], None]) -> None:
    """Let ``widget`` take focus with Tab and be activated with Space or Enter.

    customtkinter keeps the real Tk widget in a private attribute, so this may do
    nothing on other versions; it never raises.
    """
    try:
        target = getattr(widget, "_canvas", None) or widget
        target.configure(takefocus=1, highlightthickness=0, highlightcolor=_FOCUS_COLOR)

        def press(_event: Any) -> str:
            activate()
            return "break"  # keep Enter from also triggering Save

        for sequence in ("<space>", "<Return>"):
            target.bind(sequence, press)
        target.bind("<FocusIn>", lambda _e: target.configure(highlightthickness=2))
        target.bind("<FocusOut>", lambda _e: target.configure(highlightthickness=0))
    except (AttributeError, tk.TclError):
        logger.debug("Keyboard focus is not available for %r", widget, exc_info=True)
