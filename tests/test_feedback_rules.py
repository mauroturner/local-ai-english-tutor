"""Pure rules that decide which cue (if any) and notification an event earns."""

from __future__ import annotations

import pytest

from english_tutor.application.events import (
    ErrorRaised,
    LevelChanged,
    ReportReady,
    StateChanged,
    TutorSaid,
)
from english_tutor.audio.cues import Cue
from english_tutor.domain.models import SessionReport, SessionState
from english_tutor.settings.model import UserSettings
from english_tutor.ui.feedback_rules import (
    ERROR_THROTTLE_S,
    STOP_DELAY_MS,
    cue_for,
    should_notify,
)

ALL_ON = UserSettings()
REPORT = ReportReady(SessionReport(1, (), (), None))


def cue(event, state=SessionState.IDLE, settings=ALL_ON, now=100.0, last_error_at=None):
    return cue_for(event, state, settings, now, last_error_at)


def test_defaults_enable_every_cue_and_the_toast():
    assert ALL_ON.cue_record_start and ALL_ON.cue_record_stop
    assert ALL_ON.cue_error and ALL_ON.notify_report


def test_start_cue_on_recording():
    assert cue(StateChanged(SessionState.RECORDING)) is Cue.START


def test_stop_cue_on_transcribing_and_the_window_delays_it():
    assert cue(StateChanged(SessionState.TRANSCRIBING), SessionState.RECORDING) is Cue.STOP
    assert STOP_DELAY_MS == 350  # the recorder keeps listening 0.3 s after release


@pytest.mark.parametrize(
    "state",
    [SessionState.IDLE, SessionState.THINKING, SessionState.SPEAKING, SessionState.REPORTING],
)
def test_other_state_changes_are_silent(state):
    assert cue(StateChanged(state)) is None


def test_unrelated_events_are_silent():
    assert cue(LevelChanged(0.5)) is None
    assert cue(TutorSaid("hello")) is None
    assert cue(REPORT) is None


def test_error_cue():
    assert cue(ErrorRaised("boom")) is Cue.ERROR


@pytest.mark.parametrize("state", [SessionState.LOADING, SessionState.SPEAKING])
def test_error_cue_is_suppressed_while_loading_or_speaking(state):
    assert cue(ErrorRaised("boom"), state) is None


@pytest.mark.parametrize(
    "state",
    [SessionState.IDLE, SessionState.RECORDING, SessionState.TRANSCRIBING, SessionState.THINKING],
)
def test_error_cue_plays_in_other_states(state):
    assert cue(ErrorRaised("boom"), state) is Cue.ERROR


def test_error_cue_is_throttled_to_once_per_two_seconds():
    assert ERROR_THROTTLE_S == 2.0
    assert cue(ErrorRaised("a"), now=101.0, last_error_at=100.0) is None
    assert cue(ErrorRaised("a"), now=101.99, last_error_at=100.0) is None
    assert cue(ErrorRaised("a"), now=102.0, last_error_at=100.0) is Cue.ERROR
    assert cue(ErrorRaised("a"), now=500.0, last_error_at=100.0) is Cue.ERROR


@pytest.mark.parametrize(
    ("field", "event"),
    [
        ("cue_record_start", StateChanged(SessionState.RECORDING)),
        ("cue_record_stop", StateChanged(SessionState.TRANSCRIBING)),
        ("cue_error", ErrorRaised("boom")),
    ],
)
def test_each_cue_respects_its_toggle(field, event):
    assert cue(event, settings=UserSettings(**{field: False})) is None


def test_a_toggle_only_silences_its_own_cue():
    settings = UserSettings(cue_record_start=False)
    assert cue(StateChanged(SessionState.TRANSCRIBING), settings=settings) is Cue.STOP
    assert cue(ErrorRaised("boom"), settings=settings) is Cue.ERROR


def test_toast_only_for_the_report_while_unfocused_and_enabled():
    assert should_notify(REPORT, ALL_ON, focused=False) is True
    assert should_notify(REPORT, ALL_ON, focused=True) is False
    assert should_notify(REPORT, UserSettings(notify_report=False), focused=False) is False
    assert should_notify(ErrorRaised("boom"), ALL_ON, focused=False) is False
    assert should_notify(StateChanged(SessionState.IDLE), ALL_ON, focused=False) is False
