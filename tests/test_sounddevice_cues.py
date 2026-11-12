"""The cue player owns its stream, drops cues while one plays and never raises."""

from __future__ import annotations

import threading

import numpy as np

from english_tutor.adapters.sounddevice_cues import NullCuePlayer, SoundDeviceCuePlayer
from english_tutor.audio.cues import Cue, render

WAIT = 5.0


class FakeStream:
    def __init__(self, samplerate=44100, block=None, fail_write=False):
        self.samplerate = samplerate
        self.writes = []
        self.started = False
        self.closed = False
        self.entered = threading.Event()
        self.written = threading.Event()
        self._block = block
        self._fail_write = fail_write

    def start(self):
        self.started = True

    def write(self, data):
        self.entered.set()
        if self._block is not None:
            self._block.wait(WAIT)
        if self._fail_write:
            raise RuntimeError("device vanished")
        self.writes.append(np.array(data))
        self.written.set()

    def stop(self):
        self.started = False

    def close(self):
        self.closed = True


class Factory:
    def __init__(self, *streams, error=None):
        self.streams = list(streams)
        self.error = error
        self.calls = 0
        self.called = threading.Event()

    def __call__(self):
        self.calls += 1
        self.called.set()
        if self.error:
            raise self.error
        return self.streams.pop(0)


def play_until(player, cue, event):
    """Retry while the previous cue still holds the slot (it frees just after write())."""
    for _ in range(200):
        player.play(cue)
        if event.wait(0.05):
            return True
    return False


def test_plays_the_rendered_cue_on_its_own_stream():
    stream = FakeStream()
    player = SoundDeviceCuePlayer(Factory(stream))
    player.play(Cue.START)
    assert stream.written.wait(WAIT)
    data = stream.writes[0]
    assert data.dtype == np.float32
    assert data.shape == (len(render(Cue.START)), 1)
    assert np.array_equal(data[:, 0], render(Cue.START))
    assert stream.started
    player.close()
    assert stream.closed


def test_renders_at_the_stream_sample_rate():
    stream = FakeStream(samplerate=48000)
    player = SoundDeviceCuePlayer(Factory(stream))
    player.play(Cue.STOP)
    assert stream.written.wait(WAIT)
    assert len(stream.writes[0]) == len(render(Cue.STOP, sr=48000))
    player.close()


def test_a_cue_requested_while_one_plays_is_dropped():
    gate = threading.Event()
    stream = FakeStream(block=gate)
    player = SoundDeviceCuePlayer(Factory(stream))
    player.play(Cue.START)
    assert stream.entered.wait(WAIT)
    player.play(Cue.STOP)  # dropped: START is still playing
    player.play(Cue.ERROR)  # dropped as well
    gate.set()
    assert stream.written.wait(WAIT)
    player.close()
    assert len(stream.writes) == 1


def test_a_cue_after_the_previous_one_finished_plays():
    stream = FakeStream()
    player = SoundDeviceCuePlayer(Factory(stream))
    player.play(Cue.START)
    assert stream.written.wait(WAIT)
    stream.written.clear()
    assert play_until(player, Cue.STOP, stream.written)
    player.close()
    assert len(stream.writes) == 2


def test_play_never_raises_when_the_device_cannot_be_opened():
    factory = Factory(error=OSError("no output device"))
    player = SoundDeviceCuePlayer(factory)
    player.play(Cue.START)
    assert factory.called.wait(WAIT)
    player.close()
    assert factory.calls >= 1
    player.play(Cue.START)  # closed: silently ignored


def test_a_failing_stream_is_dropped_and_reopened_for_the_next_cue():
    broken, healthy = FakeStream(fail_write=True), FakeStream()
    factory = Factory(broken, healthy)
    player = SoundDeviceCuePlayer(factory)
    player.play(Cue.START)
    assert broken.entered.wait(WAIT)
    assert play_until(player, Cue.STOP, healthy.written)
    player.close()
    assert broken.closed
    assert healthy.writes
    assert factory.calls == 2


def test_play_after_close_is_a_silent_no_op():
    stream = FakeStream()
    player = SoundDeviceCuePlayer(Factory(stream))
    player.play(Cue.START)
    assert stream.written.wait(WAIT)
    player.close()
    player.close()  # idempotent
    player.play(Cue.ERROR)
    assert len(stream.writes) == 1


def test_close_without_ever_playing_opens_nothing():
    factory = Factory(FakeStream())
    player = SoundDeviceCuePlayer(factory)
    player.close()
    assert factory.calls == 0


def test_the_worker_is_a_daemon_thread():
    stream = FakeStream()
    player = SoundDeviceCuePlayer(Factory(stream))
    player.play(Cue.START)
    assert stream.written.wait(WAIT)
    workers = [t for t in threading.enumerate() if t.name == "cue-player"]
    assert workers and all(t.daemon for t in workers)
    player.close()


def test_null_player_is_a_no_op():
    player = NullCuePlayer()
    player.play(Cue.START)
    player.close()
