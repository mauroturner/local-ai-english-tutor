"""Ports: the interfaces the application layer depends on."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, Protocol

import numpy as np

from .audio.cues import Cue
from .domain.models import (
    ChatMessage,
    MistakeRecord,
    PracticeReply,
    SessionFeedback,
    Transcript,
    Turn,
    TutorReply,
)
from .domain.progress import SessionStats


class AdapterError(Exception):
    """Base class for failures raised by adapters."""


class LlmUnavailable(AdapterError):
    """The language model service cannot be reached or lacks the model."""


class SttError(AdapterError):
    """Speech recognition failed."""


class TtsError(AdapterError):
    """Speech synthesis failed."""


class StorageError(AdapterError):
    """Reading or writing local data (logs, mistake history) failed."""


@dataclass(frozen=True)
class AudioClip:
    """Recorded audio at the device's native sample rate."""

    samples: np.ndarray
    sample_rate: int


class SpeechToText(Protocol):
    """Turns 16 kHz mono audio into a literal transcript."""

    def load(self) -> str:
        """Load the model and return a description of the device used."""
        ...

    def transcribe(self, audio_16k: np.ndarray, with_words: bool = False) -> Transcript:
        """Transcribe float32 mono audio sampled at 16 kHz.

        ``with_words`` also asks for word timings (``Transcript.words``); the
        text must be exactly the same either way.
        """
        ...


class TutorModel(Protocol):
    """Conversation and feedback generator."""

    def check(self) -> None:
        """Raise LlmUnavailable when the service or model is missing."""
        ...

    def reply(self, history: Sequence[ChatMessage], user_text: str) -> TutorReply:
        """Answer the learner and report the mistakes found in ``user_text``."""
        ...

    def feedback(self, turns: Sequence[Turn]) -> SessionFeedback:
        """Write the overall end-of-session feedback."""
        ...


class SpeechSynthesizer(Protocol):
    """Reads text aloud."""

    available: bool

    def speak(self, text: str, length_scale: float = 1.0) -> None:
        """Speak ``text`` and block until playback ends.

        ``length_scale`` stretches the speech: 1.0 is normal, above 1 is slower.
        """
        ...


class AudioRecorder(Protocol):
    """Captures microphone audio between start and stop."""

    def start(self, device_index: int | None) -> None:
        """Begin recording from the given device (None = system default)."""
        ...

    def stop(self) -> AudioClip:
        """Stop recording and return everything captured."""
        ...


class PushToTalk(Protocol):
    """Global push-to-talk key listener."""

    def start(self, on_press: Callable[[], None], on_release: Callable[[], None]) -> None:
        """Start listening; callbacks must return immediately."""
        ...

    def stop(self) -> None:
        """Stop listening."""
        ...


LogSpeaker = Literal["you", "tutor", "tip", "natural", "pause", "report", "practice"]


class ConversationLog(Protocol):
    """Append-only record of what was said, one file per session."""

    def record(self, speaker: LogSpeaker, text: str) -> None:
        """Append one entry; raises StorageError when it cannot be written."""
        ...

    def new_session(self) -> None:
        """Make the next ``record`` start a new file."""
        ...


class MistakeStore(Protocol):
    """Persistent mistake history."""

    def load(self) -> list[MistakeRecord]:
        """Return the stored records; raises StorageError when unusable."""
        ...

    def save(self, records: Sequence[MistakeRecord]) -> None:
        """Replace the stored records; raises StorageError on failure."""
        ...


class SessionStatsStore(Protocol):
    """Persistent per-session statistics."""

    def load(self) -> list[SessionStats]:
        """Return the stored sessions, oldest first; raises StorageError when unusable."""
        ...

    def append(self, stats: SessionStats) -> None:
        """Add one finished session; raises StorageError on failure."""
        ...


class SettingsStore(Protocol):
    """Persistent user settings as a plain field-name -> value mapping."""

    def load(self) -> dict[str, Any]:
        """Return the stored mapping (empty when nothing is saved yet).

        Raises StorageError when the file was unusable and had to be set aside.
        """
        ...

    def save(self, data: Mapping[str, Any]) -> None:
        """Replace the stored mapping; raises StorageError on failure."""
        ...


class AutoStart(Protocol):
    """Start-with-the-operating-system registration (state lives in the OS)."""

    def is_enabled(self) -> bool:
        """Whether an auto-start entry exists."""
        ...

    def is_stale(self) -> bool:
        """Whether the entry exists but points somewhere other than this install."""
        ...

    def enable(self) -> None:
        """Create or rewrite the entry; raises StorageError on failure."""
        ...

    def disable(self) -> None:
        """Remove the entry; raises StorageError on failure."""
        ...


class PracticeCoach(Protocol):
    """Runs one turn of a targeted practice drill."""

    def practice(
        self, target: MistakeRecord, history: Sequence[ChatMessage], learner_text: str
    ) -> PracticeReply:
        """Judge ``learner_text`` against ``target`` and ask the next question."""
        ...


class CuePlayer(Protocol):
    """Plays short sound cues; ``play`` never blocks and never raises."""

    def play(self, cue: Cue) -> None:
        """Play ``cue`` unless another one is still playing."""
        ...

    def close(self) -> None:
        """Release the audio output."""
        ...


class Notifier(Protocol):
    """Shows a desktop notification; ``notify`` never blocks and never raises."""

    def notify(self, title: str, body: str) -> None:
        """Tell the user something while the window may be in the background."""
        ...


class ConnectionStatus(Enum):
    """Outcome of checking an Ollama server and model (see ``ConnectionCheck``)."""

    OK = "ok"
    MODEL_MISSING = "model_missing"
    UNREACHABLE = "unreachable"
    TIMEOUT = "timeout"
    BAD_URL = "bad_url"


@dataclass(frozen=True)
class ConnectionResult:
    """What a connection check found; ``detail`` is English text for logs and support."""

    status: ConnectionStatus
    detail: str = ""


ConnectionCheck = Callable[[str, str], ConnectionResult]
"""``check(url, model) -> ConnectionResult``; never raises, may block up to a few seconds."""
