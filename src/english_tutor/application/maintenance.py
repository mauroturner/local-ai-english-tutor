"""Jobs that delete stored data; they run on the session worker (see ``clear_data``)."""

from __future__ import annotations

import logging
from collections.abc import Callable

from ..ports import StorageError
from .events import DataCleared, ErrorRaised, EventSink, MistakesChanged
from .journal import SafeJournal
from .mistake_book import MistakeBook

logger = logging.getLogger(__name__)

ClearJob = Callable[[MistakeBook, SafeJournal, EventSink], None]
"""What ``ConversationSession.clear_data`` runs: ``job(book, journal, emit)``."""


def clear_mistakes(book: MistakeBook, journal: SafeJournal, emit: EventSink) -> None:
    """Forget the whole mistake history, then tell the UI (or report why it failed)."""
    try:
        count = book.clear()
    except StorageError as exc:
        logger.warning("Mistake history not cleared: %s", exc)
        emit(ErrorRaised(f"Could not delete the mistake history: {exc}"))
        return
    emit(MistakesChanged(()))
    emit(DataCleared("mistakes", count))


def clear_memory(forget: Callable[[], int]) -> ClearJob:
    """Build a job that calls ``forget()`` (returns how many sessions had notes)."""

    def job(book: MistakeBook, journal: SafeJournal, emit: EventSink) -> None:
        try:
            count = forget()
        except StorageError as exc:
            logger.warning("Session memory not cleared: %s", exc)
            emit(ErrorRaised(f"Could not delete the session memory: {exc}"))
            return
        emit(DataCleared("memory", count))

    return job


def clear_logs(delete: Callable[[], int]) -> ClearJob:
    """Build a job that calls ``delete()`` (returns how many files it removed).

    The journal starts a new log file afterwards so the next entry is not lost.
    """

    def job(book: MistakeBook, journal: SafeJournal, emit: EventSink) -> None:
        try:
            count = delete()
        except StorageError as exc:
            logger.warning("Conversation logs not cleared: %s", exc)
            emit(ErrorRaised(f"Could not delete the conversation logs: {exc}"))
            return
        journal.new_session()
        emit(DataCleared("logs", count))

    return job
