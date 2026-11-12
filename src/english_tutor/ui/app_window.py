"""Main window: owns the widgets and renders session events on the Tk thread."""

from __future__ import annotations

import logging
import queue
from collections.abc import Sequence

import customtkinter as ctk

from ..application.events import (
    ErrorRaised,
    LevelChanged,
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
from . import theme
from .widgets import ChatView, ControlBar, LevelMeter, MicSelector, StatusBar

logger = logging.getLogger(__name__)

_PUMP_INTERVAL_MS = 30


class TutorWindow(ctk.CTk):
    """Container: wires widgets to the session. Only this thread touches Tk."""

    def __init__(
        self,
        cfg: AppConfig,
        session: ConversationSession,
        devices: Sequence[InputDevice],
        default_device: InputDevice | None,
    ) -> None:
        ctk.set_appearance_mode(theme.APPEARANCE_MODE)
        ctk.set_default_color_theme(theme.COLOR_THEME)
        super().__init__()
        self._session = session
        self._events: queue.Queue[SessionEvent] = queue.Queue()
        self._device_by_name = {d.name: d.index for d in devices}

        self.title("AI English Tutor - Virtual Assistant")
        self.geometry("600x800")
        ctk.CTkLabel(self, text="English Virtual Tutor", font=theme.FONT_TITLE).pack(pady=15)
        default_name = default_device.name if default_device else "None"
        MicSelector(
            self, [d.name for d in devices], default_name, self._on_mic_change
        ).pack()
        self._chat = ChatView(self, width=550, height=380)
        self._chat.pack(pady=10, padx=20, fill="both", expand=True)
        self._meter = LevelMeter(self)
        self._meter.pack()
        self._status = StatusBar(self)
        self._status.pack()
        self._controls = ControlBar(self, on_end_session=session.end_session)
        self._controls.pack()
        self._controls.set_enabled(False)
        ctk.CTkLabel(
            self,
            text=f"Hold '{cfg.ptt_label}' to speak, release to send",
            font=theme.FONT_HINT,
        ).pack(pady=10)

        if default_device is not None:
            session.set_input_device(default_device.index)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(_PUMP_INTERVAL_MS, self._pump)

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
            self._status.set(event.message or event.state.value.capitalize())
            self._controls.set_enabled(event.state is SessionState.IDLE)
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

    # ---------------------------------------------------------------- handlers
    def _on_mic_change(self, name: str) -> None:
        index = self._device_by_name.get(name)
        logger.info("Microphone changed to %s (index %s)", name, index)
        self._session.set_input_device(index)

    def _on_close(self) -> None:
        self._session.shutdown()
        self.destroy()
