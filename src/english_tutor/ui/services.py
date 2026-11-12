"""What the Settings window needs from the rest of the application."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ..application.preferences import SettingsService
from ..application.ptt_gate import PttGate
from ..domain.models import MistakeRecord, SessionReport
from ..ports import AutoStart
from ..settings.model import UserSettings

Confirm = Callable[..., bool]
"""``confirm(title, message, parent=window) -> bool``; tests pass ``lambda *a, **k: True``."""

ENABLED_ACTIONS = frozenset({
    "open_data_folder", "open_logs_folder", "restore_defaults",
    "export_report", "export_mistakes", "clear_logs", "clear_mistakes", "autostart",
})  # fmt: skip
"""Action rows that exist so far; a later phase adds the connection test."""


def ask_yes_no(title: str, message: str, parent: Any = None) -> bool:
    """Ask a yes/no question with the native message box."""
    from tkinter import messagebox

    return bool(messagebox.askyesno(title, message, parent=parent))


def _ignore(*args: Any) -> None:
    """Default for optional callbacks."""


def _refuse() -> bool:
    """Default for data-clearing callbacks: nothing is wired, so nothing is deleted."""
    return False


@dataclass(frozen=True)
class UiPaths:
    """Folders the Settings actions refer to."""

    data_dir: Path
    logs_dir: Path

    @property
    def conversations_dir(self) -> Path:
        """Folder holding the ``session-*.log`` conversation files."""
        return self.data_dir / "conversations"


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
    ptt_gate: PttGate | None = None
    clear_logs: Callable[[], bool] = _refuse
    """Ask the session to delete the conversation logs; False when it is busy."""
    clear_mistakes: Callable[[], bool] = _refuse
    """Ask the session to delete the mistake history; False when it is busy."""
    is_free: Callable[[], bool] = lambda: True  # noqa: E731
    """Whether the session is idle and not practising (data may be deleted)."""
    last_report: Callable[[], SessionReport | None] = lambda: None  # noqa: E731
    mistakes: Callable[[], Sequence[MistakeRecord]] = lambda: ()  # noqa: E731
    clock: Callable[[], datetime] = datetime.now
    autostart: AutoStart | None = None
    """Windows auto-start registration; ``None`` where it does not exist (row disabled)."""
    env: Mapping[str, str] = field(default_factory=lambda: os.environ)
    """Environment consulted for the start-up warnings (relative TUTOR_PIPER_* paths)."""
