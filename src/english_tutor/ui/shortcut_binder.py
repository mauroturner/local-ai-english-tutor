"""In-app keyboard shortcuts, bound on the main window only (never globally)."""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from ..settings.model import UserSettings
from ..settings.shortcuts import find_conflicts, to_tk_sequence

logger = logging.getLogger(__name__)

ACTIONS = {
    "shortcut_end_session": "end_session",
    "shortcut_settings": "settings",
    "shortcut_chat_tab": "chat_tab",
    "shortcut_mistakes_tab": "mistakes_tab",
    "shortcut_repeat": "repeat",
    "shortcut_repeat_slow": "repeat_slow",
}
"""Settings field -> action name handled by the main window."""


@dataclass(frozen=True)
class RebindPlan:
    """Sequences to unbind first, then ``{action: sequence}`` to bind."""

    unbind: tuple[str, ...]
    bind: dict[str, str]


def sequences_for(settings: UserSettings) -> dict[str, str]:
    """``{action: Tk sequence}`` for the shortcuts that are safe to bind.

    Shortcuts with a blocking problem (invalid, duplicate, reserved, no Ctrl/Alt)
    are left out; overlaps with the push-to-talk key are only warnings.
    """
    shortcuts = {field: getattr(settings, field) for field in ACTIONS}
    blocked = {
        action
        for conflict in find_conflicts(shortcuts, settings.ptt_key)
        if conflict.blocking
        for action in conflict.actions
    }
    return {
        ACTIONS[field]: to_tk_sequence(text)
        for field, text in shortcuts.items()
        if field not in blocked
    }


def plan_rebind(old: Mapping[str, str], new: Mapping[str, str]) -> RebindPlan:
    """What changes between two ``{action: sequence}`` maps."""
    unbind = tuple(seq for action, seq in old.items() if new.get(action) != seq)
    bind = {action: seq for action, seq in new.items() if old.get(action) != seq}
    return RebindPlan(unbind, bind)


class ShortcutBinder:
    """Keeps the main window's shortcuts in step with the settings."""

    def __init__(self, widget: Any, handlers: Mapping[str, Callable[[], None]]) -> None:
        self._widget = widget
        self._handlers = handlers
        self._bound: dict[str, str] = {}

    def apply(self, settings: UserSettings) -> None:
        """Bind the new shortcuts and unbind the ones that went away."""
        target = sequences_for(settings)
        plan = plan_rebind(self._bound, target)
        for sequence in plan.unbind:
            self._safely(self._widget.unbind, sequence)
        for action, sequence in plan.bind.items():
            handler = self._handlers[action]
            self._safely(self._widget.bind, sequence, lambda _e, h=handler: (h(), "break")[1])
        self._bound = target

    @staticmethod
    def _safely(call: Callable[..., Any], *args: Any) -> None:
        try:
            call(*args)
        except tk.TclError:
            logger.warning("Could not change the key binding %r", args[0], exc_info=True)
