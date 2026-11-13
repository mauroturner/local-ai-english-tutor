"""The saved phrases in memory, backed by a store; used from the worker thread only."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime

from ..domain.models import MistakeRecord, PracticeOutcome
from ..domain.vocabulary import (
    PhraseSuggestion,
    VocabEntry,
    add_entry,
    as_target,
    practice_entry,
    remove_entry,
)
from ..ports import VocabularyStore

logger = logging.getLogger(__name__)


class VocabularyBook:
    """Keeps every saved phrase and saves after each change.

    Storage problems are never raised: they go to ``on_warning`` and the in-memory
    list stays correct for the rest of the run.
    """

    def __init__(
        self,
        store: VocabularyStore,
        on_warning: Callable[[str], None],
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._store = store
        self._on_warning = on_warning
        self._clock = clock
        self._entries: dict[str, VocabEntry] = {}

    def load(self) -> None:
        """Read the saved phrases (an unreadable file starts empty with a warning)."""
        try:
            entries = self._store.load()
        except Exception as exc:  # StorageError by contract; anything else is also non-fatal
            logger.warning("Word list not loaded: %s", exc)
            self._on_warning(str(exc))
            return
        self._entries = {e.key: e for e in entries}

    def snapshot(self) -> tuple[VocabEntry, ...]:
        """All phrases, newest first."""
        return tuple(sorted(self._entries.values(), key=lambda e: e.added, reverse=True))

    def add(self, suggestion: PhraseSuggestion) -> VocabEntry | None:
        """Save a phrase; returns the stored entry, or None when it was empty or the list is full."""
        before = set(self._entries)
        self._entries = add_entry(self._entries, suggestion, self._clock())
        self._save()
        added = set(self._entries) - before
        key = next(iter(added), None) or self._existing_key(suggestion)
        return self._entries.get(key) if key else None

    def remove(self, key: str) -> None:
        """Forget a phrase."""
        self._entries = remove_entry(self._entries, key)
        self._save()

    def practice(self, key: str, outcome: PracticeOutcome) -> None:
        """Record one practice answer and save."""
        self._entries = practice_entry(self._entries, key, outcome, self._clock())
        self._save()

    def target(self, key: str) -> MistakeRecord | None:
        """The phrase as a practice target, if it is saved."""
        entry = self._entries.get(key)
        return as_target(entry) if entry else None

    def _existing_key(self, suggestion: PhraseSuggestion) -> str | None:
        from ..domain.corrections import normalize

        key = normalize(suggestion.phrase)
        return key if key in self._entries else None

    def _save(self) -> None:
        try:
            self._store.save(self.snapshot())
        except Exception as exc:  # StorageError by contract; keep the memory copy
            logger.warning("Word list not saved: %s", exc)
            self._on_warning(f"Word list not saved: {exc}")
