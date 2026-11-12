"""Global push-to-talk key listener based on the ``keyboard`` package."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

KeyNameText = Callable[[int], "str | None"]

# Scan codes shared by the left and right variants of a modifier key.
_SHARED = {"ctrl": 29, "alt": 56}
_NAME_BUFFER_SIZE = 64


def _windows_key_name(lparam: int) -> str | None:
    """Return the localized key name Windows reports for ``lparam``, else None."""
    try:
        import ctypes

        buffer = ctypes.create_unicode_buffer(_NAME_BUFFER_SIZE)
        length = ctypes.windll.user32.GetKeyNameTextW(lparam, buffer, _NAME_BUFFER_SIZE)  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return None
    return buffer.value if length > 0 else None


def side_names(key: str, key_name_text: KeyNameText) -> frozenset[str] | None:
    """Names an event may carry for a left/right modifier, or None for no filter.

    The ``keyboard`` package matches modifiers by scan code only, so left and
    right Ctrl/Alt both fire. Events carry the localized Windows key name, so
    the accepted names are the English one plus the localized one. If the
    lookup fails there is no filter, so push-to-talk is never dead.
    """
    parts = key.lower().split()
    if len(parts) != 2 or parts[0] not in ("left", "right") or parts[1] not in _SHARED:
        return None
    scan_code = _SHARED[parts[1]]
    extended = 1 if parts[0] == "right" else 0
    localized = key_name_text((scan_code << 16) | (extended << 24))
    if not localized:
        return None
    return frozenset({key.lower(), localized.lower()})


class KeyboardPushToTalk:
    """Calls ``on_press`` once per key press and ``on_release`` on release.

    Key auto-repeat is ignored. Callbacks run on the keyboard hook thread and
    must return immediately.
    """

    def __init__(
        self, key: str = "v", key_name_text: KeyNameText = _windows_key_name
    ) -> None:
        self._key = key
        self._key_name_text = key_name_text
        self._down = False
        self._hooks: list[Any] = []
        self._keyboard: Any = None

    def start(self, on_press: Callable[[], None], on_release: Callable[[], None]) -> None:
        """Register the global hooks (may raise if the hook cannot be installed)."""
        import keyboard

        self._keyboard = keyboard
        names = side_names(self._key, self._key_name_text)

        def wrong_side(event: Any) -> bool:
            return bool(names) and (getattr(event, "name", "") or "").lower() not in names

        def pressed(event: Any) -> None:
            if wrong_side(event) or self._down:
                return
            self._down = True
            on_press()

        def released(event: Any) -> None:
            if wrong_side(event) or not self._down:
                return
            self._down = False
            on_release()

        self._hooks = [
            keyboard.on_press_key(self._key, pressed),
            keyboard.on_release_key(self._key, released),
        ]
        logger.info("Push-to-talk listening on key %r (side filter: %s)", self._key, bool(names))

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
