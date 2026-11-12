"""Plays sound cues on a dedicated sounddevice output stream.

Never uses ``sd.play``: that shares one process-wide stream, so a cue would cut off
the tutor's voice. A cue only ever touches its own ``OutputStream``.
"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from typing import Any

import numpy as np

from ..audio.cues import Cue, render

logger = logging.getLogger(__name__)

StreamFactory = Callable[[], Any]
"""Builds an unstarted output stream exposing ``samplerate``, ``start/write/stop/close``."""

_JOIN_TIMEOUT_S = 2.0


def _default_stream() -> Any:
    import sounddevice as sd

    rate = int(sd.query_devices(kind="output")["default_samplerate"])
    return sd.OutputStream(samplerate=rate, channels=1, dtype="float32")


class SoundDeviceCuePlayer:
    """Plays cues from one daemon thread; a cue requested while one plays is dropped."""

    def __init__(self, stream_factory: StreamFactory = _default_stream) -> None:
        self._factory = stream_factory
        self._lock = threading.Lock()  # guards _closed and _thread only
        self._slot = threading.Semaphore(1)  # held from play() until the cue was written
        self._queue: queue.Queue[Cue | None] = queue.Queue(maxsize=1)
        self._thread: threading.Thread | None = None
        self._closed = False
        self._stream: Any = None  # worker thread only
        self._rendered: dict[tuple[Cue, int], np.ndarray] = {}  # worker thread only

    def play(self, cue: Cue) -> None:
        """Queue ``cue`` for the worker; drops it when one is playing. Never raises."""
        try:
            with self._lock:
                if self._closed or not self._slot.acquire(blocking=False):
                    return
                try:
                    self._ensure_worker()
                    self._queue.put_nowait(cue)
                except Exception:
                    self._slot.release()
                    raise
        except Exception:
            logger.warning("Could not queue the %s cue", cue.value, exc_info=True)

    def close(self) -> None:
        """Stop the worker and release the output stream. Safe to call twice."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            thread = self._thread
        if thread is None:
            return
        try:
            self._queue.get_nowait()  # discard a cue nobody started
        except queue.Empty:
            pass
        try:
            self._queue.put_nowait(None)
        except queue.Full:  # the worker took a cue meanwhile; it sees the flag next
            pass
        thread.join(_JOIN_TIMEOUT_S)

    def _ensure_worker(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="cue-player", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        while True:
            cue = self._queue.get()
            if cue is None or self._closed:
                break
            try:
                self._play_one(cue)
            except Exception:
                logger.warning("Sound cue failed; the output will be reopened", exc_info=True)
                self._drop_stream()
            finally:
                self._slot.release()
        self._drop_stream()

    def _play_one(self, cue: Cue) -> None:
        if self._stream is None:
            stream = self._factory()
            try:
                stream.start()
            except Exception:
                _close_quietly(stream)
                raise
            self._stream = stream
        rate = int(self._stream.samplerate)
        samples = self._rendered.get((cue, rate))
        if samples is None:
            samples = self._rendered[(cue, rate)] = render(cue, sr=rate)
        self._stream.write(samples.reshape(-1, 1))

    def _drop_stream(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            _close_quietly(stream)


def _close_quietly(stream: Any) -> None:
    for step in ("stop", "close"):
        try:
            getattr(stream, step)()
        except Exception:
            logger.debug("Ignoring a failure in cue stream.%s()", step, exc_info=True)


class NullCuePlayer:
    """Silent player for tests and for machines without a usable audio output."""

    def play(self, cue: Cue) -> None:
        """Do nothing."""

    def close(self) -> None:
        """Do nothing."""
