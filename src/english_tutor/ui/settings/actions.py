"""Storage actions of the Settings window: open folders, export files, delete data."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog
from typing import Any

from ...adapters.atomic_io import atomic_write_text
from ...adapters.folders import validate_folder
from ...domain.export import (
    CSV_ENCODING,
    mistakes_csv,
    mistakes_filename,
    report_filename,
    report_markdown,
)
from ...i18n import t
from ...ports import StorageError
from ...settings.draft import SettingsDraft
from ..services import UiServices

logger = logging.getLogger(__name__)

FOLDER_KEYS = ("data_dir", "export_dir")


def check_folders(draft: SettingsDraft) -> dict[str, str]:
    """Create and probe the folders the user changed; returns an error text per setting.

    Only changed, non-empty, unlocked values are checked (empty means the default).
    """
    errors: dict[str, str] = {}
    for key in FOLDER_KEYS:
        value = str(draft.value(key))
        if key not in draft.dirty_keys or draft.is_locked(key) or not value.strip():
            continue
        try:
            validate_folder(value)
        except StorageError as exc:
            errors[key] = t("settings.folder_error", error=exc)
    return errors


class StorageActions:
    """The handlers behind the Storage (and folder) action rows.

    ``window`` must offer ``footer.set_status(text, error=...)`` and ``draft.value(key)``;
    results are reported in the footer, never raised.
    """

    def __init__(self, window: Any, services: UiServices) -> None:
        self._window = window
        self._services = services

    def actions(self) -> dict[str, Callable[[], None]]:
        """Handlers by action key, ready for the rows."""
        paths = self._services.paths
        return {
            "open_data_folder": lambda: self._open(paths.data_dir),
            "open_logs_folder": lambda: self._open(paths.logs_dir),
            "export_report": self._export_report,
            "export_mistakes": self._export_mistakes,
            "clear_logs": self._clear_logs,
            "clear_mistakes": self._clear_mistakes,
            "clear_memory": self._clear_memory,
        }

    def unavailable(self, key: str) -> str | None:
        """Why the action row ``key`` cannot be used right now, or None when it can."""
        if key == "export_report" and self._services.last_report() is None:
            return t("settings.export_report_unavailable")
        return None

    def _status(self, text: str, error: bool = False) -> None:
        self._window.footer.set_status(text, error=error)

    def _open(self, path: Path) -> None:
        try:
            self._services.open_folder(path)
        except StorageError as exc:
            self._status(t("settings.action_failed", error=exc), True)

    # ----------------------------------------------------------------- exporting
    def _initial_dir(self) -> str:
        chosen = str(self._window.draft.value("export_dir")).strip()
        if chosen and Path(chosen).is_dir():
            return chosen
        return str(Path.home() / "Documents")

    def _export(
        self, title: str, name: str, kind: tuple[str, str], text: str, encoding: str
    ) -> None:
        """Ask where to save and write ``text`` there atomically."""
        label, extension = kind
        chosen = filedialog.asksaveasfilename(
            parent=self._window, title=title, initialdir=self._initial_dir(),
            initialfile=name, defaultextension=extension,
            filetypes=[(label, f"*{extension}")],
        )  # fmt: skip
        if not chosen:
            return
        try:
            atomic_write_text(Path(chosen), text, encoding)
        except OSError as exc:
            logger.warning("Export to %s failed: %s", chosen, exc)
            self._status(t("export.failed", error=exc), True)
            return
        logger.info("Exported %s", chosen)
        self._status(t("export.done", path=chosen))

    def _export_report(self) -> None:
        report = self._services.last_report()
        if report is None:
            self._status(t("export.no_report"), True)
            return
        now = self._services.clock()
        self._export(
            t("export.report_title"), report_filename(now),
            (t("export.type_markdown"), ".md"), report_markdown(report, now), "utf-8",
        )  # fmt: skip

    def _export_mistakes(self) -> None:
        records = self._services.mistakes()
        if not records:
            self._status(t("export.no_mistakes"), True)
            return
        now = self._services.clock()
        self._export(
            t("export.mistakes_title"), mistakes_filename(now),
            (t("export.type_csv"), ".csv"), mistakes_csv(records), CSV_ENCODING,
        )  # fmt: skip

    # ------------------------------------------------------------------ deleting
    def _delete(self, title: str, message: str, run: Callable[[], bool]) -> None:
        """Refuse when busy, ask, then delete; the result arrives as a ``DataCleared`` event."""
        if not self._services.is_free():
            self._status(t("settings.clear_busy"), True)
            return
        if not self._services.confirm(title, message, parent=self._window):
            return
        if not run():  # the session became busy while the question was open
            self._status(t("settings.clear_busy"), True)

    def _clear_logs(self) -> None:
        folder = str(self._services.paths.conversations_dir)
        self._delete(
            t("settings.clear_logs_title"),
            t("settings.clear_logs_message", folder=folder),
            self._services.clear_logs,
        )

    def _clear_memory(self) -> None:
        self._delete(
            t("settings.clear_memory_title"),
            t("settings.clear_memory_message", count=self._services.memory_count()),
            self._services.clear_memory,
        )

    def _clear_mistakes(self) -> None:
        count = len(self._services.mistakes())
        self._delete(
            t("settings.clear_mistakes_title"),
            t("settings.clear_mistakes_message", count=count),
            self._services.clear_mistakes,
        )
