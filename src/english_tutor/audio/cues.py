"""Short audio cues (pure numpy): recording started, recording stopped, error."""

from __future__ import annotations

from enum import Enum

import numpy as np

_FADE_S = 0.005
_GAP_S = 0.060


class Cue(Enum):
    """Events that earn a short sound."""

    START = "start"
    STOP = "stop"
    ERROR = "error"


# (frequency in Hz, duration in seconds) of every beep of a cue
_BEEPS: dict[Cue, tuple[tuple[float, float], ...]] = {
    Cue.START: ((880.0, 0.060),),
    Cue.STOP: ((660.0, 0.060),),
    Cue.ERROR: ((330.0, 0.120), (330.0, 0.120)),
}


def _beep(frequency: float, duration: float, sr: int) -> np.ndarray:
    """One sine beep at full scale with 5 ms linear fades, so it never clicks."""
    count = round(sr * duration)
    wave = np.sin(2 * np.pi * frequency * np.arange(count) / sr)
    fade = min(round(sr * _FADE_S), count // 2)
    if fade > 0:
        ramp = np.linspace(0.0, 1.0, fade, endpoint=False)
        wave[:fade] *= ramp
        wave[count - fade :] *= ramp[::-1]
    return wave


def render(cue: Cue, sr: int = 44100, volume: float = 0.2) -> np.ndarray:
    """Return the cue as mono float32 samples whose peak never exceeds ``volume``."""
    gain = min(max(volume, 0.0), 1.0)
    gap = np.zeros(round(sr * _GAP_S))
    parts: list[np.ndarray] = []
    for index, (frequency, duration) in enumerate(_BEEPS[cue]):
        if index:
            parts.append(gap)
        parts.append(_beep(frequency, duration, sr))
    return (np.concatenate(parts) * gain).astype(np.float32)
