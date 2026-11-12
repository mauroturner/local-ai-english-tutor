"""restart_command, the windowless interpreter lookup and spawn_restart (no process started)."""

from __future__ import annotations

import subprocess

import pytest

from english_tutor.restart import restart_command, spawn_restart, windowless_executable

EXE = "C:\\py\\python.exe"


@pytest.mark.parametrize(
    ("orig_argv", "expected"),
    [
        (["python", "main.py"], [EXE, "main.py"]),
        (["python", "D:\\app\\main.py", "--flag"], [EXE, "D:\\app\\main.py", "--flag"]),
        (["python", "-m", "english_tutor"], [EXE, "-m", "english_tutor"]),
        (["python", "-m", "english_tutor.__main__"], [EXE, "-m", "english_tutor.__main__"]),
        (["C:\\Scripts\\english-tutor.exe"], [EXE, "-m", "english_tutor"]),
        (["python", "-c", "print(1)"], [EXE, "-m", "english_tutor"]),
        (["python", "-m", "pytest"], [EXE, "-m", "english_tutor"]),
        (["python"], [EXE, "-m", "english_tutor"]),
        ([], [EXE, "-m", "english_tutor"]),
    ],
)
def test_restart_command(orig_argv, expected):
    assert restart_command(orig_argv, EXE) == expected


def test_windowless_executable_prefers_pythonw_next_to_python(tmp_path):
    python = tmp_path / "python.exe"
    pythonw = tmp_path / "pythonw.exe"
    python.write_bytes(b"")
    assert windowless_executable(str(python)) == str(python)
    pythonw.write_bytes(b"")
    assert windowless_executable(str(python)) == str(pythonw)


def test_windowless_executable_leaves_other_programs_alone(tmp_path):
    other = tmp_path / "english-tutor.exe"
    (tmp_path / "pythonw.exe").write_bytes(b"")
    assert windowless_executable(str(other)) == str(other)


class FakePopen:
    calls: list = []

    def __init__(self, command, **kwargs):
        FakePopen.calls.append((command, kwargs))


def test_spawn_restart_launches_the_command_detached(tmp_path):
    python = tmp_path / "python.exe"
    pythonw = tmp_path / "pythonw.exe"
    python.write_bytes(b"")
    pythonw.write_bytes(b"")
    FakePopen.calls = []
    assert spawn_restart(["python", "main.py"], str(python), popen=FakePopen) is True
    ((command, kwargs),) = FakePopen.calls
    assert command == [str(pythonw), "main.py"]
    assert kwargs["close_fds"] is True
    assert kwargs["creationflags"] & getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def test_spawn_restart_reports_failure_instead_of_raising():
    def broken(command, **kwargs):
        raise OSError("no such file")

    assert spawn_restart(["python", "main.py"], "C:\\missing\\python.exe", popen=broken) is False
