"""Windows desktop toast through PowerShell (no extra dependency), with a taskbar flash fallback."""

from __future__ import annotations

import base64
import logging
import subprocess
import sys
import threading
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

_TIMEOUT_S = 10
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
_POWERSHELL_APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

# PowerShell treats these typographic quotes like an apostrophe.
_CURLY_QUOTES = "‘’‚‛"
_XML_ESCAPES = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;"}

_SCRIPT = """\
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml({xml})
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier({app_id}).Show($toast)
"""


def _xml_text(text: str) -> str:
    """Escape ``text`` for XML on a single line, safe inside a PowerShell '...' literal."""
    out: list[str] = []
    for char in " ".join(text.split()):  # newlines and runs of blanks become one space
        if char in _XML_ESCAPES:
            out.append(_XML_ESCAPES[char])
        elif char in _CURLY_QUOTES:
            out.append(f"&#{ord(char)};")
        elif ord(char) >= 0x20 and char != "\x7f" and not 0xD800 <= ord(char) <= 0xDFFF:
            out.append(char)
    return "".join(out)


def _ps_literal(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def build_toast_script(title: str, body: str) -> str:
    """PowerShell source that shows a toast; ``title`` and ``body`` cannot break out of it."""
    xml = (
        '<toast><visual><binding template="ToastGeneric">'
        f"<text>{_xml_text(title)}</text><text>{_xml_text(body)}</text>"
        "</binding></visual></toast>"
    )
    return _SCRIPT.format(xml=_ps_literal(xml), app_id=_ps_literal(_POWERSHELL_APP_ID))


def flash_window(hwnd: int) -> None:
    """Flash the taskbar button of ``hwnd`` until the window gets focus (Windows only)."""
    import ctypes
    from ctypes import wintypes

    class FlashInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT),
            ("hwnd", wintypes.HWND),
            ("dwFlags", wintypes.DWORD),
            ("uCount", wintypes.UINT),
            ("dwTimeout", wintypes.DWORD),
        ]  # fmt: skip

    flash_all, flash_until_foreground = 0x3, 0xC
    info = FlashInfo(
        ctypes.sizeof(FlashInfo), hwnd, flash_all | flash_until_foreground, 0, 0
    )
    ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))


def tk_hwnd(window: Any) -> int:
    """Native handle of a Tk top-level window; call it on the Tk thread."""
    import ctypes

    return int(ctypes.windll.user32.GetParent(window.winfo_id())) or int(window.winfo_id())


def _spawn_daemon(work: Callable[[], None]) -> None:
    threading.Thread(target=work, name="toast", daemon=True).start()


class WindowsNotifier:
    """Shows a toast from a daemon thread; on failure flashes the window instead."""

    def __init__(
        self,
        hwnd: Callable[[], int | None] | None = None,
        runner: Callable[..., Any] = subprocess.run,
        flasher: Callable[[int], None] = flash_window,
        spawn: Callable[[Callable[[], None]], None] = _spawn_daemon,
        platform: str = sys.platform,
    ) -> None:
        self._hwnd = hwnd
        self._runner = runner
        self._flasher = flasher
        self._spawn = spawn
        self._platform = platform

    def notify(self, title: str, body: str) -> None:
        """Return immediately; never raises."""
        if self._platform != "win32":
            return
        try:
            handle = self._hwnd() if self._hwnd is not None else None  # Tk thread only
            self._spawn(lambda: self._show(title, body, handle))
        except Exception:
            logger.warning("Could not start the desktop notification", exc_info=True)

    def _show(self, title: str, body: str, hwnd: int | None) -> None:
        try:
            encoded = base64.b64encode(build_toast_script(title, body).encode("utf-16-le"))
            result = self._runner(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand",
                 encoded.decode("ascii")],
                capture_output=True,
                timeout=_TIMEOUT_S,
                creationflags=_CREATE_NO_WINDOW,
                check=False,
            )  # fmt: skip
            if result.returncode == 0:
                return
            logger.warning("Toast notification failed: %s", _tail(result.stderr))
        except Exception:
            logger.warning("Toast notification failed", exc_info=True)
        self._flash(hwnd)

    def _flash(self, hwnd: int | None) -> None:
        if hwnd is None:
            return
        try:
            self._flasher(hwnd)
        except Exception:
            logger.warning("Could not flash the window", exc_info=True)


def _tail(raw: Any) -> str:
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw or "")
    return text.strip()[-300:]


class NullNotifier:
    """Notifier for tests and platforms without toast support."""

    def notify(self, title: str, body: str) -> None:
        """Do nothing."""
