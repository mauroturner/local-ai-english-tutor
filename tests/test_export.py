"""Export formats: the Markdown report and the mistakes CSV (pure)."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from conftest import major, minor

from english_tutor.domain.export import (
    mistakes_csv,
    mistakes_filename,
    report_filename,
    report_markdown,
)
from english_tutor.domain.models import MistakeRecord, SessionFeedback, SessionReport, Severity

WHEN = datetime(2026, 11, 12, 14, 5, 9)


def full_report() -> SessionReport:
    return SessionReport(
        3,
        (major("I go", "I went", "Past tense."),),
        (minor("a apple", "an apple", "Article."),),
        SessionFeedback("Nice work.", ("fluent", "clear"), ("tenses",)),
    )


def test_report_markdown_has_every_section():
    text = report_markdown(full_report(), WHEN)
    assert text.startswith("# Session report\n")
    assert "2026-11-12 14:05" in text
    assert "Turns: 3" in text
    assert '## Major errors\n\n- "I go" -> "I went" (Past tense.)' in text
    assert '## Minor errors\n\n- "a apple" -> "an apple" (Article.)' in text
    assert "## Feedback\n\nNice work." in text
    assert "- fluent\n- clear" in text
    assert "Focus on" in text and "- tenses" in text
    assert text.endswith("\n")


def test_report_markdown_without_errors_or_feedback():
    text = report_markdown(SessionReport(0, (), (), None), WHEN)
    assert "Major errors" in text and "None." in text
    assert "No turns were recorded in this session." in text


def test_report_markdown_when_feedback_failed():
    report = SessionReport(2, (), (), None, "Ollama not reachable")
    assert "Feedback unavailable: Ollama not reachable" in report_markdown(report, WHEN)


def test_filenames_carry_the_time():
    assert report_filename(WHEN) == "session-report-20261112-140509.md"
    assert mistakes_filename(WHEN) == "mistakes-20261112-140509.csv"


def record(**changes) -> MistakeRecord:
    base = dict(
        key="k", original="I go", corrected="I went", explanation="Past tense.",
        severity=Severity.MAJOR, count=3, first_seen=datetime(2026, 11, 1, 9, 0, 0),
        last_seen=datetime(2026, 11, 12, 8, 30, 5), examples=("I go home",),
        practice_attempts=4, practice_successes=2,
    )
    base.update(changes)
    return MistakeRecord(**base)


def parse(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text, newline="")))


def test_csv_has_english_headers_and_iso_dates():
    rows = parse(mistakes_csv([record()]))
    assert rows[0] == [
        "severity", "original", "corrected", "explanation", "count", "first_seen", "last_seen",
        "practice_attempts", "practice_successes", "examples",
    ]
    assert rows[1] == [
        "major", "I go", "I went", "Past tense.", "3", "2026-11-01T09:00:00",
        "2026-11-12T08:30:05", "4", "2", "I go home",
    ]


def test_csv_quotes_commas_quotes_and_newlines_and_round_trips():
    tricky = record(
        original='say "hi", then\nleave', explanation="a, b", examples=("one, two", 'q"uote'),
    )
    text = mistakes_csv([tricky])
    assert '"say ""hi"", then\nleave"' in text
    rows = parse(text)
    assert len(rows) == 2
    assert rows[1][1] == 'say "hi", then\nleave'
    assert rows[1][3] == "a, b"
    assert rows[1][9] == 'one, two | q"uote'


def test_csv_of_nothing_is_just_the_header():
    assert len(parse(mistakes_csv([]))) == 1


def test_csv_keeps_the_given_order():
    rows = parse(mistakes_csv([record(original="b"), record(original="a")]))
    assert [r[1] for r in rows[1:]] == ["b", "a"]
