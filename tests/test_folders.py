"""open_folder: creates the folder and hands it to the shell."""

from __future__ import annotations

import os

import pytest

from english_tutor.adapters.folders import open_folder, validate_folder, validate_folder
from english_tutor.ports import StorageError


def test_creates_the_folder_and_opens_it(tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr(os, "startfile", opened.append, raising=False)
    target = tmp_path / "a" / "b"
    open_folder(target)
    assert target.is_dir()
    assert opened == [str(target)]


def test_failures_become_storage_errors(tmp_path, monkeypatch):
    def boom(path):
        raise OSError("no shell")

    monkeypatch.setattr(os, "startfile", boom, raising=False)
    with pytest.raises(StorageError, match="no shell"):
        open_folder(tmp_path / "x")


def test_unmakeable_folder_becomes_a_storage_error(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(StorageError):
        open_folder(blocker / "sub")


# ---------------------------------------------------------------- validate_folder
def test_validate_creates_the_folder_and_leaves_no_probe(tmp_path):
    target = tmp_path / "new" / "deep"
    validate_folder(str(target))
    assert target.is_dir()
    assert list(target.iterdir()) == []


def test_validate_accepts_an_existing_folder_without_touching_its_files(tmp_path):
    (tmp_path / "keep.txt").write_text("x", encoding="utf-8")
    validate_folder(str(tmp_path))
    assert [p.name for p in tmp_path.iterdir()] == ["keep.txt"]


def test_validate_rejects_a_file_in_the_way(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(StorageError, match="file"):
        validate_folder(str(blocker / "sub"))
    with pytest.raises(StorageError):
        validate_folder(str(blocker))


def test_validate_rejects_an_unwritable_folder(tmp_path, monkeypatch):
    from pathlib import Path

    def denied(self, *args, **kwargs):
        raise PermissionError("access denied")

    monkeypatch.setattr(Path, "write_text", denied)
    with pytest.raises(StorageError, match="access denied"):
        validate_folder(str(tmp_path))


def test_validate_rejects_a_blank_path():
    with pytest.raises(StorageError):
        validate_folder("   ")
