"""Sound cues: pure rendering of the short beeps."""

from __future__ import annotations

import numpy as np
import pytest

from english_tutor.audio.cues import Cue, render

SR = 44100


def dominant_hz(samples: np.ndarray, sr: int = SR) -> float:
    spectrum = np.abs(np.fft.rfft(samples))
    return float(np.fft.rfftfreq(len(samples), 1 / sr)[int(np.argmax(spectrum))])


def test_render_returns_float32_mono():
    for cue in Cue:
        samples = render(cue)
        assert samples.dtype == np.float32
        assert samples.ndim == 1


def test_start_and_stop_last_60_ms():
    assert len(render(Cue.START)) == round(SR * 0.060)
    assert len(render(Cue.STOP)) == round(SR * 0.060)


def test_error_is_two_120_ms_beeps_with_a_gap():
    samples = render(Cue.ERROR)
    beep = round(SR * 0.120)
    assert len(samples) > 2 * beep
    gap = samples[beep:-beep]
    assert len(gap) > 0
    assert np.all(gap == 0)
    assert np.max(np.abs(samples[:beep])) > 0
    assert np.max(np.abs(samples[-beep:])) > 0


def test_tones_have_the_documented_pitch():
    assert dominant_hz(render(Cue.START)) == pytest.approx(880, abs=30)
    assert dominant_hz(render(Cue.STOP)) == pytest.approx(660, abs=30)
    assert dominant_hz(render(Cue.ERROR)) == pytest.approx(330, abs=15)


def test_peak_never_exceeds_the_volume():
    for cue in Cue:
        peak = float(np.max(np.abs(render(cue, volume=0.2))))
        assert peak <= 0.2 + 1e-6
        assert peak > 0.15
    assert float(np.max(np.abs(render(Cue.START, volume=0.05)))) <= 0.05 + 1e-6


def test_volume_is_clamped_to_full_scale():
    assert float(np.max(np.abs(render(Cue.START, volume=7.0)))) <= 1.0 + 1e-6
    assert not np.any(render(Cue.START, volume=-1.0))


def test_five_millisecond_fades_avoid_clicks():
    fade = round(SR * 0.005)
    for cue in (Cue.START, Cue.STOP):
        samples = render(cue)
        assert abs(samples[0]) < 1e-3
        assert abs(samples[-1]) < 1e-3
        # The fade-in is quieter than the steady part that follows it.
        assert np.max(np.abs(samples[:fade])) < np.max(np.abs(samples[fade : 3 * fade]))
        assert np.max(np.abs(samples[-fade:])) < np.max(np.abs(samples[-3 * fade : -fade]))


def test_every_beep_of_the_error_cue_fades_in_and_out():
    samples = render(Cue.ERROR)
    beep = round(SR * 0.120)
    assert abs(samples[0]) < 1e-3 and abs(samples[beep - 1]) < 1e-3
    assert abs(samples[-beep]) < 1e-3 and abs(samples[-1]) < 1e-3


def test_other_sample_rates_keep_the_duration():
    assert len(render(Cue.START, sr=48000)) == round(48000 * 0.060)
