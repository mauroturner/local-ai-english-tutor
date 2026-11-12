"""Sound cues and desktop toasts for the main window (Tk thread only)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from ..application.events import ReportReady, SessionEvent, StateChanged
from ..audio.cues import Cue
from ..domain.models import SessionState
from ..i18n import t
from ..ports import CuePlayer, Notifier
from ..settings.model import UserSettings
from .feedback_rules import STOP_DELAY_MS, cue_for, should_notify

logger = logging.getLogger(__name__)


class Feedback:
    """Turns session events into cues and toasts according to the current settings.

    ``master`` is the Tk window: it schedules the delayed stop cue (``after``) and
    tells whether the app has the keyboard focus (``focus_displayof``).
    """

    def __init__(
        self,
        master: Any,
        player: CuePlayer | None = None,
        notifier: Notifier | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._master = master
        self._player = player
        self._notifier = notifier
        self._clock = clock
        self._state = SessionState.LOADING  # startup warnings must not beep
        self._last_error_at: float | None = None

    def handle(self, event: SessionEvent, settings: UserSettings) -> None:
        """React to ``event``; ``settings`` are read now, so live changes apply at once."""
        try:
            self._react(event, settings)
        except Exception:
            logger.warning("Feedback for %s failed", type(event).__name__, exc_info=True)

    def close(self) -> None:
        """Release the audio output."""
        if self._player is not None:
            self._player.close()

    def _react(self, event: SessionEvent, settings: UserSettings) -> None:
        now = self._clock()
        cue = cue_for(event, self._state, settings, now, self._last_error_at)
        if isinstance(event, StateChanged):
            self._state = event.state
        if cue is Cue.ERROR:
            self._last_error_at = now
        if cue is Cue.STOP:
            self._master.after(STOP_DELAY_MS, lambda: self._play(cue))
        elif cue is not None:
            self._play(cue)
        if self._notifier is not None and isinstance(event, ReportReady):
            focused = self._master.focus_displayof() is not None
            if should_notify(event, settings, focused):
                self._notifier.notify(t("notify.report_title"), t("notify.report_body"))

    def _play(self, cue: Cue) -> None:
        try:
            if self._player is not None:
                self._player.play(cue)
        except Exception:
            logger.warning("Could not play the %s cue", cue.value, exc_info=True)
