"""Best-effort keyboard focus for customtkinter controls that ignore Tab by default."""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable, Mapping
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


def bind_keys(window: Any, bindings: Mapping[str, Callable[[], None]]) -> None:
    """Bind ``{sequence: command}`` on ``window``; each handler stops further handling."""
    for sequence, command in bindings.items():
        window.bind(sequence, lambda _e, c=command: (c(), "break")[1])


def show_modal(window: Any, first: bool = False) -> None:
    """Raise a toplevel, give it the keyboard and block its parent (best effort)."""
    try:
        if window.state() == "withdrawn":
            window.deiconify()
        window.lift()
        window.focus_force()
        if first:
            window.focus_set()  # keeps the search box unfocused so its placeholder shows
        if not window.winfo_viewable():
            window.wait_visibility()
        window.grab_set()
    except tk.TclError:
        logger.debug("Could not show %r modally", window, exc_info=True)


class PttHold:
    """Keeps push-to-talk paused (once) between ``acquire`` and ``release``."""

    def __init__(self, gate: Any) -> None:
        self._gate = gate
        self._held = False

    def acquire(self) -> None:
        """Suspend the gate, if there is one."""
        if self._gate is not None and not self._held:
            self._gate.suspend()
            self._held = True

    def release(self) -> None:
        """Resume the gate if this hold suspended it; safe to call repeatedly."""
        if self._held:
            self._held = False
            self._gate.resume()


def center_on(window: Any, master: Any, size: tuple[int, int]) -> None:
    """Size ``window`` and put it in the middle of ``master`` (never off the left/top)."""
    width, height = size
    master.update_idletasks()
    x = max(0, master.winfo_rootx() + (master.winfo_width() - width) // 2)
    y = max(0, master.winfo_rooty() + (master.winfo_height() - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")
