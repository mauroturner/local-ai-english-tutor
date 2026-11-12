"""PttGate: presses are dropped while Settings is open, releases always get through."""

from __future__ import annotations

import pytest

from english_tutor.application.ptt_gate import PttGate


def make():
    log: list[str] = []
    return PttGate(lambda: log.append("press"), lambda: log.append("release")), log


def test_forwards_both_events_when_active():
    gate, log = make()
    gate.press()
    gate.release()
    assert log == ["press", "release"]
    assert gate.suspended is False


def test_press_is_dropped_while_suspended_but_release_is_forwarded():
    gate, log = make()
    gate.suspend()
    gate.press()
    gate.release()
    assert log == ["release"]
    assert gate.suspended is True


def test_resume_restores_presses():
    gate, log = make()
    gate.suspend()
    gate.resume()
    gate.press()
    assert log == ["press"]


def test_nested_suspend_needs_matching_resumes():
    gate, log = make()
    gate.suspend()
    gate.suspend()
    gate.resume()
    gate.press()
    assert log == [] and gate.suspended is True
    gate.resume()
    gate.press()
    assert log == ["press"] and gate.suspended is False


def test_extra_resume_never_goes_negative():
    gate, log = make()
    gate.resume()
    gate.resume()
    gate.suspend()
    gate.press()
    assert log == [] and gate.suspended is True


def test_paused_context_resumes_even_when_the_body_fails():
    gate, log = make()
    with pytest.raises(RuntimeError):
        with gate.paused():
            assert gate.suspended
            raise RuntimeError("boom")
    assert gate.suspended is False
    gate.press()
    assert log == ["press"]


def test_release_while_recording_survives_a_suspend_in_between():
    gate, log = make()
    gate.press()  # recording started before Settings opened
    gate.suspend()
    gate.release()
    assert log == ["press", "release"]
