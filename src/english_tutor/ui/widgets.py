"""Presentational widgets: they receive plain data and expose callbacks only."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import customtkinter as ctk

from ..domain.formatting import format_report
from ..domain.models import Correction, MistakeRecord, PracticeOutcome, SessionReport, SessionState
from ..i18n import t, translate_status
from . import theme
from .state_style import state_style


class ChatView(ctk.CTkScrollableFrame):
    """Scrollable conversation with user, tutor, correction and report cards.

    While no bubble has been shown it displays ``empty_text`` as a hint.
    """

    def __init__(self, master: Any, empty_text: str = "", **kwargs: Any) -> None:
        super().__init__(master, fg_color=theme.CHAT_BG, border_width=1, **kwargs)
        self._empty_text = empty_text
        self._empty: ctk.CTkLabel | None = None
        self._show_empty()

    @property
    def empty_visible(self) -> bool:
        """Whether the empty-state hint is currently shown."""
        return self._empty is not None

    def _show_empty(self) -> None:
        if self._empty_text and self._empty is None:
            self._empty = ctk.CTkLabel(
                self,
                text=self._empty_text,
                text_color=theme.MUTED_TEXT,
                font=theme.body_font(),
                wraplength=theme.BUBBLE_WRAP,
            )
            self._empty.pack(pady=(theme.SPACE_XL, 0))

    def _hide_empty(self) -> None:
        if self._empty is not None:
            self._empty.destroy()
            self._empty = None

    def _bubble(self, text: str, color: Any, anchor: str, font: Any = None) -> ctk.CTkFrame:
        self._hide_empty()
        frame = ctk.CTkFrame(self, fg_color=color, corner_radius=10)
        frame.pack(fill="x", padx=10, pady=4, anchor=anchor)
        label = ctk.CTkLabel(
            frame,
            text=text,
            wraplength=theme.BUBBLE_WRAP,
            justify="left",
            text_color=theme.TEXT,
            font=font or theme.body_font(),
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
        self._bubble(t("chat.you", text=text), theme.USER_BUBBLE, "e")

    def add_tutor(self, text: str) -> None:
        """Show the tutor's reply."""
        self._bubble(t("chat.alex", text=text), theme.TUTOR_BUBBLE, "w")

    def add_correction(self, correction: Correction) -> None:
        """Highlight the single live correction of a turn."""
        tip = t("chat.tip", original=correction.original, corrected=correction.corrected)
        text = f"{tip}\n{correction.explanation}"
        self._bubble(text, theme.CORRECTION_BUBBLE, "w")

    def add_natural(self, text: str) -> None:
        """Show a more natural way to say a correct sentence (never a mistake)."""
        self._bubble(t("chat.natural", text=text), theme.REPORT_BG, "w")

    def add_practice_feedback(self, outcome: PracticeOutcome, feedback: str) -> None:
        """Show the coach's verdict on a practice answer."""
        if not feedback:
            return
        label = {
            PracticeOutcome.CORRECT: t("practice.correct") + " ",
            PracticeOutcome.INCORRECT: t("practice.retry") + " ",
            PracticeOutcome.NOT_USED: "",
        }[outcome]
        color = theme.PRACTICE_OK if outcome is PracticeOutcome.CORRECT else theme.PRACTICE_RETRY
        self._bubble(f"{label}{feedback}", color, "w")

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
        """Remove everything from the conversation and show the hint again."""
        for child in self.winfo_children():
            child.destroy()
        self._empty = None
        self._show_empty()


class PracticeBanner(ctk.CTkFrame):
    """Strip shown while a practice drill is active, with a Stop button.

    The parent places it with ``grid`` and ``grid_remove``; ``show``/``hide``
    only toggle it.
    """

    def __init__(self, master: Any, on_stop: Callable[[], None]) -> None:
        super().__init__(master, fg_color=theme.PRACTICE_OK, corner_radius=8)
        self._label = ctk.CTkLabel(
            self, text="", text_color=theme.TEXT, font=theme.FONT_BODY,
            wraplength=360, justify="left",
        )  # fmt: skip
        self._label.pack(side="left", padx=10, pady=6)
        self._button = ctk.CTkButton(
            self, text=t("button.stop_practice"), width=110, command=on_stop
        )
        self._button.pack(side="right", padx=10, pady=6)

    def show(self, target: MistakeRecord) -> None:
        """Display the banner for ``target``."""
        self._label.configure(
            text=t("practice.banner", original=target.original, corrected=target.corrected)
        )
        self.grid()

    def hide(self) -> None:
        """Remove the banner."""
        self.grid_remove()

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the Stop button."""
        self._button.configure(state="normal" if enabled else "disabled")


class MicSelector(ctk.CTkFrame):
    """Label plus drop-down listing the available microphones."""

    def __init__(
        self, master: Any, names: Sequence[str], default: str, on_change: Callable[[str], None]
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text=t("mic.label"), text_color=theme.MUTED_TEXT).grid(
            row=0, column=0, padx=(0, theme.SPACE_S), sticky="w"
        )
        self._var = ctk.StringVar(value=default)
        menu = ctk.CTkOptionMenu(
            self, values=list(names) or [t("mic.none")], variable=self._var, command=on_change
        )
        menu.grid(row=0, column=1, sticky="ew")


class LevelMeter(ctk.CTkFrame):
    """Microphone level bar."""

    def __init__(self, master: Any) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text=t("level.label"), text_color=theme.MUTED_TEXT).grid(
            row=0, column=0, padx=(0, theme.SPACE_S)
        )
        self._bar = ctk.CTkProgressBar(self, width=60)
        self._bar.set(0)
        self._bar.grid(row=0, column=1, sticky="ew")

    def set(self, value: float) -> None:
        """Show a level between 0.0 and 1.0."""
        self._bar.set(max(0.0, min(value, 1.0)))


class StatusChip(ctk.CTkLabel):
    """Coloured pill with the session state: green idle, red recording, amber busy."""

    def __init__(self, master: Any) -> None:
        super().__init__(
            master, text="", text_color="white", corner_radius=10, width=110, font=theme.FONT_HINT
        )
        self.set_state(SessionState.LOADING)

    def set_state(self, state: SessionState) -> None:
        """Show ``state`` with its translated name and colour."""
        key, colour = state_style(state)
        self.configure(text=t(key), fg_color=colour)


class StatusBar(ctk.CTkLabel):
    """One-line status detail (for example the hold instruction or ``Listening...``)."""

    def __init__(self, master: Any) -> None:
        super().__init__(
            master, text=translate_status("Initializing..."), text_color=theme.MUTED_TEXT,
            anchor="w", font=theme.FONT_HINT,
        )  # fmt: skip

    def set(self, text: str) -> None:
        """Replace the status text (already translated; see ``state_style.status_line``)."""
        self.configure(text=text)


class ControlBar(ctk.CTkFrame):
    """Holds the End session button."""

    def __init__(self, master: Any, on_end_session: Callable[[], None]) -> None:
        super().__init__(master, fg_color="transparent")
        self._enabled = False
        self._button = ctk.CTkButton(self, text=t("button.end_session"), command=on_end_session)
        self._button.pack()

    @property
    def button(self) -> ctk.CTkButton:
        """The End session button (for tooltips)."""
        return self._button

    @property
    def enabled(self) -> bool:
        """Whether End session is currently available."""
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the End session button."""
        self._enabled = enabled
        self._button.configure(state="normal" if enabled else "disabled")
