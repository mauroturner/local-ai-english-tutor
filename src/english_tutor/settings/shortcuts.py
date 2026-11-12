"""Keyboard shortcut combos, Tk event mapping, push-to-talk keys and conflicts (pure).

Combos are written ``Ctrl+Alt+Shift+<key>``: the key is a letter or digit (shown
upper-case), one of a few punctuation marks, ``F1``..``F12`` or a named key such
as ``Space`` or ``PageUp``. ``parse_combo`` accepts looser spellings and
``format_combo`` always writes the canonical one.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

SHIFT_BIT, CONTROL_BIT, ALT_BIT = 0x1, 0x4, 0x20000  # Tk event.state on Windows

_PUNCT = {
    ",": "comma", ".": "period", "/": "slash", ";": "semicolon", "'": "apostrophe",
    "[": "bracketleft", "]": "bracketright", "-": "minus", "=": "equal", "`": "grave",
    "\\": "backslash",
}  # fmt: skip
_PUNCT_BY_KEYSYM = {keysym: char for char, keysym in _PUNCT.items()}
_NAMED = {  # canonical name -> Tk keysym
    "Space": "space", "Up": "Up", "Down": "Down", "Left": "Left", "Right": "Right",
    "Home": "Home", "End": "End", "PageUp": "Prior", "PageDown": "Next",
    "Insert": "Insert", "Delete": "Delete",
}  # fmt: skip
_NAMED_BY_KEYSYM = {keysym: name for name, keysym in _NAMED.items()}
_NAMED_BY_LOWER = {name.lower(): name for name in _NAMED}
_FKEYS = {f"F{n}" for n in range(1, 13)}
_MODIFIERS = {"ctrl": "ctrl", "control": "ctrl", "alt": "alt", "shift": "shift"}
_RESERVED = frozenset({f"Ctrl+{letter}" for letter in "CVXAZYFS"} | {"Alt+F4"})
_PTT_MODIFIERS = {
    "Control_L": "left ctrl", "Control_R": "right ctrl", "Alt_L": "left alt",
    "Alt_R": "right alt", "Shift_L": "left shift", "Shift_R": "right shift",
}  # fmt: skip


@dataclass(frozen=True)
class Combo:
    """A parsed shortcut; ``key`` is canonical (``E``, ``,``, ``F5``, ``PageUp``)."""

    ctrl: bool
    alt: bool
    shift: bool
    key: str


@dataclass(frozen=True)
class Conflict:
    """A problem with one or more shortcuts.

    ``kind`` is ``invalid``, ``duplicate``, ``no_modifier`` or ``reserved``
    (all blocking) or ``ptt_overlap`` (a warning).
    """

    kind: str
    actions: tuple[str, ...]
    combo: str
    blocking: bool


def _is_alnum(char: str) -> bool:
    return len(char) == 1 and char.isascii() and char.isalnum()


def _canonical_key(text: str) -> str | None:
    if _is_alnum(text):
        return text.upper()
    if text in _PUNCT:
        return text
    if text.upper() in _FKEYS:
        return text.upper()
    return _NAMED_BY_LOWER.get(text.lower())


def parse_combo(text: str) -> Combo:
    """Parse ``text`` such as ``ctrl+shift+e``; raises ValueError when it is not a combo."""
    parts = [part.strip() for part in text.split("+")]
    if len(parts) < 2 and parts[0] == "":
        raise ValueError("The shortcut is empty.")
    if any(part == "" for part in parts):
        raise ValueError(f"{text!r} is not a valid shortcut.")
    key = _canonical_key(parts[-1])
    if key is None:
        raise ValueError(f"{parts[-1]!r} is not a key that can be used in a shortcut.")
    found: set[str] = set()
    for part in parts[:-1]:
        modifier = _MODIFIERS.get(part.lower())
        if modifier is None or modifier in found:
            raise ValueError(f"{part!r} is not a valid modifier here.")
        found.add(modifier)
    return Combo("ctrl" in found, "alt" in found, "shift" in found, key)


def format_combo(combo: Combo) -> str:
    """The canonical text of ``combo``, modifiers in the order Ctrl, Alt, Shift."""
    return "+".join([*_modifier_names(combo, ("Ctrl", "Alt", "Shift")), combo.key])


def _modifier_names(combo: Combo, names: tuple[str, str, str]) -> list[str]:
    flags = (combo.ctrl, combo.alt, combo.shift)
    return [name for name, on in zip(names, flags, strict=True) if on]


def to_tk_sequence(text: str) -> str:
    """The Tk binding sequence for ``text``, e.g. ``Ctrl+,`` -> ``<Control-comma>``."""
    combo = parse_combo(text)
    parts = _modifier_names(combo, ("Control", "Alt", "Shift"))
    key = combo.key
    if key.isalpha() and len(key) == 1:
        parts.append(key if combo.shift else key.lower())
    elif key.isdigit():
        parts.extend(["Key", key])  # a bare digit would read as a mouse button
    elif key in _PUNCT:
        parts.append(_PUNCT[key])
    elif key in _NAMED:
        parts.append(_NAMED[key])
    else:
        parts.append(key)
    return "<" + "-".join(parts) + ">"


def combo_from_event(keysym: str, state: int) -> str | None:
    """Canonical combo text for a Tk key event, or None for modifiers and unsupported keys."""
    if _is_alnum(keysym):
        key: str | None = keysym.upper()
    elif keysym in _PUNCT_BY_KEYSYM:
        key = _PUNCT_BY_KEYSYM[keysym]
    elif keysym in _FKEYS:
        key = keysym
    else:
        key = _NAMED_BY_KEYSYM.get(keysym)
    if key is None:
        return None
    return format_combo(
        Combo(bool(state & CONTROL_BIT), bool(state & ALT_BIT), bool(state & SHIFT_BIT), key)
    )


def tk_keysym_to_ptt(keysym: str, state: int = 0) -> str | None:
    """Map a Tk key event to a ``keyboard`` package key name for push-to-talk.

    ``Control_R`` -> ``right ctrl``, ``F9`` -> ``f9``. Escape, Return, Tab and other
    keys return None. AltGr arrives as a ``Control_L`` event already flagged with
    Alt, followed by ``Alt_R``; that first event is ignored so ``right alt`` wins.
    """
    if keysym == "Control_L" and state & ALT_BIT:
        return None
    if keysym in _PTT_MODIFIERS:
        return _PTT_MODIFIERS[keysym]
    if keysym in _FKEYS:
        return keysym.lower()
    if _is_alnum(keysym):
        return keysym.lower()
    if keysym == "space":
        return "space"
    return None


def _overlaps_ptt(ptt_key: str, combo: Combo) -> bool:
    ptt = ptt_key.strip().lower()
    if ptt.endswith("ctrl") or ptt == "control":
        return combo.ctrl
    if ptt.endswith("alt"):
        return combo.alt
    if ptt.endswith("shift"):
        return combo.shift
    return combo.key.lower() == ptt


def find_conflicts(shortcuts: Mapping[str, str], ptt_key: str) -> list[Conflict]:
    """Check ``{action: combo text}`` against each other, the system and the PTT key.

    Blocking: unparsable text, duplicates, combos without Ctrl or Alt (F-keys are
    allowed bare) and reserved combos (Ctrl+C/V/X/A/Z/Y/F/S, Alt+F4). Warning only:
    overlap with the push-to-talk key, because that hook does not swallow keys.
    """
    conflicts: list[Conflict] = []
    by_combo: dict[str, list[str]] = {}
    for action, text in shortcuts.items():
        try:
            combo = parse_combo(text)
        except ValueError:
            conflicts.append(Conflict("invalid", (action,), text, True))
            continue
        shown = format_combo(combo)
        by_combo.setdefault(shown, []).append(action)
        if not (combo.ctrl or combo.alt) and combo.key not in _FKEYS:
            conflicts.append(Conflict("no_modifier", (action,), shown, True))
        if shown in _RESERVED:
            conflicts.append(Conflict("reserved", (action,), shown, True))
        if _overlaps_ptt(ptt_key, combo):
            conflicts.append(Conflict("ptt_overlap", (action,), shown, False))
    for shown, actions in by_combo.items():
        if len(actions) > 1:
            conflicts.append(Conflict("duplicate", tuple(actions), shown, True))
    return conflicts
