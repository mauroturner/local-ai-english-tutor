"""Start with Windows: one value under the current user's ``Run`` registry key.

Only ``HKEY_CURRENT_USER`` is used (no administrator rights, nothing machine-wide) and
only the value named ``EnglishTutor`` is ever written or deleted. The ``winreg`` module
is passed in so tests can supply a fake; the real registry is never touched by tests.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from ..ports import StorageError
from ..restart import windowless_executable

logger = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "EnglishTutor"


def autostart_command(project_root: Path, executable: str | None = None) -> str:
    """The command Windows runs at sign-in: ``"<pythonw.exe>" "<root>\\main.py"``.

    ``pythonw.exe`` is used when it sits next to the interpreter so no console window
    opens at logon; both parts are quoted because either path may contain spaces.
    """
    interpreter = windowless_executable(sys.executable if executable is None else executable)
    return f'"{interpreter}" "{project_root / "main.py"}"'


class WindowsAutoStart:
    """``AutoStart`` backed by the registry (``winreg`` is injected)."""

    def __init__(self, winreg: Any, command: str) -> None:
        self._reg = winreg
        self._command = command

    def is_enabled(self) -> bool:
        """Whether our value exists."""
        return self._read() is not None

    def is_stale(self) -> bool:
        """Whether the value exists but differs from the command this install would write."""
        current = self._read()
        return current is not None and current.casefold() != self._command.casefold()

    def enable(self) -> None:
        """Create or rewrite our value; raises StorageError when the registry refuses."""
        reg = self._reg
        try:
            with reg.CreateKeyEx(reg.HKEY_CURRENT_USER, RUN_KEY, 0, reg.KEY_SET_VALUE) as key:
                reg.SetValueEx(key, VALUE_NAME, 0, reg.REG_SZ, self._command)
        except OSError as exc:
            raise self._error("enable", exc) from exc
        logger.info("Auto-start enabled: %s", self._command)

    def disable(self) -> None:
        """Delete our value (and only it); absent is fine. Raises StorageError on failure."""
        reg = self._reg
        try:
            with reg.OpenKey(reg.HKEY_CURRENT_USER, RUN_KEY, 0, reg.KEY_SET_VALUE) as key:
                reg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            return  # no Run key or no value: already off
        except OSError as exc:
            raise self._error("disable", exc) from exc
        logger.info("Auto-start disabled")

    def _read(self) -> str | None:
        reg = self._reg
        try:
            with reg.OpenKey(reg.HKEY_CURRENT_USER, RUN_KEY, 0, reg.KEY_READ) as key:
                data, _kind = reg.QueryValueEx(key, VALUE_NAME)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise self._error("read", exc) from exc
        return str(data)

    @staticmethod
    def _error(action: str, exc: OSError) -> StorageError:
        logger.warning("Auto-start %s failed: %s", action, exc)
        return StorageError(f"Could not {action} the Windows start-up entry: {exc}")


class NullAutoStart:
    """Used where auto-start does not exist (not Windows, or no registry module)."""

    def is_enabled(self) -> bool:
        return False

    def is_stale(self) -> bool:
        return False

    def enable(self) -> None:
        raise StorageError("Starting with the operating system is not available here.")

    def disable(self) -> None:
        """Nothing to remove."""
