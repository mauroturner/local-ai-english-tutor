"""Session statistics stored in one JSON file with atomic saves."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from ..domain.memory import clean_memory
from ..domain.progress import SessionStats
from ..ports import StorageError
from .atomic_io import atomic_write_text

logger = logging.getLogger(__name__)

_VERSION = 1


class _MovedAside(StorageError):
    """The unreadable file was renamed to ``.corrupt-<time>``; a new file may start."""


class JsonSessionStore:
    """Reads and writes ``{"version": 1, "sessions": [...]}``.

    Same safety rules as the mistake history: an unreadable file is moved aside
    (``.corrupt-<time>``) and reported; if that fails the store turns read-only;
    saves swap a temporary file in with ``os.replace``.
    """

    def __init__(self, path: Path, clock: Callable[[], datetime] = datetime.now) -> None:
        self._path = path
        self._clock = clock
        self._read_only = False

    def load(self) -> list[SessionStats]:
        """Return the stored sessions; raises StorageError if the file was unusable."""
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []
        except UnicodeDecodeError:
            self._quarantine()
        except OSError as exc:
            raise StorageError(f"Could not read the session statistics: {exc}") from exc
        try:
            entries = self._entries(json.loads(raw))
        except ValueError:  # invalid JSON, wrong structure or unknown version
            self._quarantine()
        return self._parse_all(entries)

    def append(self, stats: SessionStats) -> None:
        """Add one session to the file; a quarantined file starts a new one."""
        try:
            sessions = self.load()
        except _MovedAside:  # the old file is safe under another name
            logger.warning("Session statistics were unreadable; started a new file")
            sessions = []
        self._write([*sessions, stats])

    def clear_memory(self) -> int:
        """Remove the memory notes of every stored session; returns how many had notes.

        The numbers of the sessions are kept. Nothing is written when there was
        nothing to remove.
        """
        sessions = self.load()
        kept = [s for s in sessions if s.memory]
        if not kept:
            return 0
        self._write([replace(s, memory=None) for s in sessions])
        return len(kept)

    @staticmethod
    def _entries(data: Any) -> list[Any]:
        if not isinstance(data, dict) or data.get("version") != _VERSION:
            raise ValueError("unsupported session statistics layout")
        entries = data.get("sessions")
        if not isinstance(entries, list):
            raise ValueError("sessions must be a list")
        return entries

    def _quarantine(self) -> None:
        stamp = self._clock().strftime("%Y%m%d-%H%M%S")
        backup = self._path.with_name(f"{self._path.name}.corrupt-{stamp}")
        try:
            os.replace(self._path, backup)
        except OSError as exc:
            self._read_only = True
            logger.error("Could not back up the unreadable session statistics: %s", exc)
            raise StorageError(
                "Session statistics were unreadable and could not be backed up; "
                "they are read-only this run"
            ) from exc
        raise _MovedAside(
            f"Session statistics were unreadable; saved a copy as {backup.name} "
            "and started a new file"
        )

    @staticmethod
    def _parse_all(entries: list[Any]) -> list[SessionStats]:
        sessions: list[SessionStats] = []
        for entry in entries:
            try:
                sessions.append(_parse_entry(entry))
            except (KeyError, TypeError, ValueError, AttributeError) as exc:
                logger.warning("Skipping a bad session statistics entry: %r", exc)
        return sessions

    def _write(self, sessions: list[SessionStats]) -> None:
        if self._read_only:
            raise StorageError("Session statistics are read-only this run")
        payload = {"version": _VERSION, "sessions": [_to_dict(s) for s in sessions]}
        try:
            atomic_write_text(self._path, json.dumps(payload, ensure_ascii=False, indent=2))
        except OSError as exc:
            raise StorageError(f"Could not save the session statistics: {exc}") from exc


def _to_dict(stats: SessionStats) -> dict[str, Any]:
    data: dict[str, Any] = {
        "started_at": stats.started_at.isoformat(timespec="seconds"),
        "duration_s": round(stats.duration_s, 1),
        "turns": stats.turns,
        "words": stats.words,
        "speech_s": round(stats.speech_s, 1),
        "major": stats.major,
        "minor": stats.minor,
        "pauses": stats.pauses,
        "slow_starts": stats.slow_starts,
    }
    if stats.categories:  # optional, written only when there is something to say
        data["categories"] = dict(stats.categories)
    if stats.scenario:
        data["scenario"] = stats.scenario
    if stats.memory:
        data["memory"] = stats.memory
    return data


def _parse_scenario(entry: Any) -> str | None:
    value = entry.get("scenario")
    return (value.strip() or None) if isinstance(value, str) else None


def _parse_categories(entry: Any) -> tuple[tuple[str, int], ...]:
    """The stored counts; a damaged block is dropped and the session is kept."""
    raw = entry.get("categories")
    if not isinstance(raw, dict):
        return ()
    try:
        pairs = [(str(name), int(count)) for name, count in raw.items()]
    except (TypeError, ValueError):
        return ()
    return tuple(sorted((p for p in pairs if p[1] > 0), key=lambda p: (-p[1], p[0])))


def _count(entry: Any, key: str) -> int:
    value = int(entry[key])
    if value < 0:
        raise ValueError(f"{key} must not be negative")
    return value


def _seconds(entry: Any, key: str) -> float:
    value = float(entry[key])
    if not value >= 0:  # also rejects NaN
        raise ValueError(f"{key} must not be negative")
    return value


def _parse_entry(entry: Any) -> SessionStats:
    return SessionStats(
        started_at=datetime.fromisoformat(entry["started_at"]),
        duration_s=_seconds(entry, "duration_s"),
        turns=_count(entry, "turns"),
        words=_count(entry, "words"),
        speech_s=_seconds(entry, "speech_s"),
        major=_count(entry, "major"),
        minor=_count(entry, "minor"),
        pauses=_count(entry, "pauses"),
        slow_starts=_count(entry, "slow_starts"),
        categories=_parse_categories(entry),
        scenario=_parse_scenario(entry),
        memory=clean_memory(entry.get("memory") if isinstance(entry.get("memory"), str) else None),
    )
