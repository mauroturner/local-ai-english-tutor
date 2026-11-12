"""The session journals each turn without ever depending on the log."""

from __future__ import annotations

from conftest import major

from english_tutor.application.events import ErrorRaised, TutorSaid
from english_tutor.domain.models import SessionState, TutorReply


def test_turn_is_journaled_in_order(make_harness, fake_log):
    reply = TutorReply("Why?", (major("I go", "I went", "Past tense."),))
    h = make_harness(["I go home"], [reply], log=fake_log)
    h.say()
    assert fake_log.entries == [
        ("you", "I go home"),
        ("tutor", "Why?"),
        ("tip", '"I go" -> "I went" (Past tense.) [major]'),
    ]


def test_no_tip_entry_without_a_live_correction(make_harness, fake_log):
    h = make_harness(["hello there"], [TutorReply("Hi!")], log=fake_log)
    h.say()
    assert [speaker for speaker, _ in fake_log.entries] == ["you", "tutor"]


def test_raw_transcript_is_logged_exactly(make_harness, fake_log):
    raw = "  i  go   playa,  "
    h = make_harness([raw], [TutorReply("ok")], log=fake_log)
    h.say()
    assert fake_log.entries[0] == ("you", raw)


def test_report_is_journaled_then_the_log_starts_a_new_session(make_harness, fake_log):
    h = make_harness(["hello there"], [TutorReply("Hi!")], log=fake_log)
    h.say()
    assert fake_log.sessions == 0
    h.session.end_session()
    speaker, text = fake_log.entries[-1]
    assert speaker == "report" and text.startswith("SESSION REPORT (1 turns)")
    assert fake_log.sessions == 1


def test_log_failure_never_blocks_a_turn_and_warns_once(make_harness, fake_log):
    fake_log.fail = True
    h = make_harness(
        ["hello there", "how are you"], [TutorReply("Hi!"), TutorReply("Fine.")], log=fake_log
    )
    h.say()
    h.say()
    assert h.session.state is SessionState.IDLE
    assert len(h.of_type(TutorSaid)) == 2
    warnings = [e for e in h.of_type(ErrorRaised) if "Conversation log unavailable" in e.message]
    assert len(warnings) == 1
    assert "disk full" in warnings[0].message


def test_log_failure_on_report_still_resets_the_session(make_harness, fake_log):
    h = make_harness(["hello there"], [TutorReply("Hi!")], log=fake_log)
    h.say()
    fake_log.fail = True
    h.session.end_session()
    assert h.session.state is SessionState.IDLE
    assert h.session.turns == ()
