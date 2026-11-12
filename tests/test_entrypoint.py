"""The root main.py launches the app without installing the package."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_root_entrypoint_exposes_the_app_main_and_adds_src(monkeypatch):
    monkeypatch.setattr(sys, "path", [p for p in sys.path if Path(p).resolve() != ROOT / "src"])
    namespace = runpy.run_path(str(ROOT / "main.py"), run_name="not_main")
    from english_tutor.__main__ import main

    assert namespace["main"] is main
    assert str(ROOT / "src") in sys.path


def test_root_entrypoint_returns_the_app_exit_code(monkeypatch):
    import english_tutor.__main__ as app

    monkeypatch.setattr(app, "main", lambda: 7)
    namespace = runpy.run_path(str(ROOT / "main.py"), run_name="not_main")
    assert namespace["run"]() == 7
