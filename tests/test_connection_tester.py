"""ConnectionTester runs the check off the Tk thread and reports through callbacks."""

from __future__ import annotations

import threading
import time

from english_tutor.i18n import t
from english_tutor.ports import ConnectionResult
from english_tutor.ports import ConnectionStatus as S
from english_tutor.ui.settings.connection import ConnectionTester, describe


class Harness:
    def __init__(self, check):
        self.shown, self.scheduled = [], []
        self.tester = ConnectionTester(
            check, lambda ms, fn: self.scheduled.append((ms, fn)),
            lambda text, kind: self.shown.append((text, kind)),
        )  # fmt: skip

    def pump(self, timeout=2.0):
        """Run scheduled callbacks like Tk's event loop until nothing is left."""
        end = time.monotonic() + timeout
        while self.scheduled and time.monotonic() < end:
            _, fn = self.scheduled.pop(0)
            fn()
            time.sleep(0.005)


def test_describe_each_status():
    url, model = "http://x:1", "m:1"
    cases = {
        S.OK: ("ok", "connection.ok"),
        S.MODEL_MISSING: ("warning", "connection.model_missing"),
        S.UNREACHABLE: ("error", "connection.unreachable"),
        S.TIMEOUT: ("error", "connection.timeout"),
        S.BAD_URL: ("error", "connection.bad_url"),
    }
    for status, (kind, key) in cases.items():
        text, got = describe(ConnectionResult(status, "why"), url, model)
        assert got == kind
        assert text == t(key, url=url, model=model, detail="why")
    assert "ollama pull m:1" in describe(ConnectionResult(S.MODEL_MISSING), url, model)[0]


def test_the_result_arrives_later_and_the_check_runs_on_another_thread():
    release, ran_on = threading.Event(), []

    def check(url, model):
        ran_on.append(threading.current_thread())
        release.wait(2)
        return ConnectionResult(S.OK)

    h = Harness(check)
    h.tester.run("http://x", "m")
    assert h.shown == [(t("connection.testing"), "info")]  # shown at once, never blocking
    assert h.scheduled  # polling through `after`
    ms, poll = h.scheduled.pop(0)
    assert ms <= 200
    poll()
    assert len(h.shown) == 1  # still running
    release.set()
    h.pump()
    assert h.shown[-1][1] == "ok"
    assert ran_on[0] is not threading.main_thread()
    assert ran_on[0].daemon


def test_a_second_click_while_running_is_ignored():
    release, calls = threading.Event(), []

    def check(url, model):
        calls.append(url)
        release.wait(2)
        return ConnectionResult(S.OK)

    h = Harness(check)
    h.tester.run("http://a", "m")
    h.tester.run("http://b", "m")
    release.set()
    h.pump()
    assert calls == ["http://a"]
    assert h.tester.running is False
    h.tester.run("http://c", "m")  # free again
    h.pump()
    assert calls == ["http://a", "http://c"]


def test_a_crashing_check_becomes_an_error_result():
    def check(url, model):
        raise RuntimeError("boom")

    h = Harness(check)
    h.tester.run("http://x", "m")
    h.pump()
    assert h.shown[-1][1] == "error"


def test_last_result_is_kept_for_rebuilt_rows():
    h = Harness(lambda url, model: ConnectionResult(S.MODEL_MISSING))
    assert h.tester.last is None
    h.tester.run("http://x", "gone")
    h.pump()
    assert h.tester.last == h.shown[-1]
    assert h.tester.last[1] == "warning"
