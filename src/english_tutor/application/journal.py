"""No-op storage used when no log or mistake history is configured."""

from __future__ import annotations

from collections.abc import Sequence

from ..domain.models import MistakeRecord
from ..ports import LogSpeaker


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
