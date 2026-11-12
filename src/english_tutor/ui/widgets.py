"""Presentational widgets: they receive plain data and expose callbacks only."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import customtkinter as ctk

from ..domain.formatting import format_report
from ..domain.models import Correction, SessionReport
from . import theme


class ChatView(ctk.CTkScrollableFrame):
    """Scrollable conversation with user, tutor, correction and report cards."""

    def __init__(self, master: Any, **kwargs: Any) -> None:
        super().__init__(master, fg_color=theme.CHAT_BG, border_width=1, **kwargs)

    def _bubble(self, text: str, color: str, anchor: str, font: Any = None) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self, fg_color=color, corner_radius=10)
        frame.pack(fill="x", padx=10, pady=4, anchor=anchor)
        label = ctk.CTkLabel(
            frame,
            text=text,
            wraplength=theme.BUBBLE_WRAP,
            justify="left",
            text_color=theme.TEXT,
            font=font or theme.FONT_BODY,
        )
        label.pack(padx=10, pady=6, anchor="w")
        self._scroll_to_end()
        return frame

    def _scroll_to_end(self) -> None:
        canvas = getattr(self, "_parent_canvas", None)  # no public API for this
        if canvas is not None:
            self.after(20, lambda: canvas.yview_moveto(1.0))

    def add_user(self, text: str) -> None:
        """Show the learner's raw transcript."""
        self._bubble(f"You: {text}", theme.USER_BUBBLE, "e")

    def add_tutor(self, text: str) -> None:
        """Show the tutor's reply."""
        self._bubble(f"Alex: {text}", theme.TUTOR_BUBBLE, "w")

    def add_correction(self, correction: Correction) -> None:
        """Highlight the single live correction of a turn."""
        text = (
            f'Tip: "{correction.original}"  ->  "{correction.corrected}"\n'
            f"{correction.explanation}"
        )
        self._bubble(text, theme.CORRECTION_BUBBLE, "w")

    def add_notice(self, text: str) -> None:
        """Show a status or error message inside the conversation."""
        label = ctk.CTkLabel(
            self, text=text, text_color=theme.NOTICE_TEXT, wraplength=theme.BUBBLE_WRAP
        )
        label.pack(padx=10, pady=2)
        self._scroll_to_end()

    def add_report(self, report: SessionReport) -> None:
        """Show the end-of-session report."""
        self._bubble(format_report(report), theme.REPORT_BG, "w")

    def clear(self) -> None:
        """Remove everything from the conversation."""
        for child in self.winfo_children():
            child.destroy()


class MicSelector(ctk.CTkFrame):
    """Label plus drop-down listing the available microphones."""

    def __init__(
        self, master: Any, names: Sequence[str], default: str, on_change: Callable[[str], None]
    ) -> None:
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text="Select Microphone:").pack()
        self._var = ctk.StringVar(value=default)
        menu = ctk.CTkOptionMenu(
            self, values=list(names) or ["None"], variable=self._var, width=350, command=on_change
        )
        menu.pack(pady=5)


class LevelMeter(ctk.CTkFrame):
    """Microphone level bar."""

    def __init__(self, master: Any) -> None:
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text="Audio Level:").pack()
        self._bar = ctk.CTkProgressBar(self, width=400)
        self._bar.set(0)
        self._bar.pack(pady=5)

    def set(self, value: float) -> None:
        """Show a level between 0.0 and 1.0."""
        self._bar.set(max(0.0, min(value, 1.0)))


class StatusBar(ctk.CTkLabel):
    """One-line status text."""

    def __init__(self, master: Any) -> None:
        super().__init__(master, text="Status: Initializing...", text_color=theme.MUTED_TEXT)

    def set(self, text: str) -> None:
        """Replace the status text."""
        self.configure(text=f"Status: {text}")


class ControlBar(ctk.CTkFrame):
    """Row with the End session button."""

    def __init__(self, master: Any, on_end_session: Callable[[], None]) -> None:
        super().__init__(master, fg_color="transparent")
        self._button = ctk.CTkButton(self, text="End session", command=on_end_session)
        self._button.pack(pady=5)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the End session button."""
        self._button.configure(state="normal" if enabled else "disabled")
