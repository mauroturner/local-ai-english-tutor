"""Pure mapping from the session state to the status chip's text key and colour."""

from __future__ import annotations

from ..domain.models import SessionState
from ..i18n import t, translate_status
from . import theme

_READY = "Ready"
_READY_HOLD = "Ready: hold "


def state_style(state: SessionState) -> tuple[str, tuple[str, str]]:
    """Return ``(i18n key, (light, dark) colour)``: green idle, red recording, amber busy."""
    if state is SessionState.IDLE:
        colour = theme.CHIP_GREEN
    elif state is SessionState.RECORDING:
        colour = theme.CHIP_RED
    else:
        colour = theme.CHIP_AMBER
    return f"chip.{state.value}", colour


def status_line(state: SessionState, message: str | None, ptt_label: str) -> str:
    """The text for the footer's status line, so nothing is said twice.

    The chip already names the state. Idle shows the hold instruction (once, here);
    a message that only repeats the chip ("Thinking...") is dropped; the rest
    ("Listening...", "Too short or too quiet, try again") is kept and translated.
    """
    if not message:
        return ""
    if state is SessionState.IDLE and (message == _READY or message.startswith(_READY_HOLD)):
        return t("hint.hold", key=ptt_label)
    line = translate_status(message)
    chip = t(state_style(state)[0])
    if line.rstrip(".").casefold() == chip.casefold():
        return ""
    return line
