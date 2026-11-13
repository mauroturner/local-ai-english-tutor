"""The session stores its statistics when it ends, without ever blocking the learner."""

from __future__ import annotations

from conftest import major

from english_tutor.application.events import ErrorRaised, ReportReady
from english_tutor.domain.models import SessionState, TutorReply


def test_ending_a_session_stores_its_numbers(make_harness, fake_stats):
    fix = (major("I go", "I went"),)
    h = make_harness(
        ["I go home", "and then I sleep"], [TutorReply("a", fix), TutorReply("b")],
        session_stats=fake_stats,
    )
    h.say()
    h.say()
    assert fake_stats.sessions == []  # stored at the end, not per turn
    h.session.end_session()
    assert len(fake_stats.sessions) == 1
    saved = fake_stats.sessions[0]
    assert (saved.turns, saved.words, saved.major) == (2, 7, 1)
    assert saved.speech_s == 2.0  # FakeSTT reports 1.0 s per answer


def test_a_session_without_turns_stores_nothing(make_harness, fake_stats):
    h = make_harness(session_stats=fake_stats)
    h.session.end_session()
    assert fake_stats.sessions == []


def test_each_session_is_stored_separately(make_harness, fake_stats):
    h = make_harness(["one", "two"], [TutorReply("a"), TutorReply("b")], session_stats=fake_stats)
    h.say()
    h.session.end_session()
    h.say()
    h.session.end_session()
    assert [s.turns for s in fake_stats.sessions] == [1, 1]


def test_a_failing_store_warns_once_and_the_report_still_comes(make_harness, fake_stats):
    fake_stats.error = RuntimeError("disk full")
    h = make_harness(["one", "two"], [TutorReply("a"), TutorReply("b")], session_stats=fake_stats)
    for _ in range(2):
        h.say()
        h.session.end_session()
    assert h.session.state is SessionState.IDLE
    assert len(h.of_type(ReportReady)) == 2
    assert len([e for e in h.of_type(ErrorRaised) if "disk full" in e.message]) == 1


def test_a_session_without_a_stats_store_still_works(make_harness):
    h = make_harness(["one"], [TutorReply("a")])
    h.say()
    h.session.end_session()
    assert len(h.of_type(ReportReady)) == 1
