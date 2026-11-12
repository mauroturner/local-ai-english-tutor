"""Input device discovery with duplicate removal across Windows host APIs."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_API_PRIORITY = {"Windows WASAPI": 3, "Windows DirectSound": 2, "MME": 1}
_MME_NAME_LIMIT = 31


@dataclass(frozen=True)
class InputDevice:
    """A selectable microphone."""

    index: int
    name: str
    hostapi: str
    priority: int
    default_samplerate: int
    channels: int


def _merge_key(name: str) -> str:
    return name[:_MME_NAME_LIMIT].strip().casefold()


def dedupe_input_devices(
    devices: Sequence[Mapping], hostapis: Sequence[Mapping]
) -> list[InputDevice]:
    """Keep one entry per physical microphone, preferring WASAPI > DirectSound > MME.

    MME truncates names to 31 characters, so names are merged on that prefix.
    The entry from the higher-priority API wins and keeps its full name.
    """
    best: dict[str, InputDevice] = {}
    for index, dev in enumerate(devices):
        max_in = int(dev.get("max_input_channels", 0))
        if max_in <= 0:
            continue
        api_name = str(hostapis[dev["hostapi"]]["name"])
        candidate = InputDevice(
            index=index,
            name=str(dev["name"]),
            hostapi=api_name,
            priority=_API_PRIORITY.get(api_name, 0),
            default_samplerate=int(dev.get("default_samplerate", 44100)),
            channels=min(max_in, 2),
        )
        key = _merge_key(candidate.name)
        current = best.get(key)
        if current is None or candidate.priority > current.priority:
            best[key] = candidate
    return sorted(best.values(), key=lambda d: d.name.casefold())


def resolve_default(
    devices: Sequence[InputDevice],
    default_index: int | None,
    raw_devices: Sequence[Mapping],
) -> InputDevice | None:
    """Map the system default input to one of the deduplicated devices."""
    if default_index is not None and 0 <= default_index < len(raw_devices):
        key = _merge_key(str(raw_devices[default_index]["name"]))
        for dev in devices:
            if _merge_key(dev.name) == key:
                return dev
    return devices[0] if devices else None


def list_input_devices() -> tuple[list[InputDevice], InputDevice | None]:
    """Query PortAudio and return (devices, default). Imports sounddevice lazily."""
    import sounddevice as sd

    raw = [dict(d) for d in sd.query_devices()]
    hostapis = [dict(h) for h in sd.query_hostapis()]
    devices = dedupe_input_devices(raw, hostapis)
    default_index: int | None
    try:
        default_index = int(sd.default.device[0])
        if default_index < 0:
            default_index = None
    except (TypeError, ValueError, IndexError):
        default_index = None
    default = resolve_default(devices, default_index, raw)
    logger.info("Found %d input devices", len(devices))
    return devices, default
