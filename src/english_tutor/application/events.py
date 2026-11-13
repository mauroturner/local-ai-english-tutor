"""Events emitted by the conversation session for the UI to render."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from ..domain.models import (
    Correction,
    MistakeRecord,
    PracticeOutcome,
    SessionReport,
    SessionState,
)


@dataclass(frozen=True)
class StateChanged:
    """The session moved to a new state."""

    state: SessionState
    message: str = ""


@dataclass(frozen=True)
class UserSaid:
    """The learner's raw Whisper transcript."""

    text: str


@dataclass(frozen=True)
class TutorSaid:
    """The tutor's reply plus the single live correction, if any."""

    text: str
    correction: Correction | None = None
    natural: str | None = None  # a more natural way to say what the learner said


@dataclass(frozen=True)
class ReportReady:
    """The end-of-session report."""

    report: SessionReport


@dataclass(frozen=True)
class ErrorRaised:
    """A recoverable problem worth showing to the learner."""

    message: str


@dataclass(frozen=True)
class LevelChanged:
    """Microphone level between 0.0 and 1.0."""

    value: float


@dataclass(frozen=True)
class MistakesChanged:
    """The mistake history changed; carries the full ranked list."""

    mistakes: tuple[MistakeRecord, ...]


@dataclass(frozen=True)
class PracticeChanged:
    """A practice drill started (``target`` set) or stopped (``None``)."""

    target: MistakeRecord | None


@dataclass(frozen=True)
class PracticeFeedback:
    """The coach's verdict on one practice answer plus the next question."""

    outcome: PracticeOutcome
    feedback: str
    prompt: str


@dataclass(frozen=True)
class DataCleared:
    """Stored data was deleted: ``count`` conversation log files or mistake records."""

    kind: Literal["logs", "mistakes"]
    count: int


SessionEvent = (
    StateChanged
    | UserSaid
    | TutorSaid
    | ReportReady
    | ErrorRaised
    | LevelChanged
    | MistakesChanged
    | PracticeChanged
    | PracticeFeedback
    | DataCleared
)
EventSink = Callable[[SessionEvent], None]
