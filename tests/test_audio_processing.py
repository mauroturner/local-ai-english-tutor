"""Pure audio helpers."""

from __future__ import annotations

import numpy as np

from english_tutor.audio.processing import (
    peak_normalize,
    prepare_for_stt,
    resample,
    to_mono,
)
from english_tutor.ports import AudioClip


def tone(seconds=1.0, sr=48000, channels=1, amp=0.4):
    t = np.arange(int(seconds * sr)) / sr
    mono = (amp * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    return np.stack([mono] * channels, axis=1) if channels > 1 else mono.reshape(-1, 1)


def test_stereo_to_mono_averages_channels():
    stereo = np.array([[1.0, 0.0], [0.5, 0.5]], dtype=np.float32)
    assert to_mono(stereo).tolist() == [0.5, 0.5]
    assert to_mono(stereo).ndim == 1


def test_resample_48k_to_16k_length():
    out = resample(tone(1.0, 48000).ravel(), 48000, 16000)
    assert len(out) == 16000 and out.dtype == np.float32


def test_resample_uneven_ratio_44100():
    out = resample(tone(1.0, 44100).ravel(), 44100, 16000)
    assert abs(len(out) - 16000) <= 1


def test_resample_same_rate_is_identity():
    audio = tone(0.1, 16000).ravel()
    assert np.array_equal(resample(audio, 16000, 16000), audio)


def test_peak_normalize_reaches_target():
    out = peak_normalize(np.array([0.1, -0.2], dtype=np.float32), 0.95)
    assert np.isclose(np.max(np.abs(out)), 0.95)


def test_peak_normalize_silence_unchanged():
    out = peak_normalize(np.zeros(10, dtype=np.float32))
    assert not out.any()


def test_prepare_returns_16k_mono_float32_normalised():
    out = prepare_for_stt(AudioClip(tone(1.0, 48000, channels=2), 48000))
    assert out is not None
    assert out.dtype == np.float32 and out.ndim == 1
    assert len(out) == 16000
    assert np.isclose(np.max(np.abs(out)), 0.95, atol=0.02)


def test_too_short_clip_returns_none():
    assert prepare_for_stt(AudioClip(tone(0.1, 16000), 16000)) is None


def test_too_quiet_clip_returns_none():
    assert prepare_for_stt(AudioClip(tone(1.0, 16000, amp=0.001), 16000)) is None


def test_empty_clip_returns_none():
    assert prepare_for_stt(AudioClip(np.zeros((0, 1), dtype=np.float32), 16000)) is None
