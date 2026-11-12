"""Desktop toast: script building is injection-safe and the runner call has the right shape."""

from __future__ import annotations

import base64
import re
import subprocess
import threading

import pytest

from english_tutor.adapters.windows_notifier import (
    NullNotifier,
    WindowsNotifier,
    build_toast_script,
)


def decode(encoded: str) -> str:
    return base64.b64decode(encoded).decode("utf-16-le")


def literal_strings(script: str) -> list[str]:
    """PowerShell single-quoted literals ('' is an escaped quote)."""
    return re.findall(r"'((?:[^']|'')*)'", script)


def test_script_contains_title_and_body():
    script = build_toast_script("Report ready", "Open the app")
    assert "Report ready" in script
    assert "Open the app" in script
    assert "ToastNotificationManager" in script


def test_markup_characters_are_xml_escaped():
    script = build_toast_script("<b>Tom & Jerry</b>", 'say "hi" <script>')
    assert "<b>" not in script
    assert "<script>" not in script
    assert "&lt;b&gt;Tom &amp; Jerry&lt;/b&gt;" in script
    assert "&quot;hi&quot;" in script


def test_quotes_cannot_break_out_of_the_powershell_string():
    nasty = "x'; Remove-Item -Recurse C:\\ ; '"
    script = build_toast_script(nasty, nasty)
    inert = [s for s in literal_strings(script) if "Remove-Item" in s]
    assert inert  # the text survives only inside a string literal, never as a command
    for literal in inert:
        assert "'" not in literal.replace("''", "")
    assert "x'; Remove-Item" not in script


def test_curly_quotes_are_neutralised_too():
    # PowerShell treats typographic single quotes as quote characters.
    script = build_toast_script("it\u2019s \u2018x\u2019 \u201a \u201b", "\u201cq\u201d")
    for char in "\u2018\u2019\u201a\u201b":
        assert char not in script


def test_here_string_terminator_cannot_break_out():
    script = build_toast_script("'@\nWrite-Host pwned", "\n'@\nWrite-Host pwned")
    assert "\n'@" not in script
    payload = "".join(literal_strings(script))
    assert "'@" not in payload and "\n" not in payload


def test_control_characters_are_dropped_and_newlines_flattened():
    script = build_toast_script("a\x00b\x1bc", "line1\r\nline2")
    assert "\x00" not in script and "\x1b" not in script
    assert "line1 line2" in script


class Recorder:
    def __init__(self, result=None, error=None):
        self.calls = []
        self.result = result or subprocess.CompletedProcess([], 0)
        self.error = error

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if self.error:
            raise self.error
        return self.result


def make(runner, flashes, hwnd=lambda: 42, platform="win32"):
    return WindowsNotifier(
        runner=runner,
        flasher=flashes.append,
        hwnd=hwnd,
        spawn=lambda fn: fn(),  # run the "thread" inline
        platform=platform,
    )


def test_notify_runs_powershell_with_an_encoded_command():
    runner, flashes = Recorder(), []
    make(runner, flashes).notify("Title", "Body \u00f1")
    ((args, kwargs),) = runner.calls
    assert args[:4] == ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand"]
    assert decode(args[4]) == build_toast_script("Title", "Body \u00f1")
    assert kwargs["timeout"] == 10
    assert kwargs["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    assert kwargs["capture_output"] is True
    assert kwargs.get("shell", False) is False
    assert flashes == []


@pytest.mark.parametrize(
    "runner",
    [
        Recorder(result=subprocess.CompletedProcess([], 1, b"", b"boom")),
        Recorder(error=subprocess.TimeoutExpired("powershell.exe", 10)),
        Recorder(error=FileNotFoundError("powershell.exe")),
    ],
)
def test_failures_fall_back_to_flashing_the_window_and_never_raise(runner):
    flashes = []
    make(runner, flashes).notify("Title", "Body")
    assert flashes == [42]


def test_a_failing_flash_is_swallowed():
    def broken(hwnd):
        raise OSError("no window")

    notifier = WindowsNotifier(
        runner=Recorder(error=OSError("x")), flasher=broken, hwnd=lambda: 1,
        spawn=lambda fn: fn(), platform="win32",
    )  # fmt: skip
    notifier.notify("T", "B")  # must not raise


def test_a_failing_hwnd_lookup_is_swallowed():
    def broken():
        raise RuntimeError("tk is gone")

    flashes = []
    make(Recorder(error=OSError("x")), flashes, hwnd=broken).notify("T", "B")
    assert flashes == []


def test_other_platforms_do_nothing():
    runner, flashes = Recorder(), []
    make(runner, flashes, platform="linux").notify("T", "B")
    assert runner.calls == [] and flashes == []


def test_notify_returns_without_waiting_for_the_runner():
    started, release, done = threading.Event(), threading.Event(), threading.Event()

    def slow(args, **kwargs):
        started.set()
        release.wait(5)
        done.set()
        return subprocess.CompletedProcess([], 0)

    notifier = WindowsNotifier(
        runner=slow, flasher=lambda h: None, hwnd=lambda: 1, platform="win32"
    )
    notifier.notify("T", "B")  # default spawn: a daemon thread
    assert started.wait(5)
    assert not done.is_set()
    release.set()
    assert done.wait(5)


def test_null_notifier_is_a_no_op():
    NullNotifier().notify("T", "B")
