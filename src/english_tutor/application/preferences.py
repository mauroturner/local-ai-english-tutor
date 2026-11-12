"""Loading and saving user settings (runs on the UI thread)."""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Mapping
from dataclasses import dataclass

from ..ports import AdapterError, AutoStart, SettingsStore, StorageError
from ..settings.model import (
    ENV_VARS,
    RESTART_FIELDS,
    UserSettings,
    locked_fields,
    parse_field,
    parse_settings,
    to_json_dict,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Loaded:
    """Result of ``SettingsService.load``.

    ``settings`` holds the values stored in settings.json (defaults for anything
    missing or invalid), not the environment overrides; ``locked`` names the
    fields a ``TUTOR_*`` variable currently pins. ``effective`` is what is in force:
    the file values with those variables applied.
    """

    settings: UserSettings
    warnings: tuple[str, ...]
    locked: frozenset[str]
    effective: UserSettings


@dataclass(frozen=True)
class SaveOutcome:
    """Result of ``SettingsService.save``."""

    restart_keys: tuple[str, ...]
    errors: tuple[str, ...]


class SettingsService:
    """Reads settings.json and writes changes back without leaking env values."""

    def __init__(
        self, store: SettingsStore, autostart: AutoStart | None, env: Mapping[str, str]
    ) -> None:
        self._store = store
        self._autostart = autostart
        self._env = env
        self._stored = UserSettings()

    def load(self) -> Loaded:
        """Read the stored settings; a corrupt file yields defaults plus a warning."""
        warnings: list[str] = []
        try:
            raw = self._store.load()
        except StorageError as exc:
            logger.warning("Settings unavailable: %s", exc)
            raw = {}
            warnings.append(str(exc))
        settings, invalid = parse_settings(raw)
        warnings.extend(invalid)
        for message in invalid:
            logger.warning(message)
        self._stored = settings
        effective = self._with_env(settings)
        return Loaded(settings, tuple(warnings), locked_fields(self._env), effective)

    def _with_env(self, settings: UserSettings) -> UserSettings:
        values = {}
        for field in locked_fields(self._env):
            try:
                values[field] = parse_field(field, self._env[ENV_VARS[field]])
            except ValueError as exc:
                logger.warning("Ignoring %s for display: %s", ENV_VARS[field], exc)
        return dataclasses.replace(settings, **values)

    def save(
        self, new: UserSettings, old: UserSettings, *, autostart: bool | None = None
    ) -> SaveOutcome:
        """Persist ``new``; fields pinned by environment variables keep their stored value.

        ``old`` is what the window started from; it only decides which restart
        notices apply. ``autostart`` is the desired OS auto-start state (kept in
        the registry, never in settings.json); ``None`` leaves it alone.
        """
        locked = locked_fields(self._env)
        keep = {name: getattr(self._stored, name) for name in locked}
        to_store = dataclasses.replace(new, **keep)
        try:
            self._store.save(to_json_dict(to_store))
        except StorageError as exc:
            return SaveOutcome((), (str(exc),))
        self._stored = to_store
        restart = tuple(
            f.name
            for f in dataclasses.fields(UserSettings)
            if f.name in RESTART_FIELDS
            and f.name not in locked
            and getattr(new, f.name) != getattr(old, f.name)
        )
        return SaveOutcome(restart, self._apply_autostart(autostart))

    def _apply_autostart(self, wanted: bool | None) -> tuple[str, ...]:
        if wanted is None or self._autostart is None:
            return ()
        try:
            if wanted and (not self._autostart.is_enabled() or self._autostart.is_stale()):
                self._autostart.enable()
            elif not wanted and self._autostart.is_enabled():
                self._autostart.disable()
        except (AdapterError, OSError) as exc:
            logger.warning("Auto-start change failed: %s", exc)
            return (str(exc),)
        return ()
