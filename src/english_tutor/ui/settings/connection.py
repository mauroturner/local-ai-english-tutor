"""The "Test connection" action: run the Ollama check off the Tk thread, show the outcome."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from ...i18n import t
from ...ports import ConnectionCheck, ConnectionResult, ConnectionStatus

logger = logging.getLogger(__name__)

POLL_MS = 150
Schedule = Callable[[int, Callable[[], None]], object]
"""``schedule(delay_ms, callback)``: Tk's ``after``."""
Show = Callable[[str, str], None]
"""``show(text, kind)`` with kind ``info``, ``ok``, ``warning`` or ``error``."""

_KINDS = {
    ConnectionStatus.OK: ("connection.ok", "ok"),
    ConnectionStatus.MODEL_MISSING: ("connection.model_missing", "warning"),
    ConnectionStatus.UNREACHABLE: ("connection.unreachable", "error"),
    ConnectionStatus.TIMEOUT: ("connection.timeout", "error"),
    ConnectionStatus.BAD_URL: ("connection.bad_url", "error"),
}


def describe(result: ConnectionResult, url: str, model: str) -> tuple[str, str]:
    """The learner-facing ``(text, kind)`` for a check result, in the active language."""
    key, kind = _KINDS[result.status]
    return t(key, url=url.strip(), model=model.strip(), detail=result.detail), kind


class ConnectionTester:
    """Starts the check on a daemon thread and polls for it with ``schedule`` (never blocks Tk)."""

    def __init__(self, check: ConnectionCheck, schedule: Schedule, show: Show) -> None:
        self._check = check
        self._schedule = schedule
        self._show = show
        self._outcome: ConnectionResult | None = None
        self._running = False
        self.last: tuple[str, str] | None = None
        """The latest ``(text, kind)`` shown, so a rebuilt row can display it again."""

    @property
    def running(self) -> bool:
        """Whether a check is in progress."""
        return self._running

    def run(self, url: str, model: str) -> None:
        """Test ``url`` and ``model`` (the unsaved values); ignored while a check is running."""
        if self._running:
            return
        self._running, self._outcome = True, None
        self._publish(t("connection.testing"), "info")
        threading.Thread(
            target=self._work, args=(url, model), name="ollama-check", daemon=True
        ).start()
        self._schedule(POLL_MS, lambda: self._poll(url, model))

    def _work(self, url: str, model: str) -> None:
        try:
            self._outcome = self._check(url, model)
        except Exception as exc:  # a check must never leave the row stuck on "Testing"
            logger.exception("Connection check crashed")
            self._outcome = ConnectionResult(ConnectionStatus.UNREACHABLE, str(exc))

    def _poll(self, url: str, model: str) -> None:
        outcome = self._outcome
        if outcome is None:
            self._schedule(POLL_MS, lambda: self._poll(url, model))
            return
        self._running = False
        self._publish(*describe(outcome, url, model))

    def _publish(self, text: str, kind: str) -> None:
        self.last = (text, kind)
        self._show(text, kind)
