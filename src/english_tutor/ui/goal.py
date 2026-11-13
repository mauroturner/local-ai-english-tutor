"""The one-line "today and streak" text of the main window (pure apart from ``t``)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from ..domain.progress import SessionStats, goal_met, minutes_on, streak_days
from ..domain.topics import topic_of_the_day
from ..i18n import t


def goal_text(sessions: Sequence[SessionStats], goal_minutes: int, today: date) -> str:
    """``Today: 4 / 10 min   Streak: 3 days``; empty when there is nothing to say."""
    parts: list[str] = []
    minutes = int(minutes_on(sessions, today))
    if goal_minutes > 0:
        if goal_met(sessions, goal_minutes, today):
            parts.append(t("goal.reached", minutes=minutes))
        else:
            parts.append(t("goal.today", minutes=minutes, goal=goal_minutes))
    streak = streak_days(sessions, today)
    if streak:
        parts.append(t("goal.streak_one" if streak == 1 else "goal.streak", days=streak))
    return "   ".join(parts)


def topic_text(sessions: Sequence[SessionStats], today: date) -> str:
    """``Topic for today: "..." (practises verb tense)``; empty without a weak category."""
    chosen = topic_of_the_day(sessions, today)
    if chosen is None:
        return ""
    category, topic = chosen
    return t("topic.line", topic=topic, category=t(f"category.{category}").lower())
