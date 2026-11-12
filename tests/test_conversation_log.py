"""FileConversationLog writes one UTF-8 .log file per session."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from english_tutor.adapters.file_conversation_log import FileConversationLog
from english_tutor.ports import StorageError


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 12, 14, 3, 22)

    def __call__(self) -> datetime:
        return self.now


def read(path) -> list[str]:
    return path.read_text(encoding="utf-8").split("\n")


def test_nothing_is_created_until_the_first_record(tmp_path):
    FileConversationLog(tmp_path / "logs", Clock())
    assert not (tmp_path / "logs").exists()


def test_creates_folder_file_header_and_line(tmp_path):
    folder = tmp_path / "a" / "b"
    log = FileConversationLog(folder, Clock())
    log.record("you", "I go to school")
    path = folder / "session-20261112-140322.log"
    assert read(path) == [
        "# English tutor conversation - 2026-11-12 14:03:22",
        "[2026-11-12 14:03:22] YOU: I go to school",
        "",
    ]


def test_labels_and_timestamps_per_record(tmp_path):
    clock = Clock()
    log = FileConversationLog(tmp_path, clock)
    log.record("you", "a")
    clock.now += timedelta(seconds=5)
    log.record("tutor", "b")
    log.record("tip", "c")
    log.record("report", "d")
    log.record("practice", "e")
    lines = read(next(tmp_path.glob("*.log")))
    assert lines[1] == "[2026-11-12 14:03:22] YOU: a"
    assert lines[2:7] == [
        "[2026-11-12 14:03:27] ALEX: b",
        "[2026-11-12 14:03:27] TIP: c",
        "[2026-11-12 14:03:27] REPORT: d",
        "[2026-11-12 14:03:27] PRACTICE: e",
        "",
    ]


def test_unicode_and_exact_transcript(tmp_path):
    log = FileConversationLog(tmp_path, Clock())
    raw = "  i  go   to the playa, señor ñandú — “quotes”  "
    log.record("you", raw)
    content = next(tmp_path.glob("*.log")).read_bytes().decode("utf-8")
    assert f"YOU: {raw}\n" in content


def test_multiline_text_is_indented(tmp_path):
    log = FileConversationLog(tmp_path, Clock())
    log.record("report", "line one\nline two\n  line three")
    lines = read(next(tmp_path.glob("*.log")))
    assert lines[1:4] == [
        "[2026-11-12 14:03:22] REPORT: line one",
        "    line two",
        "      line three",
    ]


def test_lf_line_endings(tmp_path):
    log = FileConversationLog(tmp_path, Clock())
    log.record("you", "a")
    assert b"\r" not in next(tmp_path.glob("*.log")).read_bytes()


def test_new_session_starts_a_second_file(tmp_path):
    clock = Clock()
    log = FileConversationLog(tmp_path, clock)
    log.record("you", "first")
    log.new_session()
    clock.now += timedelta(seconds=10)
    log.record("you", "second")
    names = sorted(p.name for p in tmp_path.glob("*.log"))
    assert names == ["session-20261112-140322.log", "session-20261112-140332.log"]


def test_same_second_gets_a_numeric_suffix(tmp_path):
    log = FileConversationLog(tmp_path, Clock())
    log.record("you", "first")
    log.new_session()
    log.record("you", "second")
    log.new_session()
    log.record("you", "third")
    names = sorted(p.name for p in tmp_path.glob("*.log"))
    assert names == [
        "session-20261112-140322-2.log",
        "session-20261112-140322-3.log",
        "session-20261112-140322.log",
    ]


def test_records_append_to_the_same_file(tmp_path):
    log = FileConversationLog(tmp_path, Clock())
    log.record("you", "a")
    log.record("tutor", "b")
    assert len(list(tmp_path.glob("*.log"))) == 1


def test_folder_that_is_a_file_raises_storage_error(tmp_path):
    blocker = tmp_path / "data"
    blocker.write_text("not a folder")
    log = FileConversationLog(blocker / "conversations", Clock())
    with pytest.raises(StorageError):
        log.record("you", "hello")
