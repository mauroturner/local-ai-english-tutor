"""KeyboardPushToTalk side filtering, with a fake ``keyboard`` module."""

from __future__ import annotations

import sys
import types
from collections.abc import Callable
from dataclasses import dataclass

import pytest

from english_tutor.adapters.keyboard_ptt import KeyboardPushToTalk, side_names


@dataclass
class FakeEvent:
    name: str


class FakeKeyboard(types.ModuleType):
    """Records the callbacks registered by the adapter."""

    def __init__(self) -> None:
        super().__init__("keyboard")
        self.press_cb: Callable[[FakeEvent], None] | None = None
        self.release_cb: Callable[[FakeEvent], None] | None = None
        self.keys: list[str] = []
        self.unhooked: list[object] = []

    def on_press_key(self, key: str, callback: Callable[[FakeEvent], None]) -> object:
        self.keys.append(key)
        self.press_cb = callback
        return ("press", key)

    def on_release_key(self, key: str, callback: Callable[[FakeEvent], None]) -> object:
        self.release_cb = callback
        return ("release", key)

    def unhook(self, hook: object) -> None:
        self.unhooked.append(hook)


def fake_names(lparam: int) -> str | None:
    """Localized names as observed on a Spanish Windows (see the feature log)."""
    return {29 << 16: "CTRL", (29 << 16) | (1 << 24): "CTRL DERECHA"}.get(lparam)


@pytest.fixture()
def kb(monkeypatch):
    fake = FakeKeyboard()
    monkeypatch.setitem(sys.modules, "keyboard", fake)
    return fake


def start(key: str, key_name_text=fake_names):
    calls: list[str] = []
    ptt = KeyboardPushToTalk(key, key_name_text=key_name_text)
    ptt.start(lambda: calls.append("press"), lambda: calls.append("release"))
    return ptt, calls


def test_left_ctrl_is_ignored_and_right_ctrl_accepted(kb):
    _ptt, calls = start("right ctrl")
    kb.press_cb(FakeEvent("CTRL"))
    kb.release_cb(FakeEvent("CTRL"))
    assert calls == []
    kb.press_cb(FakeEvent("CTRL DERECHA"))
    kb.release_cb(FakeEvent("CTRL DERECHA"))
    assert calls == ["press", "release"]


def test_english_name_is_accepted(kb):
    _ptt, calls = start("right ctrl")
    kb.press_cb(FakeEvent("Right Ctrl"))
    assert calls == ["press"]


def test_left_ctrl_key_accepts_only_the_left_side(kb):
    _ptt, calls = start("left ctrl")
    kb.press_cb(FakeEvent("CTRL DERECHA"))
    assert calls == []
    kb.press_cb(FakeEvent("CTRL"))
    assert calls == ["press"]


def test_auto_repeat_is_ignored(kb):
    _ptt, calls = start("right ctrl")
    for _ in range(3):
        kb.press_cb(FakeEvent("CTRL DERECHA"))
    kb.release_cb(FakeEvent("CTRL DERECHA"))
    kb.release_cb(FakeEvent("CTRL DERECHA"))
    assert calls == ["press", "release"]


def test_failed_lookup_means_no_filter(kb):
    _ptt, calls = start("right ctrl", key_name_text=lambda _lparam: None)
    kb.press_cb(FakeEvent("CTRL"))
    assert calls == ["press"]


def test_other_keys_have_no_filter(kb):
    _ptt, calls = start("f9")
    kb.press_cb(FakeEvent("whatever"))
    assert calls == ["press"]


def test_side_names():
    assert side_names("right ctrl", fake_names) == frozenset({"right ctrl", "ctrl derecha"})
    assert side_names("left ctrl", fake_names) == frozenset({"left ctrl", "ctrl"})
    assert side_names("v", fake_names) is None
    assert side_names("right ctrl", lambda _lparam: None) is None


def test_registers_configured_key_and_unhooks(kb):
    ptt, _calls = start("right ctrl")
    assert kb.keys == ["right ctrl"]
    ptt.stop()
    assert len(kb.unhooked) == 2
