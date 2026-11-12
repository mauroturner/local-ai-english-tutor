"""The session keeps the mistake history without ever blocking a turn."""

from __future__ import annotations

from conftest import major, minor

from english_tutor.application.events import ErrorRaised, MistakesChanged, TutorSaid
from english_tutor.domain.models import SessionState, TutorReply


def changed(h) -> list[MistakesChanged]:
    return h.of_type(MistakesChanged)


def test_history_is_loaded_before_the_session_is_ready(make_harness, fake_store, old_record):
    fake_store.records = [old_record]
    h = make_harness(store=fake_store)
    assert changed(h)[0].mistakes == (old_record,)


def test_turn_with_corrections_is_persisted_and_announced(make_harness, fake_store):
    reply = TutorReply("Why?", (major("I go", "I went", "Past tense."), minor("a apple", "an apple")))
    h = make_harness(["I go eat a apple"], [reply], store=fake_store)
    h.say()
    assert len(fake_store.saves) == 1
    saved = {r.key: r for r in fake_store.saves[0]}
    assert set(saved) == {"i go => i went", "a apple => an apple"}
    assert saved["i go => i went"].examples == ("I go eat a apple",)
    last = changed(h)[-1].mistakes
    assert {r.key for r in last} == set(saved)


def test_turn_without_corrections_does_not_touch_the_store(make_harness, fake_store):
    h = make_harness(["hello there"], [TutorReply("Hi!")], store=fake_store)
    h.say()
    assert fake_store.saves == []
    assert len(changed(h)) == 1  # only the initial load


def test_repeated_mistake_increments_the_count(make_harness, fake_store):
    fix = (major("I go", "I went"),)
    h = make_harness(
        ["I go home", "I go out"], [TutorReply("a", fix), TutorReply("b", fix)], store=fake_store
    )
    h.say()
    h.say()
    assert fake_store.saves[-1][0].count == 2


def test_invented_corrections_are_not_recorded(make_harness, fake_store):
    reply = TutorReply("ok", (major("she goes", "she went"),))
    h = make_harness(["hello there"], [reply], store=fake_store)
    h.say()
    assert fake_store.saves == []


def test_save_failure_warns_once_and_the_turn_completes(make_harness, fake_store):
    fake_store.save_error = RuntimeError("disk full")
    fix = (major("I go", "I went"),)
    h = make_harness(
        ["I go home", "I go out"], [TutorReply("a", fix), TutorReply("b", fix)], store=fake_store
    )
    h.say()
    h.say()
    assert h.session.state is SessionState.IDLE
    assert len(h.of_type(TutorSaid)) == 2
    warnings = [e for e in h.of_type(ErrorRaised) if "disk full" in e.message]
    assert len(warnings) == 1
    assert changed(h)[-1].mistakes[0].count == 2  # memory kept despite the failure


def test_load_failure_warns_and_the_session_still_starts(make_harness, fake_store):
    fake_store.load_error = RuntimeError("History was unreadable")
    h = make_harness(store=fake_store)
    assert h.session.state is SessionState.IDLE
    assert any("History was unreadable" in e.message for e in h.of_type(ErrorRaised))
    assert changed(h)[0].mistakes == ()
