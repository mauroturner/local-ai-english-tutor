"""Pure rules: which sound cue or desktop toast does a session event earn?"""

from __future__ import annotations

from ..application.events import ErrorRaised, ReportReady, SessionEvent, StateChanged
from ..audio.cues import Cue
from ..domain.models import SessionState
from ..settings.model import UserSettings

STOP_DELAY_MS = 350
"""The recorder keeps listening 0.3 s after release; play the stop cue after that."""

ERROR_THROTTLE_S = 2.0
"""At most one error cue in this window, however many errors arrive."""

_QUIET_FOR_ERRORS = frozenset({SessionState.LOADING, SessionState.SPEAKING})


def cue_for(
    event: SessionEvent,
    state: SessionState,
    settings: UserSettings,
    now: float,
    last_error_at: float | None,
) -> Cue | None:
    """The cue for ``event`` or None.

    ``state`` is the session state before ``event`` and ``now`` / ``last_error_at``
    are monotonic seconds (``last_error_at`` is None before the first error cue).
    """
    if isinstance(event, StateChanged):
        if event.state is SessionState.RECORDING and settings.cue_record_start:
            return Cue.START
        if event.state is SessionState.TRANSCRIBING and settings.cue_record_stop:
            return Cue.STOP
        return None
    if isinstance(event, ErrorRaised) and settings.cue_error:
        if state in _QUIET_FOR_ERRORS:
            return None
        if last_error_at is not None and now - last_error_at < ERROR_THROTTLE_S:
            return None
        return Cue.ERROR
    return None


def should_notify(event: SessionEvent, settings: UserSettings, focused: bool) -> bool:
    """Whether the end-of-session report earns a desktop toast (window not focused)."""
    return isinstance(event, ReportReady) and settings.notify_report and not focused
