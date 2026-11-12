"""Deleting local data: log files, the mistake history and the session entry point."""

from __future__ import annotations

from datetime import datetime

import pytest
from conftest import FakeMistakeStore, ManualRunner, major

from english_tutor.adapters.file_conversation_log import FileConversationLog
from english_tutor.application.events import DataCleared, ErrorRaised, MistakesChanged
from english_tutor.application.journal import SafeJournal
from english_tutor.application.maintenance import clear_logs, clear_mistakes
from english_tutor.application.mistake_book import MistakeBook
from english_tutor.domain.models import PracticeOutcome, PracticeReply, TutorReply
from english_tutor.ports import StorageError

NOW = datetime(2026, 11, 12, 14, 3, 22)


# --------------------------------------------------------- FileConversationLog.clear
def test_clear_removes_only_session_logs(tmp_path):
    folder = tmp_path / "conversations"
    folder.mkdir()
    (folder / "session-20261101-090000.log").write_text("a", encoding="utf-8")
    (folder / "session-20261102-090000-2.log").write_text("b", encoding="utf-8")
    keep = [folder / "notes.txt", folder / "session-1.log.bak", folder / "app.log"]
    for path in keep:
        path.write_text("keep", encoding="utf-8")
    (folder / "session-dir.log").mkdir()
    log = FileConversationLog(folder, lambda: NOW)

    assert log.clear() == 2

    assert sorted(p.name for p in folder.iterdir()) == sorted(
        ["notes.txt", "session-1.log.bak", "app.log", "session-dir.log"]
    )


def test_clear_never_touches_the_app_logs_folder(tmp_path):
    (tmp_path / "logs").mkdir()
    app_log = tmp_path / "logs" / "app.log"
    app_log.write_text("x", encoding="utf-8")
    folder = tmp_path / "conversations"
    log = FileConversationLog(folder, lambda: NOW)
    log.record("you", "hi")
    log.clear()
    assert app_log.read_text(encoding="utf-8") == "x"


def test_clear_on_a_missing_folder_is_zero(tmp_path):
    assert FileConversationLog(tmp_path / "nope", lambda: NOW).clear() == 0
    assert not (tmp_path / "nope").exists()


def test_next_record_after_clear_starts_a_new_file(tmp_path):
    log = FileConversationLog(tmp_path, lambda: NOW)
    log.record("you", "before")
    assert log.clear() == 1
    assert list(tmp_path.glob("*.log")) == []
    log.record("you", "after")
    (path,) = tmp_path.glob("*.log")
    text = path.read_text(encoding="utf-8")
    assert "after" in text and "before" not in text
    assert text.startswith("# English tutor conversation")


def test_clear_reports_files_it_cannot_delete(tmp_path, monkeypatch):
    log = FileConversationLog(tmp_path, lambda: NOW)
    log.record("you", "x")
    from pathlib import Path

    def locked(self, missing_ok=False):
        raise PermissionError("in use")

    monkeypatch.setattr(Path, "unlink", locked)
    with pytest.raises(StorageError, match="in use"):
        log.clear()


# ----------------------------------------------------------------- MistakeBook.clear
def make_book(store, warnings=None):
    return MistakeBook(store, (warnings if warnings is not None else []).append)


def test_book_clear_empties_memory_and_saves(old_record):
    store = FakeMistakeStore()
    store.records = [old_record]
    book = make_book(store)
    book.load()
    assert book.clear() == 1
    assert book.snapshot() == ()
    assert store.saves == [[]]


def test_book_clear_on_an_empty_history_is_zero():
    store = FakeMistakeStore()
    assert make_book(store).clear() == 0


def test_book_clear_keeps_memory_when_the_save_fails(old_record):
    store = FakeMistakeStore()
    store.records = [old_record]
    book = make_book(store)
    book.load()
    store.save_error = StorageError("disk full")
    with pytest.raises(StorageError):
        book.clear()
    assert book.snapshot() == (old_record,)


# --------------------------------------------------------------------- maintenance
class Journal:
    def __init__(self):
        self.sessions = 0

    def new_session(self):
        self.sessions += 1


def test_clear_mistakes_emits_empty_list_and_notice(old_record):
    store, events = FakeMistakeStore(), []
    store.records = [old_record]
    book = make_book(store)
    book.load()
    clear_mistakes(book, Journal(), events.append)
    assert events == [MistakesChanged(()), DataCleared("mistakes", 1)]


def test_clear_mistakes_storage_error_becomes_an_error_event(old_record):
    store, events = FakeMistakeStore(), []
    store.records = [old_record]
    book = make_book(store)
    book.load()
    store.save_error = StorageError("disk full")
    clear_mistakes(book, Journal(), events.append)
    assert len(events) == 1 and isinstance(events[0], ErrorRaised)
    assert "disk full" in events[0].message


def test_clear_logs_deletes_starts_a_new_session_and_announces():
    events, journal = [], Journal()
    clear_logs(lambda: 3)(make_book(FakeMistakeStore()), journal, events.append)
    assert events == [DataCleared("logs", 3)]
    assert journal.sessions == 1


def test_clear_logs_storage_error_becomes_an_error_event():
    def boom() -> int:
        raise StorageError("in use")

    events = []
    clear_logs(boom)(make_book(FakeMistakeStore()), Journal(), events.append)
    assert len(events) == 1 and isinstance(events[0], ErrorRaised)
    assert "in use" in events[0].message


# ----------------------------------------------------------- session.clear_data
def test_clear_data_runs_the_job_on_the_runner_when_idle(make_harness):
    runner = ManualRunner()
    h = make_harness(runner=runner)
    calls = []
    assert h.session.clear_data(lambda book, journal, emit: calls.append((book, journal))) is True
    assert calls == []  # queued, not run inline
    runner.run_all()
    assert len(calls) == 1
    assert isinstance(calls[0][0], MistakeBook) and isinstance(calls[0][1], SafeJournal)


def test_clear_data_clears_the_real_history_and_emits(make_harness, fake_store, old_record):
    fake_store.records = [old_record]
    h = make_harness(store=fake_store)
    assert h.session.clear_data(clear_mistakes) is True
    assert h.of_type(MistakesChanged)[-1].mistakes == ()
    assert h.of_type(DataCleared) == [DataCleared("mistakes", 1)]
    assert fake_store.saves[-1] == []


def test_clear_data_new_session_reaches_the_journal(make_harness, fake_log):
    h = make_harness(log=fake_log)
    assert h.session.clear_data(clear_logs(lambda: 0)) is True
    assert fake_log.sessions == 1


@pytest.mark.parametrize("busy", ["recording", "thinking"])
def test_clear_data_is_refused_while_busy(make_harness, busy):
    runner = ManualRunner()
    h = make_harness(["hello"], [TutorReply("Hi")], runner=runner)
    if busy == "recording":
        h.session.on_ptt_press()
    else:
        h.session.on_ptt_press()
        h.session.on_ptt_release()
    calls = []
    assert h.session.clear_data(lambda *a: calls.append(a)) is False
    runner.run_all()
    assert calls == []


def test_clear_data_is_refused_while_practicing(make_harness, fake_store, old_record):
    from conftest import FakeCoach

    fake_store.records = [old_record]
    opener = PracticeReply(PracticeOutcome.NOT_USED, "Let's practice.", "Where is she?")
    h = make_harness(store=fake_store, coach=FakeCoach([opener]))
    h.session.start_practice(old_record.key)
    calls = []
    assert h.session.clear_data(lambda *a: calls.append(a)) is False
    assert calls == []
    assert fake_store.records == [old_record]


def test_clear_data_is_refused_while_loading():
    from conftest import FakeRecorder, FakeSTT, FakeTTS, FakeTutor

    from english_tutor.application.session import ConversationSession

    session = ConversationSession(
        FakeSTT(), FakeTutor(), FakeTTS(), FakeRecorder(), lambda e: None, runner=ManualRunner()
    )
    assert session.clear_data(lambda *a: None) is False


def test_session_still_records_mistakes_after_clearing(make_harness, fake_store, old_record):
    fake_store.records = [old_record]
    h = make_harness(["I go home"], [TutorReply("Why?", (major("I go", "I went"),))], store=fake_store)
    h.session.clear_data(clear_mistakes)
    h.say()
    assert [r.key for r in h.of_type(MistakesChanged)[-1].mistakes] == ["i go => i went"]
