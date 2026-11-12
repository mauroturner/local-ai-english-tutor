"""Presentational widgets: they receive plain data and expose callbacks only."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import customtkinter as ctk

from ..domain.formatting import format_report
from ..domain.models import Correction, MistakeRecord, PracticeOutcome, SessionReport
from ..i18n import t, translate_status
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
        self._bubble(t("chat.you", text=text), theme.USER_BUBBLE, "e")

    def add_tutor(self, text: str) -> None:
        """Show the tutor's reply."""
        self._bubble(t("chat.alex", text=text), theme.TUTOR_BUBBLE, "w")

    def add_correction(self, correction: Correction) -> None:
        """Highlight the single live correction of a turn."""
        tip = t("chat.tip", original=correction.original, corrected=correction.corrected)
        text = f"{tip}\n{correction.explanation}"
        self._bubble(text, theme.CORRECTION_BUBBLE, "w")

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
        """Remove everything from the conversation."""
        for child in self.winfo_children():
            child.destroy()


class PracticeBanner(ctk.CTkFrame):
    """Strip shown while a practice drill is active, with a Stop button."""

    def __init__(self, master: Any, on_stop: Callable[[], None]) -> None:
        super().__init__(master, fg_color=theme.PRACTICE_OK, corner_radius=8)
        self._label = ctk.CTkLabel(
            self, text="", text_color=theme.TEXT, font=theme.FONT_BODY,
            wraplength=360, justify="left",
        )
        self._label.pack(side="left", padx=10, pady=6)
        self._button = ctk.CTkButton(self, text=t("button.stop_practice"), width=110, command=on_stop)
        self._button.pack(side="right", padx=10, pady=6)

    def show(self, target: MistakeRecord, before: Any) -> None:
        """Display the banner for ``target`` just above the ``before`` widget."""
        self._label.configure(
            text=t("practice.banner", original=target.original, corrected=target.corrected)
        )
        self.pack(before=before, fill="x", padx=20, pady=(0, 6))

    def hide(self) -> None:
        """Remove the banner."""
        self.pack_forget()

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the Stop button."""
        self._button.configure(state="normal" if enabled else "disabled")


class MicSelector(ctk.CTkFrame):
    """Label plus drop-down listing the available microphones."""

    def __init__(
        self, master: Any, names: Sequence[str], default: str, on_change: Callable[[str], None]
    ) -> None:
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text=t("mic.label")).pack()
        self._var = ctk.StringVar(value=default)
        menu = ctk.CTkOptionMenu(
            self, values=list(names) or [t("mic.none")], variable=self._var, width=350, command=on_change
        )
        menu.pack(pady=5)


class LevelMeter(ctk.CTkFrame):
    """Microphone level bar."""

    def __init__(self, master: Any) -> None:
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text=t("level.label")).pack()
        self._bar = ctk.CTkProgressBar(self, width=400)
        self._bar.set(0)
        self._bar.pack(pady=5)

    def set(self, value: float) -> None:
        """Show a level between 0.0 and 1.0."""
        self._bar.set(max(0.0, min(value, 1.0)))


class StatusBar(ctk.CTkLabel):
    """One-line status text."""

    def __init__(self, master: Any) -> None:
        initial = t("status.prefix", text=translate_status("Initializing..."))
        super().__init__(master, text=initial, text_color=theme.MUTED_TEXT)

    def set(self, text: str) -> None:
        """Replace the status text (known session messages are translated)."""
        self.configure(text=t("status.prefix", text=translate_status(text)))


class ControlBar(ctk.CTkFrame):
    """Row with the End session button."""

    def __init__(self, master: Any, on_end_session: Callable[[], None]) -> None:
        super().__init__(master, fg_color="transparent")
        self._button = ctk.CTkButton(self, text=t("button.end_session"), command=on_end_session)
        self._button.pack(pady=5)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the End session button."""
        self._button.configure(state="normal" if enabled else "disabled")
