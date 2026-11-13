"""JsonSessionStore: atomic appends, corrupt-file quarantine, tolerant loading."""

from __future__ import annotations

import json
import os
from datetime import datetime

import pytest

from english_tutor.adapters.json_session_store import JsonSessionStore
from english_tutor.domain.progress import SessionStats
from english_tutor.ports import StorageError

NOW = datetime(2026, 11, 13, 10, 0, 0)


def stats(**kw) -> SessionStats:
    fields = dict(
        started_at=datetime(2026, 11, 12, 9, 30, 0), duration_s=300.0, turns=5, words=80,
        speech_s=40.0, major=2, minor=3, pauses=1, slow_starts=1,
    )
    fields.update(kw)
    return SessionStats(**fields)


def make(tmp_path):
    return JsonSessionStore(tmp_path / "data" / "sessions.json", clock=lambda: NOW)


def write_raw(tmp_path, text):
    path = tmp_path / "data" / "sessions.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_round_trip_keeps_order(tmp_path):
    store = make(tmp_path)
    first, second = stats(), stats(words=120, started_at=datetime(2026, 11, 13, 8, 0, 0))
    store.append(first)
    store.append(second)
    assert make(tmp_path).load() == [first, second]


def test_file_layout(tmp_path):
    store = make(tmp_path)
    store.append(stats())
    data = json.loads((tmp_path / "data" / "sessions.json").read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["sessions"][0]["started_at"] == "2026-11-12T09:30:00"
    assert data["sessions"][0]["slow_starts"] == 1
    assert not (tmp_path / "data" / "sessions.json.tmp").exists()


def test_missing_file_is_an_empty_list(tmp_path):
    assert make(tmp_path).load() == []


def test_corrupt_file_is_quarantined_and_append_starts_a_new_one(tmp_path):
    write_raw(tmp_path, "{ nope")
    store = make(tmp_path)
    store.append(stats())
    backup = tmp_path / "data" / "sessions.json.corrupt-20261113-100000"
    assert backup.read_text(encoding="utf-8") == "{ nope"
    assert make(tmp_path).load() == [stats()]


def test_load_reports_a_corrupt_file(tmp_path):
    write_raw(tmp_path, "[]")
    with pytest.raises(StorageError, match="saved a copy"):
        make(tmp_path).load()


def test_unknown_version_is_quarantined(tmp_path):
    path = write_raw(tmp_path, json.dumps({"version": 2, "sessions": []}))
    with pytest.raises(StorageError):
        make(tmp_path).load()
    assert not path.exists()


def test_bad_entries_are_skipped_not_fatal(tmp_path):
    store = make(tmp_path)
    store.append(stats())
    path = tmp_path / "data" / "sessions.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["sessions"] += [{"started_at": "garbage"}, {**data["sessions"][0], "words": -1}]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert make(tmp_path).load() == [stats()]


def test_unmovable_corrupt_file_makes_the_store_read_only(tmp_path, monkeypatch):
    path = write_raw(tmp_path, "{ nope")

    def refuse(*args, **kwargs):
        raise PermissionError("locked")

    monkeypatch.setattr(os, "replace", refuse)
    store = make(tmp_path)
    with pytest.raises(StorageError, match="read-only"):
        store.append(stats())
    assert path.read_text(encoding="utf-8") == "{ nope"  # nothing was overwritten


def test_a_failed_save_keeps_the_old_file(tmp_path, monkeypatch):
    store = make(tmp_path)
    store.append(stats())

    def refuse(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(StorageError, match="Could not save"):
        store.append(stats(words=1))
    monkeypatch.undo()
    assert make(tmp_path).load() == [stats()]


def test_a_read_error_never_overwrites_the_history(tmp_path, monkeypatch):
    from pathlib import Path

    store = make(tmp_path)
    store.append(stats())
    path = tmp_path / "data" / "sessions.json"
    before = path.read_text(encoding="utf-8")

    def locked(self, *args, **kwargs):
        raise PermissionError("file is locked")

    monkeypatch.setattr(Path, "read_text", locked)
    with pytest.raises(StorageError, match="Could not read"):
        store.append(stats(words=1))
    monkeypatch.undo()
    assert path.read_text(encoding="utf-8") == before
    assert list((tmp_path / "data").glob("*.corrupt-*")) == []


def test_categories_round_trip_and_are_optional(tmp_path):
    store = make(tmp_path)
    with_cats = stats(categories=(("articles", 3), ("verb_tense", 1)))
    store.append(with_cats)
    store.append(stats())
    data = json.loads((tmp_path / "data" / "sessions.json").read_text(encoding="utf-8"))
    assert data["sessions"][0]["categories"] == {"articles": 3, "verb_tense": 1}
    assert "categories" not in data["sessions"][1]
    assert make(tmp_path).load() == [with_cats, stats()]


@pytest.mark.parametrize("bad", ["x", [1], {"articles": "many"}, {"articles": None}])
def test_damaged_categories_are_dropped_but_the_session_is_kept(tmp_path, bad):
    store = make(tmp_path)
    store.append(stats())
    path = tmp_path / "data" / "sessions.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["sessions"][0]["categories"] = bad
    path.write_text(json.dumps(data), encoding="utf-8")
    assert make(tmp_path).load() == [stats()]
