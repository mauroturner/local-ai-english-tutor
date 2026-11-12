"""JsonSettingsStore and atomic_write_text: round trip, atomicity, quarantine."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from english_tutor.adapters import atomic_io
from english_tutor.adapters.atomic_io import atomic_write_text
from english_tutor.adapters.json_settings_store import JsonSettingsStore
from english_tutor.ports import StorageError

NOW = datetime(2026, 11, 12, 14, 3, 22)


def make(tmp_path):
    return JsonSettingsStore(tmp_path / "data" / "settings.json", clock=lambda: NOW)


def failing_replace(message):
    def replace(src, dst):
        raise OSError(message)

    return replace


def test_missing_file_loads_as_empty(tmp_path):
    assert make(tmp_path).load() == {}


def test_round_trip_and_file_layout(tmp_path):
    store = make(tmp_path)
    data = {"language": "es", "chat_font_size": 15, "note": "señal"}
    store.save(data)
    assert store.load() == data
    path = tmp_path / "data" / "settings.json"
    assert json.loads(path.read_text(encoding="utf-8")) == {"version": 1, "settings": data}
    assert "señal" in path.read_text(encoding="utf-8")


def test_failed_atomic_write_keeps_the_old_file(tmp_path, monkeypatch):
    target = tmp_path / "f.txt"
    target.write_text("old", encoding="utf-8")
    monkeypatch.setattr(atomic_io.os, "replace", failing_replace("disk full"))
    with pytest.raises(OSError):
        atomic_write_text(target, "new", "utf-8")
    assert target.read_text(encoding="utf-8") == "old"
    assert not (tmp_path / "f.txt.tmp").exists()


def test_atomic_write_creates_parents_and_replaces(tmp_path):
    target = tmp_path / "a" / "b" / "f.txt"
    atomic_write_text(target, "one\ntwo", "utf-8")
    atomic_write_text(target, "three", "utf-8")
    assert target.read_text(encoding="utf-8") == "three"
    assert [p.name for p in target.parent.iterdir()] == ["f.txt"]


def test_failed_store_save_raises_storage_error_and_keeps_old(tmp_path, monkeypatch):
    store = make(tmp_path)
    store.save({"language": "en"})
    monkeypatch.setattr(atomic_io.os, "replace", failing_replace("nope"))
    with pytest.raises(StorageError, match="Could not save the settings"):
        store.save({"language": "es"})
    assert store.load() == {"language": "en"}


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        "[]",
        json.dumps({"version": 2, "settings": {}}),
        json.dumps({"settings": {}}),
        json.dumps({"version": 1, "settings": [1]}),
        json.dumps({"version": 1}),
    ],
)
def test_corrupt_or_unknown_version_is_backed_up(tmp_path, content):
    path = tmp_path / "data" / "settings.json"
    path.parent.mkdir()
    path.write_text(content, encoding="utf-8")
    with pytest.raises(StorageError, match=r"settings\.json\.corrupt-20261112-140322"):
        make(tmp_path).load()
    assert not path.exists()
    backup = tmp_path / "data" / "settings.json.corrupt-20261112-140322"
    assert backup.read_text(encoding="utf-8") == content
    assert make(tmp_path).load() == {}


def test_undecodable_bytes_are_backed_up(tmp_path):
    path = tmp_path / "data" / "settings.json"
    path.parent.mkdir()
    path.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(StorageError, match="corrupt"):
        make(tmp_path).load()
    assert not path.exists()


def test_unmovable_corrupt_file_makes_the_store_read_only(tmp_path, monkeypatch):
    path = tmp_path / "data" / "settings.json"
    path.parent.mkdir()
    path.write_text("{bad", encoding="utf-8")
    store = make(tmp_path)
    from english_tutor.adapters import json_settings_store

    monkeypatch.setattr(json_settings_store.os, "replace", failing_replace("locked"))
    with pytest.raises(StorageError, match="could not be backed up"):
        store.load()
    with pytest.raises(StorageError, match="read-only"):
        store.save({"language": "es"})
    assert path.read_text(encoding="utf-8") == "{bad"
