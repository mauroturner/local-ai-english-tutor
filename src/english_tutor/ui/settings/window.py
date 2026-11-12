"""The Settings window: one modal, resizable dialog with Save and Cancel."""

from __future__ import annotations

import dataclasses
import logging
import tkinter as tk
from pathlib import Path
from typing import Any, ClassVar

import customtkinter as ctk

from ...ports import StorageError
from ...i18n import t
from ...settings.draft import SettingsDraft
from ...settings.model import ENV_VARS
from ...settings.registry import Category, Control, SettingSpec
from .. import theme
from ..layout import content_padding
from ..services import UiServices
from .chrome import SIDEBAR_WIDTH, Footer, Sidebar
from .live import LIVE_KEYS, PREVIEW_KEYS, apply_live
from .pages import build_page, match_counts, visible_result
from .rows import Row

logger = logging.getLogger(__name__)

DEFAULT_SIZE = (860, 600)
MIN_SIZE = (720, 480)
MAX_CONTENT = 640
_CATEGORIES = tuple(Category)


class SettingsWindow(ctk.CTkToplevel):
    """Edits a ``SettingsDraft`` and writes it through ``UiServices.settings`` on Save."""

    _current: ClassVar[SettingsWindow | None] = None

    @classmethod
    def open(cls, master: Any, services: UiServices) -> SettingsWindow:
        """Show the window, or focus the one that is already open."""
        current = cls._current
        try:
            if current is not None and current.winfo_exists():
                current.lift()
                current.focus_force()
                return current
        except tk.TclError:
            pass
        cls._current = cls(master, services)
        return cls._current

    def __init__(self, master: Any, services: UiServices) -> None:
        super().__init__(master)
        self._master = master
        self._services = services
        loaded = services.settings.load()
        self._effective = loaded.effective
        self._draft = SettingsDraft(loaded.settings, loaded.effective, loaded.locked)
        self._category = Category.GENERAL
        self._query = ""
        self._rows: dict[str, Row] = {}
        self._closed = False
        self._actions = {
            "open_data_folder": lambda: self._open(services.paths.data_dir),
            "open_logs_folder": lambda: self._open(services.paths.logs_dir),
            "restore_defaults": self.restore_defaults,
        }
        self._build()
        self._bind_keys()
        self._refresh_page()
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.after(250, lambda: self._show_modal(first=True))

    # ---------------------------------------------------------------- building
    def _build(self) -> None:
        self.title(t("settings.title"))
        self.minsize(*MIN_SIZE)
        width, height = DEFAULT_SIZE
        self._master.update_idletasks()
        x = max(0, self._master.winfo_rootx() + (self._master.winfo_width() - width) // 2)
        y = max(0, self._master.winfo_rooty() + (self._master.winfo_height() - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.transient(self._master)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.sidebar = Sidebar(self, self.select_category, self._apply_search)
        self.sidebar.grid(row=0, column=0, sticky="ns")
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.grid(row=0, column=1, sticky="nsew")
        self._inner = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._inner.pack(fill="x", padx=theme.SPACE_L)
        self.footer = Footer(self, self.restore_defaults, self.cancel, self.save)
        self.footer.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.bind("<Configure>", self._on_configure, add="+")

    def _bind_keys(self) -> None:
        bindings = {
            "<Escape>": self._on_escape,
            "<Return>": self._on_enter,
            "<KP_Enter>": self._on_enter,
            "<Control-s>": self.save,
            "<Control-S>": self.save,
            "<Control-f>": self.sidebar.focus_search,
            "<Control-F>": self.sidebar.focus_search,
            "<Control-Prior>": lambda: self._step_category(-1),
            "<Control-Next>": lambda: self._step_category(1),
        }
        for sequence, command in bindings.items():
            self.bind(sequence, lambda _e, c=command: (c(), "break")[1])

    def _on_configure(self, event: Any) -> None:
        if event.widget is not self:
            return
        try:
            scale = self._get_widget_scaling()
        except AttributeError:
            scale = 1.0
        content = int(event.width / scale) - SIDEBAR_WIDTH
        self._inner.pack_configure(padx=content_padding(content, MAX_CONTENT, theme.SPACE_L))

    def _show_modal(self, first: bool = False) -> None:
        """Raise the window, take the keyboard and block the main window (best effort)."""
        if self._closed:
            return
        try:
            if self.state() == "withdrawn":
                self.deiconify()
            self.lift()
            self.focus_force()
            if first:
                self.focus_set()  # keeps the search box unfocused so its placeholder shows
            if not self.winfo_viewable():
                self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            logger.debug("Could not show the Settings window modally", exc_info=True)

    # -------------------------------------------------------------------- page
    def _refresh_page(self) -> None:
        actions = self._services.enabled_actions
        result = visible_result(self._query, self._category, actions, t)
        searching = bool(self._query.strip())
        counts = match_counts(self._query, actions, t) if searching else None
        self.sidebar.show_state(None if searching else self._category, counts)
        for child in self._inner.winfo_children():
            child.destroy()
        self._rows = build_page(self._inner, result, self._query, self._make_row)
        canvas = getattr(self._scroll, "_parent_canvas", None)
        if canvas is not None:
            canvas.yview_moveto(0)
        self._refresh_status()

    def _make_row(self, parent: Any, spec: SettingSpec) -> Row:
        is_action = spec.control is Control.ACTION
        locked = not is_action and self._draft.is_locked(spec.key)
        value = None if is_action else self._draft.value(spec.key)
        return Row(
            parent, spec, value, self._on_change, self._actions.get(spec.key),
            ENV_VARS[spec.key] if locked else None,
        )  # fmt: skip

    def _refresh_status(self) -> None:
        errors, warnings = self._draft.errors, self._draft.warnings
        for key, row in self._rows.items():
            row.set_note(errors.get(key), warnings.get(key))
        count = len(self._draft.dirty_keys)
        self.footer.set_dirty(count)
        self.footer.set_save_enabled(count > 0 and not self._draft.has_errors)
        self.title(t("settings.title") + (" •" if count else ""))

    # ------------------------------------------------------------------ events
    def _on_change(self, key: str, value: Any) -> None:
        self._draft.set(key, value)
        if key in PREVIEW_KEYS:
            self._preview(key)
        self._refresh_status()

    def _preview(self, key: str | None = None) -> None:
        apply_live(PREVIEW_KEYS, self._draft.to_settings(), self._services.apply_log_level)
        if key in (None, "appearance_mode"):
            # customtkinter hides a toplevel while it recolours the title bar and can leave
            # it hidden when two such passes overlap, so bring the window back afterwards.
            for delay in (150, 600):
                self.after(delay, self._show_modal)

    def _apply_search(self, text: str) -> None:
        if text == self._query:
            return
        self._query = text
        self._refresh_page()

    def _step_category(self, step: int) -> None:
        index = (_CATEGORIES.index(self._category) + step) % len(_CATEGORIES)
        self.select_category(_CATEGORIES[index])

    def _on_escape(self) -> None:
        if self._query:
            self.set_search("")
        else:
            self.cancel()

    def _on_enter(self) -> None:
        if self.sidebar.search_has_focus():
            first = next(iter(self._rows.values()), None)
            if first is not None:
                first.focus_set()
        else:
            self.save()

    def _open(self, path: Path) -> None:
        try:
            self._services.open_folder(path)
        except StorageError as exc:
            self.footer.set_status(t("settings.action_failed", error=exc), error=True)

    # --------------------------------------------------------- public / tests
    def select_category(self, category: Category) -> None:
        """Show one category (this clears the search box)."""
        self._category = category
        self.sidebar.set_search_text("")
        self._query = ""
        self._refresh_page()

    def set_search(self, text: str) -> None:
        """Type ``text`` into the search box."""
        self.sidebar.set_search_text(text)
        self._apply_search(text)

    def set_value(self, key: str, value: Any) -> None:
        """Edit a setting as a control would, then redraw the page."""
        self._on_change(key, value)
        self._refresh_page()

    def visible_keys(self) -> list[str]:
        """Setting keys of the rows currently shown."""
        return list(self._rows)

    @property
    def draft(self) -> SettingsDraft:
        """The draft being edited."""
        return self._draft

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
        if self._draft.has_errors or not self._draft.dirty_keys:
            return False
        new = self._draft.to_settings()
        outcome = self._services.settings.save(new, self._effective)
        if outcome.errors:
            message = t("settings.save_failed", error="; ".join(outcome.errors))
            self.footer.set_status(message, error=True)
            return False
        draft = self._draft
        live = [k for k in draft.dirty_keys if k in LIVE_KEYS and not draft.is_locked(k)]
        shown = dataclasses.replace(new, **{k: self._draft.value(k) for k in live})
        apply_live(live, shown, self._services.apply_log_level)
        if outcome.restart_keys:
            self._services.on_restart_needed(outcome.restart_keys)
        self._services.on_applied(shown)
        self._close()
        return True

    def cancel(self) -> bool:
        """Close without saving (asks first if there are changes); reverts previews."""
        if self._draft.dirty_keys and not self._services.confirm(
            t("settings.confirm_discard_title"), t("settings.confirm_discard"), parent=self
        ):
            return False
        apply_live(PREVIEW_KEYS, self._effective, self._services.apply_log_level)
        self._close()
        return True

    def _close(self) -> None:
        self._closed = True
        SettingsWindow._current = None
        try:
            self.grab_release()
        except tk.TclError:
            pass
        try:
            self._master.focus_force()
        except tk.TclError:
            pass
        self.destroy()
