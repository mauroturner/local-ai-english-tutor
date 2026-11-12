"""Shortcut combos: parsing, Tk mapping, push-to-talk keys and conflict rules (pure)."""

from __future__ import annotations

import pytest

from english_tutor.settings.shortcuts import (
    Combo,
    Conflict,
    combo_from_event,
    find_conflicts,
    format_combo,
    parse_combo,
    tk_keysym_to_ptt,
    to_tk_sequence,
)

SHIFT, CONTROL, ALT = 0x1, 0x4, 0x20000


@pytest.mark.parametrize(
    "text",
    [
        "Ctrl+E", "Ctrl+,", "Ctrl+1", "F5", "Alt+F4", "Ctrl+Shift+E", "Ctrl+Alt+Shift+X",
        "Ctrl+Space", "Ctrl+PageUp", "Ctrl+.", "Shift+F5", "Alt+Left",
    ],
)  # fmt: skip
def test_canonical_text_round_trips(text):
    assert format_combo(parse_combo(text)) == text


def test_parse_is_forgiving_and_formats_canonically():
    assert parse_combo("ctrl+e") == Combo(True, False, False, "E")
    assert format_combo(parse_combo(" control + shift + e ")) == "Ctrl+Shift+E"
    assert format_combo(parse_combo("Shift+Alt+Ctrl+x")) == "Ctrl+Alt+Shift+X"
    assert format_combo(parse_combo("f5")) == "F5"
    assert format_combo(parse_combo("ctrl+space")) == "Ctrl+Space"


@pytest.mark.parametrize(
    "text",
    ["", "   ", "Ctrl+", "+", "Ctrl+Ctrl+E", "Ctrl+AB", "Ctrl+Escape", "Banana+E", "Ctrl+F13",
     "Ctrl+Enter", "Ctrl+Tab", "E+Ctrl"],
)  # fmt: skip
def test_invalid_combos_raise_value_error(text):
    with pytest.raises(ValueError):
        parse_combo(text)


@pytest.mark.parametrize(
    ("text", "sequence"),
    [
        ("Ctrl+E", "<Control-e>"),
        ("Ctrl+,", "<Control-comma>"),
        ("Ctrl+1", "<Control-Key-1>"),
        ("Ctrl+Shift+E", "<Control-Shift-E>"),
        ("F5", "<F5>"),
        ("Alt+F4", "<Alt-F4>"),
        ("Ctrl+Alt+Shift+X", "<Control-Alt-Shift-X>"),
        ("Ctrl+Space", "<Control-space>"),
        ("Ctrl+PageUp", "<Control-Prior>"),
        ("Ctrl+PageDown", "<Control-Next>"),
        ("Ctrl+.", "<Control-period>"),
    ],
)
def test_to_tk_sequence(text, sequence):
    assert to_tk_sequence(text) == sequence


@pytest.mark.parametrize(
    ("keysym", "state", "expected"),
    [
        ("e", CONTROL, "Ctrl+E"),
        ("E", CONTROL | SHIFT, "Ctrl+Shift+E"),
        ("comma", CONTROL, "Ctrl+,"),
        ("1", CONTROL, "Ctrl+1"),
        ("F5", 0, "F5"),
        ("F4", ALT, "Alt+F4"),
        ("space", CONTROL, "Ctrl+Space"),
        ("Prior", CONTROL, "Ctrl+PageUp"),
        ("x", CONTROL | ALT | SHIFT, "Ctrl+Alt+Shift+X"),
        ("e", CONTROL | 0x2 | 0x8, "Ctrl+E"),  # caps lock / num lock bits are ignored
        ("E", CONTROL, "Ctrl+E"),  # caps lock gives an upper-case keysym without Shift
    ],
)
def test_combo_from_event(keysym, state, expected):
    assert combo_from_event(keysym, state) == expected


@pytest.mark.parametrize(
    "keysym",
    ["Control_L", "Control_R", "Shift_L", "Alt_R", "Escape", "Return", "Tab", "exclam", "Super_L"],
)
def test_combo_from_event_ignores_modifiers_and_unsupported_keys(keysym):
    assert combo_from_event(keysym, CONTROL) is None


@pytest.mark.parametrize(
    ("keysym", "state", "expected"),
    [
        ("Control_R", CONTROL, "right ctrl"),
        ("Control_L", CONTROL, "left ctrl"),
        ("Alt_R", ALT, "right alt"),
        ("Alt_L", ALT, "left alt"),
        ("Shift_R", SHIFT, "right shift"),
        ("F9", 0, "f9"),
        ("v", 0, "v"),
        ("V", SHIFT, "v"),
        ("space", 0, "space"),
        ("Escape", 0, None),
        ("Return", 0, None),
        ("Tab", 0, None),
        ("BackSpace", 0, None),
        ("exclam", SHIFT, None),
        ("Super_L", 0, None),
        ("Control_L", CONTROL | ALT, None),  # first half of AltGr; Alt_R follows
    ],
)
def test_tk_keysym_to_ptt(keysym, state, expected):
    assert tk_keysym_to_ptt(keysym, state) == expected


# ------------------------------------------------------------------- conflicts
DEFAULTS = {
    "shortcut_end_session": "Ctrl+E",
    "shortcut_settings": "Ctrl+,",
    "shortcut_chat_tab": "Ctrl+1",
    "shortcut_mistakes_tab": "Ctrl+2",
}


def kinds(conflicts):
    return sorted((c.kind, c.blocking) for c in conflicts)


def test_defaults_do_not_conflict_with_the_default_ptt_key():
    assert find_conflicts(DEFAULTS, "v") == []


def test_duplicates_are_blocking_and_compare_canonically():
    shortcuts = {**DEFAULTS, "shortcut_chat_tab": "ctrl+e"}
    (conflict,) = find_conflicts(shortcuts, "v")
    assert conflict == Conflict(
        "duplicate", ("shortcut_end_session", "shortcut_chat_tab"), "Ctrl+E", True
    )


def test_invalid_text_is_blocking():
    (conflict,) = find_conflicts({**DEFAULTS, "shortcut_settings": "nonsense"}, "v")
    assert (conflict.kind, conflict.actions, conflict.blocking) == (
        "invalid",
        ("shortcut_settings",),
        True,
    )
    assert conflict.combo == "nonsense"


@pytest.mark.parametrize("combo", ["E", "Shift+E", "Space", "Shift+1"])
def test_combos_without_ctrl_or_alt_are_blocking(combo):
    conflicts = find_conflicts({"shortcut_settings": combo}, "v")
    assert kinds(conflicts) == [("no_modifier", True)]


@pytest.mark.parametrize("combo", ["F5", "Shift+F5", "Alt+E", "Ctrl+Shift+E"])
def test_function_keys_and_ctrl_alt_combos_are_fine(combo):
    assert find_conflicts({"shortcut_settings": combo}, "v") == []


@pytest.mark.parametrize("letter", list("CVXAZYFS"))
def test_reserved_ctrl_combos_are_blocking(letter):
    conflicts = find_conflicts({"shortcut_settings": f"Ctrl+{letter}"}, "q")
    assert kinds(conflicts) == [("reserved", True)]


def test_alt_f4_is_reserved_but_ctrl_shift_c_is_not():
    assert kinds(find_conflicts({"shortcut_settings": "Alt+F4"}, "q")) == [("reserved", True)]
    assert find_conflicts({"shortcut_settings": "Ctrl+Shift+C"}, "q") == []


def test_ptt_v_with_ctrl_v_is_reserved_and_a_warning():
    conflicts = find_conflicts({"shortcut_settings": "Ctrl+V"}, "v")
    assert kinds(conflicts) == [("ptt_overlap", False), ("reserved", True)]


def test_ptt_right_ctrl_warns_for_every_ctrl_shortcut_and_never_blocks():
    conflicts = find_conflicts(DEFAULTS, "right ctrl")
    assert [c.kind for c in conflicts] == ["ptt_overlap"] * 4
    assert not any(c.blocking for c in conflicts)
    assert {c.actions[0] for c in conflicts} == set(DEFAULTS)


def test_ptt_letter_overlapping_a_shortcut_key_warns():
    conflicts = find_conflicts(DEFAULTS, "e")
    assert [(c.kind, c.actions, c.combo, c.blocking) for c in conflicts] == [
        ("ptt_overlap", ("shortcut_end_session",), "Ctrl+E", False)
    ]


def test_ptt_alt_only_overlaps_alt_shortcuts():
    assert find_conflicts(DEFAULTS, "left alt") == []
    assert kinds(find_conflicts({"shortcut_settings": "Alt+E"}, "left alt")) == [
        ("ptt_overlap", False)
    ]
