"""The daily practice reminder: when to show it (pure)."""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date, datetime, time, timedelta

from .progress import SessionStats, goal_met, minutes_on

MAX_LATE = timedelta(hours=2)
"""A reminder that was missed by more than this (the app was closed) is not shown late."""

_TIME = re.compile(r"^(\d{1,2}):(\d{2})$")


def parse_time(text: str) -> time | None:
    """``19:30`` (or ``7:05``) as a time; None for an empty or invalid text."""
    match = _TIME.match(text.strip())
    if match is None:
        return None
    hour, minute = int(match[1]), int(match[2])
    return time(hour, minute) if hour < 24 and minute < 60 else None


def time_error(text: str) -> str | None:
    """Why ``text`` cannot be a reminder time, or None when it can (empty means "off")."""
    if not text.strip() or parse_time(text) is not None:
        return None
    return "Use the format HH:MM, for example 19:30, or leave it empty."


def normalize_time(text: str) -> str:
    """The text as stored: ``HH:MM`` with two digits, or empty."""
    parsed = parse_time(text)
    return f"{parsed:%H:%M}" if parsed else ""


def should_remind(
    now: datetime,
    reminder: str,
    sessions: Sequence[SessionStats],
    goal_minutes: int,
    last_reminded: date | None,
) -> bool:
    """Whether to show the reminder now.

    Only once a day, from the chosen time up to two hours later, and only when
    today's goal is not met yet (with no goal: when there is no session today).
    """
    chosen = parse_time(reminder)
    if chosen is None or last_reminded == now.date():
        return False
    due = datetime.combine(now.date(), chosen)
    if not due <= now <= due + MAX_LATE:
        return False
    if goal_minutes > 0:
        return not goal_met(sessions, goal_minutes, now.date())
    return minutes_on(sessions, now.date()) == 0
