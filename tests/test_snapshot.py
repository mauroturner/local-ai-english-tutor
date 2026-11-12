"""What the main window remembers for the Settings actions (pure, no Tk)."""

from __future__ import annotations

from english_tutor.application.events import (
    DataCleared,
    ErrorRaised,
    MistakesChanged,
    ReportReady,
)
from english_tutor.domain.models import SessionReport
from english_tutor.i18n import set_language
from english_tutor.ui.snapshot import SessionSnapshot, cleared_message


def test_starts_empty():
    snap = SessionSnapshot()
    assert snap.report is None
    assert snap.mistakes == ()


def test_remembers_the_latest_report_and_mistakes(old_record):
    snap = SessionSnapshot()
    first, second = SessionReport(1, (), (), None), SessionReport(2, (), (), None)
    snap.observe(ReportReady(first))
    snap.observe(ReportReady(second))
    snap.observe(MistakesChanged((old_record,)))
    snap.observe(ErrorRaised("ignored"))
    assert snap.report is second
    assert snap.mistakes == (old_record,)
    snap.observe(MistakesChanged(()))
    assert snap.mistakes == ()


def test_cleared_message_names_what_was_deleted():
    set_language("en")
    assert "3" in cleared_message(DataCleared("logs", 3))
    assert "log" in cleared_message(DataCleared("logs", 3)).lower()
    assert "mistake" in cleared_message(DataCleared("mistakes", 2)).lower()


def test_cleared_message_is_translated():
    set_language("es")
    try:
        assert "errores" in cleared_message(DataCleared("mistakes", 2)).lower()
    finally:
        set_language("en")
