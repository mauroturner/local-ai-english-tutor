"""Pure text formatting shared by the UI and the conversation log."""

from __future__ import annotations

from conftest import major, minor

from english_tutor.application.report import make_report
from english_tutor.domain.formatting import correction_text, format_report
from english_tutor.domain.formatting import practice_speech
from english_tutor.domain.models import (
    PracticeOutcome,
    PracticeReply,
    SessionFeedback,
    SessionReport,
    Turn,
)


def test_correction_text():
    assert correction_text(major("I go", "I went", "Past tense.")) == (
        '"I go" -> "I went" (Past tense.) [major]'
    )
    assert correction_text(minor("a apple", "an apple", "Article.")).endswith("[minor]")


def test_practice_speech_joins_non_empty_parts():
    reply = PracticeReply(PracticeOutcome.CORRECT, "Perfect!", "Where did you go?")
    assert practice_speech(reply) == "Perfect! Where did you go?"
    only_prompt = PracticeReply(PracticeOutcome.NOT_USED, "", "Where did you go?", False)
    assert practice_speech(only_prompt) == "Where did you go?"
    assert practice_speech(PracticeReply(PracticeOutcome.NOT_USED, "", "")) == ""


def test_format_report_with_feedback():
    report = SessionReport(
        2,
        (major("I go", "I went", "Past tense."),),
        (),
        SessionFeedback("Nice work.", ("fluent",), ("tenses",)),
    )
    assert format_report(report) == "\n".join(
        [
            "SESSION REPORT (2 turns)",
            "",
            "Major errors:",
            '  - "I go" -> "I went" (Past tense.)',
            "Minor errors: none",
            "",
            "Feedback: Nice work.",
            "  + fluent",
            "  > Focus on: tenses",
        ]
    )


def test_format_report_without_turns_and_with_feedback_error():
    assert format_report(SessionReport(0, (), (), None)).endswith(
        "No turns were recorded in this session."
    )
    failed = SessionReport(1, (), (), None, "model down")
    assert format_report(failed).endswith("Feedback unavailable: model down")
    assert format_report(SessionReport(1, (), (), None)).endswith(
        "Feedback unavailable: unknown error"
    )


class StubTutor:
    def __init__(self, result) -> None:
        self.result = result
        self.calls = 0

    def feedback(self, turns):
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def turn(index: int, *corrections) -> Turn:
    return Turn(index, "text", "reply", tuple(corrections), None)


def test_make_report_dedupes_and_splits_by_severity():
    tutor = StubTutor(SessionFeedback("ok"))
    turns = (
        turn(1, major("I go", "I went"), minor("a apple", "an apple")),
        turn(2, major("i go", "I went!")),
    )
    report = make_report(tutor, turns)
    assert report.turn_count == 2
    assert len(report.major_errors) == 1 and len(report.minor_errors) == 1
    assert report.feedback == SessionFeedback("ok")
    assert report.feedback_error is None


def test_make_report_without_turns_skips_the_model():
    tutor = StubTutor(SessionFeedback("ok"))
    report = make_report(tutor, ())
    assert tutor.calls == 0
    assert report.feedback is None


def test_make_report_keeps_errors_when_feedback_fails():
    report = make_report(StubTutor(RuntimeError("boom")), (turn(1, major("I go", "I went")),))
    assert report.feedback is None
    assert report.feedback_error == "boom"
    assert len(report.major_errors) == 1
