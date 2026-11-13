"""Strip shown while a listening drill runs: the sentence, Next/Stop and, for dictation, a text box."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from ..i18n import t
from . import theme

DICTATION = "dictation"


class ListeningBanner(ctk.CTkFrame):
    """Presentational: it reports clicks through callbacks and never touches the session."""

    def __init__(
        self,
        master: Any,
        on_next: Callable[[], None],
        on_stop: Callable[[], None],
        on_check: Callable[[str], None],
    ) -> None:
        super().__init__(master, fg_color=theme.PRACTICE_OK, corner_radius=8)
        self._on_check = on_check
        self._kind: str | None = None
        self.grid_columnconfigure(0, weight=1)
        self._label = ctk.CTkLabel(
            self, text="", text_color=theme.TEXT, font=theme.FONT_BODY, wraplength=330, justify="left"
        )
        self._label.grid(row=0, column=0, padx=10, pady=(6, 2), sticky="w")
        self._next = ctk.CTkButton(self, text=t("button.next"), width=70, command=on_next)
        self._next.grid(row=0, column=1, padx=(0, 6), pady=(6, 2))
        self._stop = ctk.CTkButton(self, text=t("button.stop_drill"), width=90, command=on_stop)
        self._stop.grid(row=0, column=2, padx=(0, 10), pady=(6, 2))
        self._entry = ctk.CTkEntry(self, placeholder_text=t("drill.type_here"))
        self._entry.bind("<Return>", lambda _e: self._check())
        self._check_button = ctk.CTkButton(self, text=t("button.check"), width=70, command=self._check)
        self._feedback = ctk.CTkLabel(
            self, text="", text_color=theme.MUTED_TEXT, font=theme.FONT_HINT, wraplength=400, justify="left"
        )

    def show(self, kind: str, text: str | None) -> None:
        """Display the banner for a drill of ``kind``; ``text`` is None when it must stay hidden."""
        self._kind = kind
        shown = t(f"drill.banner.{kind}", text=text) if text else t(f"drill.banner.{kind}_hidden")
        self._label.configure(text=shown)
        self._feedback.configure(text="")
        self._entry.delete(0, "end")
        if kind == DICTATION:
            self._entry.grid(row=1, column=0, padx=(10, 6), pady=(0, 6), sticky="ew")
            self._check_button.grid(row=1, column=1, columnspan=2, padx=(0, 10), pady=(0, 6))
        else:
            self._entry.grid_remove()
            self._check_button.grid_remove()
        self._feedback.grid(row=2, column=0, columnspan=3, padx=10, pady=(0, 6), sticky="w")
        self.grid()

    def hide(self) -> None:
        """Remove the banner."""
        self._kind = None
        self.grid_remove()

    def show_feedback(self, text: str) -> None:
        """Show the verdict on the last answer inside the banner."""
        self._feedback.configure(text=text)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable every control (they need an idle session)."""
        state = "normal" if enabled else "disabled"
        for widget in (self._next, self._stop, self._entry, self._check_button):
            widget.configure(state=state)

    def _check(self) -> None:
        text = self._entry.get().strip()
        if text:
            self._on_check(text)
