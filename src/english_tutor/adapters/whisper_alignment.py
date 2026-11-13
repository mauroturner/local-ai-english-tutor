"""Word timings for a transcript we already have, using faster-whisper's own parts.

Asking faster-whisper for ``word_timestamps`` while decoding changes the text
(1.2.1 re-decodes the audio after the last word and can repeat or invent words),
and a second decoding pass costs about as much as the first. Instead this module
force-aligns the known text, which needs one encoder pass and no decoding:

1. Silero VAD (bundled with faster-whisper) finds the stretches of speech.
2. The speech stretches are joined, so the aligner never has silence to stretch
   a word over, and the text is aligned to that audio.
3. Each word goes back to the original timeline by the stretch its middle is in,
   so the silences reappear as gaps between words.

It relies on faster-whisper internals (``encode``, ``find_alignment``), pinned
in requirements.txt; any failure is turned into "no timings" by the caller.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..domain.hesitation import restore_times
from ..domain.models import TimedWord

SAMPLE_RATE = 16000
_MIN_SILENCE_MS = 300
_SPEECH_PAD_MS = 100


def speech_chunks(audio_16k: np.ndarray) -> list[tuple[int, int]]:
    """``(start, end)`` sample indices of every stretch of speech."""
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    options = VadOptions(min_silence_duration_ms=_MIN_SILENCE_MS, speech_pad_ms=_SPEECH_PAD_MS)
    return [(int(c["start"]), int(c["end"])) for c in get_speech_timestamps(audio_16k, options)]


def _probability(word: Any) -> float | None:
    """The recogniser's confidence in an aligned word, when it reports one."""
    try:
        return float(word["probability"])
    except (KeyError, TypeError, ValueError):
        return None


def _force_align(model: Any, audio_16k: np.ndarray, text: str) -> tuple[TimedWord, ...]:
    """Times of each word of ``text`` within ``audio_16k`` (at most 30 s)."""
    from faster_whisper.audio import pad_or_trim
    from faster_whisper.tokenizer import Tokenizer

    extractor = model.feature_extractor
    features = extractor(audio_16k)
    num_frames = min(features.shape[-1], extractor.nb_max_frames)
    encoder_output = model.encode(pad_or_trim(features[:, :num_frames]))
    tokenizer = Tokenizer(
        model.hf_tokenizer, model.model.is_multilingual, task="transcribe", language="en"
    )
    tokens = tokenizer.encode(" " + text)
    (aligned,) = model.find_alignment(tokenizer, [tokens], encoder_output, num_frames)
    return tuple(
        TimedWord(str(w["word"]), float(w["start"]), float(w["end"]), _probability(w))
        for w in aligned
    )


def align_words(model: Any, audio_16k: np.ndarray, text: str) -> tuple[TimedWord, ...]:
    """Word timings of ``text`` in ``audio_16k``; empty when there is no usable speech.

    Recordings with more than 30 s of speech are not aligned (one encoder
    window); they simply get no timings.
    """
    chunks = speech_chunks(audio_16k)
    speech = sum(end - start for start, end in chunks)
    if not chunks or not text.strip() or speech > model.feature_extractor.n_samples:
        return ()
    compact = np.concatenate([audio_16k[start:end] for start, end in chunks])
    words = _force_align(model, compact, text)
    spans = [(start / SAMPLE_RATE, end / SAMPLE_RATE) for start, end in chunks]
    return restore_times(words, spans)
