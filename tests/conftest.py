"""Shared fakes: no hardware, network or GUI is ever touched."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pytest

from english_tutor.application.session import ConversationSession
from english_tutor.application.worker import InlineRunner
from english_tutor.domain.models import (
    ChatMessage,
    Correction,
    MistakeRecord,
    PracticeReply,
    SessionFeedback,
    Severity,
    Transcript,
    Turn,
    TutorReply,
)
from english_tutor.domain.progress import SessionStats
from english_tutor.ports import AudioClip, LlmUnavailable, StorageError, TtsError


def major(original: str, corrected: str, why: str = "because") -> Correction:
    """Build a major correction."""
    return Correction(original, corrected, why, Severity.MAJOR)


def minor(original: str, corrected: str, why: str = "because") -> Correction:
    """Build a minor correction."""
    return Correction(original, corrected, why, Severity.MINOR)


class FakeSTT:
    """Returns scripted transcripts, unchanged."""

    def __init__(self, texts: Sequence[str | Transcript] = ()) -> None:
        self.texts = list(texts)
        self.loaded = False
        self.received: list[np.ndarray] = []
        self.with_words: list[bool] = []

    def load(self) -> str:
        self.loaded = True
        return "fake-device"

    def transcribe(self, audio_16k: np.ndarray, with_words: bool = False) -> Transcript:
        self.received.append(audio_16k)
        self.with_words.append(with_words)
        item = self.texts.pop(0)  # a plain text, or a Transcript with word timings
        if not isinstance(item, Transcript):
            return Transcript(item, 1.0)
        return item if with_words else Transcript(item.text, item.duration_s)


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


class ManualRunner:
    """Queues jobs until a test runs them, to control thread interleavings."""

    def __init__(self) -> None:
        self.jobs: list[Callable[[], None]] = []
        self.closed = False

    def submit(self, fn: Callable[[], None]) -> None:
        self.jobs.append(fn)

    def close(self) -> None:
        self.closed = True

    def run_all(self) -> None:
        """Run queued jobs in FIFO order, including jobs they submit."""
        while self.jobs:
            self.jobs.pop(0)()


class FakeLog:
    """In-memory ConversationLog; ``fail`` makes every call raise StorageError."""

    def __init__(self) -> None:
        self.entries: list[tuple[str, str]] = []
        self.sessions = 0
        self.fail = False

    def record(self, speaker: str, text: str) -> None:
        if self.fail:
            raise StorageError("disk full")
        self.entries.append((speaker, text))

    def new_session(self) -> None:
        if self.fail:
            raise StorageError("disk full")
        self.sessions += 1


class FakeMistakeStore:
    """In-memory MistakeStore; the ``*_error`` attributes make calls raise."""

    def __init__(self) -> None:
        self.records: list[MistakeRecord] = []
        self.saves: list[list[MistakeRecord]] = []
        self.load_error: Exception | None = None
        self.save_error: Exception | None = None

    def load(self) -> list[MistakeRecord]:
        if self.load_error is not None:
            raise self.load_error
        return list(self.records)

    def save(self, records: Sequence[MistakeRecord]) -> None:
        if self.save_error is not None:
            raise self.save_error
        self.saves.append(list(records))


class FakeSessionStatsStore:
    """In-memory SessionStatsStore; ``error`` makes ``append`` raise."""

    def __init__(self) -> None:
        self.sessions: list[SessionStats] = []
        self.error: Exception | None = None
        self.load_error: Exception | None = None

    def load(self) -> list[SessionStats]:
        if self.load_error is not None:
            raise self.load_error
        return list(self.sessions)

    def append(self, stats: SessionStats) -> None:
        if self.error is not None:
            raise self.error
        self.sessions.append(stats)


class FakeCoach:
    """Scripted PracticeCoach; items may be PracticeReply or an exception to raise."""

    def __init__(self, replies: Sequence[PracticeReply | Exception] = ()) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[MistakeRecord, list[ChatMessage], str]] = []

    def practice(
        self, target: MistakeRecord, history: Sequence[ChatMessage], learner_text: str
    ) -> PracticeReply:
        self.calls.append((target, list(history), learner_text))
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeRecorder:
    """Returns a fixed audible clip; ``start`` can fail or run a hook."""

    def __init__(self, clip: AudioClip | None = None) -> None:
        self.start_error: Exception | None = None
        self.on_start: Callable[[], None] | None = None
        self.calls: list[str] = []
        tone = (0.5 * np.sin(np.linspace(0, 440 * 2 * np.pi, 16000))).astype(np.float32)
        self.clip = clip or AudioClip(tone.reshape(-1, 1), 16000)
        self.started_with: list[int | None] = []
        self.stops = 0

    def start(self, device_index: int | None) -> None:
        self.calls.append("start")
        if self.on_start is not None:
            self.on_start()
        if self.start_error is not None:
            raise self.start_error
        self.started_with.append(device_index)

    def stop(self) -> AudioClip:
        self.calls.append("stop")
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
def fake_store() -> FakeMistakeStore:
    """A fresh in-memory mistake store."""
    return FakeMistakeStore()


@pytest.fixture
def fake_stats() -> FakeSessionStatsStore:
    """A fresh in-memory session statistics store."""
    return FakeSessionStatsStore()


@pytest.fixture
def old_record() -> MistakeRecord:
    """A mistake already present in the stored history."""
    when = datetime(2026, 11, 1, 9, 0, 0)
    return MistakeRecord(
        "she go => she goes", "she go", "she goes", "Third person.", Severity.MINOR,
        4, when, when, ("she go home",),
    )


@pytest.fixture
def fake_log() -> FakeLog:
    """A fresh in-memory conversation log."""
    return FakeLog()


class FakeWinreg:
    """In-memory stand-in for the ``winreg`` module; the real registry is never touched.

    ``values`` maps (hive, sub key) to {name: data}. ``fail`` is raised by every call
    that writes, ``read_fail`` by every call that opens a key to read.
    """

    HKEY_CURRENT_USER = "HKCU"
    HKEY_LOCAL_MACHINE = "HKLM"
    KEY_READ = 0x20019
    KEY_SET_VALUE = 0x2
    REG_SZ = 1

    def __init__(self, values=None, fail=None, read_fail=None):
        self.keys = {k: dict(v) for k, v in (values or {}).items()}
        self.fail, self.read_fail = fail, read_fail
        self.hives_used: set[str] = set()
        self.writes: list[tuple] = []

    class _Handle:
        def __init__(self, values, hive_path):
            self.values, self.hive_path = values, hive_path

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def OpenKey(self, hive, path, reserved=0, access=0):  # noqa: N802
        self.hives_used.add(hive)
        if self.read_fail is not None:
            raise self.read_fail
        if (hive, path) not in self.keys:
            raise FileNotFoundError(path)
        return self._Handle(self.keys[(hive, path)], (hive, path))

    def CreateKeyEx(self, hive, path, reserved=0, access=0):  # noqa: N802
        self.hives_used.add(hive)
        if self.fail is not None:
            raise self.fail
        return self._Handle(self.keys.setdefault((hive, path), {}), (hive, path))

    def QueryValueEx(self, key, name):  # noqa: N802
        if name not in key.values:
            raise FileNotFoundError(name)
        return key.values[name], self.REG_SZ

    def SetValueEx(self, key, name, reserved, kind, data):  # noqa: N802
        if self.fail is not None:
            raise self.fail
        key.values[name] = data
        self.writes.append(("set", key.hive_path, name, kind, data))

    def DeleteValue(self, key, name):  # noqa: N802
        if self.fail is not None:
            raise self.fail
        if name not in key.values:
            raise FileNotFoundError(name)
        del key.values[name]
        self.writes.append(("delete", key.hive_path, name))


@pytest.fixture
def make_harness():
    """Factory building a ready (IDLE) session around fakes."""

    def _make(
        texts=(), replies=(), tts_available=True, history_exchanges=6, runner=None, log=None, store=None,
        coach=None, track_pauses=None, session_stats=None, suggest_natural=None,
    ) -> Harness:
        events: list = []
        stt, tutor = FakeSTT(texts), FakeTutor(replies)
        tts, recorder = FakeTTS(tts_available), FakeRecorder()
        session = ConversationSession(
            stt, tutor, tts, recorder, events.append,
            history_exchanges=history_exchanges,
            runner=runner if runner is not None else InlineRunner(),
            conversation_log=log,
            mistakes=store,
            session_stats=session_stats,
            coach=coach,
            track_pauses=track_pauses or (lambda: True),
            suggest_natural=suggest_natural or (lambda: True),
        )
        session.start()
        if isinstance(runner, ManualRunner):
            runner.run_all()
        return Harness(session, stt, tutor, tts, recorder, events)

    return _make


__all__ = ["LlmUnavailable", "TtsError", "major", "minor"]
