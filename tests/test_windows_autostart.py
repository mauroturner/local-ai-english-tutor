"""The Windows auto-start adapter, driven with a fake ``winreg`` (no real registry)."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import FakeWinreg

from english_tutor.adapters.windows_autostart import (
    RUN_KEY,
    VALUE_NAME,
    NullAutoStart,
    WindowsAutoStart,
    autostart_command,
)
from english_tutor.ports import StorageError

COMMAND = '"C:\\py\\pythonw.exe" "C:\\app\\main.py"'
HKCU = FakeWinreg.HKEY_CURRENT_USER
RUN = (HKCU, RUN_KEY)


def adapter(registry: FakeWinreg, command: str = COMMAND) -> WindowsAutoStart:
    return WindowsAutoStart(registry, command)


def test_the_value_lives_under_the_current_user_run_key():
    assert RUN_KEY == r"Software\Microsoft\Windows\CurrentVersion\Run"
    assert VALUE_NAME == "EnglishTutor"


def test_enable_writes_exactly_the_expected_value_under_hkcu_run():
    registry = FakeWinreg({RUN: {}})
    adapter(registry).enable()
    assert registry.keys[RUN] == {"EnglishTutor": COMMAND}
    assert registry.writes == [("set", RUN, "EnglishTutor", FakeWinreg.REG_SZ, COMMAND)]
    assert registry.hives_used == {HKCU}  # never HKLM


def test_enable_creates_the_run_key_when_it_is_missing():
    registry = FakeWinreg()
    adapter(registry).enable()
    assert registry.keys[RUN] == {"EnglishTutor": COMMAND}


def test_enable_rewrites_a_stale_value_and_keeps_other_programs():
    registry = FakeWinreg({RUN: {"EnglishTutor": '"old" "x"', "Other": "keep"}})
    adapter(registry).enable()
    assert registry.keys[RUN] == {"EnglishTutor": COMMAND, "Other": "keep"}


def test_disable_removes_only_our_own_value():
    registry = FakeWinreg({RUN: {"EnglishTutor": COMMAND, "Other": "keep", "More": "x"}})
    adapter(registry).disable()
    assert registry.keys[RUN] == {"Other": "keep", "More": "x"}
    assert registry.hives_used == {HKCU}


def test_disable_when_the_value_is_absent_is_a_no_op():
    registry = FakeWinreg({RUN: {"Other": "keep"}})
    adapter(registry).disable()
    assert registry.keys[RUN] == {"Other": "keep"}
    assert registry.writes == []


def test_disable_when_the_whole_key_is_absent_is_a_no_op():
    registry = FakeWinreg()
    adapter(registry).disable()
    assert registry.writes == []


def test_is_enabled_follows_the_presence_of_our_value():
    assert adapter(FakeWinreg({RUN: {"EnglishTutor": COMMAND}})).is_enabled() is True
    assert adapter(FakeWinreg({RUN: {"Other": "x"}})).is_enabled() is False
    assert adapter(FakeWinreg()).is_enabled() is False


def test_a_matching_entry_is_not_stale():
    assert adapter(FakeWinreg({RUN: {"EnglishTutor": COMMAND}})).is_stale() is False


def test_an_entry_that_differs_from_the_expected_command_is_stale():
    registry = FakeWinreg({RUN: {"EnglishTutor": '"C:\\old\\pythonw.exe" "C:\\old\\main.py"'}})
    assert adapter(registry).is_stale() is True


def test_without_an_entry_nothing_is_stale():
    assert adapter(FakeWinreg()).is_stale() is False


def test_enable_failure_is_a_typed_error():
    registry = FakeWinreg({RUN: {}}, fail=PermissionError("denied"))
    with pytest.raises(StorageError, match="denied"):
        adapter(registry).enable()
    assert registry.keys[RUN] == {}


def test_disable_failure_is_a_typed_error():
    registry = FakeWinreg({RUN: {"EnglishTutor": COMMAND}}, fail=PermissionError("denied"))
    with pytest.raises(StorageError, match="denied"):
        adapter(registry).disable()
    assert registry.keys[RUN] == {"EnglishTutor": COMMAND}


def test_registry_read_errors_become_a_typed_error():
    registry = FakeWinreg({RUN: {}}, read_fail=PermissionError("no access"))
    with pytest.raises(StorageError, match="no access"):
        adapter(registry).is_enabled()
    with pytest.raises(StorageError, match="no access"):
        adapter(registry).is_stale()


def test_autostart_command_quotes_both_parts(tmp_path):
    exe = tmp_path / "Program Files" / "python.exe"
    exe.parent.mkdir()
    exe.write_text("")
    (exe.parent / "pythonw.exe").write_text("")
    command = autostart_command(tmp_path / "my app", str(exe))
    assert command == f'"{exe.parent / "pythonw.exe"}" "{tmp_path / "my app" / "main.py"}"'


def test_autostart_command_falls_back_to_the_running_interpreter(tmp_path):
    exe = tmp_path / "python.exe"  # no pythonw.exe next to it
    command = autostart_command(Path("C:/app"), str(exe))
    assert command == f'"{exe}" "{Path("C:/app") / "main.py"}"'


def test_the_null_implementation_is_inert_and_refuses_to_enable():
    null = NullAutoStart()
    assert null.is_enabled() is False
    assert null.is_stale() is False
    null.disable()
    with pytest.raises(StorageError):
        null.enable()
