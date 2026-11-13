"""Listening and speaking drills (shadowing, minimal pairs, dictation) on top of the session.

The coach owns the drill state; the session decides *when* a drill may start or
end (it must be idle) and calls the coach on the worker thread.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from ..domain.drills import (
    DrillKind,
    Target,
    judge,
    pick_dictation,
    pick_pair,
    pick_shadow,
)
from ..ports import LogSpeaker
from .events import EventSink, ListeningChanged, ListeningFeedback


@dataclass(frozen=True)
class ListeningServices:
    """What the coach needs from the session."""

    emit: EventSink
    journal: Callable[[LogSpeaker, str], None]
    speak: Callable[[str], None]
    last_reply: Callable[[], str]
    """The tutor's latest reply, the source of sentences to repeat ("" when there is none)."""


class ListeningCoach:
    """Picks a sentence, says it, and judges the answer."""

    def __init__(self, svc: ListeningServices, rng: random.Random | None = None) -> None:
        self._svc = svc
        self._rng = rng or random.Random()
        self._kind: DrillKind | None = None
        self._target: Target | None = None

    @property
    def active(self) -> bool:
        """Whether a drill is running."""
        return self._kind is not None

    @property
    def kind(self) -> DrillKind | None:
        """The running drill's kind, if any."""
        return self._kind

    def open(self, kind: DrillKind) -> None:
        """Start a drill of ``kind`` with its first sentence."""
        self._kind = kind
        self.next()

    def next(self) -> None:
        """Move on to a new sentence of the running drill."""
        if self._kind is None:
            return
        reply = self._svc.last_reply()
        picks = {
            DrillKind.SHADOW: lambda: pick_shadow(reply, self._rng),
            DrillKind.PAIRS: lambda: pick_pair(self._rng),
            DrillKind.DICTATION: lambda: pick_dictation(reply, self._rng),
        }
        self._target = picks[self._kind]()
        shown = None if self._kind is DrillKind.DICTATION else self._target.text
        self._svc.emit(ListeningChanged(self._kind.value, shown))
        self._svc.journal("drill", f"{self._kind.value}: {self._target.text}")
        if self._kind is not DrillKind.PAIRS:  # in pairs the learner reads the sentence
            self._svc.speak(self._target.text)

    def answer(self, said: str) -> bool:
        """Judge ``said`` (transcript or typed text); True when it was right."""
        if self._target is None:
            return False
        verdict = judge(self._target, said)
        self._svc.emit(ListeningFeedback(verdict.perfect, verdict.feedback))
        self._svc.journal("drill", f"[{'ok' if verdict.perfect else 'retry'}] {verdict.feedback}")
        self._svc.speak(verdict.feedback)
        return verdict.perfect

    def close(self) -> None:
        """End the drill."""
        self._kind = None
        self._target = None
        self._svc.emit(ListeningChanged(None, None))
