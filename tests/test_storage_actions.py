"""The Storage actions of the Settings window, driven with fakes (no Tk window)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from types import SimpleNamespace

import pytest

from english_tutor.domain.models import MistakeRecord, SessionReport, Severity
from english_tutor.i18n import set_language, t
from english_tutor.ports import StorageError
from english_tutor.ui.services import UiPaths, UiServices
from english_tutor.ui.settings.actions import StorageActions

WHEN = datetime(2026, 11, 12, 14, 5, 9)
REPORT = SessionReport(1, (), (), None)


class FakeFooter:
    def __init__(self):
        self.messages: list[tuple[str, bool]] = []

    def set_status(self, text, error=False):
        self.messages.append((text, error))


class Harness:
    def __init__(self, tmp_path: Path):
        self.confirms: list[tuple[str, str]] = []
        self.answer = True
        self.accepted = True
        self.free = True
        self.cleared: list[str] = []
        self.report: SessionReport | None = None
        self.mistakes: tuple[MistakeRecord, ...] = ()
        self.opened: list[Path] = []
        self.export_dir = ""
        self.footer = FakeFooter()
        self.window = SimpleNamespace(
            footer=self.footer, draft=SimpleNamespace(value=lambda key: self.export_dir)
        )
        self.services = UiServices(
            settings=None,  # type: ignore[arg-type]
            paths=UiPaths(tmp_path / "data", tmp_path / "data" / "logs"),
            open_folder=self.opened.append,
            confirm=self._confirm,
            clear_logs=lambda: self._clear("logs"),
            clear_mistakes=lambda: self._clear("mistakes"),
            is_free=lambda: self.free,
            last_report=lambda: self.report,
            mistakes=lambda: self.mistakes,
            clock=lambda: WHEN,
        )
        self.actions = StorageActions(self.window, self.services)

    def _confirm(self, title, message, parent=None):
        self.confirms.append((title, message))
        return self.answer

    def _clear(self, kind):
        if self.accepted:
            self.cleared.append(kind)
        return self.accepted

    def run(self, key):
        self.actions.actions()[key]()


@pytest.fixture(autouse=True)
def english():
    set_language("en")


@pytest.fixture
def h(tmp_path):
    return Harness(tmp_path)


def record() -> MistakeRecord:
    return MistakeRecord(
        "k", "I go", "I went", "Past.", Severity.MAJOR, 2, WHEN, WHEN, ("I go home",)
    )


# ------------------------------------------------------------------ clearing
def test_clear_logs_asks_first_naming_what_goes(h):
    h.run("clear_logs")
    ((title, message),) = h.confirms
    assert "conversation" in title.lower()
    assert str(h.services.paths.data_dir / "conversations") in message
    assert "session-*.log" in message
    assert h.cleared == ["logs"]


def test_clear_mistakes_asks_first_with_the_number(h):
    h.mistakes = (record(), record())
    h.run("clear_mistakes")
    ((_, message),) = h.confirms
    assert "2" in message
    assert h.cleared == ["mistakes"]


def test_declining_the_confirmation_deletes_nothing(h):
    h.answer = False
    h.run("clear_logs")
    h.run("clear_mistakes")
    assert h.cleared == []
    assert len(h.confirms) == 2


def test_clearing_is_refused_before_asking_when_not_idle(h):
    h.free = False
    h.run("clear_logs")
    h.run("clear_mistakes")
    assert h.confirms == [] and h.cleared == []
    assert h.footer.messages == [(t("settings.clear_busy"), True)] * 2


def test_clearing_refused_by_the_session_after_confirming_says_so(h):
    h.accepted = False
    h.run("clear_logs")
    assert h.footer.messages[-1] == (t("settings.clear_busy"), True)


# ------------------------------------------------------------------- exports
def pick(monkeypatch, path):
    seen = {}

    def fake(**kwargs):
        seen.update(kwargs)
        return str(path) if path else ""

    monkeypatch.setattr(filedialog, "asksaveasfilename", fake)
    return seen


def test_export_report_writes_markdown(h, tmp_path, monkeypatch):
    h.report = REPORT
    target = tmp_path / "out" / "r.md"
    seen = pick(monkeypatch, target)
    h.run("export_report")
    assert target.read_text(encoding="utf-8").startswith("# Session report")
    assert seen["initialfile"] == "session-report-20261112-140509.md"
    assert seen["defaultextension"] == ".md"
    assert h.footer.messages[-1] == (t("export.done", path=str(target)), False)


def test_export_report_without_a_report_does_nothing(h, monkeypatch):
    seen = pick(monkeypatch, "x")
    h.run("export_report")
    assert seen == {}
    assert h.footer.messages[-1][1] is True


def test_export_mistakes_writes_csv_with_a_bom(h, tmp_path, monkeypatch):
    h.mistakes = (record(),)
    target = tmp_path / "m.csv"
    seen = pick(monkeypatch, target)
    h.run("export_mistakes")
    raw = target.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbfseverity,original")
    assert b"2026-11-12T14:05:09" in raw
    assert seen["initialfile"] == "mistakes-20261112-140509.csv"


def test_export_mistakes_with_none_says_so_without_a_dialog(h, monkeypatch):
    seen = pick(monkeypatch, "x")
    h.run("export_mistakes")
    assert seen == {}
    assert h.footer.messages[-1] == (t("export.no_mistakes"), True)


def test_cancelling_the_save_dialog_writes_nothing(h, monkeypatch):
    h.mistakes = (record(),)
    pick(monkeypatch, "")
    h.run("export_mistakes")
    assert h.footer.messages == []


def test_a_write_failure_is_shown_not_raised(h, tmp_path, monkeypatch):
    h.mistakes = (record(),)
    pick(monkeypatch, tmp_path / "m.csv")

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("english_tutor.ui.settings.actions.atomic_write_text", boom)
    h.run("export_mistakes")
    text, error = h.footer.messages[-1]
    assert error and "disk full" in text


def test_save_dialog_starts_in_the_export_folder_else_documents(h, tmp_path, monkeypatch):
    h.mistakes = (record(),)
    seen = pick(monkeypatch, "")
    h.export_dir = str(tmp_path)
    h.run("export_mistakes")
    assert seen["initialdir"] == str(tmp_path)
    h.export_dir = str(tmp_path / "missing")
    h.run("export_mistakes")
    assert seen["initialdir"] == str(Path.home() / "Documents")
    h.export_dir = ""
    h.run("export_mistakes")
    assert seen["initialdir"] == str(Path.home() / "Documents")


# -------------------------------------------------------------- availability
def test_export_report_is_unavailable_until_a_report_exists(h):
    assert h.actions.unavailable("export_report") == t("settings.export_report_unavailable")
    h.report = REPORT
    assert h.actions.unavailable("export_report") is None
    assert h.actions.unavailable("export_mistakes") is None


# ----------------------------------------------------------------- open folder
def test_open_folders_use_the_service(h):
    h.run("open_data_folder")
    h.run("open_logs_folder")
    assert h.opened == [h.services.paths.data_dir, h.services.paths.logs_dir]


def test_open_failure_is_shown(h):
    def boom(path):
        raise StorageError("no shell")

    h.services.open_folder = boom
    h.run("open_data_folder")
    assert h.footer.messages[-1] == ("no shell", True)


# --------------------------------------------------------- folder check on Save
def make_draft(locked=frozenset()):
    from english_tutor.settings.draft import SettingsDraft
    from english_tutor.settings.model import UserSettings

    return SettingsDraft(UserSettings(), UserSettings(), locked)


def test_check_folders_accepts_and_creates_new_folders(tmp_path):
    from english_tutor.ui.settings.actions import check_folders

    draft = make_draft()
    draft.set("data_dir", str(tmp_path / "data2"))
    draft.set("export_dir", str(tmp_path / "exports"))
    assert check_folders(draft) == {}
    assert (tmp_path / "data2").is_dir() and (tmp_path / "exports").is_dir()


def test_check_folders_reports_the_row_that_failed(tmp_path):
    from english_tutor.ui.settings.actions import check_folders

    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    draft = make_draft()
    draft.set("data_dir", str(blocker / "sub"))
    draft.set("export_dir", str(tmp_path / "ok"))
    errors = check_folders(draft)
    assert list(errors) == ["data_dir"]
    assert errors["data_dir"].startswith(t("settings.folder_error", error="")[:12])


def test_check_folders_ignores_untouched_empty_and_locked_values(tmp_path):
    from english_tutor.ui.settings.actions import check_folders

    assert check_folders(make_draft()) == {}
    draft = make_draft()
    draft.set("export_dir", "")
    assert check_folders(draft) == {}
    locked = make_draft(frozenset({"data_dir"}))
    locked.set("data_dir", str(tmp_path / "never"))
    assert check_folders(locked) == {} and not (tmp_path / "never").exists()
