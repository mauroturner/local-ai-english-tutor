"""ConversationSession behaviour through its public interface."""

from __future__ import annotations

from conftest import FakeRecorder, FakeSTT, FakeTTS, FakeTutor, InlineRunner, major, minor

from english_tutor.application.session import ConversationSession
from english_tutor.application.events import (
    ErrorRaised,
    ReportReady,
    StateChanged,
    TutorSaid,
    UserSaid,
)
from english_tutor.domain.models import SessionState, TutorReply
from english_tutor.ports import LlmUnavailable, TtsError


def states(h) -> list[SessionState]:
    return [e.state for e in h.of_type(StateChanged)]


def test_start_loads_models_and_becomes_idle(make_harness):
    h = make_harness()
    assert h.stt.loaded
    assert h.session.state is SessionState.IDLE
    assert states(h)[0] is SessionState.LOADING


def test_ready_status_names_the_configured_ptt_label(make_harness):
    h = make_harness()
    assert h.of_type(StateChanged)[-1].message == "Ready: hold Right Ctrl"
    events: list = []
    session = ConversationSession(
        FakeSTT(), FakeTutor(), FakeTTS(True), FakeRecorder(), events.append,
        runner=InlineRunner(), ptt_label="F9",
    )
    session.start()
    assert [e for e in events if isinstance(e, StateChanged)][-1].message == "Ready: hold F9"


def test_start_warns_when_ollama_down_but_stays_usable(make_harness):
    h = make_harness()
    h.tutor.check_error = LlmUnavailable("Ollama not reachable")
    h.session.start()
    assert any("Ollama not reachable" in e.message for e in h.of_type(ErrorRaised))
    assert h.session.state is SessionState.IDLE


def test_start_warns_when_tts_unavailable(make_harness):
    h = make_harness(tts_available=False)
    assert any("text-only" in e.message for e in h.of_type(ErrorRaised))
    assert h.session.state is SessionState.IDLE


def test_turn_state_transitions_in_order(make_harness):
    h = make_harness(["I like music"], [TutorReply("Nice! What kind?")])
    h.events.clear()
    h.say()
    assert states(h) == [
        SessionState.RECORDING,
        SessionState.TRANSCRIBING,
        SessionState.THINKING,
        SessionState.SPEAKING,
        SessionState.IDLE,
    ]


def test_press_ignored_when_not_idle(make_harness):
    h = make_harness()
    h.session.on_ptt_press()
    h.session.on_ptt_press()  # second press while RECORDING
    assert h.recorder.started_with == [None]
    assert h.session.state is SessionState.RECORDING


def test_release_ignored_when_not_recording(make_harness):
    h = make_harness()
    h.session.on_ptt_release()
    assert h.recorder.stops == 0
    assert h.session.state is SessionState.IDLE


def test_selected_device_is_used_for_recording(make_harness):
    h = make_harness()
    h.session.set_input_device(7)
    h.session.on_ptt_press()
    assert h.recorder.started_with == [7]


def test_raw_transcript_flows_unchanged(make_harness):
    raw = "Hi - Could you hear me?"
    h = make_harness([raw], [TutorReply("Yes, I can! How are you?")])
    h.say()
    assert h.of_type(UserSaid)[0].text == raw
    assert h.session.turns[0].user_text == raw
    assert h.tutor.calls[0][1] == raw


def test_short_transcript_is_not_dropped(make_harness):
    h = make_harness(["Hi there"], [TutorReply("Hello! How are you?")])
    h.say()
    assert h.of_type(UserSaid)[0].text == "Hi there"
    assert len(h.session.turns) == 1


def test_empty_transcript_is_dropped(make_harness):
    h = make_harness(["   "], [])
    h.say()
    assert h.of_type(UserSaid) == []
    assert h.tutor.calls == []
    assert h.session.state is SessionState.IDLE


def test_too_quiet_clip_skips_stt(make_harness):
    import numpy as np

    from english_tutor.ports import AudioClip

    h = make_harness()
    h.recorder.clip = AudioClip(np.zeros((16000, 1), dtype=np.float32), 16000)
    h.say()
    assert h.stt.received == []
    assert h.session.state is SessionState.IDLE


def test_spoken_is_correction_line_then_reply(make_harness):
    fix = major("I go", "I went", "Past tense.")
    h = make_harness(
        ["yesterday I go to the park"],
        [TutorReply("Sounds fun! Who went with you?", (fix,))],
    )
    h.say()
    said = h.of_type(TutorSaid)[0]
    assert said.correction == fix
    assert h.tts.spoken == [
        "Quick tip: instead of 'I go', say 'I went'. Sounds fun! Who went with you?"
    ]


def test_only_one_live_correction_per_turn_others_recorded_silently(make_harness):
    first = major("I go", "I went")
    second = major("he don't", "he doesn't")
    small = minor("the Paris", "Paris")
    h = make_harness(
        ["yesterday I go and he don't like the Paris"],
        [TutorReply("Interesting! Why?", (first, second, small))],
    )
    h.say()
    said = h.of_type(TutorSaid)[0]
    assert said.correction == first
    assert h.tts.spoken[0].count("Quick tip") == 1
    assert h.session.turns[0].corrections == (first, second, small)


def test_minor_only_turn_shows_and_speaks_no_correction(make_harness):
    small = minor("the Paris", "Paris")
    h = make_harness(["I love the Paris"], [TutorReply("Me too! Why?", (small,))])
    h.say()
    assert h.of_type(TutorSaid)[0].correction is None
    assert h.tts.spoken == ["Me too! Why?"]
    assert h.session.turns[0].corrections == (small,)


def test_invented_and_cosmetic_corrections_are_dropped(make_harness):
    invented = major("she go", "she goes")
    cosmetic = major("hi", "Hi,")
    h = make_harness(["hi I am fine"], [TutorReply("Great!", (invented, cosmetic))])
    h.say()
    assert h.session.turns[0].corrections == ()
    assert h.of_type(TutorSaid)[0].correction is None


def test_tts_failure_falls_back_to_text_only(make_harness):
    h = make_harness(["hello there"], [TutorReply("Hi! How are you?")])
    h.tts.error = TtsError("boom")
    h.say()
    assert h.of_type(TutorSaid)[0].text == "Hi! How are you?"
    assert h.session.state is SessionState.IDLE


def test_nothing_spoken_when_tts_unavailable(make_harness):
    h = make_harness(["hello there"], [TutorReply("Hi!")], tts_available=False)
    h.say()
    assert h.tts.spoken == []
    assert len(h.of_type(TutorSaid)) == 1


def test_ollama_down_returns_to_idle_and_turn_not_saved(make_harness):
    h = make_harness(["hello there"], [LlmUnavailable("Ollama not reachable")])
    h.say()
    assert h.session.state is SessionState.IDLE
    assert h.session.turns == ()
    assert any("not reachable" in e.message for e in h.of_type(ErrorRaised))
    assert h.of_type(TutorSaid) == []


def test_history_is_sent_with_each_turn_and_bounded(make_harness):
    texts = [f"message {i}" for i in range(4)]
    h = make_harness(texts, [TutorReply(f"reply {i}") for i in range(4)], history_exchanges=2)
    for _ in texts:
        h.say()
    sent_history, _ = h.tutor.calls[3]
    assert [m.content for m in sent_history] == [
        "message 1", "reply 1", "message 2", "reply 2",
    ]
    assert [m.role for m in sent_history] == ["user", "assistant", "user", "assistant"]
    assert len(h.session.turns) == 4


def test_end_session_builds_report_and_resets(make_harness):
    h = make_harness(
        ["yesterday I go home", "I love the Paris"],
        [
            TutorReply("Nice!", (major("I go", "I went"),)),
            TutorReply("Cool!", (minor("the Paris", "Paris"),)),
        ],
    )
    h.say()
    h.say()
    h.events.clear()
    h.tts.spoken.clear()
    h.session.end_session()
    report = h.of_type(ReportReady)[0].report
    assert report.turn_count == 2
    assert [c.original for c in report.major_errors] == ["I go"]
    assert [c.original for c in report.minor_errors] == ["the Paris"]
    assert report.feedback is not None and report.feedback.summary == "Nice work."
    assert h.tts.spoken == ["Nice work."]
    assert h.session.turns == ()
    assert h.session.state is SessionState.IDLE
    assert len(h.tutor.feedback_turns[0]) == 2
    # history was reset: the next turn is sent with no previous messages
    h.stt.texts.append("again")
    h.tutor.replies.append(TutorReply("Yes!"))
    h.say()
    assert h.tutor.calls[-1][0] == []


def test_report_dedupes_repeated_errors(make_harness):
    h = make_harness(
        ["yesterday I go", "today I go"],
        [TutorReply("a", (major("I go", "I went"),)), TutorReply("b", (major("I go", "I went"),))],
    )
    h.say()
    h.say()
    h.session.end_session()
    assert len(h.of_type(ReportReady)[0].report.major_errors) == 1


def test_zero_turn_report_skips_llm(make_harness):
    h = make_harness()
    h.session.end_session()
    report = h.of_type(ReportReady)[0].report
    assert report.turn_count == 0
    assert report.major_errors == () and report.minor_errors == ()
    assert report.feedback is None
    assert h.tutor.feedback_turns == []
    assert h.session.state is SessionState.IDLE


def test_report_keeps_errors_when_feedback_fails(make_harness):
    h = make_harness(["yesterday I go"], [TutorReply("a", (major("I go", "I went"),))])
    h.tutor.feedback_result = LlmUnavailable("Ollama down")
    h.say()
    h.session.end_session()
    report = h.of_type(ReportReady)[0].report
    assert report.feedback is None
    assert report.feedback_error == "Ollama down"
    assert len(report.major_errors) == 1


def test_end_session_ignored_unless_idle(make_harness):
    h = make_harness()
    h.session.on_ptt_press()
    h.session.end_session()
    assert h.of_type(ReportReady) == []
    assert h.session.state is SessionState.RECORDING
