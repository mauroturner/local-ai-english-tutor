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
