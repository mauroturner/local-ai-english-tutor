"""faster-whisper speech-to-text adapter producing literal transcripts."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import numpy as np

from ..config import AppConfig
from ..domain.hesitation import matching_words
from ..domain.models import TimedWord, Transcript
from ..ports import SttError
from .whisper_alignment import align_words

Aligner = Callable[[Any, np.ndarray, str], tuple[TimedWord, ...]]

logger = logging.getLogger(__name__)

_SAMPLE_RATE = 16000


def build_transcribe_kwargs(cfg: AppConfig) -> dict[str, Any]:
    """Decoding options chosen to keep the transcript as literal as possible.

    No ``initial_prompt`` (it would bias towards "correct" English), greedy
    temperature 0 and no conditioning on previous text. No word timestamps:
    faster-whisper (1.2.1) then re-decodes the audio after the last word,
    which can repeat or invent words at the end; word timings come from
    ``whisper_alignment`` instead.
    """
    return dict(
        language="en",
        task="transcribe",
        beam_size=cfg.whisper_beam_size,
        temperature=0.0,
        condition_on_previous_text=False,
        initial_prompt=None,
        hotwords=None,
        without_timestamps=True,
        word_timestamps=False,
        suppress_blank=True,
        suppress_tokens=[-1],
        multilingual=False,
        no_speech_threshold=0.6,
        log_prob_threshold=-1.0,
        compression_ratio_threshold=2.4,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500, "speech_pad_ms": 400},
    )


class WhisperTranscriber:
    """Loads faster-whisper lazily and transcribes numpy audio directly."""

    def __init__(self, cfg: AppConfig, aligner: Aligner = align_words) -> None:
        self._cfg = cfg
        self._model: Any = None
        self._kwargs = build_transcribe_kwargs(cfg)
        self._aligner = aligner

    def load(self) -> str:
        """Load the model, warming up CUDA, and fall back to CPU int8 on failure."""
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise SttError(f"faster-whisper is not installed: {exc}") from exc

        cfg = self._cfg
        if cfg.whisper_device in ("auto", "cuda"):
            try:
                model = WhisperModel(
                    cfg.whisper_model, device="cuda", compute_type=cfg.whisper_compute_type
                )
                self._warm_up(model)
                self._model = model
                return f"cuda ({cfg.whisper_compute_type})"
            except Exception as exc:  # missing CUDA/cuDNN DLLs surface as many types
                logger.warning("CUDA unavailable (%s); falling back to CPU", exc)
        try:
            self._model = WhisperModel(
                cfg.whisper_model,
                device="cpu",
                compute_type=cfg.whisper_cpu_compute_type,
            )
        except Exception as exc:
            raise SttError(f"Could not load Whisper model: {exc}") from exc
        return f"cpu ({cfg.whisper_cpu_compute_type})"

    def _warm_up(self, model: Any) -> None:
        """CUDA library errors only appear on the first decode, so decode once."""
        # VAD is disabled here: on pure silence it would skip the GPU entirely.
        kwargs = {**self._kwargs, "vad_filter": False, "vad_parameters": None}
        segments, _ = model.transcribe(np.zeros(_SAMPLE_RATE, dtype=np.float32), **kwargs)
        list(segments)

    def transcribe(
        self, audio_16k: np.ndarray, with_words: bool = False, language: str = "en"
    ) -> Transcript:
        """Transcribe 16 kHz mono float32 audio without altering the text.

        ``language`` is "en" for the conversation and "es" for a request in Spanish; word
        timings are only computed for English.

        With ``with_words`` the finished text is also aligned to the audio to
        learn when each word was said; that step never changes the text.
        """
        if self._model is None:
            raise SttError("Speech model is not loaded yet")
        try:
            segments, _ = self._model.transcribe(audio_16k, **{**self._kwargs, "language": language})
            text = "".join(seg.text for seg in list(segments)).strip()
        except Exception as exc:  # decoding errors are library specific
            raise SttError(f"Transcription failed: {exc}") from exc
        words = self._timed_words(audio_16k, text) if with_words and text and language == "en" else ()
        return Transcript(text, len(audio_16k) / _SAMPLE_RATE, words)

    def _timed_words(self, audio_16k: np.ndarray, text: str) -> tuple[TimedWord, ...]:
        """Word timings for ``text``; a failure only costs the pause check of this turn."""
        try:
            timed = self._aligner(self._model, audio_16k, text)
        except Exception as exc:  # library internals: any error means "no timings"
            logger.warning("Word timings unavailable for this turn: %s", exc)
            return ()
        return matching_words(text, timed)
