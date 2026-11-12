"""User settings stored in one JSON file with atomic saves."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

from ..ports import StorageError
from .atomic_io import atomic_write_text

logger = logging.getLogger(__name__)

_VERSION = 1


class JsonSettingsStore:
    """Reads and writes ``{"version": 1, "settings": {...}}``.

    A missing file is an empty mapping. An unreadable file or an unknown
    version is moved aside (``.corrupt-<time>``) and reported with a
    StorageError; if even that fails the store turns read-only so the file is
    never overwritten.
    """

    def __init__(self, path: Path, clock: Callable[[], datetime] = datetime.now) -> None:
        self._path = path
        self._clock = clock
        self._read_only = False

    def load(self) -> dict[str, Any]:
        """Return the stored mapping; raises StorageError if the file was unusable."""
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        except UnicodeDecodeError:
            self._quarantine()
        except OSError as exc:
            raise StorageError(f"Could not read the settings: {exc}") from exc
        try:
            return self._settings(json.loads(raw))
        except ValueError:  # invalid JSON, wrong structure or unknown version
            self._quarantine()

    @staticmethod
    def _settings(data: Any) -> dict[str, Any]:
        if not isinstance(data, dict) or data.get("version") != _VERSION:
            raise ValueError("unsupported settings layout")
        settings = data.get("settings")
        if not isinstance(settings, dict):
            raise ValueError("settings must be an object")
        return settings

    def _quarantine(self) -> NoReturn:
        stamp = self._clock().strftime("%Y%m%d-%H%M%S")
        backup = self._path.with_name(f"{self._path.name}.corrupt-{stamp}")
        try:
            os.replace(self._path, backup)
        except OSError as exc:
            self._read_only = True
            logger.error("Could not back up the unreadable settings: %s", exc)
            raise StorageError(
                "Settings were unreadable and could not be backed up; "
                "they are read-only this run"
            ) from exc
        raise StorageError(
            f"Settings were unreadable; saved a copy as {backup.name} and started with defaults"
        )

    def save(self, data: Mapping[str, Any]) -> None:
        """Write ``data`` atomically; raises StorageError on failure."""
        if self._read_only:
            raise StorageError(
                "Settings are read-only this run (the unreadable file could not be moved)"
            )
        payload = {"version": _VERSION, "settings": dict(data)}
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        try:
            atomic_write_text(self._path, text, "utf-8")
        except OSError as exc:
            raise StorageError(f"Could not save the settings: {exc}") from exc
