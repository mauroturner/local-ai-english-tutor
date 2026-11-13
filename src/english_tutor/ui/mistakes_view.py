"""Presentational list of the learner's recurring mistakes."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date
from typing import Any

import customtkinter as ctk

from ..domain.categories import filter_by_category, present_categories
from ..domain.models import MistakeRecord, Severity
from ..domain.review_schedule import due_first, due_items
from ..i18n import format_date, t
from . import theme

_BADGES = {
    Severity.MAJOR: "BADGE_MAJOR",
    Severity.MINOR: "BADGE_MINOR",
    Severity.HESITATION: "BADGE_PAUSE",
}
"""Theme colour name of each badge (looked up when drawn, so theme changes apply)."""

MAX_ROWS = 50


class MistakesView(ctk.CTkScrollableFrame):
    """Shows the most frequent mistakes, each with a Practice button.

    It only renders what ``show`` receives and reports clicks through
    ``on_practice(key)`` and ``on_review_due()``; it never touches the session.
    Mistakes due for review today come first and carry a badge.
    """

    def __init__(
        self,
        master: Any,
        on_practice: Callable[[str], None],
        on_review_due: Callable[[], None] = lambda: None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color=theme.CHAT_BG, **kwargs)
        self._on_practice = on_practice
        self._on_review_due = on_review_due
        self._enabled = False
        self._buttons: list[ctk.CTkButton] = []
        self._due_keys: frozenset[str] = frozenset()
        self._records: Sequence[MistakeRecord] = ()
        self._today = date.today()
        self._category: str | None = None  # the category filter; None shows everything

    def show(self, records: Sequence[MistakeRecord], today: date | None = None) -> None:
        """Rebuild the list from ``records`` (already ranked); due ones go first."""
        for child in self.winfo_children():
            child.destroy()
        self._buttons = []
        if not records:
            ctk.CTkLabel(self, text=t("mistakes.empty"), text_color=theme.MUTED_TEXT).pack(pady=20)
            return
        today = today or date.today()
        self._records, self._today = records, today
        categories = present_categories(records)
        if self._category not in categories:
            self._category = None
        shown = filter_by_category(due_first(records, today), self._category)
        self._due_keys = frozenset(r.key for r in due_items(records, today))
        self._add_header(len(self._due_keys), categories)
        for record in shown[:MAX_ROWS]:
            self._add_row(record)
        if len(shown) > MAX_ROWS:
            note = t("mistakes.truncated", shown=MAX_ROWS, total=len(shown))
            ctk.CTkLabel(self, text=note, text_color=theme.MUTED_TEXT).pack(pady=6)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable every Practice button."""
        self._enabled = enabled
        for button in self._buttons:
            button.configure(state="normal" if enabled else "disabled")

    def _pick_category(self, label: str) -> None:
        by_label = {t(f"category.{c}"): c for c in present_categories(self._records)}
        self._category = by_label.get(label)  # the "all" label maps to None
        self.show(self._records, self._today)

    def _add_header(self, due: int, categories: Sequence[str]) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=6, pady=(4, 2))
        header.grid_columnconfigure(0, weight=1)
        text = t("mistakes.due_count", count=due) if due else t("mistakes.none_due")
        ctk.CTkLabel(header, text=text, text_color=theme.MUTED_TEXT, font=theme.FONT_BODY).grid(
            row=0, column=0, sticky="w", padx=4
        )
        if due:
            button = ctk.CTkButton(
                header,
                text=t("button.review_due"),
                state="normal" if self._enabled else "disabled",
                command=self._on_review_due,
            )
            button.grid(row=0, column=1, sticky="e")
            self._buttons.append(button)
        if categories:
            everything = t("mistakes.all_categories")
            picker = ctk.CTkOptionMenu(
                header,
                values=[everything, *(t(f"category.{c}") for c in categories)],
                command=self._pick_category,
            )
            picker.set(everything if self._category is None else t(f"category.{self._category}"))
            picker.grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=(4, 0))

    def _add_row(self, record: MistakeRecord) -> None:
        row = ctk.CTkFrame(self, fg_color=theme.USER_BUBBLE, corner_radius=8)
        row.pack(fill="x", padx=6, pady=3)
        ctk.CTkLabel(
            row,
            text=t(f"severity.{record.severity.value}"),
            fg_color=getattr(theme, _BADGES[record.severity]),
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
        if record.key in self._due_keys:
            ctk.CTkLabel(
                row, text=t("mistakes.due_badge"), text_color=theme.NOTICE_TEXT, font=theme.FONT_HINT
            ).grid(row=1, column=0, padx=8, pady=(0, 8), sticky="w")
        stats = t(
            "mistakes.stats",
            count=record.count,
            date=format_date(record.last_seen),
            successes=record.practice_successes,
            attempts=record.practice_attempts,
        )
        ctk.CTkLabel(row, text=stats, text_color=theme.MUTED_TEXT, font=theme.FONT_HINT).grid(
            row=1, column=1, padx=4, pady=(0, 8), sticky="w"
        )
        button = ctk.CTkButton(
            row,
            text=t("button.practice"),
            width=80,
            state="normal" if self._enabled else "disabled",
            command=lambda key=record.key: self._on_practice(key),
        )
        button.grid(row=0, column=2, rowspan=2, padx=8, pady=8, sticky="e")
        row.grid_columnconfigure(1, weight=1)
        self._buttons.append(button)
