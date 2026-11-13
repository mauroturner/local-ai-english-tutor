"""A versioned JSON file holding one list, with the same safety rules as the other stores.

An unreadable file is moved aside (``.corrupt-<time>``) and reported once; if even
that fails the file turns read-only for the run so nothing is overwritten. Writes
swap a temporary file in with ``os.replace`` (see ``atomic_io``).
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from ..ports import StorageError
from .atomic_io import atomic_write_text

logger = logging.getLogger(__name__)


class MovedAside(StorageError):
    """The unreadable file was renamed to ``.corrupt-<time>``; a new file may start."""


class VersionedJsonList:
    """``{"version": 1, "<key>": [...]}`` in one file; ``label`` names it in messages."""

    def __init__(
        self,
        path: Path,
        key: str,
        label: str,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._path = path
        self._key = key
        self._label = label
        self._clock = clock
        self._read_only = False

    def read(self) -> list[Any]:
        """The stored entries; raises StorageError when the file was unusable."""
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []
        except UnicodeDecodeError:
            self._quarantine()
        except OSError as exc:
            raise StorageError(f"Could not read the {self._label}: {exc}") from exc
        try:
            data = json.loads(raw)
            if not isinstance(data, dict) or data.get("version") != 1:
                raise ValueError("unsupported layout")
            entries = data.get(self._key)
            if not isinstance(entries, list):
                raise ValueError(f"{self._key} must be a list")
        except ValueError:  # invalid JSON, wrong structure or unknown version
            self._quarantine()
        return entries

    def write(self, entries: list[Any]) -> None:
        """Replace the stored entries atomically; raises StorageError on failure."""
        if self._read_only:
            raise StorageError(f"The {self._label} is read-only this run")
        text = json.dumps({"version": 1, self._key: entries}, ensure_ascii=False, indent=2)
        try:
            atomic_write_text(self._path, text)
        except OSError as exc:
            raise StorageError(f"Could not save the {self._label}: {exc}") from exc

    def _quarantine(self) -> None:
        stamp = self._clock().strftime("%Y%m%d-%H%M%S")
        backup = self._path.with_name(f"{self._path.name}.corrupt-{stamp}")
        try:
            os.replace(self._path, backup)
        except OSError as exc:
            self._read_only = True
            logger.error("Could not back up the unreadable %s: %s", self._label, exc)
            raise StorageError(
                f"The {self._label} was unreadable and could not be backed up; "
                "it is read-only this run"
            ) from exc
        raise MovedAside(
            f"The {self._label} was unreadable; saved a copy as {backup.name} and started a new one"
        )
