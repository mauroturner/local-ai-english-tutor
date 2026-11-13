"""Words the recogniser was unsure about: a pronunciation hint, never a mistake."""

from __future__ import annotations

from conftest import FakeSTT

from english_tutor.adapters.whisper_alignment import _probability
from english_tutor.application.report import make_report
from english_tutor.domain.export import report_markdown
from english_tutor.domain.formatting import format_report, uncertain_line
from english_tutor.domain.hesitation import LOW_CONFIDENCE, low_confidence, restore_times
from english_tutor.domain.models import SessionReport, TimedWord, Transcript, TutorReply, Turn

from datetime import datetime


def word(text, probability, start=0.0):
    return TimedWord(text, start, start + 0.3, probability)


def test_only_words_under_the_threshold_are_listed_once_in_order():
    words = [word(" Very", 0.2), word(" good", 0.9), word(" world,", 0.1), word(" very", 0.3)]
    assert low_confidence(words) == ("very", "world")


def test_the_threshold_is_exclusive_and_can_be_changed():
    assert low_confidence([word("exact", LOW_CONFIDENCE)]) == ()
    assert low_confidence([word("exact", 0.5)], threshold=0.6) == ("exact",)


def test_short_words_and_unknown_probabilities_are_ignored():
    words = [word(" a", 0.0), word(" to", 0.0), word(" cat", None), word(" dog", 0.0)]
    assert low_confidence(words) == ("dog",)


def test_no_words_no_hints():
    assert low_confidence(()) == ()


def test_restoring_times_keeps_the_probability():
    restored = restore_times([TimedWord(" hello", 0.0, 0.5, 0.42)], [(1.0, 2.0)])
    assert restored[0].probability == 0.42


def test_the_aligner_reads_the_probability_when_present():
    assert _probability({"probability": "0.25"}) == 0.25
    assert _probability({}) is None
    assert _probability({"probability": None}) is None
    assert _probability({"probability": "high"}) is None


# ---- turns and report ------------------------------------------------------------------------


def test_a_turn_keeps_the_words_the_recogniser_was_unsure_about(make_harness):
    words = (word(" I", 0.9), word(" live", 0.9, 0.4), word(" there", 0.1, 0.8))
    h = make_harness([Transcript("I live there", 1.0, words)], [TutorReply("Nice.")])
    h.say()
    assert h.session.turns[0].uncertain == ("there",)


def test_the_report_collects_every_hint_once():
    turns = (
        Turn(1, "a", "ok", (), None, uncertain=("there", "very")),
        Turn(2, "b", "ok", (), None, uncertain=("very", "world")),
    )

    class Tutor:
        def feedback(self, turns):
            raise RuntimeError("no model")

    report = make_report(Tutor(), turns)
    assert report.uncertain_words == ("there", "very", "world")


def test_the_report_text_says_the_recogniser_was_unsure():
    report = SessionReport(1, (), (), None, uncertain_words=("very", "world"))
    line = uncertain_line(report)
    assert line == "Check your pronunciation (the recogniser was unsure about): very, world"
    assert line in format_report(report)
    assert line in report_markdown(report, datetime(2026, 11, 13, 10))


def test_no_hints_means_no_line():
    report = SessionReport(1, (), (), None)
    assert uncertain_line(report) == ""
    assert "pronunciation" not in format_report(report)


def test_hints_never_become_mistakes(make_harness, fake_store):
    words = (word(" there", 0.05),)
    h = make_harness([Transcript("there", 1.0, words)], [TutorReply("Nice.")], store=fake_store)
    h.say()
    assert fake_store.saves == []


def test_the_fake_stt_still_returns_plain_transcripts():
    assert FakeSTT(["hello"]).transcribe(None).words == ()
