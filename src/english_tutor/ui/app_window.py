"""Main window: owns the widgets and renders session events on the Tk thread."""

from __future__ import annotations

import logging
import queue
from collections.abc import Callable, Sequence
from datetime import date
from typing import Any

import customtkinter as ctk

from ..application.events import (
    DataCleared,
    ErrorRaised,
    LevelChanged,
    MistakesChanged,
    PracticeChanged,
    PracticeFeedback,
    ProgressChanged,
    ScenarioChanged,
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
from ..domain.review_schedule import next_due
from ..domain.scenarios import KEYS as SCENARIO_KEYS
from ..i18n import t
from ..ports import CuePlayer, Notifier
from ..settings.model import UserSettings
from . import theme
from .banners import RestartBanner
from .feedback import Feedback
from .goal import goal_text
from .mistakes_view import MistakesView
from .progress_view import ProgressView
from .widgets import (
    ChatView,
    ControlBar,
    LevelMeter,
    MicSelector,
    PracticeBanner,
    ScenarioPicker,
    StatusBar,
    StatusChip,
)
from .services import Confirm, ask_yes_no
from .shortcut_binder import ShortcutBinder
from .snapshot import SessionSnapshot, cleared_message
from .state_style import status_line
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
        confirm: Confirm = ask_yes_no,
        on_data_cleared: Callable[[str], None] | None = None,
        cue_player: CuePlayer | None = None,
        notifier: Notifier | None = None,
    ) -> None:
        ctk.set_default_color_theme(theme.COLOR_THEME)
        super().__init__()
        self._session = session
        self._ptt_label = cfg.ptt_label
        self._settings = settings or UserSettings()
        self._has_settings = on_open_settings is not None
        self._on_open_settings = on_open_settings or (lambda: None)
        self._confirm = confirm
        self._on_data_cleared = on_data_cleared or (lambda text: None)
        self.snapshot = SessionSnapshot()
        self._feedback = Feedback(self, cue_player, notifier)
        self.restart_requested = False
        self._sp = theme.spacing(self._settings.density)
        self._events: queue.Queue[SessionEvent] = queue.Queue()
        self._device_by_name = {d.name: d.index for d in devices}
        self._idle = False
        self._practicing = False
        self._last_practiced: str | None = None  # so "review due" moves on to another item

        self.title(t("app.title"))
        self.geometry(f"{DEFAULT_SIZE[0]}x{DEFAULT_SIZE[1]}")
        self.minsize(*MIN_SIZE)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        theme.set_chat_font_size(self._settings.chat_font_size)
        self._restart_banner = RestartBanner(self, on_restart=self._restart_now)
        self._restart_banner.grid(
            row=0, column=0, sticky="ew", padx=self._sp.l, pady=(self._sp.s, 0)
        )
        self._restart_banner.grid_remove()
        self._build_header(devices, default_device)
        self._build_tabs(cfg)
        self._banner = PracticeBanner(self, on_stop=session.stop_practice)
        self._banner.grid(row=3, column=0, sticky="ew", padx=self._sp.l, pady=(0, self._sp.s))
        self._banner.grid_remove()
        self._build_footer()
        self._refresh_controls()

        if default_device is not None:
            session.set_input_device(default_device.index)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._binder = ShortcutBinder(self, {
            "end_session": self._shortcut_end_session,
            "settings": self._shortcut_settings,
            "chat_tab": lambda: self._tabs.set(self._chat_tab_name),
            "mistakes_tab": lambda: self._tabs.set(self._mistakes_tab_name),
            "repeat": self._session.repeat_last,
            "repeat_slow": lambda: self._session.repeat_last(slower=True),
        })  # fmt: skip
        self._binder.apply(self._settings)
        self.after(_PUMP_INTERVAL_MS, self._pump)

    def _build_header(
        self, devices: Sequence[InputDevice], default_device: InputDevice | None
    ) -> None:
        sp = self._sp
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=1, column=0, sticky="ew", padx=sp.l, pady=(sp.m, sp.s))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text=t("app.heading"), font=theme.FONT_TITLE, anchor="w").grid(
            row=0, column=0, sticky="w"
        )
        self._settings_button = ctk.CTkButton(
            header, text="⚙", width=36, height=36, font=(theme.FAMILY, 18),
            fg_color="transparent", text_color=theme.TEXT, hover_color=theme.HOVER,
            command=self._on_open_settings,
        )  # fmt: skip
        if self._has_settings:  # never show a button that does nothing
            self._settings_button.grid(row=0, column=1, sticky="e")
        self._settings_tip = Tooltip(
            self._settings_button,
            lambda: t("tooltip.settings", shortcut=self._settings.shortcut_settings),
        )
        self._goal_label = ctk.CTkLabel(
            header, text="", text_color=theme.MUTED_TEXT, font=theme.FONT_BODY, anchor="w"
        )
        self._goal_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(sp.xs, 0))
        default_name = default_device.name if default_device else t("mic.none")
        MicSelector(header, [d.name for d in devices], default_name, self._on_mic_change).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(sp.s, 0)
        )
        self._scenario = ScenarioPicker(header, SCENARIO_KEYS, self._session.set_scenario)
        self._scenario.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(sp.s, 0))

    def _build_tabs(self, cfg: AppConfig) -> None:
        sp = self._sp
        self._tabs = ctk.CTkTabview(self)
        self._tabs.grid(row=2, column=0, sticky="nsew", padx=sp.l, pady=sp.s)
        self._chat_tab_name = t("tab.chat")
        chat_tab = self._tabs.add(self._chat_tab_name)
        self._mistakes_tab_name = t("tab.mistakes")
        mistakes_tab = self._tabs.add(self._mistakes_tab_name)
        self._chat = ChatView(chat_tab, empty_text=t("chat.empty", key=cfg.ptt_label))
        self._chat.pack(fill="both", expand=True)
        self._mistakes = MistakesView(
            mistakes_tab, on_practice=self._on_practice, on_review_due=self._on_review_due
        )
        self._mistakes.pack(fill="both", expand=True)
        progress_tab = self._tabs.add(t("tab.progress"))
        self._progress = ProgressView(progress_tab)
        self._progress.pack(fill="both", expand=True)

    def _build_footer(self) -> None:
        sp = self._sp
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew", padx=sp.l, pady=(0, sp.m))
        footer.grid_columnconfigure(0, weight=1)
        self._meter = LevelMeter(footer)
        self._meter.grid(row=0, column=0, sticky="ew", padx=(0, sp.m))
        self._chip = StatusChip(footer)
        self._chip.grid(row=0, column=1, padx=(0, sp.m))
        self._controls = ControlBar(
            footer,
            on_end_session=self._session.end_session,
            on_repeat=self._session.repeat_last,
            on_repeat_slow=lambda: self._session.repeat_last(slower=True),
        )
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
        self.snapshot.observe(event)
        self._feedback.handle(event, self._settings)
        if isinstance(event, StateChanged):
            self._chip.set_state(event.state)
            self._status.set(status_line(event.state, event.message, self._ptt_label))
            self._idle = event.state is SessionState.IDLE
            self._refresh_controls()
        elif isinstance(event, UserSaid):
            self._chat.add_user(event.text)
        elif isinstance(event, TutorSaid):
            self._chat.add_tutor(event.text)
            if event.correction is not None:
                self._chat.add_correction(event.correction)
            if event.natural is not None:
                self._chat.add_natural(event.natural)
        elif isinstance(event, ProgressChanged):
            self._progress.show(event.sessions)
            self._refresh_goal()
        elif isinstance(event, ScenarioChanged):
            self._scenario.show(event.key)
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
        elif isinstance(event, DataCleared):
            message = cleared_message(event)
            self._chat.add_notice(message)
            self._on_data_cleared(message)

    def _on_practice_changed(self, event: PracticeChanged) -> None:
        self._practicing = event.target is not None
        if event.target is not None:
            self._banner.show(event.target)
            self._tabs.set(self._chat_tab_name)
        else:
            self._banner.hide()
        self._refresh_controls()

    @property
    def is_free(self) -> bool:
        """Whether the session is idle and not in a practice drill."""
        return self._idle and not self._practicing

    def _refresh_controls(self) -> None:
        """End session and Practice need an idle session outside a drill; Stop only idle."""
        free = self.is_free
        self._controls.set_enabled(free)
        self._controls.set_replay_enabled(self._idle)
        self._scenario.set_enabled(free and not self._session.turns)
        self._mistakes.set_enabled(free)
        self._banner.set_enabled(self._idle)

    # ---------------------------------------------------------------- handlers
    def _on_mic_change(self, name: str) -> None:
        index = self._device_by_name.get(name)
        logger.info("Microphone changed to %s (index %s)", name, index)
        self._session.set_input_device(index)

    def _on_practice(self, key: str) -> None:
        self._last_practiced = key
        self._tabs.set(self._chat_tab_name)
        self._session.start_practice(key)

    def _on_review_due(self) -> None:
        """Practise the next mistake due today, after the one practised last."""
        target = next_due(self.snapshot.mistakes, date.today(), self._last_practiced)
        if target is not None:
            self._on_practice(target.key)

    # ------------------------------------------------- settings, restart, shortcuts
    def apply_settings(self, settings: UserSettings) -> None:
        """Take over saved settings that the main window itself uses (shortcuts, goal)."""
        self._settings = settings
        self._binder.apply(settings)
        self._refresh_goal()

    def _refresh_goal(self) -> None:
        text = goal_text(self.snapshot.sessions, self._settings.daily_goal_minutes, date.today())
        self._goal_label.configure(text=text)

    def _shortcut_end_session(self) -> None:
        if self._controls.enabled:  # same rule as the button
            self._session.end_session()

    def _shortcut_settings(self) -> None:
        if self._has_settings:
            self._on_open_settings()

    def show_restart_banner(self, keys: Sequence[str]) -> None:
        """Tell the learner which saved settings need a restart."""
        self._restart_banner.show([t(f"setting.{key}.label") for key in keys])

    def _restart_now(self) -> None:
        asked = t("restart.confirm_title"), t("restart.confirm_message")
        if self._session.turns and not self._confirm(*asked, parent=self):
            return
        self.restart_requested = True
        self._on_close()

    def report_callback_exception(
        self, exc: type[BaseException], val: BaseException, tb: Any
    ) -> None:
        """Log errors raised inside Tk callbacks instead of printing them to stderr."""
        logger.error("Unhandled error in a Tk callback", exc_info=(exc, val, tb))

    def _on_close(self) -> None:
        self._session.shutdown()
        self.destroy()
