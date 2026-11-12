"""The Settings window's commands: restore defaults, Save and Cancel."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from typing import Any

from ...i18n import t
from ...settings.autostart import AutostartDraft
from ...settings.draft import SettingsDraft
from ...settings.model import UserSettings
from ..services import UiServices
from .actions import check_folders
from .chrome import Footer
from .live import LIVE_KEYS, PREVIEW_KEYS, apply_live


class SettingsCommands:
    """Mixin for ``SettingsWindow``; it relies on the window's attributes below."""

    _services: UiServices
    _draft: SettingsDraft
    _autostart: AutostartDraft
    _effective: UserSettings
    footer: Footer
    _folder_errors: dict[str, str]

    def _preview(self, key: str | None = None) -> None: ...
    def _refresh_page(self) -> None: ...
    def _refresh_status(self) -> None: ...
    def _close(self) -> None: ...

    @property
    def pending_changes(self) -> int:
        """Unsaved changes: edited settings plus a pending auto-start change."""
        return len(self._draft.dirty_keys) + int(self._autostart.dirty)

    def restore_defaults(self) -> None:
        """After confirmation, reset the draft (locked settings stay); the user must Save."""
        if not self._services.confirm(
            t("settings.confirm_restore_title"), t("settings.confirm_restore"), parent=self
        ):
            return
        self._draft.reset_to_defaults()
        self._preview()
        self._refresh_page()

    def save(self) -> bool:
        """Write the draft; closes the window on success."""
        if self._draft.has_errors or not self.pending_changes:
            return False
        self._folder_errors = check_folders(self._draft)  # creates and probes the folders
        if self._folder_errors:
            self._refresh_status()
            self.footer.set_status(
                t("settings.save_failed", error="; ".join(self._folder_errors.values())),
                error=True,
            )
            return False
        new = self._draft.to_settings()
        outcome = self._services.settings.save(
            new, self._effective, autostart=self._autostart.to_save()
        )
        if outcome.autostart_failed:
            # The settings file was written; only the start-up entry failed. Apply what
            # was saved and keep just the auto-start change pending, so Cancel cannot
            # pretend to discard settings that are already stored.
            self._apply_saved(new, outcome.restart_keys)
            self._rebase_on_saved()
            self._autostart.fail("; ".join(outcome.errors))
            self._refresh_page()  # shows the failure under the row
            message = self._autostart.error or "; ".join(outcome.errors)
            self.footer.set_status(message, error=True)
            return False
        if outcome.errors:
            message = t("settings.save_failed", error="; ".join(outcome.errors))
            self.footer.set_status(message, error=True)
            return False
        try:
            self._apply_saved(new, outcome.restart_keys)
        finally:
            self._close()
        return True

    def _apply_saved(self, new: UserSettings, restart_keys: Sequence[str]) -> None:
        """Apply live settings, announce restart-only ones and notify the main window."""
        draft = self._draft
        live = [k for k in draft.dirty_keys if k in LIVE_KEYS and not draft.is_locked(k)]
        shown = dataclasses.replace(new, **{k: draft.value(k) for k in live})
        apply_live(live, shown, self._services.apply_log_level)
        if restart_keys:
            self._services.on_restart_needed(restart_keys)
        self._services.on_applied(shown)

    def _rebase_on_saved(self) -> None:
        """Make the stored settings the new baseline (nothing left unsaved but auto-start)."""
        loaded = self._services.settings.load()
        self._effective = loaded.effective
        self._draft = SettingsDraft(loaded.settings, loaded.effective, loaded.locked)

    def cancel(self) -> bool:
        """Close without saving (asks first if there are changes); reverts previews."""
        if self.pending_changes and not self._services.confirm(
            t("settings.confirm_discard_title"), t("settings.confirm_discard"), parent=self
        ):
            return False
        try:
            apply_live(PREVIEW_KEYS, self._effective, self._services.apply_log_level)
        finally:
            self._close()
        return True
