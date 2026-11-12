"""Presentational list of the learner's recurring mistakes."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import customtkinter as ctk

from ..domain.models import MistakeRecord, Severity
from . import theme

MAX_ROWS = 50
EMPTY_TEXT = "No mistakes yet. Talk with Alex and they will appear here."


class MistakesView(ctk.CTkScrollableFrame):
    """Shows the most frequent mistakes, each with a Practice button.

    It only renders what ``show`` receives and reports clicks through
    ``on_practice(key)``; it never touches the session.
    """

    def __init__(self, master: Any, on_practice: Callable[[str], None], **kwargs: Any) -> None:
        super().__init__(master, fg_color=theme.CHAT_BG, **kwargs)
        self._on_practice = on_practice
        self._enabled = False
        self._buttons: list[ctk.CTkButton] = []

    def show(self, records: Sequence[MistakeRecord]) -> None:
        """Rebuild the list from ``records`` (already ranked)."""
        for child in self.winfo_children():
            child.destroy()
        self._buttons = []
        if not records:
            ctk.CTkLabel(self, text=EMPTY_TEXT, text_color=theme.MUTED_TEXT).pack(pady=20)
            return
        for record in records[:MAX_ROWS]:
            self._add_row(record)
        if len(records) > MAX_ROWS:
            note = f"Showing the {MAX_ROWS} most frequent of {len(records)} mistakes."
            ctk.CTkLabel(self, text=note, text_color=theme.MUTED_TEXT).pack(pady=6)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable every Practice button."""
        self._enabled = enabled
        for button in self._buttons:
            button.configure(state="normal" if enabled else "disabled")

    def _add_row(self, record: MistakeRecord) -> None:
        row = ctk.CTkFrame(self, fg_color=theme.USER_BUBBLE, corner_radius=8)
        row.pack(fill="x", padx=6, pady=3)
        major = record.severity is Severity.MAJOR
        ctk.CTkLabel(
            row,
            text=record.severity.value.upper(),
            fg_color=theme.BADGE_MAJOR if major else theme.BADGE_MINOR,
            text_color="white",
            corner_radius=6,
            width=60,
            font=theme.FONT_HINT,
        ).grid(row=0, column=0, padx=8, pady=(8, 2), sticky="w")
        ctk.CTkLabel(
            row,
            text=f'"{record.original}" -> "{record.corrected}"',
            text_color=theme.TEXT,
            font=theme.FONT_BODY,
            wraplength=theme.BUBBLE_WRAP - 120,
            justify="left",
        ).grid(row=0, column=1, padx=4, pady=(8, 2), sticky="w")
        stats = (
            f"x{record.count}   last seen {record.last_seen:%Y-%m-%d}   "
            f"practice {record.practice_successes}/{record.practice_attempts}"
        )
        ctk.CTkLabel(row, text=stats, text_color=theme.MUTED_TEXT, font=theme.FONT_HINT).grid(
            row=1, column=1, padx=4, pady=(0, 8), sticky="w"
        )
        button = ctk.CTkButton(
            row,
            text="Practice",
            width=80,
            state="normal" if self._enabled else "disabled",
            command=lambda key=record.key: self._on_practice(key),
        )
        button.grid(row=0, column=2, rowspan=2, padx=8, pady=8, sticky="e")
        row.grid_columnconfigure(1, weight=1)
        self._buttons.append(button)
