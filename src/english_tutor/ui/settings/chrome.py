"""Fixed parts of the Settings window: the sidebar and the footer."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import customtkinter as ctk

from ...i18n import t
from ...settings.registry import Category
from .. import theme
from .focus import enable_keyboard

SIDEBAR_WIDTH = 180


class Sidebar(ctk.CTkFrame):
    """Search box plus one button per category, with match counts while searching."""

    def __init__(
        self,
        master: Any,
        on_select: Callable[[Category], None],
        on_search: Callable[[str], None],
    ) -> None:
        super().__init__(master, width=SIDEBAR_WIDTH, corner_radius=0, fg_color=theme.SIDEBAR_BG)
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self._on_search = on_search
        self._entry = ctk.CTkEntry(self, placeholder_text=t("settings.search_placeholder"))
        self._entry.bind("<KeyRelease>", self._typed)
        self._entry.grid(row=0, column=0, sticky="ew", padx=theme.SPACE_S, pady=theme.SPACE_S)
        self._buttons: dict[Category, ctk.CTkButton] = {}
        for index, category in enumerate(Category, start=1):
            button = ctk.CTkButton(
                self, text=t(f"category.{category.value}"), anchor="w", corner_radius=6,
                fg_color="transparent", text_color=theme.TEXT, hover_color=theme.HOVER,
                command=lambda c=category: on_select(c),
            )  # fmt: skip
            button.grid(row=index, column=0, sticky="ew", padx=theme.SPACE_S, pady=1)
            enable_keyboard(button, button.invoke)
            self._buttons[category] = button

    def _typed(self, _event: Any = None) -> None:
        self._on_search(self._entry.get())

    def set_search_text(self, text: str) -> None:
        """Change the box without notifying ``on_search`` (inserting is not a key press)."""
        if self._entry.get() == text:  # also keeps the placeholder visible when empty
            return
        self._entry.delete(0, "end")
        if text:
            self._entry.insert(0, text)

    def focus_search(self) -> None:
        """Put the cursor in the search box."""
        self._entry.focus_set()

    def search_has_focus(self) -> bool:
        """Whether the search box has the keyboard focus."""
        return bool(self.focus_get() is getattr(self._entry, "_entry", None))

    def show_state(self, selected: Category | None, counts: Mapping[Category, int] | None) -> None:
        """Highlight ``selected`` and, while searching, show ``(n)`` match counts."""
        for category, button in self._buttons.items():
            name = t(f"category.{category.value}")
            label = name if counts is None else f"{name} ({counts.get(category, 0)})"
            dim = counts is not None and counts.get(category, 0) == 0
            button.configure(
                text=label,
                fg_color=theme.SELECTED if category is selected else "transparent",
                text_color=theme.MUTED_TEXT if dim else theme.TEXT,
            )

    @property
    def button_texts(self) -> dict[Category, str]:
        """Current button captions (for tests)."""
        return {c: str(b.cget("text")) for c, b in self._buttons.items()}


class Footer(ctk.CTkFrame):
    """Dirty indicator, status text and the Restore defaults / Cancel / Save buttons."""

    def __init__(
        self,
        master: Any,
        on_restore: Callable[[], None],
        on_cancel: Callable[[], None],
        on_save: Callable[[], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        pad = theme.SPACE_M
        self._dirty = ctk.CTkLabel(self, text="", anchor="w", text_color=theme.NOTICE_TEXT)
        self._dirty.grid(row=0, column=0, sticky="w", padx=pad)
        self._status = ctk.CTkLabel(
            self, text="", anchor="w", font=theme.FONT_HINT, wraplength=420, justify="left"
        )
        self._status.grid(row=1, column=0, sticky="w", padx=pad)
        restore = ctk.CTkButton(
            self, text=t("button.restore_defaults"), width=130, fg_color="transparent",
            border_width=1, text_color=theme.TEXT, hover_color=theme.HOVER, command=on_restore,
        )  # fmt: skip
        restore.grid(row=0, column=1, rowspan=2, padx=(0, theme.SPACE_S), pady=pad)
        cancel = ctk.CTkButton(
            self, text=t("button.cancel"), width=90, fg_color="transparent", border_width=1,
            text_color=theme.TEXT, hover_color=theme.HOVER, command=on_cancel,
        )  # fmt: skip
        cancel.grid(row=0, column=2, rowspan=2, padx=(0, theme.SPACE_S), pady=pad)
        self._save = ctk.CTkButton(self, text=t("button.save"), width=90, command=on_save)
        self._save.grid(row=0, column=3, rowspan=2, padx=(0, pad), pady=pad)
        for button in (restore, cancel, self._save):
            enable_keyboard(button, button.invoke)

    def set_dirty(self, count: int) -> None:
        """Show ``● Unsaved changes (n)`` (nothing when ``count`` is 0)."""
        self._dirty.configure(text=t("settings.dirty", count=count) if count else "")

    def set_save_enabled(self, enabled: bool) -> None:
        """Enable or disable Save."""
        self._save.configure(state="normal" if enabled else "disabled")

    @property
    def save_enabled(self) -> bool:
        """Whether Save is enabled."""
        return str(self._save.cget("state")) == "normal"

    def set_status(self, text: str, error: bool = False) -> None:
        """Show a one-line message under the dirty indicator."""
        colour = theme.ERROR_TEXT if error else theme.MUTED_TEXT
        self._status.configure(text=text, text_color=colour)
