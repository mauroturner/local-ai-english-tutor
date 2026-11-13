"""Presentational Progress tab: a few numbers and three small trend charts."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date
from typing import Any

import customtkinter as ctk

from ..domain.progress import (
    SessionStats,
    Trend,
    best_session,
    meaningful,
    trend,
    week_summary,
)
from ..i18n import format_date, t
from . import theme
from .charts import scale_points

MAX_SESSIONS = 20
"""How many of the latest sessions each chart shows."""

_CHART_HEIGHT = 90
_CHART_WIDTH = 420

_METRICS: tuple[tuple[str, Callable[[SessionStats], float], bool], ...] = (
    ("mistakes", lambda s: s.mistakes_per_100_words, True),
    ("pauses", lambda s: s.pauses_per_100_words, True),
    ("pace", lambda s: s.words_per_minute, False),
)
"""(i18n name, value of a session, whether lower is better)."""


def _colour(pair: tuple[str, str]) -> str:
    """The light or dark member of a theme colour pair, for a plain Tk canvas."""
    return pair[1] if ctk.get_appearance_mode() == "Dark" else pair[0]


class ProgressView(ctk.CTkScrollableFrame):
    """Shows how the learner is doing over time; it only renders what ``show`` receives."""

    def __init__(self, master: Any, **kwargs: Any) -> None:
        super().__init__(master, fg_color=theme.CHAT_BG, **kwargs)

    def show(self, sessions: Sequence[SessionStats], today: date | None = None) -> None:
        """Rebuild the tab from ``sessions`` (oldest first)."""
        for child in self.winfo_children():
            child.destroy()
        today = today or date.today()
        if not sessions:
            ctk.CTkLabel(self, text=t("progress.empty"), text_color=theme.MUTED_TEXT).pack(pady=20)
            return
        self._summary(sessions, today)
        recent = meaningful(sessions)[-MAX_SESSIONS:]
        if not recent:
            ctk.CTkLabel(
                self, text=t("progress.too_short"), text_color=theme.MUTED_TEXT, wraplength=420
            ).pack(pady=10)
            return
        for name, value, lower_is_better in _METRICS:
            self._chart(name, [value(s) for s in recent], lower_is_better)

    def _summary(self, sessions: Sequence[SessionStats], today: date) -> None:
        week = week_summary(sessions, today)
        lines = [
            t("progress.total", count=len(sessions)),
            t("progress.week", count=week.sessions, minutes=round(week.minutes), words=week.words),
        ]
        best = best_session(sessions, lambda s: s.mistakes_per_100_words)
        if best is not None:
            lines.append(
                t(
                    "progress.best",
                    rate=f"{best.mistakes_per_100_words:.1f}",
                    date=format_date(best.started_at),
                )
            )
        ctk.CTkLabel(
            self, text="\n".join(lines), justify="left", anchor="w", font=theme.FONT_BODY
        ).pack(fill="x", padx=10, pady=(8, 4))

    def _chart(self, name: str, values: list[float], lower_is_better: bool) -> None:
        card = ctk.CTkFrame(self, fg_color=theme.USER_BUBBLE, corner_radius=8)
        card.pack(fill="x", padx=6, pady=6)
        verdict = {
            Trend.BETTER: t("progress.trend.better"),
            Trend.WORSE: t("progress.trend.worse"),
            Trend.STEADY: t("progress.trend.steady"),
            Trend.UNKNOWN: t("progress.trend.unknown"),
        }[trend(values, lower_is_better)]
        heading = t(f"progress.metric.{name}", value=f"{values[-1]:.1f}")
        ctk.CTkLabel(card, text=heading, font=theme.FONT_HEADING, anchor="w").pack(
            fill="x", padx=10, pady=(8, 0)
        )
        ctk.CTkLabel(
            card, text=verdict, text_color=theme.MUTED_TEXT, font=theme.FONT_HINT, anchor="w"
        ).pack(fill="x", padx=10)
        self._draw(card, values)

    @staticmethod
    def _draw(card: Any, values: list[float]) -> None:
        canvas = ctk.CTkCanvas(
            card,
            width=_CHART_WIDTH,
            height=_CHART_HEIGHT,
            highlightthickness=0,
            bg=_colour(theme.USER_BUBBLE),
        )
        canvas.pack(padx=10, pady=(4, 10), anchor="w")
        points = scale_points(values, _CHART_WIDTH, _CHART_HEIGHT)
        colour = _colour(theme.BADGE_PAUSE)
        if len(points) > 1:
            canvas.create_line(*[c for point in points for c in point], fill=colour, width=2)
        for x, y in points:
            canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill=colour, outline=colour)
