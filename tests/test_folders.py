"""open_folder: creates the folder and hands it to the shell."""

from __future__ import annotations

import os

import pytest

from english_tutor.adapters.folders import open_folder
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
