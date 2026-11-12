"""Piper text-to-speech adapter (external binary + sounddevice playback)."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from ..ports import TtsError

logger = logging.getLogger(__name__)

_TIMEOUT_S = 60


class PiperSynthesizer:
    """Synthesises speech with the Piper executable and plays it."""

    def __init__(self, exe: Path | None, voice: Path) -> None:
        self._exe = exe
        self._voice = voice

    @property
    def available(self) -> bool:
        """True only if the binary, the voice and its .json config all exist."""
        if self._exe is None:
            return False
        config = Path(f"{self._voice}.json")
        return self._exe.is_file() and self._voice.is_file() and config.is_file()

    def speak(self, text: str) -> None:
        """Synthesise ``text`` to a temp WAV, play it and delete the file."""
        if not self.available or self._exe is None:
            raise TtsError("Piper is not available")
        import scipy.io.wavfile as wav
        import sounddevice as sd

        handle, tmp_name = tempfile.mkstemp(suffix=".wav")
        os.close(handle)
        tmp = Path(tmp_name)
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            subprocess.run(
                [str(self._exe), "--model", str(self._voice), "--output_file", str(tmp)],
                input=text.replace("\n", " ").encode("utf-8"),
                cwd=self._exe.parent,
                check=True,
                timeout=_TIMEOUT_S,
                capture_output=True,
                creationflags=flags,
            )
            rate, data = wav.read(str(tmp))
            sd.play(data, rate)
            sd.wait()
        except (subprocess.SubprocessError, OSError, ValueError, sd.PortAudioError) as exc:
            raise TtsError(f"Speech synthesis failed: {exc}") from exc
        finally:
            tmp.unlink(missing_ok=True)


class NullSynthesizer:
    """Text-only fallback used when Piper is missing or disabled."""

    def __init__(self, available: bool = False) -> None:
        self.available = available

    def speak(self, text: str) -> None:
        """Do nothing."""
