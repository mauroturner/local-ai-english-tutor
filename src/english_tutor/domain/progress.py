"""Per-session statistics: what a finished session says about the learner's progress."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum

from .categories import count_categories
from .fillers import total_fillers
from .models import Severity, Turn

MIN_WORDS = 20
"""Sessions with fewer words say little about rates, so charts and records skip them."""

_TREND_TOLERANCE = 0.1
_WEEK_DAYS = 7

_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)*")


def count_words(text: str) -> int:
    """How many words ``text`` has; ``don't`` and ``how's`` count as one."""
    return len(_WORD.findall(text))


@dataclass(frozen=True)
class SessionStats:
    """The numbers of one finished session (stored in ``data/sessions.json``)."""

    started_at: datetime
    duration_s: float  # from the first answer to the end of the session
    turns: int
    words: int
    speech_s: float  # seconds of recorded speech, used for the speaking pace
    major: int  # corrections made, every occurrence counted
    minor: int
    pauses: int  # long pauses inside sentences
    slow_starts: int  # long waits before the first word
    categories: tuple[tuple[str, int], ...] = ()  # mistakes per kind, most frequent first
    scenario: str | None = None  # the role-play practised, None for a free conversation
    memory: str | None = None  # notes for the next session (personal data, see domain.memory)
    fillers: int = 0  # filler sounds said (um, uh, er, hmm)

    @property
    def words_per_minute(self) -> float:
        """Speaking pace over the recorded speech; 0 when nothing was recorded."""
        return self.words * 60.0 / self.speech_s if self.speech_s > 0 else 0.0

    @property
    def mistakes_per_100_words(self) -> float:
        """Corrections (major and minor) per 100 words said."""
        return (self.major + self.minor) * 100.0 / self.words if self.words else 0.0

    @property
    def pauses_per_100_words(self) -> float:
        """Long pauses inside sentences per 100 words said."""
        return self.pauses * 100.0 / self.words if self.words else 0.0


def build_stats(
    turns: Sequence[Turn],
    started_at: datetime,
    ended_at: datetime,
    scenario: str | None = None,
    memory: str | None = None,
) -> SessionStats:
    """Fold the turns of a session into its statistics."""
    corrections = [c for turn in turns for c in turn.corrections]
    hesitations = [h for turn in turns for h in turn.hesitations]
    return SessionStats(
        started_at=started_at,
        duration_s=max(0.0, (ended_at - started_at).total_seconds()),
        turns=len(turns),
        words=sum(count_words(turn.user_text) for turn in turns),
        speech_s=sum(turn.speech_s for turn in turns),
        major=sum(1 for c in corrections if c.severity is Severity.MAJOR),
        minor=sum(1 for c in corrections if c.severity is Severity.MINOR),
        pauses=sum(1 for h in hesitations if not h.at_start),
        slow_starts=sum(1 for h in hesitations if h.at_start),
        categories=count_categories(corrections),
        scenario=scenario,
        memory=memory,
        fillers=sum(total_fillers(turn.user_text for turn in turns).values()),
    )


def meaningful(sessions: Sequence[SessionStats]) -> list[SessionStats]:
    """The sessions long enough (``MIN_WORDS``) to compare by rate."""
    return [s for s in sessions if s.words >= MIN_WORDS]


class Trend(Enum):
    """Where a metric is heading."""

    BETTER = "better"
    WORSE = "worse"
    STEADY = "steady"
    UNKNOWN = "unknown"  # too few sessions to say


def trend(values: Sequence[float], lower_is_better: bool) -> Trend:
    """Compare the older half of ``values`` (oldest first) with the newer half.

    Changes within 10 % of the older average count as steady. At least four
    values are needed.
    """
    half = len(values) // 2
    if half < 2:
        return Trend.UNKNOWN
    old = sum(values[:half]) / half
    new = sum(values[-half:]) / half
    if abs(new - old) <= _TREND_TOLERANCE * abs(old):
        return Trend.STEADY
    improved = (new < old) == lower_is_better
    return Trend.BETTER if improved else Trend.WORSE


@dataclass(frozen=True)
class WeekSummary:
    """What the last seven days add up to."""

    sessions: int
    minutes: float
    words: int


def week_summary(sessions: Sequence[SessionStats], today: date) -> WeekSummary:
    """Sessions, minutes and words of the last seven days, today included."""
    first = today - timedelta(days=_WEEK_DAYS - 1)
    week = [s for s in sessions if first <= s.started_at.date() <= today]
    return WeekSummary(len(week), sum(s.duration_s for s in week) / 60.0, sum(s.words for s in week))


def best_session(
    sessions: Sequence[SessionStats], rate: Callable[[SessionStats], float]
) -> SessionStats | None:
    """The meaningful session with the lowest ``rate``, or None."""
    return min(meaningful(sessions), key=rate, default=None)


def minutes_on(sessions: Sequence[SessionStats], day: date) -> float:
    """Minutes spent in sessions that started on ``day``."""
    return sum(s.duration_s for s in sessions if s.started_at.date() == day) / 60.0


def streak_days(sessions: Sequence[SessionStats], today: date) -> int:
    """Consecutive days with at least one session, ending today (or yesterday if today has none)."""
    days = {s.started_at.date() for s in sessions}
    day = today if today in days else today - timedelta(days=1)
    count = 0
    while day in days:
        count += 1
        day -= timedelta(days=1)
    return count


def goal_met(sessions: Sequence[SessionStats], goal_minutes: int, today: date) -> bool:
    """Whether today's minutes reach the daily goal; a goal of 0 is switched off."""
    return goal_minutes > 0 and minutes_on(sessions, today) >= goal_minutes
