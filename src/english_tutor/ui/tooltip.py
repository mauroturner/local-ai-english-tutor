"""Hover tooltip for any widget, shown after a short delay."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from . import theme

DELAY_MS = 500


class Tooltip:
    """Shows ``text`` near the pointer after ``DELAY_MS`` of hovering.

    ``text`` may be a function, so the tip can depend on the widget's state; an
    empty string means "no tooltip right now".
    """

    def __init__(self, widget: Any, text: str | Callable[[], str]) -> None:
        self._widget = widget
        self._text = text
        self._job: str | None = None
        self._window: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._cancel, add="+")
        widget.bind("<ButtonPress>", self._cancel, add="+")

    def current_text(self) -> str:
        """The text that would be shown right now (``""`` for none)."""
        return self._text() if callable(self._text) else self._text

    def _schedule(self, event: Any = None) -> None:
        self._cancel()
        self._job = self._widget.after(DELAY_MS, self._show)

    def _cancel(self, event: Any = None) -> None:
        if self._job is not None:
            self._widget.after_cancel(self._job)
            self._job = None
        if self._window is not None:
            self._window.destroy()
            self._window = None

    def _show(self) -> None:
        self._job = None
        text = self.current_text()
        if not text or self._window is not None:
            return
        window = tk.Toplevel(self._widget)
        window.wm_overrideredirect(True)
        x, y = self._widget.winfo_pointerx() + 12, self._widget.winfo_pointery() + 16
        window.wm_geometry(f"+{x}+{y}")
        ctk.CTkLabel(
            window,
            text=f"  {text}  ",
            fg_color=theme.TOOLTIP_BG,
            text_color=theme.TOOLTIP_TEXT,
            corner_radius=0,
            height=24,
            font=theme.FONT_HINT,
        ).pack()
        self._window = window
