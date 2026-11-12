"""The settings button is only shown when something can open the settings."""

from __future__ import annotations

import tkinter

import pytest

from english_tutor.config import load_config


def build_window(make_harness, **kwargs):
    ui = pytest.importorskip("english_tutor.ui.app_window")
    from english_tutor.ui import theme

    theme._body_font = None  # the shared font is bound to the previous (destroyed) root
    try:
        return ui.TutorWindow(load_config({}), make_harness().session, [], None, **kwargs)
    except tkinter.TclError as exc:  # no display available
        pytest.skip(f"Tk unavailable: {exc}")


def test_settings_button_is_hidden_without_a_handler(make_harness):
    window = build_window(make_harness)
    try:
        window.update_idletasks()
        assert not window._settings_button.winfo_ismapped()
        assert window._settings_button.grid_info() == {}
    finally:
        window.destroy()


def test_settings_button_opens_settings_when_wired(make_harness):
    opened = []
    window = build_window(make_harness, on_open_settings=lambda: opened.append(True))
    try:
        assert window._settings_button.grid_info() != {}
        window._settings_button.invoke()
        assert opened == [True]
    finally:
        window.destroy()
