"""What the main window remembers from the event stream for the Settings actions."""

from __future__ import annotations

from ..application.events import (
    DataCleared,
    MistakesChanged,
    ProgressChanged,
    ReportReady,
    SessionEvent,
)
from ..domain.models import MistakeRecord, SessionReport
from ..domain.progress import SessionStats
from ..i18n import t


class SessionSnapshot:
    """The last end-of-session report of this run and the current mistake list."""

    def __init__(self) -> None:
        self.report: SessionReport | None = None
        self.mistakes: tuple[MistakeRecord, ...] = ()
        self.sessions: tuple[SessionStats, ...] = ()

    def observe(self, event: SessionEvent) -> None:
        """Update from ``event``; events that do not matter are ignored."""
        if isinstance(event, ReportReady):
            self.report = event.report
        elif isinstance(event, MistakesChanged):
            self.mistakes = tuple(event.mistakes)
        elif isinstance(event, ProgressChanged):
            self.sessions = tuple(event.sessions)


def cleared_message(event: DataCleared) -> str:
    """Translated one-line notice for a finished deletion."""
    return t(f"data.cleared_{event.kind}", count=event.count)
