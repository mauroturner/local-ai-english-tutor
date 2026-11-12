"""Pure audio helpers: mono mixdown, resampling, normalisation."""

from __future__ import annotations

from math import gcd

import numpy as np
from scipy.signal import resample_poly

from ..ports import AudioClip

STT_SAMPLE_RATE = 16000


def to_mono(samples: np.ndarray) -> np.ndarray:
    """Average channels of a (frames, channels) array into a 1-D float32 array."""
    arr = np.asarray(samples, dtype=np.float32)
    if arr.ndim > 1:
        arr = arr.mean(axis=1)
    return arr.astype(np.float32, copy=False)


def resample(audio: np.ndarray, src_sr: int, dst_sr: int = STT_SAMPLE_RATE) -> np.ndarray:
    """Resample with a polyphase filter using the gcd-reduced ratio."""
    if src_sr == dst_sr:
        return np.asarray(audio, dtype=np.float32)
    divisor = gcd(src_sr, dst_sr)
    out = resample_poly(audio, dst_sr // divisor, src_sr // divisor)
    return np.asarray(out, dtype=np.float32)


def peak_normalize(audio: np.ndarray, target: float = 0.95) -> np.ndarray:
    """Scale so the loudest sample reaches ``target`` (silence is unchanged)."""
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak == 0.0:
        return np.asarray(audio, dtype=np.float32)
    return np.asarray(audio * (target / peak), dtype=np.float32)


def prepare_for_stt(
    clip: AudioClip, min_duration_s: float = 0.25, silence_peak: float = 0.01
) -> np.ndarray | None:
    """Convert a recording into 16 kHz mono float32 for Whisper.

    Returns None when the clip is too short or too quiet to contain speech.
    """
    mono = to_mono(clip.samples)
    if clip.sample_rate <= 0 or mono.size / clip.sample_rate < min_duration_s:
        return None
    if float(np.max(np.abs(mono))) < silence_peak:
        return None
    return peak_normalize(resample(mono, clip.sample_rate))
