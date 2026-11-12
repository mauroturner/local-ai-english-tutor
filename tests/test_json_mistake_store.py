"""JsonMistakeStore: atomic saves, corrupt-file quarantine, tolerant loading."""

from __future__ import annotations

import json
import os
from datetime import datetime

import pytest

from english_tutor.adapters.json_mistake_store import JsonMistakeStore
from english_tutor.domain.models import MistakeRecord, Severity
from english_tutor.ports import StorageError

NOW = datetime(2026, 11, 12, 14, 3, 22)


def record(original="I go", corrected="I went", **kw) -> MistakeRecord:
    fields = dict(
        key=f"{original.lower()} => {corrected.lower()}",
        original=original,
        corrected=corrected,
        explanation="Past tense.",
        severity=Severity.MAJOR,
        count=2,
        first_seen=datetime(2026, 11, 1, 9, 0, 0),
        last_seen=datetime(2026, 11, 12, 9, 30, 15),
        examples=("I go home", "I go out"),
        practice_attempts=3,
        practice_successes=1,
    )
    fields.update(kw)
    return MistakeRecord(**fields)


def make(tmp_path):
    return JsonMistakeStore(tmp_path / "data" / "mistakes.json", clock=lambda: NOW)


def test_round_trip(tmp_path):
    store = make(tmp_path)
    saved = [record(), record("a apple", "an apple", severity=Severity.MINOR)]
    store.save(saved)
    assert make(tmp_path).load() == saved


def test_file_layout(tmp_path):
    store = make(tmp_path)
    store.save([record()])
    data = json.loads((tmp_path / "data" / "mistakes.json").read_text(encoding="utf-8"))
    assert data["version"] == 1
    entry = data["mistakes"][0]
    assert entry["first_seen"] == "2026-11-01T09:00:00"
    assert entry["last_seen"] == "2026-11-12T09:30:15"
    assert entry["practice"] == {"attempts": 3, "successes": 1}
    assert entry["severity"] == "major"
    assert not (tmp_path / "data" / "mistakes.json.tmp").exists()


def test_missing_file_is_an_empty_history(tmp_path):
    assert make(tmp_path).load() == []


def test_unicode_is_kept_readable(tmp_path):
    store = make(tmp_path)
    store.save([record("voy a la playa", "I go to the beach", examples=("señor",))])
    text = (tmp_path / "data" / "mistakes.json").read_text(encoding="utf-8")
    assert "señor" in text


def test_corrupt_file_is_quarantined_and_reported(tmp_path):
    path = tmp_path / "data" / "mistakes.json"
    path.parent.mkdir()
    path.write_text("{not json", encoding="utf-8")
    store = make(tmp_path)
    with pytest.raises(StorageError, match="saved a copy as mistakes.json.corrupt-20261112-140322"):
        store.load()
    assert not path.exists()
    assert (tmp_path / "data" / "mistakes.json.corrupt-20261112-140322").read_text() == "{not json"
    store.save([record()])  # a new history starts cleanly
    assert make(tmp_path).load() == [record()]


def test_unknown_version_counts_as_corrupt(tmp_path):
    path = tmp_path / "data" / "mistakes.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"version": 2, "mistakes": []}), encoding="utf-8")
    with pytest.raises(StorageError):
        make(tmp_path).load()
    assert (tmp_path / "data" / "mistakes.json.corrupt-20261112-140322").exists()


def test_wrong_structure_counts_as_corrupt(tmp_path):
    path = tmp_path / "data" / "mistakes.json"
    path.parent.mkdir()
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(StorageError):
        make(tmp_path).load()


def test_bad_entry_is_skipped_and_the_rest_loaded(tmp_path):
    store = make(tmp_path)
    store.save([record(), record("a apple", "an apple")])
    path = tmp_path / "data" / "mistakes.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["mistakes"].insert(0, {"original": "broken"})
    data["mistakes"].append({**data["mistakes"][0], "last_seen": "not a date"})
    path.write_text(json.dumps(data), encoding="utf-8")
    assert [r.key for r in store.load()] == ["i go => i went", "a apple => an apple"]


def test_duplicate_entries_are_merged_by_recomputed_key(tmp_path):
    store = make(tmp_path)
    store.save([record("I go", "I went", count=2), record("i  go", "I went!", count=3)])
    loaded = make(tmp_path).load()
    assert len(loaded) == 1
    assert loaded[0].count == 5
    assert loaded[0].practice_attempts == 6


def test_failing_replace_keeps_the_old_file_and_removes_tmp(tmp_path, monkeypatch):
    store = make(tmp_path)
    store.save([record()])

    def boom(src, dst):
        raise OSError("locked")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(StorageError):
        store.save([record(count=99)])
    monkeypatch.undo()
    assert not (tmp_path / "data" / "mistakes.json.tmp").exists()
    assert make(tmp_path).load()[0].count == 2


def test_failed_backup_makes_the_store_read_only(tmp_path, monkeypatch):
    path = tmp_path / "data" / "mistakes.json"
    path.parent.mkdir()
    path.write_text("garbage", encoding="utf-8")
    store = make(tmp_path)

    def boom(src, dst):
        raise OSError("locked")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(StorageError):
        store.load()
    monkeypatch.undo()
    with pytest.raises(StorageError, match="read-only"):
        store.save([record()])
    assert path.read_text(encoding="utf-8") == "garbage"  # never overwritten
