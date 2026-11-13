"""Presentational list of the saved phrases (the word list)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date
from typing import Any

import customtkinter as ctk

from ..domain.review_schedule import is_due
from ..domain.vocabulary import VocabEntry
from ..i18n import t
from . import theme

MAX_ROWS = 100


class WordsView(ctk.CTkScrollableFrame):
    """Shows the saved phrases, each with Practice and Delete buttons.

    It only renders what ``show`` receives and reports clicks through
    ``on_practice(key)``, ``on_remove(key)`` and ``on_save()``; it never touches the session.
    """

    def __init__(
        self,
        master: Any,
        on_practice: Callable[[str], None],
        on_remove: Callable[[str], None],
        on_save: Callable[[], None],
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color=theme.CHAT_BG, **kwargs)
        self._on_practice = on_practice
        self._on_remove = on_remove
        self._on_save = on_save
        self._enabled = False
        self._buttons: list[ctk.CTkButton] = []

    def show(self, entries: Sequence[VocabEntry], today: date | None = None) -> None:
        """Rebuild the list from ``entries`` (newest first)."""
        for child in self.winfo_children():
            child.destroy()
        self._buttons = []
        today = today or date.today()
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=6, pady=(4, 2))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text=t("words.hint"), text_color=theme.MUTED_TEXT, font=theme.FONT_HINT,
            wraplength=theme.BUBBLE_WRAP - 150, justify="left", anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=4)
        save = ctk.CTkButton(
            header, text=t("button.save_phrase"),
            state="normal" if self._enabled else "disabled", command=self._on_save,
        )
        save.grid(row=0, column=1, sticky="e")
        self._buttons.append(save)
        if not entries:
            ctk.CTkLabel(self, text=t("words.empty"), text_color=theme.MUTED_TEXT).pack(pady=20)
            return
        for entry in entries[:MAX_ROWS]:
            self._add_row(entry, is_due(entry.review, today))

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable every button (they need an idle session)."""
        self._enabled = enabled
        for button in self._buttons:
            button.configure(state="normal" if enabled else "disabled")

    def _add_row(self, entry: VocabEntry, due: bool) -> None:
        row = ctk.CTkFrame(self, fg_color=theme.USER_BUBBLE, corner_radius=8)
        row.pack(fill="x", padx=6, pady=3)
        row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            row, text=entry.phrase, font=theme.FONT_HEADING, anchor="w", justify="left",
            wraplength=theme.BUBBLE_WRAP - 190,
        ).grid(row=0, column=0, padx=10, pady=(8, 0), sticky="w")
        details = " - ".join(p for p in (entry.meaning, f'"{entry.example}"' if entry.example else "") if p)
        if details:
            ctk.CTkLabel(
                row, text=details, text_color=theme.MUTED_TEXT, font=theme.FONT_BODY, anchor="w",
                justify="left", wraplength=theme.BUBBLE_WRAP - 190,
            ).grid(row=1, column=0, padx=10, pady=(0, 2), sticky="w")
        stats = t("words.stats", successes=entry.practice_successes, attempts=entry.practice_attempts)
        if due:
            stats = f"{t('mistakes.due_badge')}   {stats}"
        ctk.CTkLabel(
            row, text=stats, text_color=theme.NOTICE_TEXT if due else theme.MUTED_TEXT,
            font=theme.FONT_HINT, anchor="w",
        ).grid(row=2, column=0, padx=10, pady=(0, 8), sticky="w")
        for column, (text, command) in enumerate((
            (t("button.practice"), lambda key=entry.key: self._on_practice(key)),
            (t("button.delete"), lambda key=entry.key: self._on_remove(key)),
        ), start=1):
            button = ctk.CTkButton(
                row, text=text, width=80, command=command,
                state="normal" if self._enabled else "disabled",
            )
            button.grid(row=0, column=column, rowspan=3, padx=(0, 8), pady=8)
            self._buttons.append(button)
