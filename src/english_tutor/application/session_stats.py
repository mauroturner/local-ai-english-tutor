"""Saves the statistics of a finished session without ever blocking the learner."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import datetime

from ..domain.models import Turn
from ..domain.progress import build_stats
from ..ports import SessionStatsStore

logger = logging.getLogger(__name__)


class StatsRecorder:
    """Remembers when a session began and stores its numbers when it ends.

    A storage problem goes to ``on_warning``; the session still ends normally.
    """

    def __init__(
        self,
        store: SessionStatsStore,
        on_warning: Callable[[str], None],
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._store = store
        self._on_warning = on_warning
        self._clock = clock
        self._started: datetime | None = None

    def turn_done(self) -> None:
        """Note a finished turn; the first one marks the start of the session."""
        if self._started is None:
            self._started = self._clock()

    def finish(self, turns: Sequence[Turn]) -> None:
        """Store the statistics of ``turns`` (nothing when there were none) and reset."""
        started, self._started = self._started, None
        if not turns or started is None:
            return
        try:
            self._store.append(build_stats(turns, started, self._clock()))
        except Exception as exc:  # StorageError by contract; anything else is also non-fatal
            logger.warning("Session statistics not saved: %s", exc)
            self._on_warning(f"Session statistics not saved: {exc}")
