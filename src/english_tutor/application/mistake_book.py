"""In-memory mistake history backed by a store; used from the worker thread only."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import datetime

from ..domain.mistakes import add_corrections, add_practice, rank
from ..domain.models import Correction, MistakeRecord, PracticeOutcome
from ..ports import MistakeStore

logger = logging.getLogger(__name__)


class MistakeBook:
    """Keeps every known mistake and saves after each change.

    Storage problems are never raised: they are passed to ``on_warning`` and
    the in-memory history stays correct for the rest of the run.
    """

    def __init__(
        self,
        store: MistakeStore,
        on_warning: Callable[[str], None],
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._store = store
        self._on_warning = on_warning
        self._clock = clock
        self._records: dict[str, MistakeRecord] = {}

    def load(self) -> None:
        """Read the stored history (an unreadable one starts empty with a warning)."""
        try:
            records = self._store.load()
        except Exception as exc:  # StorageError by contract; anything else is also non-fatal
            logger.warning("Mistake history not loaded: %s", exc)
            self._on_warning(str(exc))
            return
        self._records = {r.key: r for r in records}

    def snapshot(self) -> tuple[MistakeRecord, ...]:
        """All records, most frequent first."""
        return rank(self._records)

    def get(self, key: str) -> MistakeRecord | None:
        """The record for ``key``, if known."""
        return self._records.get(key)

    def add_corrections(self, corrections: Iterable[Correction], sentence: str) -> None:
        """Count the corrections found in ``sentence`` and save."""
        self._records = add_corrections(self._records, corrections, sentence, self._clock())
        self._save()

    def add_practice(self, key: str, outcome: PracticeOutcome) -> None:
        """Record one practice attempt and save."""
        self._records = add_practice(self._records, key, outcome, self._clock())
        self._save()

    def _save(self) -> None:
        try:
            self._store.save(self.snapshot())
        except Exception as exc:  # StorageError by contract; keep the memory copy
            logger.warning("Mistake history not saved: %s", exc)
            self._on_warning(f"Mistake history not saved: {exc}")
