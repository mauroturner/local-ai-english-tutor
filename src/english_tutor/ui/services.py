"""What the Settings window needs from the rest of the application."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..application.preferences import SettingsService
from ..settings.model import UserSettings

Confirm = Callable[..., bool]
"""``confirm(title, message, parent=window) -> bool``; tests pass ``lambda *a, **k: True``."""

ENABLED_ACTIONS = frozenset({"open_data_folder", "open_logs_folder", "restore_defaults"})
"""Action rows that exist so far; later phases add export, clear, test and auto-start."""


def ask_yes_no(title: str, message: str, parent: Any = None) -> bool:
    """Ask a yes/no question with the native message box."""
    from tkinter import messagebox

    return bool(messagebox.askyesno(title, message, parent=parent))


def _ignore(*args: Any) -> None:
    """Default for optional callbacks."""


@dataclass(frozen=True)
class UiPaths:
    """Folders the Settings actions refer to."""

    data_dir: Path
    logs_dir: Path


@dataclass
class UiServices:
    """Collaborators injected into the Settings window by the composition root."""

    settings: SettingsService
    paths: UiPaths
    open_folder: Callable[[Path], None]
    confirm: Confirm = ask_yes_no
    apply_log_level: Callable[[str], None] = _ignore
    on_applied: Callable[[UserSettings], None] = _ignore
    on_restart_needed: Callable[[Sequence[str]], None] = _ignore
    enabled_actions: frozenset[str] = ENABLED_ACTIONS
