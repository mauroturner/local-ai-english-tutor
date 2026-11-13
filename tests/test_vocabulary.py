"""The personal word list: rules, storage, the model call and the session flows."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import pytest
from conftest import FakePhrases

from english_tutor.adapters.json_vocabulary_store import JsonVocabularyStore
from english_tutor.adapters.ollama_parsing import parse_phrase
from english_tutor.application.events import (
    ErrorRaised,
    PhraseSaved,
    TutorSaid,
    UserSaid,
    VocabularyChanged,
)
from english_tutor.domain.models import PracticeOutcome, PracticeReply, Severity, TutorReply
from english_tutor.domain.practice_prompts import build_practice_system_prompt
from english_tutor.domain.review_schedule import first_review
from english_tutor.domain.vocab_prompts import phrase_system_prompt, phrase_user_message
from english_tutor.domain.vocabulary import (
    MAX_ENTRIES,
    PhraseSuggestion,
    add_entry,
    as_target,
    clean_suggestion,
    practice_entry,
    remove_entry,
)
from english_tutor.ports import AdapterError, StorageError

NOW = datetime(2026, 11, 13, 10, 0, 0)
LOT = PhraseSuggestion("a lot of fun", "muy divertido", "The party was a lot of fun.")


# ---- rules ----------------------------------------------------------------------------------


def test_a_new_phrase_is_due_tomorrow_with_a_clean_key():
    entries = add_entry({}, LOT, NOW)
    entry = entries["a lot of fun"]
    assert entry.review == first_review(NOW.date()) and entry.added == NOW
    assert (entry.meaning, entry.example) == ("muy divertido", "The party was a lot of fun.")


def test_saving_a_phrase_again_keeps_its_schedule_and_fills_gaps():
    first = add_entry({}, PhraseSuggestion("A lot of fun!", "", ""), NOW)
    later = add_entry(first, LOT, NOW + timedelta(days=3))
    assert len(later) == 1
    entry = later["a lot of fun"]
    assert entry.added == NOW and entry.meaning == "muy divertido" and entry.review == first_review(NOW.date())


def test_empty_and_unprintable_suggestions_are_ignored():
    assert add_entry({}, PhraseSuggestion("  ", "x", "y"), NOW) == {}
    assert clean_suggestion(PhraseSuggestion("\x00\x01", "", "")) is None


def test_text_is_cleaned_for_the_prompts():
    cleaned = clean_suggestion(PhraseSuggestion('say  "hi"\nthere ' + "x" * 200, "a\tb", "e" * 500))
    assert '"' not in cleaned.phrase and "\n" not in cleaned.phrase and len(cleaned.phrase) <= 80
    assert cleaned.meaning == "a b" and len(cleaned.example) <= 160


def test_the_list_is_bounded():
    entries = {}
    for i in range(MAX_ENTRIES + 5):
        entries = add_entry(entries, PhraseSuggestion(f"phrase number {i}"), NOW)
    assert len(entries) == MAX_ENTRIES
    assert len(add_entry(entries, PhraseSuggestion("phrase number 0", "now with meaning"), NOW)) == MAX_ENTRIES


def test_removing_a_phrase():
    assert remove_entry(add_entry({}, LOT, NOW), "a lot of fun") == {}
    assert remove_entry({}, "x") == {}


def test_practice_moves_the_review_date_like_a_mistake():
    entries = add_entry({}, LOT, NOW)
    right = practice_entry(entries, "a lot of fun", PracticeOutcome.CORRECT, NOW)["a lot of fun"]
    assert (right.practice_attempts, right.practice_successes) == (1, 1)
    assert right.review.step == 1 and right.review.due == NOW.date() + timedelta(days=3)
    wrong = practice_entry({"a lot of fun": right}, "a lot of fun", PracticeOutcome.INCORRECT, NOW)["a lot of fun"]
    assert wrong.review.step == 0 and wrong.practice_attempts == 2
    assert practice_entry(entries, "a lot of fun", PracticeOutcome.NOT_USED, NOW) == entries
    assert practice_entry(entries, "unknown", PracticeOutcome.CORRECT, NOW) == entries


def test_an_entry_becomes_a_practice_target_that_is_never_a_mistake():
    target = as_target(add_entry({}, LOT, NOW)["a lot of fun"])
    assert target.severity is Severity.VOCABULARY and target.corrected == "a lot of fun"
    prompt = build_practice_system_prompt(target)
    assert "vocabulary, not a mistake" in prompt and '"a lot of fun"' in prompt and "muy divertido" in prompt


# ---- the model --------------------------------------------------------------------------------


def test_the_suggestion_parser():
    raw = '{"phrase": "a lot of fun", "meaning": "muy divertido", "example": "It was a lot of fun."}'
    assert parse_phrase(raw) == PhraseSuggestion("a lot of fun", "muy divertido", "It was a lot of fun.")
    assert parse_phrase('prefix {"phrase": "x y", "meaning": 5}') == PhraseSuggestion("x y", "", "")
    for bad in ("no json", '{"phrase": ""}', '{"phrase": 7}', "[]"):
        assert parse_phrase(bad) is None


def test_the_prompts_name_the_source_and_bound_the_input():
    assert "Learner asked" in phrase_user_message("como se dice hola", True)
    assert phrase_user_message("Nice " * 300, False).startswith("Tutor said: Nice")
    assert len(phrase_user_message("x " * 1000, True)) < 450
    assert "LEARNER" not in phrase_system_prompt(True) + phrase_system_prompt(False)  # no name
    assert "in Spanish" in phrase_system_prompt(True)


def test_the_model_adapter_raises_when_no_phrase_comes_back():
    from english_tutor.adapters.ollama_chat import OllamaTutorModel

    class Http:
        def post(self, url, json, timeout):
            class Reply:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {"message": {"content": "sorry, no"}}

            return Reply()

    with pytest.raises(AdapterError):
        OllamaTutorModel("http://x", "m", 1.0, 0.3, session=Http()).suggest_phrase("hi", False)


# ---- storage ------------------------------------------------------------------------------------


def test_the_word_list_round_trips_and_keeps_its_schedule(tmp_path):
    store = JsonVocabularyStore(tmp_path / "vocabulary.json")
    entries = list(practice_entry(add_entry({}, LOT, NOW), "a lot of fun", PracticeOutcome.CORRECT, NOW).values())
    store.save(entries)
    assert JsonVocabularyStore(tmp_path / "vocabulary.json").load() == entries
    assert json.loads((tmp_path / "vocabulary.json").read_text(encoding="utf-8"))["version"] == 1


def test_a_corrupt_word_list_is_set_aside(tmp_path):
    path = tmp_path / "vocabulary.json"
    path.write_text("{ nope", encoding="utf-8")
    with pytest.raises(StorageError, match="saved a copy"):
        JsonVocabularyStore(path, clock=lambda: NOW).load()
    assert (tmp_path / "vocabulary.json.corrupt-20261113-100000").exists()
    assert JsonVocabularyStore(path).load() == []


def test_bad_entries_are_skipped_and_duplicates_collapse(tmp_path):
    path = tmp_path / "vocabulary.json"
    good = {"phrase": "a lot of fun", "added": "2026-11-13T10:00:00", "review": {"due": "bad"}}
    path.write_text(json.dumps({"version": 1, "words": [good, {"phrase": ""}, {"nothing": 1}, dict(good)]}), encoding="utf-8")
    (entry,) = JsonVocabularyStore(path).load()
    assert entry.phrase == "a lot of fun" and entry.review is None


# ---- the session ------------------------------------------------------------------------------------


def test_save_phrase_uses_the_tutors_last_reply(make_harness, fake_vocab):
    phrases = FakePhrases([LOT])
    h = make_harness(["hello"], [TutorReply("That sounds like a lot of fun!")], vocabulary=fake_vocab, phrases=phrases)
    h.say()
    h.session.save_phrase()
    assert phrases.calls == [("That sounds like a lot of fun!", False)]
    assert h.of_type(PhraseSaved)[-1].entry.phrase == "a lot of fun"
    assert [e.phrase for e in h.of_type(VocabularyChanged)[-1].entries] == ["a lot of fun"]
    assert fake_vocab.saves and fake_vocab.saves[-1][0].phrase == "a lot of fun"


def test_save_phrase_needs_something_said_and_the_helper(make_harness, fake_vocab):
    h = make_harness(vocabulary=fake_vocab, phrases=FakePhrases([LOT]))
    h.session.save_phrase()
    assert h.of_type(PhraseSaved) == []
    plain = make_harness(["hello"], [TutorReply("Hi there my friend")])
    plain.say()
    plain.session.save_phrase()
    assert plain.of_type(PhraseSaved) == []


def test_a_failing_model_reports_and_leaves_the_list_alone(make_harness, fake_vocab):
    h = make_harness(["hello"], [TutorReply("Hi there my friend")], vocabulary=fake_vocab,
                     phrases=FakePhrases([AdapterError("model down")]))
    h.say()
    h.session.save_phrase()
    assert h.of_type(PhraseSaved) == [] and fake_vocab.saves == []
    assert any("model down" in e.message for e in h.of_type(ErrorRaised))


def test_a_spanish_request_is_transcribed_in_spanish_and_answered_with_a_phrase(make_harness, fake_vocab):
    phrases = FakePhrases([PhraseSuggestion("I feel like going out", "tengo ganas de salir", "I feel like going out tonight.")])
    h = make_harness(["como se dice tengo ganas de salir"], vocabulary=fake_vocab, phrases=phrases)
    h.session.on_ptt_press(spanish=True)
    h.session.on_ptt_release()
    assert h.stt.languages == ["es"] and h.stt.with_words == [False]
    assert phrases.calls == [("como se dice tengo ganas de salir", True)]
    assert h.of_type(UserSaid)[-1].text == "como se dice tengo ganas de salir"
    said = h.of_type(TutorSaid)[-1].text
    assert said == "You can say: I feel like going out. For example: I feel like going out tonight."
    assert h.tts.spoken[-1] == said
    assert h.session.turns == () and h.tutor.calls == []  # not a turn of the conversation


def test_the_normal_key_still_uses_english(make_harness):
    h = make_harness(["hello"], [TutorReply("Hi")])
    h.say()
    assert h.stt.languages == ["en"]


def test_the_spanish_key_needs_the_helper_and_a_free_session(make_harness):
    plain = make_harness(["x"])
    plain.session.on_ptt_press(spanish=True)
    assert plain.stt.languages == [] and plain.recorder.calls == []


def test_a_saved_phrase_can_be_removed(make_harness, fake_vocab):
    h = make_harness(["hello"], [TutorReply("Hi there my friend")], vocabulary=fake_vocab, phrases=FakePhrases([LOT]))
    h.say()
    h.session.save_phrase()
    h.session.remove_phrase("a lot of fun")
    assert h.of_type(VocabularyChanged)[-1].entries == ()
    assert fake_vocab.saves[-1] == []


def test_the_saved_phrases_are_loaded_at_start(make_harness, fake_vocab):
    fake_vocab.entries = list(add_entry({}, LOT, NOW).values())
    h = make_harness(vocabulary=fake_vocab)
    assert [e.phrase for e in h.of_type(VocabularyChanged)[0].entries] == ["a lot of fun"]


def test_an_unreadable_word_list_warns_and_the_session_starts(make_harness, fake_vocab):
    fake_vocab.load_error = StorageError("The word list was unreadable")
    h = make_harness(vocabulary=fake_vocab)
    assert any("unreadable" in e.message for e in h.of_type(ErrorRaised))
    assert h.of_type(VocabularyChanged)[0].entries == ()


def test_practising_a_saved_phrase_updates_the_word_list_not_the_mistakes(make_harness, fake_vocab, fake_store):
    from conftest import FakeCoach

    fake_vocab.entries = list(add_entry({}, LOT, NOW).values())
    coach = FakeCoach([
        PracticeReply(PracticeOutcome.NOT_USED, "Let's practise.", "Did you have fun?"),
        PracticeReply(PracticeOutcome.CORRECT, "Great!", "What else?"),
    ])
    h = make_harness(["it was a lot of fun"], vocabulary=fake_vocab, coach=coach, store=fake_store)
    h.session.start_practice("a lot of fun")
    assert coach.calls[0][0].severity is Severity.VOCABULARY
    h.say()
    assert fake_store.saves == []
    assert fake_vocab.saves[-1][0].practice_successes == 1
    assert fake_vocab.saves[-1][0].review.step == 1
