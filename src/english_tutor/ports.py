"""Ports: the interfaces the application layer depends on."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from .domain.models import ChatMessage, SessionFeedback, Transcript, Turn, TutorReply


class AdapterError(Exception):
    """Base class for failures raised by adapters."""


class LlmUnavailable(AdapterError):
    """The language model service cannot be reached or lacks the model."""


class SttError(AdapterError):
    """Speech recognition failed."""


class TtsError(AdapterError):
    """Speech synthesis failed."""


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

    def transcribe(self, audio_16k: np.ndarray) -> Transcript:
        """Transcribe float32 mono audio sampled at 16 kHz."""
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

    def speak(self, text: str) -> None:
        """Speak ``text`` and block until playback ends."""
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
