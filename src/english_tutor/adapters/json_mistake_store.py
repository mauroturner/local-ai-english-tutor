"""Mistake history stored in one JSON file with atomic saves."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ..domain.corrections import normalize
from ..domain.mistakes import MAX_EXAMPLES, mistake_key
from ..domain.models import MistakeRecord, ReviewState, Severity
from ..ports import StorageError

logger = logging.getLogger(__name__)

_VERSION = 1


class JsonMistakeStore:
    """Reads and writes ``{"version": 1, "mistakes": [...]}``.

    An unreadable file is moved aside (``.corrupt-<time>``) and reported once;
    if even that fails the store turns read-only so nothing is overwritten.
    Saves write a temporary file in the same folder and swap it in with
    ``os.replace``, so the old file survives any failure.
    """

    def __init__(self, path: Path, clock: Callable[[], datetime] = datetime.now) -> None:
        self._path = path
        self._clock = clock
        self._read_only = False

    # ------------------------------------------------------------------- load
    def load(self) -> list[MistakeRecord]:
        """Return the stored records; raises StorageError if the file was unusable."""
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []
        except UnicodeDecodeError:
            self._quarantine()
        except OSError as exc:
            raise StorageError(f"Could not read the mistake history: {exc}") from exc
        try:
            entries = self._entries(json.loads(raw))
        except ValueError:  # invalid JSON, wrong structure or unknown version
            self._quarantine()
        return self._merge(self._parse_all(entries))

    @staticmethod
    def _entries(data: Any) -> list[Any]:
        if not isinstance(data, dict) or data.get("version") != _VERSION:
            raise ValueError("unsupported mistake history layout")
        entries = data.get("mistakes")
        if not isinstance(entries, list):
            raise ValueError("mistakes must be a list")
        return entries

    def _quarantine(self) -> None:
        stamp = self._clock().strftime("%Y%m%d-%H%M%S")
        backup = self._path.with_name(f"{self._path.name}.corrupt-{stamp}")
        try:
            os.replace(self._path, backup)
        except OSError as exc:
            self._read_only = True
            logger.error("Could not back up the unreadable mistake history: %s", exc)
            raise StorageError(
                "Mistake history was unreadable and could not be backed up; "
                "it is read-only this run"
            ) from exc
        raise StorageError(
            f"Mistake history was unreadable; saved a copy as {backup.name} and started a new one"
        )

    @staticmethod
    def _parse_all(entries: Sequence[Any]) -> list[MistakeRecord]:
        records: list[MistakeRecord] = []
        for entry in entries:
            try:
                records.append(_parse_entry(entry))
            except (KeyError, TypeError, ValueError, AttributeError) as exc:
                logger.warning("Skipping a bad mistake history entry: %r", exc)
        return records

    @staticmethod
    def _merge(records: Sequence[MistakeRecord]) -> list[MistakeRecord]:
        merged: dict[str, MistakeRecord] = {}
        for item in records:
            old = merged.get(item.key)
            merged[item.key] = item if old is None else _combine(old, item)
        return list(merged.values())

    # ------------------------------------------------------------------- save
    def save(self, records: Sequence[MistakeRecord]) -> None:
        """Write ``records`` atomically; raises StorageError on failure."""
        if self._read_only:
            raise StorageError(
                "Mistake history is read-only this run (the unreadable file could not be moved)"
            )
        payload = {"version": _VERSION, "mistakes": [_to_dict(r) for r in records]}
        tmp = self._path.with_name(f"{self._path.name}.tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self._path)
        except OSError as exc:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                logger.debug("Could not remove %s", tmp)
            raise StorageError(f"Could not save the mistake history: {exc}") from exc


def _to_dict(record: MistakeRecord) -> dict[str, Any]:
    data: dict[str, Any] = {
        "original": record.original,
        "corrected": record.corrected,
        "explanation": record.explanation,
        "severity": record.severity.value,
        "count": record.count,
        "first_seen": record.first_seen.isoformat(timespec="seconds"),
        "last_seen": record.last_seen.isoformat(timespec="seconds"),
        "examples": list(record.examples),
        "practice": {
            "attempts": record.practice_attempts,
            "successes": record.practice_successes,
        },
    }
    if record.category:  # optional fields are written only when set (additive within version 1)
        data["category"] = record.category
    if record.review is not None:
        data["review"] = {"due": record.review.due.isoformat(), "step": record.review.step}
    return data


def _parse_category(entry: Any) -> str | None:
    value = entry.get("category")
    return (value.strip() or None) if isinstance(value, str) else None


def _parse_review(entry: Any) -> ReviewState | None:
    """The stored schedule; a damaged one is dropped (the mistake itself is kept)."""
    raw = entry.get("review")
    if not isinstance(raw, dict):
        return None
    try:
        step = int(raw.get("step", 0))
        return ReviewState(date.fromisoformat(raw["due"]), step) if step >= 0 else None
    except (KeyError, TypeError, ValueError):
        return None


def _parse_entry(entry: Any) -> MistakeRecord:
    original, corrected = str(entry["original"]), str(entry["corrected"])
    if not normalize(original) or not normalize(corrected):
        raise ValueError("empty original or corrected text")
    practice = entry.get("practice") or {}
    count = int(entry["count"])
    if count < 1:
        raise ValueError("count must be positive")
    return MistakeRecord(
        key=mistake_key(original, corrected),
        original=original,
        corrected=corrected,
        explanation=str(entry.get("explanation", "")),
        severity=Severity(entry["severity"]),
        count=count,
        first_seen=datetime.fromisoformat(entry["first_seen"]),
        last_seen=datetime.fromisoformat(entry["last_seen"]),
        examples=tuple(str(e) for e in entry.get("examples", ()))[-MAX_EXAMPLES:],
        practice_attempts=max(0, int(practice.get("attempts", 0))),
        practice_successes=max(0, int(practice.get("successes", 0))),
        category=_parse_category(entry),
        review=_parse_review(entry),
    )


def _combine(a: MistakeRecord, b: MistakeRecord) -> MistakeRecord:
    newest, other = (b, a) if b.last_seen >= a.last_seen else (a, b)
    examples = tuple(dict.fromkeys(other.examples + newest.examples))[-MAX_EXAMPLES:]
    severity = Severity.MAJOR if Severity.MAJOR in (a.severity, b.severity) else a.severity
    return replace(
        newest,
        explanation=newest.explanation or other.explanation,
        severity=severity,
        count=a.count + b.count,
        first_seen=min(a.first_seen, b.first_seen),
        examples=examples,
        practice_attempts=a.practice_attempts + b.practice_attempts,
        practice_successes=a.practice_successes + b.practice_successes,
        category=newest.category or other.category,
        review=newest.review or other.review,
    )
