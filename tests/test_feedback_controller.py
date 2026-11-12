"""The feedback controller wires events to cues and toasts without a real window."""

from __future__ import annotations

import pytest

from english_tutor.application.events import ErrorRaised, ReportReady, StateChanged
from english_tutor.audio.cues import Cue
from english_tutor.domain.models import SessionReport, SessionState
from english_tutor.settings.model import UserSettings
from english_tutor.ui.feedback import Feedback
from english_tutor.ui.feedback_rules import STOP_DELAY_MS

REPORT = ReportReady(SessionReport(1, (), (), None))


class FakeMaster:
    def __init__(self, focused=True):
        self.focused = focused
        self.scheduled = []

    def after(self, ms, fn):
        self.scheduled.append((ms, fn))

    def focus_displayof(self):
        return object() if self.focused else None

    def fire(self):
        pending, self.scheduled = self.scheduled, []
        for _, fn in pending:
            fn()


class Player:
    def __init__(self, fail=False):
        self.cues = []
        self.closed = False
        self.fail = fail

    def play(self, cue):
        if self.fail:
            raise RuntimeError("bad player")
        self.cues.append(cue)

    def close(self):
        self.closed = True


class Notifier:
    def __init__(self):
        self.sent = []

    def notify(self, title, body):
        self.sent.append((title, body))


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def parts():
    master, player, notifier, clock = FakeMaster(), Player(), Notifier(), Clock()
    feedback = Feedback(master, player, notifier, clock=clock)
    feedback.handle(StateChanged(SessionState.IDLE), UserSettings())  # leave LOADING
    return feedback, master, player, notifier, clock


def test_start_plays_immediately_and_stop_is_delayed(parts):
    feedback, master, player, _, _ = parts
    settings = UserSettings()
    feedback.handle(StateChanged(SessionState.RECORDING), settings)
    assert player.cues == [Cue.START]
    feedback.handle(StateChanged(SessionState.TRANSCRIBING), settings)
    assert player.cues == [Cue.START]  # not yet: the recorder still has post-roll
    assert [ms for ms, _ in master.scheduled] == [STOP_DELAY_MS]
    master.fire()
    assert player.cues == [Cue.START, Cue.STOP]


def test_errors_are_throttled_and_follow_the_clock(parts):
    feedback, _, player, _, clock = parts
    settings = UserSettings()
    feedback.handle(ErrorRaised("a"), settings)
    clock.now += 1.0
    feedback.handle(ErrorRaised("b"), settings)
    clock.now += 1.5
    feedback.handle(ErrorRaised("c"), settings)
    assert player.cues == [Cue.ERROR, Cue.ERROR]


def test_errors_during_loading_are_silent():
    player = Player()
    feedback = Feedback(FakeMaster(), player, Notifier())
    feedback.handle(ErrorRaised("warning at startup"), UserSettings())
    assert player.cues == []
    feedback.handle(StateChanged(SessionState.LOADING), UserSettings())
    feedback.handle(ErrorRaised("still loading"), UserSettings())
    assert player.cues == []


def test_errors_while_speaking_are_silent(parts):
    feedback, _, player, _, _ = parts
    feedback.handle(StateChanged(SessionState.SPEAKING), UserSettings())
    feedback.handle(ErrorRaised("x"), UserSettings())
    assert player.cues == []


def test_settings_are_read_on_every_event(parts):
    feedback, _, player, _, _ = parts
    feedback.handle(StateChanged(SessionState.RECORDING), UserSettings(cue_record_start=False))
    feedback.handle(StateChanged(SessionState.IDLE), UserSettings())
    feedback.handle(StateChanged(SessionState.RECORDING), UserSettings())
    assert player.cues == [Cue.START]


def test_stop_toggle_off_schedules_nothing(parts):
    feedback, master, player, _, _ = parts
    feedback.handle(StateChanged(SessionState.TRANSCRIBING), UserSettings(cue_record_stop=False))
    assert master.scheduled == []
    assert player.cues == []


def test_toast_only_when_the_window_is_not_focused(parts):
    feedback, master, _, notifier, _ = parts
    master.focused = True
    feedback.handle(REPORT, UserSettings())
    assert notifier.sent == []
    master.focused = False
    feedback.handle(REPORT, UserSettings())
    assert len(notifier.sent) == 1
    title, body = notifier.sent[0]
    assert title and body
    feedback.handle(REPORT, UserSettings(notify_report=False))
    assert len(notifier.sent) == 1


def test_a_broken_player_never_propagates(parts):
    _, master, _, notifier, clock = parts
    feedback = Feedback(master, Player(fail=True), notifier, clock=clock)
    feedback.handle(StateChanged(SessionState.RECORDING), UserSettings())
    feedback.handle(StateChanged(SessionState.TRANSCRIBING), UserSettings())
    master.fire()


def test_a_broken_notifier_never_propagates(parts):
    _, master, player, _, clock = parts

    class Broken:
        def notify(self, title, body):
            raise RuntimeError("no powershell")

    master.focused = False
    Feedback(master, player, Broken(), clock=clock).handle(REPORT, UserSettings())


def test_without_collaborators_everything_is_a_no_op():
    feedback = Feedback(FakeMaster(focused=False))
    feedback.handle(StateChanged(SessionState.RECORDING), UserSettings())
    feedback.handle(StateChanged(SessionState.TRANSCRIBING), UserSettings())
    feedback.handle(REPORT, UserSettings())
    feedback.close()


def test_close_closes_the_player():
    player = Player()
    Feedback(FakeMaster(), player).close()
    assert player.closed
