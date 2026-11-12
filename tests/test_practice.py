"""Practice mode: the drill object and its use inside the session."""

from __future__ import annotations

import pytest
from conftest import FakeCoach

from english_tutor.application.events import (
    ErrorRaised,
    MistakesChanged,
    PracticeChanged,
    PracticeFeedback,
    ReportReady,
    StateChanged,
    TutorSaid,
    UserSaid,
)
from english_tutor.application.practice import PracticeDrill
from english_tutor.domain.models import PracticeOutcome, PracticeReply, SessionState, TutorReply
from english_tutor.ports import LlmUnavailable

KEY = "she go => she goes"


def reply(outcome=PracticeOutcome.CORRECT, feedback="Great.", prompt="What next?", ok=True):
    return PracticeReply(outcome, feedback, prompt, ok)


OPENER = reply(PracticeOutcome.NOT_USED, "Let's practice.", "Where is she?")


@pytest.fixture
def ready(make_harness, fake_store, fake_log, old_record):
    """A harness holding one stored mistake and a scripted coach."""

    def _make(coach_replies=(), texts=(), tutor_replies=()):
        fake_store.records = [old_record]
        coach = FakeCoach(coach_replies)
        h = make_harness(texts, tutor_replies, store=fake_store, log=fake_log, coach=coach)
        return h, coach

    return _make


def test_drill_open_sends_start_and_answer_sends_history(old_record):
    coach = FakeCoach([OPENER, reply()])
    drill = PracticeDrill(old_record)
    assert drill.open(coach) == OPENER
    drill.answer(coach, "she goes home")
    target, history, text = coach.calls[1]
    assert target == old_record and text == "she goes home"
    assert [(m.role, m.content) for m in history] == [
        ("user", "START"),
        ("assistant", "Let's practice. Where is she?"),
    ]


def test_drill_history_is_bounded(old_record):
    coach = FakeCoach([OPENER] + [reply() for _ in range(8)])
    drill = PracticeDrill(old_record, history_exchanges=4)
    drill.open(coach)
    for i in range(8):
        drill.answer(coach, f"answer {i}")
    assert len(coach.calls[-1][1]) == 8
    assert coach.calls[-1][1][-2].content == "answer 6"


def test_drill_failure_does_not_pollute_the_history(old_record):
    coach = FakeCoach([OPENER, LlmUnavailable("down"), reply()])
    drill = PracticeDrill(old_record)
    drill.open(coach)
    with pytest.raises(LlmUnavailable):
        drill.answer(coach, "lost answer")
    drill.answer(coach, "second try")
    assert [m.content for m in coach.calls[2][1] if m.role == "user"] == ["START"]


def test_start_opens_the_drill_and_speaks(ready, old_record):
    h, coach = ready([OPENER])
    h.session.start_practice(KEY)
    assert coach.calls == [(old_record, [], "START")]
    assert h.of_type(PracticeChanged)[0].target == old_record
    assert h.of_type(TutorSaid)[-1].text == "Let's practice. Where is she?"
    assert h.tts.spoken == ["Let's practice. Where is she?"]
    last = h.of_type(StateChanged)[-1]
    assert last.state is SessionState.IDLE
    assert last.message == "Practice: hold V to answer"


def test_start_is_journaled(ready, fake_log):
    h, _ = ready([OPENER])
    h.session.start_practice(KEY)
    assert fake_log.entries == [
        ("practice", "Started: 'she go' -> 'she goes'"),
        ("tutor", "Let's practice. Where is she?"),
    ]


def test_answer_gets_feedback_and_updates_stats(ready, fake_store, fake_log):
    h, coach = ready([OPENER, reply(PracticeOutcome.CORRECT, "Perfect.", "Who is she?")],
                     texts=["she goes home"])
    h.session.start_practice(KEY)
    h.say()
    feedback = h.of_type(PracticeFeedback)[0]
    assert (feedback.outcome, feedback.feedback, feedback.prompt) == (
        PracticeOutcome.CORRECT, "Perfect.", "Who is she?",
    )
    assert h.of_type(UserSaid)[0].text == "she goes home"
    assert coach.calls[1][2] == "she goes home"
    saved = fake_store.saves[-1][0]
    assert (saved.practice_attempts, saved.practice_successes) == (1, 1)
    assert h.of_type(MistakesChanged)[-1].mistakes[0].practice_attempts == 1
    assert h.tts.spoken[-1] == "Perfect. Who is she?"
    assert fake_log.entries[-3:] == [
        ("you", "she goes home"),
        ("practice", "[correct] Perfect."),
        ("tutor", "Who is she?"),
    ]
    assert h.session.state is SessionState.IDLE


def test_incorrect_counts_an_attempt_only(ready, fake_store):
    h, _ = ready([OPENER, reply(PracticeOutcome.INCORRECT)], texts=["she go home"])
    h.session.start_practice(KEY)
    h.say()
    saved = fake_store.saves[-1][0]
    assert (saved.practice_attempts, saved.practice_successes) == (1, 0)


def test_not_used_and_unparsed_replies_do_not_change_stats(ready, fake_store):
    unparsed = reply(PracticeOutcome.CORRECT, "", "Just talk.", ok=False)
    h, _ = ready([OPENER, reply(PracticeOutcome.NOT_USED), unparsed], texts=["a b", "c d"])
    h.session.start_practice(KEY)
    h.say()
    h.say()
    assert fake_store.saves == []
    assert len(h.of_type(PracticeFeedback)) == 2


def test_practice_turns_skip_the_tutor_and_the_report(ready):
    h, _ = ready([OPENER, reply()], texts=["she goes home"])
    h.session.start_practice(KEY)
    h.say()
    assert h.tutor.calls == []
    assert h.session.turns == ()


def test_stop_returns_to_the_conversation_with_untouched_history(ready):
    h, coach = ready(
        [OPENER, reply()], texts=["she goes home", "hello there"],
        tutor_replies=[TutorReply("Hi!")],
    )
    h.session.start_practice(KEY)
    h.say()
    h.session.stop_practice()
    assert h.of_type(PracticeChanged)[-1].target is None
    assert h.session.state is SessionState.IDLE
    h.say()
    assert len(coach.calls) == 2  # no further coach call
    assert h.tutor.calls == [([], "hello there")]  # history had no practice messages


def test_stop_is_journaled(ready, fake_log):
    h, _ = ready([OPENER])
    h.session.start_practice(KEY)
    h.session.stop_practice()
    assert fake_log.entries[-1] == ("practice", "Stopped practice")


def test_start_ignored_unless_idle_or_when_already_practicing(ready):
    h, coach = ready([OPENER, OPENER], texts=["hello there"], tutor_replies=[TutorReply("Hi!")])
    h.session.on_ptt_press()  # RECORDING
    h.session.start_practice(KEY)
    assert coach.calls == []
    h.session.on_ptt_release()  # the turn completes and the session is idle again
    h.session.start_practice(KEY)
    assert len(coach.calls) == 1
    h.session.start_practice(KEY)  # already practicing
    assert len(coach.calls) == 1


def test_stop_ignored_without_a_drill_or_when_busy(ready):
    h, _ = ready([OPENER])
    before = len(h.events)
    h.session.stop_practice()
    assert len(h.events) == before
    h.session.start_practice(KEY)
    h.session.on_ptt_press()
    h.session.stop_practice()
    assert h.of_type(PracticeChanged)[-1].target is not None


@pytest.mark.parametrize("problem", ["unknown key", "no coach", "llm down"])
def test_start_failures_stay_in_the_conversation(
    make_harness, fake_store, old_record, problem
):
    fake_store.records = [old_record]
    coach = FakeCoach([LlmUnavailable("Ollama not reachable")])
    key = "nope => nope" if problem == "unknown key" else KEY
    h = make_harness(
        ["hello there"], [TutorReply("Hi!")], store=fake_store,
        coach=None if problem == "no coach" else coach,
    )
    h.session.start_practice(key)
    assert h.of_type(ErrorRaised)
    assert h.of_type(PracticeChanged) == []
    assert h.session.state is SessionState.IDLE
    h.say()
    assert h.tutor.calls == [([], "hello there")]


def test_coach_failure_during_an_answer_keeps_the_drill(ready):
    h, coach = ready([OPENER, LlmUnavailable("down"), reply()], texts=["x y", "z w"])
    h.session.start_practice(KEY)
    h.say()
    assert any("down" in e.message for e in h.of_type(ErrorRaised))
    assert h.session.state is SessionState.IDLE
    h.say()
    assert len(coach.calls) == 3
    assert h.tutor.calls == []


def test_end_session_is_ignored_while_practicing(ready):
    h, _ = ready([OPENER])
    h.session.start_practice(KEY)
    h.session.end_session()
    assert h.of_type(ReportReady) == []
    assert h.session.state is SessionState.IDLE
    h.session.stop_practice()
    h.session.end_session()
    assert len(h.of_type(ReportReady)) == 1
