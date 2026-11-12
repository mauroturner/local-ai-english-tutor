"""Job runners: a serial background thread for the app, inline for tests."""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from typing import Protocol

logger = logging.getLogger(__name__)


class Runner(Protocol):
    """Anything that can execute a no-argument job."""

    def submit(self, fn: Callable[[], None]) -> None:
        """Schedule ``fn``."""
        ...

    def close(self) -> None:
        """Stop accepting jobs."""
        ...


class SerialWorker:
    """Runs submitted jobs one at a time on a daemon thread."""

    def __init__(self) -> None:
        self._queue: queue.Queue[Callable[[], None] | None] = queue.Queue()
        self._thread = threading.Thread(target=self._loop, name="tutor-worker", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while True:
            job = self._queue.get()
            if job is None:
                return
            try:
                job()
            except Exception:  # keep the worker alive whatever a job does
                logger.exception("Unhandled error in worker job")

    def submit(self, fn: Callable[[], None]) -> None:
        """Queue ``fn`` for execution on the worker thread."""
        self._queue.put(fn)

    def close(self) -> None:
        """Ask the worker to finish after the queued jobs."""
        self._queue.put(None)


class InlineRunner:
    """Runs jobs immediately on the caller's thread (used by tests)."""

    def submit(self, fn: Callable[[], None]) -> None:
        """Execute ``fn`` right away."""
        fn()

    def close(self) -> None:
        """Nothing to release."""
