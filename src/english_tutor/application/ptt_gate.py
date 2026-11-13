"""Pausing push-to-talk while a window that takes keyboard input is open."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager


class GateGroup:
    """Several gates suspended and resumed together (one per push-to-talk key)."""

    def __init__(self, *gates: PttGate) -> None:
        self._gates = gates

    def suspend(self) -> None:
        """Suspend every gate."""
        for gate in self._gates:
            gate.suspend()

    def resume(self) -> None:
        """Resume every gate."""
        for gate in self._gates:
            gate.resume()

    @contextmanager
    def paused(self) -> Iterator[None]:
        """Suspend every gate for the duration of a ``with`` block."""
        self.suspend()
        try:
            yield
        finally:
            self.resume()


class PttGate:
    """Sits between the keyboard hook and the session.

    The hook does not swallow keys, so typing in the Settings window would start
    recordings. While suspended a press is dropped; a release is always forwarded
    (the session ignores it unless a recording is running, and a recording that
    began before the pause must still be able to end). Suspends nest. ``press`` and
    ``release`` run on the keyboard hook thread, ``suspend``/``resume`` on the UI thread.
    """

    def __init__(self, on_press: Callable[[], None], on_release: Callable[[], None]) -> None:
        self._on_press = on_press
        self._on_release = on_release
        self._lock = threading.Lock()
        self._depth = 0

    @property
    def suspended(self) -> bool:
        """Whether presses are currently dropped."""
        with self._lock:
            return self._depth > 0

    def press(self) -> None:
        """Forward a key press unless suspended."""
        if not self.suspended:
            self._on_press()

    def release(self) -> None:
        """Forward a key release."""
        self._on_release()

    def suspend(self) -> None:
        """Start dropping presses (nestable)."""
        with self._lock:
            self._depth += 1

    def resume(self) -> None:
        """Undo one ``suspend``; extra calls are harmless."""
        with self._lock:
            self._depth = max(0, self._depth - 1)

    @contextmanager
    def paused(self) -> Iterator[None]:
        """Suspend for the duration of a ``with`` block, resuming even on errors."""
        self.suspend()
        try:
            yield
        finally:
            self.resume()
