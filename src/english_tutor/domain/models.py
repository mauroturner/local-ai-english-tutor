"""Pure domain value objects shared by every layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Literal


class Severity(str, Enum):
    """How noticeable a learner mistake is."""

    MAJOR = "major"
    MINOR = "minor"
    HESITATION = "hesitation"  # a long pause, not an error (see domain.hesitation)


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


PAUSE_MARK = "…"


@dataclass(frozen=True)
class TimedWord:
    """One recognised word with its position in the recording, in seconds."""

    text: str
    start_s: float
    end_s: float


@dataclass(frozen=True)
class Hesitation:
    """A long pause: the words around it and how long it lasted."""

    before: str  # empty for a pause before the first word
    after: str
    pause_s: float

    @property
    def phrase(self) -> str:
        """The words said without the pause, e.g. ``how's everything``."""
        return " ".join(part for part in (self.before, self.after) if part)

    @property
    def marked(self) -> str:
        """The words with the pause shown, e.g. ``how's … everything``."""
        return " ".join(part for part in (self.before, PAUSE_MARK, self.after) if part)

    @property
    def at_start(self) -> bool:
        """Whether the pause came before the first word."""
        return not self.before


@dataclass(frozen=True)
class Turn:
    """One completed learner/tutor exchange."""

    index: int
    user_text: str
    tutor_reply: str
    corrections: tuple[Correction, ...]
    live_correction: Correction | None
    hesitations: tuple[Hesitation, ...] = ()
    speech_s: float = 0.0  # seconds of recorded speech


@dataclass(frozen=True)
class Transcript:
    """Raw speech-to-text output."""

    text: str
    duration_s: float
    words: tuple[TimedWord, ...] = ()  # empty when the recogniser gave no timings


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
    pauses: tuple[Hesitation, ...] = ()  # inside sentences
    slow_starts: tuple[tuple[str, float], ...] = ()  # (tutor question, seconds to start)


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
class ReviewState:
    """When a mistake is next due for review and how far up the schedule it has climbed."""

    due: date
    step: int = 0  # position in the review ladder (see domain.review_schedule)


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
    category: str | None = None  # kind of mistake, once known
    review: ReviewState | None = None  # None until the mistake is scheduled
