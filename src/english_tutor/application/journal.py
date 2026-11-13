"""Conversation-log helpers: a failure-proof wrapper and no-op storage."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from ..domain.models import MistakeRecord
from ..domain.progress import SessionStats
from ..domain.vocabulary import VocabEntry
from ..ports import ConversationLog, LogSpeaker

logger = logging.getLogger(__name__)


class NullConversationLog:
    """A conversation log that discards everything."""

    def record(self, speaker: LogSpeaker, text: str) -> None:
        """Ignore the entry."""

    def new_session(self) -> None:
        """Nothing to start."""


class NullMistakeStore:
    """A mistake store that remembers nothing."""

    def load(self) -> list[MistakeRecord]:
        """Return an empty history."""
        return []

    def save(self, records: Sequence[MistakeRecord]) -> None:
        """Ignore the records."""


class NullVocabularyStore:
    """A word list store that remembers nothing."""

    def load(self) -> list[VocabEntry]:
        """Return an empty list."""
        return []

    def save(self, entries: Sequence[VocabEntry]) -> None:
        """Ignore the entries."""


class NullSessionStatsStore:
    """A statistics store that remembers nothing."""

    def load(self) -> list[SessionStats]:
        """Return no sessions."""
        return []

    def append(self, stats: SessionStats) -> None:
        """Ignore the statistics."""

    def clear_memory(self) -> int:
        """Nothing is stored, so nothing is removed."""
        return 0


class SafeJournal:
    """Wraps a conversation log: a storage failure warns once and never raises."""

    def __init__(self, log: ConversationLog, warn: Callable[[str], None]) -> None:
        self._log = log
        self._warn = warn

    def record(self, speaker: LogSpeaker, text: str) -> None:
        """Append one entry."""
        self._guard(lambda: self._log.record(speaker, text))

    def new_session(self) -> None:
        """Start a new log file with the next entry."""
        self._guard(self._log.new_session)

    def _guard(self, action: Callable[[], None]) -> None:
        try:
            action()
        except Exception as exc:  # any storage problem must leave the turn untouched
            logger.warning("Conversation log failed: %s", exc)
            self._warn(f"Conversation log unavailable: {exc}")
