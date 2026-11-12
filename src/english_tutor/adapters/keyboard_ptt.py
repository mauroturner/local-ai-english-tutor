"""Global push-to-talk key listener based on the ``keyboard`` package."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class KeyboardPushToTalk:
    """Calls ``on_press`` once per key press and ``on_release`` on release.

    Key auto-repeat is ignored. Callbacks run on the keyboard hook thread and
    must return immediately.
    """

    def __init__(self, key: str = "v") -> None:
        self._key = key
        self._down = False
        self._hooks: list[Any] = []
        self._keyboard: Any = None

    def start(self, on_press: Callable[[], None], on_release: Callable[[], None]) -> None:
        """Register the global hooks (may raise if the hook cannot be installed)."""
        import keyboard

        self._keyboard = keyboard

        def pressed(_event: Any) -> None:
            if self._down:
                return
            self._down = True
            on_press()

        def released(_event: Any) -> None:
            if not self._down:
                return
            self._down = False
            on_release()

        self._hooks = [
            keyboard.on_press_key(self._key, pressed),
            keyboard.on_release_key(self._key, released),
        ]
        logger.info("Push-to-talk listening on key %r", self._key)

    def stop(self) -> None:
        """Remove the hooks."""
        if self._keyboard is None:
            return
        for hook in self._hooks:
            try:
                self._keyboard.unhook(hook)
            except (KeyError, ValueError):
                logger.debug("Hook already removed")
        self._hooks = []
