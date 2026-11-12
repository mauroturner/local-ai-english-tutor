"""Banners shown in the main window."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import customtkinter as ctk

from ..i18n import t
from . import theme


class RestartBanner(ctk.CTkFrame):
    """Strip that says which saved settings need a restart, with Restart now / Later.

    The parent places it with ``grid`` and ``grid_remove``; ``show``/``hide`` toggle it.
    """

    def __init__(self, master: Any, on_restart: Callable[[], None]) -> None:
        super().__init__(master, fg_color=theme.PILL_BG, corner_radius=8)
        self._label = ctk.CTkLabel(
            self, text="", text_color=theme.PILL_TEXT, font=theme.FONT_BODY,
            wraplength=360, justify="left", anchor="w",
        )  # fmt: skip
        self._label.pack(side="left", padx=10, pady=6, fill="x", expand=True)
        later = ctk.CTkButton(
            self, text=t("banner.later"), width=80, fg_color="transparent",
            text_color=theme.PILL_TEXT, hover_color=theme.HOVER, command=self.hide,
        )  # fmt: skip
        later.pack(side="right", padx=(0, 8), pady=6)
        self._restart = ctk.CTkButton(
            self, text=t("banner.restart_now"), width=110, command=on_restart
        )
        self._restart.pack(side="right", padx=4, pady=6)

    @property
    def text(self) -> str:
        """The message currently shown."""
        return str(self._label.cget("text"))

    def show(self, names: Sequence[str]) -> None:
        """Display the banner naming the settings (already translated)."""
        self._label.configure(text=t("banner.restart", names=", ".join(names)))
        self.grid()

    def hide(self) -> None:
        """Remove the banner."""
        self.grid_remove()
