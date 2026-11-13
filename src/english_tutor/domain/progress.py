"""Per-session statistics: what a finished session says about the learner's progress."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from .categories import count_categories
from .models import Severity, Turn

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

    @property
    def words_per_minute(self) -> float:
        """Speaking pace over the recorded speech; 0 when nothing was recorded."""
        return self.words * 60.0 / self.speech_s if self.speech_s > 0 else 0.0


def build_stats(turns: Sequence[Turn], started_at: datetime, ended_at: datetime) -> SessionStats:
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
    )
