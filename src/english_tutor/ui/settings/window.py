"""The Settings window: one modal, resizable dialog with Save and Cancel."""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from collections.abc import Callable
from typing import Any, ClassVar

import customtkinter as ctk

from ...i18n import t
from ...ports import StorageError
from ...settings.draft import SettingsDraft
from ...settings.model import ENV_VARS
from ...settings.registry import Category, Control, SettingSpec
from .. import theme
from ..layout import content_padding
from ..services import UiServices
from .chrome import SIDEBAR_WIDTH, Footer, Sidebar
from .commands import SettingsCommands
from .focus import PttHold, bind_keys, center_on, show_modal
from .key_capture import PTT, SHORTCUT, KeyCaptureDialog
from .live import PREVIEW_KEYS, apply_live
from .pages import build_page, match_counts, visible_result
from .rows import Row

logger = logging.getLogger(__name__)

DEFAULT_SIZE = (860, 600)
MIN_SIZE = (720, 480)
MAX_CONTENT = 640
_CATEGORIES = tuple(Category)


class SettingsWindow(SettingsCommands, ctk.CTkToplevel):
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
        self._ptt = PttHold(services.ptt_gate)
        self._ptt.acquire()  # typing here would otherwise start recordings
        try:
            self._init_window(master, services)
        except BaseException:
            self._ptt.release()
            self.destroy()
            raise

    def _init_window(self, master: Any, services: UiServices) -> None:
        self._master = master
        self._services = services
        self._capture_dialog: KeyCaptureDialog | None = None
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
        self.bind("<Destroy>", self._on_destroy, add="+")
        self.after(250, lambda: self._show_modal(first=True))

    def _on_destroy(self, event: Any) -> None:
        if event.widget is self:  # however the window goes away, push-to-talk comes back
            self._ptt.release()

    # ---------------------------------------------------------------- building
    def _build(self) -> None:
        self.title(t("settings.title"))
        self.minsize(*MIN_SIZE)
        center_on(self, self._master, DEFAULT_SIZE)
        self.transient(self._master)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.sidebar = Sidebar(self, self.select_category, self._apply_search)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="ns")
        ctk.CTkLabel(
            self, text=t("settings.ptt_paused"), font=theme.FONT_HINT, anchor="w",
            text_color=theme.MUTED_TEXT,
        ).grid(  # fmt: skip
            row=0, column=1, sticky="ew", padx=theme.SPACE_L, pady=(theme.SPACE_S, 0)
        )
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.grid(row=1, column=1, sticky="nsew")
        self._inner = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._inner.pack(fill="x", padx=theme.SPACE_L)
        self.footer = Footer(self, self.restore_defaults, self.cancel, self.save)
        self.footer.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.bind("<Configure>", self._on_configure, add="+")

    def _bind_keys(self) -> None:
        bind_keys(self, {
            "<Escape>": self._on_escape,
            "<Return>": self._on_enter,
            "<KP_Enter>": self._on_enter,
            "<Control-s>": self.save,
            "<Control-S>": self.save,
            "<Control-f>": self.sidebar.focus_search,
            "<Control-F>": self.sidebar.focus_search,
            "<Control-Prior>": lambda: self._step_category(-1),
            "<Control-Next>": lambda: self._step_category(1),
        })  # fmt: skip

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
        if not self._closed:
            show_modal(self, first)

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
            ENV_VARS[spec.key] if locked else None, self._capture,
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

    def _capture(self, key: str, apply: Callable[[str], None]) -> None:
        """Open the key-capture dialog for ``key``; the result goes to ``apply``."""
        if self._capture_dialog is not None:
            return
        mode = PTT if key == "ptt_key" else SHORTCUT

        def done(value: str | None) -> None:
            self._capture_dialog = None
            self._show_modal()  # take the keyboard grab back from the closed dialog
            if value is not None:
                apply(value)

        self._capture_dialog = KeyCaptureDialog(self, mode, done)

    @property
    def capture_dialog(self) -> KeyCaptureDialog | None:
        """The key-capture dialog while one is open."""
        return self._capture_dialog

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

    def _close(self) -> None:
        self._closed = True
        SettingsWindow._current = None
        try:
            if self._capture_dialog is not None:
                self._capture_dialog.cancel()
            try:
                self.grab_release()
            except tk.TclError:
                pass
            try:
                self._master.focus_force()
            except tk.TclError:
                pass
            self.destroy()
        finally:
            self._ptt.release()
