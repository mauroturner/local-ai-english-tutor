"""Pure mapping from the session state to the status chip's text key and colour."""

from __future__ import annotations

from ..domain.models import SessionState
from . import theme


def state_style(state: SessionState) -> tuple[str, tuple[str, str]]:
    """Return ``(i18n key, (light, dark) colour)``: green idle, red recording, amber busy."""
    if state is SessionState.IDLE:
        colour = theme.CHIP_GREEN
    elif state is SessionState.RECORDING:
        colour = theme.CHIP_RED
    else:
        colour = theme.CHIP_AMBER
    return f"chip.{state.value}", colour
