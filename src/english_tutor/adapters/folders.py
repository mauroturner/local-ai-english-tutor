"""Folder helpers for the Settings window."""

from __future__ import annotations

import os
from pathlib import Path

from ..ports import StorageError


def open_folder(path: Path) -> None:
    """Create ``path`` if needed and show it in the file manager.

    Raises StorageError when the folder cannot be created or opened.
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))  # type: ignore[attr-defined]  # Windows only
    except (OSError, AttributeError) as exc:
        raise StorageError(f"Could not open {path}: {exc}") from exc


def validate_folder(text: str) -> None:
    """Make sure the folder named by ``text`` exists and can be written to.

    Creates it (and its parents) when needed and writes then removes a small probe
    file. Raises StorageError with a message fit for the learner when that fails.
    """
    if not text.strip():
        raise StorageError("The folder path is empty.")
    path = Path(text.strip())
    probe = path / f".tutor-write-test-{os.getpid()}"
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass  # nothing left to clean up if the folder itself is unusable
        raise StorageError(f"{path}: {exc.strerror or exc}") from exc
