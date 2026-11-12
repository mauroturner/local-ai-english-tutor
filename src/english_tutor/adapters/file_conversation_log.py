"""Conversation log stored as one plain-text ``.log`` file per session."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from ..ports import LogSpeaker, StorageError

logger = logging.getLogger(__name__)

_LABELS: dict[str, str] = {
    "you": "YOU",
    "tutor": "ALEX",
    "tip": "TIP",
    "report": "REPORT",
    "practice": "PRACTICE",
}
_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
_INDENT = "    "


class FileConversationLog:
    """Writes timestamped lines to ``<folder>/session-YYYYmmdd-HHMMSS.log``.

    The file is created on the first ``record`` after construction or after
    ``new_session``. Every record opens, appends and closes the file so the
    log survives a crash. Text is written exactly as given (UTF-8, LF); only
    the continuation lines of multi-line text are indented.
    """

    def __init__(self, folder: Path, clock: Callable[[], datetime] = datetime.now) -> None:
        self._folder = folder
        self._clock = clock
        self._path: Path | None = None

    def record(self, speaker: LogSpeaker, text: str) -> None:
        """Append one entry, creating the folder and file when needed."""
        now = self._clock()
        first, *rest = text.split("\n")
        lines = [f"[{now.strftime(_TIME_FORMAT)}] {_LABELS[speaker]}: {first}"]
        lines += [f"{_INDENT}{line}" for line in rest]
        try:
            path = self._path if self._path is not None else self._create(now)
            with open(path, "a", encoding="utf-8", newline="\n") as handle:
                handle.write("\n".join(lines) + "\n")
        except OSError as exc:
            raise StorageError(f"Could not write the conversation log: {exc}") from exc

    def new_session(self) -> None:
        """Start a new file with the next entry."""
        self._path = None

    def clear(self) -> int:
        """Delete every ``session-*.log`` file in the folder; returns how many were deleted.

        Nothing else is touched (other files, sub-folders, the application logs). The next
        ``record`` starts a new file. Raises StorageError if a file could not be deleted.
        """
        self._path = None
        deleted, failures = 0, []
        for path in self._folder.glob("session-*.log") if self._folder.is_dir() else ():
            if not path.is_file():
                continue
            try:
                path.unlink()
                deleted += 1
            except OSError as exc:
                failures.append(f"{path.name}: {exc}")
        if failures:
            raise StorageError(
                f"Could not delete {len(failures)} conversation log(s): {'; '.join(failures)}"
            )
        logger.info("Deleted %d conversation log file(s)", deleted)
        return deleted

    def _create(self, now: datetime) -> Path:
        self._folder.mkdir(parents=True, exist_ok=True)
        stamp = now.strftime("%Y%m%d-%H%M%S")
        header = f"# English tutor conversation - {now.strftime(_TIME_FORMAT)}\n"
        number = 1
        while True:
            suffix = "" if number == 1 else f"-{number}"
            path = self._folder / f"session-{stamp}{suffix}.log"
            try:
                with open(path, "x", encoding="utf-8", newline="\n") as handle:
                    handle.write(header)
            except FileExistsError:
                number += 1
                continue
            self._path = path
            logger.info("Conversation log: %s", path)
            return path
