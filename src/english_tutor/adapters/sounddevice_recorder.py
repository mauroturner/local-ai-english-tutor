"""sounddevice microphone recorder (callback mode, thread-safe)."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

import numpy as np

from ..audio.devices import list_input_devices
from ..ports import AudioClip

logger = logging.getLogger(__name__)

_LEVEL_GAIN = 15.0
_LEVEL_EVERY_N_BLOCKS = 3


class SoundDeviceRecorder:
    """Records float32 audio from the chosen input device."""

    def __init__(
        self,
        blocksize: int = 1024,
        post_roll_s: float = 0.3,
        on_level: Callable[[float], None] | None = None,
    ) -> None:
        self._blocksize = blocksize
        self._post_roll_s = post_roll_s
        self._on_level = on_level
        self._lock = threading.Lock()
        self._chunks: list[np.ndarray] = []
        self._stream: Any = None
        self._samplerate = 16000
        self._channels = 1
        self._block_count = 0

    def start(self, device_index: int | None) -> None:
        """Open an input stream on ``device_index`` (None = system default)."""
        import sounddevice as sd

        devices, default = list_input_devices()
        chosen = next((d for d in devices if d.index == device_index), default)
        if chosen is None:
            raise RuntimeError("No input device available")
        with self._lock:
            self._chunks = []
            self._block_count = 0
        self._samplerate = chosen.default_samplerate
        self._channels = chosen.channels
        logger.info("Recording from %s at %d Hz", chosen.name, self._samplerate)
        self._stream = sd.InputStream(
            samplerate=self._samplerate,
            channels=self._channels,
            device=chosen.index,
            dtype="float32",
            blocksize=self._blocksize,
            callback=self._callback,
        )
        self._stream.start()

    def _callback(self, indata: np.ndarray, frames: int, time_info: Any, status: Any) -> None:
        if status:
            logger.debug("Input stream status: %s", status)
        chunk = indata.copy()
        with self._lock:
            self._chunks.append(chunk)
            self._block_count += 1
            emit_level = self._block_count % _LEVEL_EVERY_N_BLOCKS == 0
        if emit_level and self._on_level is not None:
            rms = float(np.sqrt(np.mean(chunk**2)))
            self._on_level(min(rms * _LEVEL_GAIN, 1.0))

    def stop(self) -> AudioClip:
        """Stop after a short post-roll and return everything recorded."""
        stream, self._stream = self._stream, None
        if stream is None:
            return AudioClip(np.zeros((0, self._channels), dtype=np.float32), self._samplerate)
        time.sleep(self._post_roll_s)  # avoid clipping the end of the last word
        try:
            stream.stop()
        finally:
            stream.close()
        if self._on_level is not None:
            self._on_level(0.0)
        with self._lock:
            chunks, self._chunks = self._chunks, []
        if not chunks:
            return AudioClip(np.zeros((0, self._channels), dtype=np.float32), self._samplerate)
        return AudioClip(np.concatenate(chunks, axis=0), self._samplerate)
