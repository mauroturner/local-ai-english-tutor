"""interpret_key: what a key press means inside the capture dialog (pure)."""

from __future__ import annotations

import pytest

from english_tutor.ui.settings.key_capture import interpret_key

CONTROL, ALT, SHIFT = 0x4, 0x20000, 0x1


@pytest.mark.parametrize(
    ("keysym", "state", "expected"),
    [
        ("k", CONTROL, ("done", "Ctrl+K")),
        ("K", CONTROL | SHIFT, ("done", "Ctrl+Shift+K")),
        ("F5", 0, ("done", "F5")),
        ("comma", CONTROL, ("done", "Ctrl+,")),
        ("Escape", 0, ("cancel", None)),
        ("Control_L", CONTROL, ("ignore", None)),
        ("Shift_R", SHIFT, ("ignore", None)),
        ("Tab", 0, ("unsupported", None)),
        ("exclam", SHIFT, ("unsupported", None)),
    ],
)
def test_shortcut_mode(keysym, state, expected):
    assert interpret_key("shortcut", keysym, state) == expected


@pytest.mark.parametrize(
    ("keysym", "state", "expected"),
    [
        ("F9", 0, ("done", "f9")),
        ("v", 0, ("done", "v")),
        ("V", SHIFT, ("done", "v")),
        ("Control_R", CONTROL, ("done", "right ctrl")),
        ("Alt_R", ALT, ("done", "right alt")),
        ("Shift_L", SHIFT, ("done", "left shift")),
        ("space", 0, ("done", "space")),
        ("Escape", 0, ("cancel", None)),
        ("Return", 0, ("unsupported", None)),
        ("Tab", 0, ("unsupported", None)),
        ("Control_L", CONTROL | ALT, ("ignore", None)),  # first half of AltGr
    ],
)
def test_ptt_mode(keysym, state, expected):
    assert interpret_key("ptt", keysym, state) == expected
