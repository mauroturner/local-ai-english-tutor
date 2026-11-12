"""Modal dialog that records a key press for push-to-talk or an in-app shortcut.

It listens through Tk key bindings, so it only ever sees keys pressed in this
dialog (no global keyboard hook).
"""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from ...i18n import t
from ...settings.shortcuts import combo_from_event, tk_keysym_to_ptt
from .. import theme
from .focus import center_on

logger = logging.getLogger(__name__)

PTT = "ptt"
SHORTCUT = "shortcut"
_SIZE = (400, 200)


def interpret_key(mode: str, keysym: str, state: int) -> tuple[str, str | None]:
    """Meaning of a key press in the dialog.

    Returns ``("done", value)`` with the captured key, ``("cancel", None)`` for Esc,
    ``("ignore", None)`` for a lone modifier in shortcut mode (or the first half of
    AltGr) and ``("unsupported", None)`` for keys that cannot be used.
    """
    if keysym == "Escape":
        return "cancel", None
    value = tk_keysym_to_ptt(keysym, state) if mode == PTT else combo_from_event(keysym, state)
    if value is not None:
        return "done", value
    if keysym.endswith(("_L", "_R")):  # Control_L, Shift_R, ... pressed alone
        return "ignore", None
    return "unsupported", None


class KeyCaptureDialog(ctk.CTkToplevel):
    """Asks for one key press and reports it through ``on_result(value | None)``.

    ``None`` means the dialog was cancelled. ``on_result`` runs after the dialog is
    gone, so the caller can take the keyboard grab back.
    """

    def __init__(
        self, master: Any, mode: str, on_result: Callable[[str | None], None]
    ) -> None:
        super().__init__(master)
        self._mode = mode
        self._on_result = on_result
        self._done = False
        self.title(t("capture.title_ptt" if mode == PTT else "capture.title_shortcut"))
        width = _SIZE[0]
        center_on(self, master, _SIZE)
        self.resizable(False, False)
        self.transient(master)
        pad = theme.SPACE_L
        prompt = "capture.prompt_ptt" if mode == PTT else "capture.prompt_shortcut"
        ctk.CTkLabel(
            self, text=t(prompt), font=theme.FONT_HEADING, wraplength=width - 2 * pad
        ).pack(padx=pad, pady=(pad * 2, theme.SPACE_S))
        self._message = ctk.CTkLabel(
            self, text=t("capture.hint"), font=theme.FONT_HINT, text_color=theme.MUTED_TEXT
        )
        self._message.pack()
        ctk.CTkButton(self, text=t("button.cancel"), width=90, command=self.cancel).pack(
            pady=pad
        )
        self.bind("<KeyPress>", self._on_key)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.after(250, self._take_keyboard)

    def _take_keyboard(self) -> None:
        if self._done:
            return
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except tk.TclError:
            logger.debug("Could not grab input for the capture dialog", exc_info=True)

    def _on_key(self, event: Any) -> str:
        self.handle_key(event.keysym, event.state)
        return "break"

    def handle_key(self, keysym: str, state: int) -> None:
        """Process one key press (also the entry point for tests)."""
        kind, value = interpret_key(self._mode, keysym, state)
        if kind == "done":
            self._finish(value)
        elif kind == "cancel":
            self.cancel()
        elif kind == "unsupported":
            self._message.configure(text=t("capture.unsupported"), text_color=theme.ERROR_TEXT)

    def cancel(self) -> None:
        """Close without a result."""
        self._finish(None)

    def _finish(self, value: str | None) -> None:
        if self._done:
            return
        self._done = True
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
        self._on_result(value)
