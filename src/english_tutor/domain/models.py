"""Pure domain value objects shared by every layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal


class Severity(str, Enum):
    """How noticeable a learner mistake is."""

    MAJOR = "major"
    MINOR = "minor"


class SessionState(Enum):
    """Lifecycle states of a conversation session."""

    LOADING = "loading"
    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"
    REPORTING = "reporting"


@dataclass(frozen=True)
class Correction:
    """A single mistake found in the learner's speech."""

    original: str
    corrected: str
    explanation: str
    severity: Severity


@dataclass(frozen=True)
class TutorReply:
    """Parsed answer of the tutor model for one turn."""

    reply: str
    corrections: tuple[Correction, ...] = ()
    parsed_ok: bool = True


@dataclass(frozen=True)
class Turn:
    """One completed learner/tutor exchange."""

    index: int
    user_text: str
    tutor_reply: str
    corrections: tuple[Correction, ...]
    live_correction: Correction | None


@dataclass(frozen=True)
class Transcript:
    """Raw speech-to-text output."""

    text: str
    duration_s: float


@dataclass(frozen=True)
class ChatMessage:
    """One message of the LLM conversation."""

    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class SessionFeedback:
    """Overall end-of-session feedback written by the tutor model."""

    summary: str
    strengths: tuple[str, ...] = ()
    focus_areas: tuple[str, ...] = ()


@dataclass(frozen=True)
class SessionReport:
    """Everything shown to the learner when the session ends."""

    turn_count: int
    major_errors: tuple[Correction, ...]
    minor_errors: tuple[Correction, ...]
    feedback: SessionFeedback | None
    feedback_error: str | None = None


class PracticeOutcome(str, Enum):
    """Whether the learner used the practised structure correctly."""

    CORRECT = "correct"
    INCORRECT = "incorrect"
    NOT_USED = "not_used"


@dataclass(frozen=True)
class PracticeReply:
    """The coach's answer to one practice turn."""

    outcome: PracticeOutcome
    feedback: str
    next_prompt: str
    parsed_ok: bool = True


@dataclass(frozen=True)
class MistakeRecord:
    """A recurring mistake, grouped by its normalized original/corrected pair."""

    key: str
    original: str
    corrected: str
    explanation: str
    severity: Severity
    count: int
    first_seen: datetime
    last_seen: datetime
    examples: tuple[str, ...]
    practice_attempts: int = 0
    practice_successes: int = 0
