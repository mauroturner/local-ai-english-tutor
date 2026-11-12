"""The microphone is opened on the worker, never on the key-hook thread."""

from __future__ import annotations

from conftest import ManualRunner

from english_tutor.application.events import ErrorRaised, StateChanged
from english_tutor.domain.models import SessionState, TutorReply


def make(make_harness, texts=(), replies=()):
    runner = ManualRunner()
    return make_harness(texts, replies, runner=runner), runner


def idle_events(h) -> list[StateChanged]:
    return [e for e in h.of_type(StateChanged) if e.state is SessionState.IDLE]


def test_press_does_not_start_the_recorder_on_the_calling_thread(make_harness):
    h, runner = make(make_harness)
    h.session.on_ptt_press()
    assert h.session.state is SessionState.RECORDING
    assert h.recorder.calls == []
    runner.run_all()
    assert h.recorder.started_with == [None]
    assert h.session.state is SessionState.RECORDING


def test_start_then_stop_run_in_order_on_the_worker(make_harness):
    h, runner = make(make_harness, ["I like music"], [TutorReply("Nice!")])
    h.session.on_ptt_press()
    runner.run_all()  # the start job
    h.session.on_ptt_release()
    assert len(runner.jobs) == 1
    assert h.recorder.calls == ["start"]
    runner.run_all()  # the turn job stops the recorder after it started
    assert h.recorder.calls == ["start", "stop"]
    assert h.tutor.calls[0][1] == "I like music"
    assert h.session.state is SessionState.IDLE


def test_quick_tap_never_touches_the_device(make_harness):
    h, runner = make(make_harness)
    h.session.on_ptt_press()
    h.session.on_ptt_release()
    runner.run_all()
    assert h.recorder.calls == []
    assert h.session.state is SessionState.IDLE
    assert "Too short" in idle_events(h)[-1].message
    assert h.tutor.calls == []


def test_start_error_reports_and_returns_to_idle(make_harness):
    h, runner = make(make_harness)
    h.recorder.start_error = RuntimeError("no device")
    h.session.on_ptt_press()
    runner.run_all()
    errors = h.of_type(ErrorRaised)
    assert [e.message for e in errors][-1] == "Could not start recording: no device"
    assert h.session.state is SessionState.IDLE
    h.session.on_ptt_release()  # a late release is ignored
    assert runner.jobs == []
    assert h.recorder.stops == 0


def test_release_during_failing_start_ends_in_one_idle_and_no_tutor_call(make_harness):
    h, runner = make(make_harness, ["x"], [TutorReply("never")])
    h.recorder.start_error = RuntimeError("boom")
    h.recorder.on_start = h.session.on_ptt_release
    before = len(idle_events(h))
    h.session.on_ptt_press()
    runner.run_all()
    assert len(idle_events(h)) - before == 1
    assert h.session.state is SessionState.IDLE
    assert h.tutor.calls == []
    assert h.recorder.stops == 0
    # the next press works normally
    h.recorder.start_error = None
    h.recorder.on_start = None
    h.session.on_ptt_press()
    runner.run_all()
    assert h.session.state is SessionState.RECORDING
    assert h.recorder.started_with == [None]


def test_shutdown_before_the_start_job_never_opens_the_microphone(make_harness):
    h, runner = make(make_harness)
    h.session.on_ptt_press()
    h.session.shutdown()
    runner.run_all()
    assert h.recorder.calls == []
    assert runner.closed


def test_shutdown_stops_an_open_microphone(make_harness):
    h, runner = make(make_harness)
    h.session.on_ptt_press()
    runner.run_all()
    h.session.shutdown()
    assert h.recorder.calls == ["start", "stop"]


def test_shutdown_does_not_hang_when_the_device_hangs(make_harness):
    import threading
    import time

    h, runner = make(make_harness)
    entered, release = threading.Event(), threading.Event()

    def hang() -> None:
        entered.set()
        release.wait(5)

    h.recorder.on_start = hang
    h.session.on_ptt_press()
    worker = threading.Thread(target=runner.run_all, daemon=True)
    worker.start()
    assert entered.wait(2)
    started = time.monotonic()
    h.session.shutdown(timeout_s=0.2)
    elapsed = time.monotonic() - started
    release.set()
    worker.join(2)
    assert elapsed < 1.0
    assert runner.closed
