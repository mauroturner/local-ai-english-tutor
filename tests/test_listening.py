"""Listening and speaking drills inside the session."""

from __future__ import annotations

from english_tutor.application.events import ErrorRaised, ListeningChanged, ListeningFeedback
from english_tutor.domain.drills import FALLBACK_SENTENCES, DrillKind
from english_tutor.domain.models import SessionState, TutorReply


def started(h) -> ListeningChanged:
    return h.of_type(ListeningChanged)[-1]


def test_shadowing_says_a_sentence_of_the_last_reply_and_shows_it(make_harness):
    h = make_harness(["hello there"], [TutorReply("Nice! What did you do at the park yesterday?")])
    h.say()
    h.session.start_listening(DrillKind.SHADOW)
    assert started(h) == ListeningChanged("shadow", "What did you do at the park yesterday?")
    assert h.tts.spoken[-1] == "What did you do at the park yesterday?"
    assert h.session.state is SessionState.IDLE


def test_without_a_reply_a_fixed_sentence_is_used(make_harness):
    h = make_harness()
    h.session.start_listening(DrillKind.SHADOW)
    assert started(h).text in FALLBACK_SENTENCES


def test_a_spoken_answer_is_judged_and_never_goes_through_the_tutor(make_harness, fake_store):
    h = make_harness(["could you tell me where the station is"], store=fake_store)
    h.session.start_listening(DrillKind.SHADOW)
    target = started(h).text
    h.stt.texts = [target.replace("?", "").replace(".", "")]
    h.say()
    feedback = h.of_type(ListeningFeedback)[-1]
    assert feedback.perfect and feedback.text == "Perfect!"
    assert h.tutor.calls == [] and fake_store.saves == [] and h.session.turns == ()
    assert h.tts.spoken[-1] == "Perfect!"


def test_a_wrong_answer_explains_the_difference(make_harness):
    h = make_harness()
    h.session.start_listening(DrillKind.SHADOW)
    h.stt.texts = ["banana"]
    h.say()
    feedback = h.of_type(ListeningFeedback)[-1]
    assert not feedback.perfect and feedback.text.endswith("% of the words)")


def test_minimal_pairs_need_no_voice_and_do_not_speak_the_sentence(make_harness):
    h = make_harness(tts_available=False)
    h.session.start_listening(DrillKind.PAIRS)
    event = started(h)
    assert event.kind == "pairs" and event.text and h.tts.spoken == []


def test_shadowing_and_dictation_need_the_voice(make_harness):
    h = make_harness(tts_available=False)
    h.session.start_listening(DrillKind.SHADOW)
    h.session.start_listening(DrillKind.DICTATION)
    assert h.of_type(ListeningChanged) == []


def test_dictation_hides_the_sentence_and_is_checked_against_typed_text(make_harness):
    h = make_harness()
    h.session.start_listening(DrillKind.DICTATION)
    assert started(h).kind == "dictation" and started(h).text is None
    spoken = h.tts.spoken[-1]
    h.session.submit_dictation(spoken)
    assert h.of_type(ListeningFeedback)[-1].perfect
    h.session.submit_dictation("totally different words here")
    assert not h.of_type(ListeningFeedback)[-1].perfect


def test_speaking_during_a_dictation_asks_to_type(make_harness):
    h = make_harness(["something"])
    h.session.start_listening(DrillKind.DICTATION)
    h.say()
    assert any("Type what you heard" in e.message for e in h.of_type(ErrorRaised))
    assert h.of_type(ListeningFeedback) == [] and h.session.state is SessionState.IDLE


def test_typed_text_outside_a_dictation_is_ignored(make_harness):
    h = make_harness()
    h.session.submit_dictation("hello")
    h.session.start_listening(DrillKind.SHADOW)
    h.session.submit_dictation("hello")
    assert h.of_type(ListeningFeedback) == []


def test_next_gives_a_new_sentence_and_stop_ends_the_drill(make_harness):
    h = make_harness()
    h.session.start_listening(DrillKind.PAIRS)
    h.session.next_listening()
    assert len(h.of_type(ListeningChanged)) == 2
    h.session.stop_listening()
    assert started(h) == ListeningChanged(None, None)
    h.session.next_listening()  # nothing is running any more
    assert len(h.of_type(ListeningChanged)) == 3


def test_a_drill_blocks_what_needs_a_free_session(make_harness, fake_store):
    h = make_harness(store=fake_store)
    h.session.start_listening(DrillKind.PAIRS)
    h.session.end_session()
    h.session.start_practice("whatever")
    h.session.start_listening(DrillKind.SHADOW)
    h.session.set_scenario("doctor")
    assert h.session.state is SessionState.IDLE
    assert len(h.of_type(ListeningChanged)) == 1 and h.session.scenario == "free"
    assert not h.session.clear_data(lambda *a: None)


def test_the_status_line_explains_what_to_do(make_harness):
    h = make_harness()
    h.session.start_listening(DrillKind.DICTATION)
    messages = [e.message for e in h.events if type(e).__name__ == "StateChanged"]
    assert messages[-1] == "Dictation: type what you heard"
    h.session.stop_listening()
    h.session.start_listening(DrillKind.PAIRS)
    messages = [e.message for e in h.events if type(e).__name__ == "StateChanged"]
    assert messages[-1].startswith("Drill: hold ")


def test_replay_works_during_a_dictation(make_harness):
    h = make_harness()
    h.session.start_listening(DrillKind.DICTATION)
    sentence = h.tts.spoken[-1]
    h.session.repeat_last(slower=True)
    assert h.tts.spoken[-1] == sentence
