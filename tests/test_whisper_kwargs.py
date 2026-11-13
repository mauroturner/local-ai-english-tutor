"""S4: Whisper decoding must be configured for literal transcripts."""

from __future__ import annotations

import sys

import numpy as np
import pytest

from english_tutor.adapters.whisper_stt import WhisperTranscriber, build_transcribe_kwargs
from english_tutor.config import AppConfig
from english_tutor.domain.models import TimedWord
from english_tutor.ports import SttError


def test_exact_kwargs():
    assert build_transcribe_kwargs(AppConfig()) == dict(
        language="en",
        task="transcribe",
        beam_size=5,
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


def test_no_initial_prompt_and_greedy_temperature():
    kwargs = build_transcribe_kwargs(AppConfig(whisper_beam_size=1))
    assert kwargs["initial_prompt"] is None
    assert kwargs["temperature"] == 0.0 and isinstance(kwargs["temperature"], float)
    assert kwargs["condition_on_previous_text"] is False
    assert kwargs["beam_size"] == 1


class Seg:
    def __init__(self, text):
        self.text = text


class FakeModel:
    instances = []

    def __init__(self, name, device, compute_type):
        self.args = (name, device, compute_type)
        self.calls = []
        FakeModel.instances.append(self)
        if device == "cuda" and FakeModel.cuda_broken:
            self.fail = True
        else:
            self.fail = False

    cuda_broken = False

    def transcribe(self, audio, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("cublas64_12.dll not found")
        return iter([Seg(" Hi - Could you"), Seg(" hear me? ")]), None


@pytest.fixture
def fake_faster_whisper(monkeypatch):
    FakeModel.instances = []
    FakeModel.cuda_broken = False
    module = type(sys)("faster_whisper")
    module.WhisperModel = FakeModel
    monkeypatch.setitem(sys.modules, "faster_whisper", module)
    return FakeModel


def test_transcript_is_joined_unchanged(fake_faster_whisper):
    stt = WhisperTranscriber(AppConfig())
    assert stt.load() == "cuda (float16)"
    result = stt.transcribe(np.zeros(32000, dtype=np.float32))
    assert result.text == "Hi - Could you hear me?"
    assert result.duration_s == 2.0
    assert fake_faster_whisper.instances[0].calls[-1]["initial_prompt"] is None


def test_warm_up_runs_on_gpu_and_cuda_failure_falls_back_to_cpu_int8(fake_faster_whisper):
    fake_faster_whisper.cuda_broken = True
    stt = WhisperTranscriber(AppConfig())
    assert stt.load() == "cpu (int8)"
    devices = [(m.args[1], m.args[2]) for m in fake_faster_whisper.instances]
    assert devices == [("cuda", "float16"), ("cpu", "int8")]


def test_cpu_device_skips_cuda(fake_faster_whisper):
    stt = WhisperTranscriber(AppConfig(whisper_device="cpu"))
    assert stt.load() == "cpu (int8)"
    assert len(fake_faster_whisper.instances) == 1


def test_transcribe_before_load_raises(fake_faster_whisper):
    with pytest.raises(SttError):
        WhisperTranscriber(AppConfig()).transcribe(np.zeros(10, dtype=np.float32))


def aligned(*items):
    return tuple(TimedWord(*item) for item in items)


def test_text_is_decoded_once_and_timings_come_from_the_aligner(fake_faster_whisper):
    seen = []

    def aligner(model, audio, text):
        seen.append(text)
        # an extra word the transcript does not have is dropped
        return aligned((" Hi", 0.1, 0.3), (" Could", 1.9, 2.1), (" you", 2.1, 2.2),
                       (" hear", 2.2, 2.4), (" me?", 2.4, 2.6), (" Thanks", 4.0, 4.2))  # fmt: skip

    stt = WhisperTranscriber(AppConfig(), aligner=aligner)
    stt.load()
    calls = len(fake_faster_whisper.instances[0].calls)
    result = stt.transcribe(np.zeros(32000, dtype=np.float32), with_words=True)
    assert result.text == "Hi - Could you hear me?"
    assert seen == ["Hi - Could you hear me?"]
    assert [w.text for w in result.words] == [" Hi", " Could", " you", " hear", " me?"]
    assert len(fake_faster_whisper.instances[0].calls) == calls + 1  # no second decode
    assert fake_faster_whisper.instances[0].calls[-1]["word_timestamps"] is False


def test_without_words_the_aligner_is_not_called(fake_faster_whisper):
    stt = WhisperTranscriber(AppConfig(), aligner=lambda *a: pytest.fail("aligned"))
    stt.load()
    assert stt.transcribe(np.zeros(16000, dtype=np.float32)).words == ()


def test_a_failed_alignment_keeps_the_transcript(fake_faster_whisper):
    def broken(model, audio, text):
        raise RuntimeError("alignment failed")

    stt = WhisperTranscriber(AppConfig(), aligner=broken)
    stt.load()
    result = stt.transcribe(np.zeros(16000, dtype=np.float32), with_words=True)
    assert (result.text, result.words) == ("Hi - Could you hear me?", ())
