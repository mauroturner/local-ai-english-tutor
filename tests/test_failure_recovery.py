"""Unexpected failures must never leave the session stuck outside IDLE."""

from __future__ import annotations

import pytest

from english_tutor.adapters.ollama_chat import OllamaTutorModel
from english_tutor.adapters.piper_tts import PiperSynthesizer
from english_tutor.application.events import ErrorRaised, ReportReady
from english_tutor.application.history import ChatHistory
from english_tutor.config import ConfigError, load_config
from english_tutor.domain.models import SessionState, TutorReply
from english_tutor.ports import LlmUnavailable, TtsError

from test_ollama_chat import FakeResponse, FakeSession


def test_unexpected_check_error_still_reaches_idle(make_harness):
    h = make_harness()
    h.tutor.check_error = RuntimeError("weird payload")
    h.session.start()
    assert h.session.state is SessionState.IDLE
    assert any("weird payload" in e.message for e in h.of_type(ErrorRaised))


def test_unexpected_tts_error_returns_to_idle_and_keeps_turn(make_harness):
    h = make_harness(["I like music"], [TutorReply("Nice! What kind?")])
    h.tts.error = OSError("disk full")
    h.say()
    assert h.session.state is SessionState.IDLE
    assert len(h.session.turns) == 1
    assert any("disk full" in e.message for e in h.of_type(ErrorRaised))


def test_unexpected_feedback_error_still_reports_and_resets(make_harness):
    h = make_harness(["I go home"], [TutorReply("Why?")])
    h.say()
    h.tutor.feedback_result = RuntimeError("boom")
    h.session.end_session()
    assert h.session.state is SessionState.IDLE
    assert h.of_type(ReportReady)
    assert h.session.turns == ()


def test_history_zero_keeps_no_memory():
    history = ChatHistory(0)
    history.add_exchange("hi", "hello")
    assert history.messages() == []


def test_negative_history_is_rejected():
    with pytest.raises(ConfigError, match="TUTOR_HISTORY_EXCHANGES"):
        load_config({"TUTOR_HISTORY_EXCHANGES": "-1"})


@pytest.mark.parametrize("payload", [{"models": None}, {"models": ["m:1"]}, ["m:1"]])
def test_check_unexpected_tags_payload_raises_llm_unavailable(payload):
    tutor = OllamaTutorModel("http://x:11434", "m:1", 90, 0.5, session=FakeSession(get=FakeResponse(payload)))
    with pytest.raises(LlmUnavailable):
        tutor.check()


def test_piper_temp_file_failure_raises_tts_error(tmp_path, monkeypatch):
    exe, voice = tmp_path / "piper.exe", tmp_path / "v.onnx"
    for path in (exe, voice, tmp_path / "v.onnx.json"):
        path.write_bytes(b"")
    tts = PiperSynthesizer(exe, voice)

    def no_space(*_args, **_kwargs):
        raise OSError("no space left")

    monkeypatch.setattr("tempfile.mkstemp", no_space)
    with pytest.raises(TtsError, match="no space left"):
        tts.speak("hello")
