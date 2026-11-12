"""Main window: owns the widgets and renders session events on the Tk thread."""

from __future__ import annotations

import logging
import queue
from collections.abc import Callable, Sequence
from typing import Any

import customtkinter as ctk

from ..application.events import (
    ErrorRaised,
    LevelChanged,
    MistakesChanged,
    PracticeChanged,
    PracticeFeedback,
    ReportReady,
    SessionEvent,
    StateChanged,
    TutorSaid,
    UserSaid,
)
from ..application.session import ConversationSession
from ..audio.devices import InputDevice
from ..config import AppConfig
from ..domain.models import SessionState
from ..i18n import t
from ..settings.model import UserSettings
from . import theme
from .mistakes_view import MistakesView
from .widgets import (
    ChatView,
    ControlBar,
    LevelMeter,
    MicSelector,
    PracticeBanner,
    StatusBar,
    StatusChip,
)
from .tooltip import Tooltip

logger = logging.getLogger(__name__)

_PUMP_INTERVAL_MS = 30
DEFAULT_SIZE = (640, 820)
MIN_SIZE = (520, 600)


class TutorWindow(ctk.CTk):
    """Container: wires widgets to the session. Only this thread touches Tk."""

    def __init__(
        self,
        cfg: AppConfig,
        session: ConversationSession,
        devices: Sequence[InputDevice],
        default_device: InputDevice | None,
        settings: UserSettings | None = None,
        on_open_settings: Callable[[], None] | None = None,
    ) -> None:
        ctk.set_default_color_theme(theme.COLOR_THEME)
        super().__init__()
        self._session = session
        self._settings = settings or UserSettings()
        self._on_open_settings = on_open_settings or (lambda: None)
        self._sp = theme.spacing(self._settings.density)
        self._events: queue.Queue[SessionEvent] = queue.Queue()
        self._device_by_name = {d.name: d.index for d in devices}
        self._idle = False
        self._practicing = False

        self.title(t("app.title"))
        self.geometry(f"{DEFAULT_SIZE[0]}x{DEFAULT_SIZE[1]}")
        self.minsize(*MIN_SIZE)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        theme.set_chat_font_size(self._settings.chat_font_size)
        self._build_header(devices, default_device)
        self._build_tabs(cfg)
        self._banner = PracticeBanner(self, on_stop=session.stop_practice)
        self._banner.grid(row=2, column=0, sticky="ew", padx=self._sp.l, pady=(0, self._sp.s))
        self._banner.grid_remove()
        self._build_footer()
        ctk.CTkLabel(
            self,
            text=t("hint.hold", key=cfg.ptt_label),
            font=theme.FONT_HINT,
            text_color=theme.MUTED_TEXT,
        ).grid(row=4, column=0, pady=(0, self._sp.m))
        self._refresh_controls()

        if default_device is not None:
            session.set_input_device(default_device.index)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(_PUMP_INTERVAL_MS, self._pump)

    def _build_header(
        self, devices: Sequence[InputDevice], default_device: InputDevice | None
    ) -> None:
        sp = self._sp
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=sp.l, pady=(sp.l, sp.s))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text=t("app.heading"), font=theme.FONT_TITLE, anchor="w").grid(
            row=0, column=0, sticky="w"
        )
        self._settings_button = ctk.CTkButton(
            header, text="⚙", width=36, height=36, font=(theme.FAMILY, 18),
            fg_color="transparent", text_color=theme.TEXT, hover_color=theme.HOVER,
            command=self._on_open_settings,
        )  # fmt: skip
        self._settings_button.grid(row=0, column=1, sticky="e")
        shortcut = self._settings.shortcut_settings
        self._settings_tip = Tooltip(
            self._settings_button, t("tooltip.settings", shortcut=shortcut)
        )
        default_name = default_device.name if default_device else t("mic.none")
        MicSelector(header, [d.name for d in devices], default_name, self._on_mic_change).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(sp.s, 0)
        )

    def _build_tabs(self, cfg: AppConfig) -> None:
        sp = self._sp
        self._tabs = ctk.CTkTabview(self)
        self._tabs.grid(row=1, column=0, sticky="nsew", padx=sp.l, pady=sp.s)
        self._chat_tab_name = t("tab.chat")
        chat_tab = self._tabs.add(self._chat_tab_name)
        mistakes_tab = self._tabs.add(t("tab.mistakes"))
        self._chat = ChatView(chat_tab, empty_text=t("chat.empty", key=cfg.ptt_label))
        self._chat.pack(fill="both", expand=True)
        self._mistakes = MistakesView(mistakes_tab, on_practice=self._on_practice)
        self._mistakes.pack(fill="both", expand=True)

    def _build_footer(self) -> None:
        sp = self._sp
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=sp.l, pady=(0, sp.s))
        footer.grid_columnconfigure(0, weight=1)
        self._meter = LevelMeter(footer)
        self._meter.grid(row=0, column=0, sticky="ew", padx=(0, sp.m))
        self._chip = StatusChip(footer)
        self._chip.grid(row=0, column=1, padx=(0, sp.m))
        self._controls = ControlBar(footer, on_end_session=self._session.end_session)
        self._controls.grid(row=0, column=2)
        self._end_tip = Tooltip(
            self._controls.button,
            lambda: "" if self._controls.enabled else t("tooltip.end_session_disabled"),
        )
        self._status = StatusBar(footer)
        self._status.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(sp.xs, 0))

    # ----------------------------------------------------------- thread bridge
    def post(self, event: SessionEvent) -> None:
        """Queue an event from any thread; rendering happens in ``_pump``."""
        self._events.put(event)

    def _pump(self) -> None:
        try:
            while True:
                self._dispatch(self._events.get_nowait())
        except queue.Empty:
            pass
        self.after(_PUMP_INTERVAL_MS, self._pump)

    def _dispatch(self, event: SessionEvent) -> None:
        if isinstance(event, StateChanged):
            self._chip.set_state(event.state)
            self._status.set(event.message or event.state.value.capitalize())
            self._idle = event.state is SessionState.IDLE
            self._refresh_controls()
        elif isinstance(event, UserSaid):
            self._chat.add_user(event.text)
        elif isinstance(event, TutorSaid):
            self._chat.add_tutor(event.text)
            if event.correction is not None:
                self._chat.add_correction(event.correction)
        elif isinstance(event, ReportReady):
            self._chat.add_report(event.report)
        elif isinstance(event, ErrorRaised):
            self._chat.add_notice(event.message)
        elif isinstance(event, LevelChanged):
            self._meter.set(event.value)
        elif isinstance(event, MistakesChanged):
            self._mistakes.show(event.mistakes)
        elif isinstance(event, PracticeChanged):
            self._on_practice_changed(event)
        elif isinstance(event, PracticeFeedback):
            self._chat.add_practice_feedback(event.outcome, event.feedback)
            if event.prompt:
                self._chat.add_tutor(event.prompt)

    def _on_practice_changed(self, event: PracticeChanged) -> None:
        self._practicing = event.target is not None
        if event.target is not None:
            self._banner.show(event.target)
            self._tabs.set(self._chat_tab_name)
        else:
            self._banner.hide()
        self._refresh_controls()

    def _refresh_controls(self) -> None:
        """End session and Practice need an idle session outside a drill; Stop only idle."""
        free = self._idle and not self._practicing
        self._controls.set_enabled(free)
        self._mistakes.set_enabled(free)
        self._banner.set_enabled(self._idle)

    # ---------------------------------------------------------------- handlers
    def _on_mic_change(self, name: str) -> None:
        index = self._device_by_name.get(name)
        logger.info("Microphone changed to %s (index %s)", name, index)
        self._session.set_input_device(index)

    def _on_practice(self, key: str) -> None:
        self._tabs.set(self._chat_tab_name)
        self._session.start_practice(key)

    def report_callback_exception(
        self, exc: type[BaseException], val: BaseException, tb: Any
    ) -> None:
        """Log errors raised inside Tk callbacks instead of printing them to stderr."""
        logger.error("Unhandled error in a Tk callback", exc_info=(exc, val, tb))

    def _on_close(self) -> None:
        self._session.shutdown()
        self.destroy()
