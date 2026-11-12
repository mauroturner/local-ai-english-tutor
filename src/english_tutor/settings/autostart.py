"""State of the "Start with Windows" row (pure; the real state lives in the OS).

The Settings window reads the registry once when it opens, lets the user toggle the
wish, and hands ``to_save()`` to ``SettingsService.save``. Nothing here is written
to settings.json.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PureWindowsPath

from ..i18n import t
from ..ports import AdapterError, AutoStart

_PIPER_VARIABLES = ("TUTOR_PIPER_EXE", "TUTOR_PIPER_VOICE")


def relative_paths(data_dir: str, env: Mapping[str, str]) -> tuple[str, ...]:
    """Names of the path settings that are relative.

    At sign-in Windows starts the app from ``System32``, so a relative data folder or
    Piper path would resolve somewhere else. Empty values mean "use the default".
    """
    found: list[str] = []
    if data_dir.strip() and not PureWindowsPath(data_dir.strip()).is_absolute():
        found.append(t("autostart.name_data_dir"))
    for name in _PIPER_VARIABLES:
        value = env.get(name, "").strip()
        if value and not PureWindowsPath(value).is_absolute():
            found.append(name)
    return tuple(found)


@dataclass
class AutostartDraft:
    """What the registry says (``enabled``/``stale``) and what the user now wants."""

    available: bool = False
    enabled: bool = False
    stale: bool = False
    wanted: bool = False
    read_error: str | None = None
    error: str | None = None

    @classmethod
    def read(cls, port: AutoStart | None) -> AutostartDraft:
        """Snapshot the real state; ``None`` or an unreadable registry disable the row."""
        if port is None:
            return cls()
        try:
            enabled = port.is_enabled()
            stale = enabled and port.is_stale()
        except (AdapterError, OSError) as exc:
            return cls(available=True, read_error=str(exc))
        return cls(available=True, enabled=enabled, stale=stale, wanted=enabled)

    @property
    def usable(self) -> bool:
        """Whether the user can change it."""
        return self.available and self.read_error is None

    def unavailable_text(self) -> str | None:
        """Why the switch is disabled, or None when it can be used."""
        if not self.available:
            return t("autostart.unavailable")
        if self.read_error is not None:
            return t("autostart.read_failed", error=self.read_error)
        return None

    def set(self, wanted: bool) -> None:
        """Record the user's choice; a new choice clears the last failure."""
        if self.usable:
            self.wanted = wanted
            self.error = None

    def fail(self, message: str) -> None:
        """Remember that applying the change failed (shown under the row)."""
        self.error = t("autostart.change_failed", error=message)

    @property
    def dirty(self) -> bool:
        """Whether Save has something to do (a stale entry counts: Save rewrites it)."""
        return self.usable and (self.wanted != self.enabled or (self.stale and self.wanted))

    def to_save(self) -> bool | None:
        """The state to ask ``SettingsService.save`` for; ``None`` leaves it alone."""
        return self.wanted if self.dirty else None

    def notes(self, data_dir: str, env: Mapping[str, str]) -> tuple[str | None, str | None]:
        """``(error, warning)`` for the row.

        Warnings about the start-up environment appear only while an enabling (or
        rewriting) save is pending, i.e. before the entry is written.
        """
        lines: list[str] = []
        if self.stale:
            lines.append(t("autostart.stale"))
        if self.dirty and self.wanted:
            names = relative_paths(data_dir, env)
            if names:
                lines.append(t("autostart.warn_relative", names=", ".join(names)))
            lines.append(t("autostart.warn_startup"))
        return self.error, "\n".join(lines) or None
