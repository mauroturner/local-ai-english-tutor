"""Shared fakes: no hardware, network or GUI is ever touched."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import pytest

from english_tutor.application.session import ConversationSession
from english_tutor.application.worker import InlineRunner
from english_tutor.domain.models import (
    ChatMessage,
    Correction,
    SessionFeedback,
    Severity,
    Transcript,
    Turn,
    TutorReply,
)
from english_tutor.ports import AudioClip, LlmUnavailable, TtsError


def major(original: str, corrected: str, why: str = "because") -> Correction:
    """Build a major correction."""
    return Correction(original, corrected, why, Severity.MAJOR)


def minor(original: str, corrected: str, why: str = "because") -> Correction:
    """Build a minor correction."""
    return Correction(original, corrected, why, Severity.MINOR)


class FakeSTT:
    """Returns scripted transcripts, unchanged."""

    def __init__(self, texts: Sequence[str] = ()) -> None:
        self.texts = list(texts)
        self.loaded = False
        self.received: list[np.ndarray] = []

    def load(self) -> str:
        self.loaded = True
        return "fake-device"

    def transcribe(self, audio_16k: np.ndarray) -> Transcript:
        self.received.append(audio_16k)
        return Transcript(self.texts.pop(0), 1.0)


class FakeTutor:
    """Scripted tutor; items may be TutorReply or an exception to raise."""

    def __init__(self, replies: Sequence[TutorReply | Exception] = ()) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[list[ChatMessage], str]] = []
        self.feedback_turns: list[Sequence[Turn]] = []
        self.feedback_result: SessionFeedback | Exception = SessionFeedback(
            "Nice work.", ("fluent",), ("tenses",)
        )
        self.check_error: Exception | None = None

    def check(self) -> None:
        if self.check_error is not None:
            raise self.check_error

    def reply(self, history: Sequence[ChatMessage], user_text: str) -> TutorReply:
        self.calls.append((list(history), user_text))
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def feedback(self, turns: Sequence[Turn]) -> SessionFeedback:
        self.feedback_turns.append(turns)
        if isinstance(self.feedback_result, Exception):
            raise self.feedback_result
        return self.feedback_result


class FakeTTS:
    """Records what would be spoken."""

    def __init__(self, available: bool = True) -> None:
        self.available = available
        self.spoken: list[str] = []
        self.error: Exception | None = None

    def speak(self, text: str) -> None:
        if self.error is not None:
            raise self.error
        self.spoken.append(text)


class FakeRecorder:
    """Returns a fixed audible clip."""

    def __init__(self, clip: AudioClip | None = None) -> None:
        tone = (0.5 * np.sin(np.linspace(0, 440 * 2 * np.pi, 16000))).astype(np.float32)
        self.clip = clip or AudioClip(tone.reshape(-1, 1), 16000)
        self.started_with: list[int | None] = []
        self.stops = 0

    def start(self, device_index: int | None) -> None:
        self.started_with.append(device_index)

    def stop(self) -> AudioClip:
        self.stops += 1
        return self.clip


@dataclass
class Harness:
    """A session wired to fakes plus the events it emitted."""

    session: ConversationSession
    stt: FakeSTT
    tutor: FakeTutor
    tts: FakeTTS
    recorder: FakeRecorder
    events: list = field(default_factory=list)

    def say(self) -> None:
        """Simulate holding and releasing the push-to-talk key."""
        self.session.on_ptt_press()
        self.session.on_ptt_release()

    def of_type(self, kind: type) -> list:
        return [e for e in self.events if isinstance(e, kind)]


@pytest.fixture
def make_harness():
    """Factory building a ready (IDLE) session around fakes."""

    def _make(texts=(), replies=(), tts_available=True, history_exchanges=6) -> Harness:
        events: list = []
        stt, tutor = FakeSTT(texts), FakeTutor(replies)
        tts, recorder = FakeTTS(tts_available), FakeRecorder()
        session = ConversationSession(
            stt, tutor, tts, recorder, events.append,
            history_exchanges=history_exchanges, runner=InlineRunner(),
        )
        session.start()
        return Harness(session, stt, tutor, tts, recorder, events)

    return _make


__all__ = ["LlmUnavailable", "TtsError", "major", "minor"]
