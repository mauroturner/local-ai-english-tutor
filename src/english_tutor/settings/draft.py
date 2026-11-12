"""The settings being edited in the window, before Save (pure).

``SettingsDraft`` starts from the effective settings (file values with environment
overrides applied), validates every edit with the same rules as the settings file,
and tracks what changed. Fields pinned by a ``TUTOR_*`` variable are read-only and
never leave the draft with the variable's value.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from .model import ENV_VARS, RESTART_FIELDS, UserSettings, parse_field, validate_ollama_url
from .shortcuts import Conflict, find_conflicts, format_combo, parse_combo

_FIELD_NAMES = tuple(f.name for f in dataclasses.fields(UserSettings))
_SHORTCUT_KEYS = tuple(name for name in _FIELD_NAMES if name.startswith("shortcut_"))
_DEFAULTS = dataclasses.asdict(UserSettings())


def _conflict_message(conflict: Conflict) -> str:
    if conflict.kind == "invalid":
        return f"{conflict.combo!r} is not a valid shortcut."
    if conflict.kind == "duplicate":
        return f"{conflict.combo} is already used by another action."
    if conflict.kind == "no_modifier":
        return "Use Ctrl or Alt together with this key."
    return f"{conflict.combo} is reserved by Windows or common editing keys."


class SettingsDraft:
    """Editable copy of the settings with validation, dirty tracking and conflicts."""

    def __init__(
        self, stored: UserSettings, effective: UserSettings, locked: frozenset[str]
    ) -> None:
        self._stored = stored
        self._effective = dataclasses.asdict(effective)
        self._locked = frozenset(locked)
        self._values: dict[str, Any] = dict(self._effective)
        self._field_errors: dict[str, str] = {}

    # ------------------------------------------------------------------ access
    def value(self, key: str) -> Any:
        """The current (last valid) value of ``key``; KeyError for unknown names."""
        return self._values[key]

    def is_locked(self, key: str) -> bool:
        """Whether an environment variable pins ``key``."""
        return key in self._locked

    def set(self, key: str, raw: Any) -> str | None:
        """Edit ``key``; returns an error message, or None when the value was accepted.

        An invalid value leaves the last valid one in place and is listed in
        ``errors`` until a valid one replaces it. Locked fields refuse the edit.
        """
        if key not in self._values:
            raise KeyError(key)
        if key in self._locked:
            return f"Set by {ENV_VARS[key]}; unset the variable to change it here."
        try:
            value = self._parse(key, raw)
        except ValueError as exc:
            self._field_errors[key] = str(exc)
            return str(exc)
        self._field_errors.pop(key, None)
        self._values[key] = value
        return None

    @staticmethod
    def _parse(key: str, raw: Any) -> Any:
        if isinstance(raw, str) and not raw.strip() and _DEFAULTS[key] != "":
            raise ValueError("This value cannot be empty.")
        if key in _SHORTCUT_KEYS:
            return format_combo(parse_combo(str(raw)))
        return parse_field(key, raw)

    # ------------------------------------------------------------------ status
    @property
    def dirty_keys(self) -> tuple[str, ...]:
        """Settings changed since the window opened (including ones with an error)."""
        return tuple(
            k
            for k in _FIELD_NAMES
            if k in self._field_errors or self._values[k] != self._effective[k]
        )

    @property
    def restart_keys(self) -> tuple[str, ...]:
        """Valid, changed settings that only take effect after a restart."""
        return tuple(
            k
            for k in self.dirty_keys
            if k in RESTART_FIELDS and k not in self._field_errors and k not in self._locked
        )

    def conflicts(self) -> list[Conflict]:
        """Shortcut problems for the current values (see ``shortcuts.find_conflicts``)."""
        shortcuts = {k: self._values[k] for k in _SHORTCUT_KEYS}
        return find_conflicts(shortcuts, self._values["ptt_key"])

    @property
    def errors(self) -> dict[str, str]:
        """Per-key blocking problems: invalid values and blocking shortcut conflicts."""
        errors = dict(self._field_errors)
        for conflict in self.conflicts():
            if conflict.blocking:
                for action in conflict.actions:
                    errors.setdefault(action, _conflict_message(conflict))
        return errors

    @property
    def has_errors(self) -> bool:
        """Whether Save must stay disabled."""
        return bool(self.errors)

    @property
    def warnings(self) -> dict[str, str]:
        """Per-key notices that do not block saving."""
        warnings: dict[str, str] = {}
        _, url_warning = validate_ollama_url(str(self._values["ollama_url"]))
        if url_warning:
            warnings["ollama_url"] = url_warning
        overlaps = [c for c in self.conflicts() if c.kind == "ptt_overlap"]
        for conflict in overlaps:
            warnings[conflict.actions[0]] = (
                f"{conflict.combo} also starts a recording while the push-to-talk key "
                "is held, because that key is not blocked for other applications."
            )
        if overlaps:
            shown = ", ".join(c.combo for c in overlaps)
            warnings["ptt_key"] = f"This key overlaps with the shortcut(s): {shown}."
        return warnings

    # ----------------------------------------------------------------- actions
    def reset_to_defaults(self) -> None:
        """Put every unlocked setting back to its default (the user still has to Save)."""
        for key in _FIELD_NAMES:
            if key not in self._locked:
                self._values[key] = _DEFAULTS[key]
                self._field_errors.pop(key, None)

    def to_settings(self) -> UserSettings:
        """The edited settings; locked fields carry their stored (file) value."""
        values = dict(self._values)
        for key in self._locked:
            values[key] = getattr(self._stored, key)
        return UserSettings(**values)
