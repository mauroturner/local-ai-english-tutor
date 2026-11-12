"""Device deduplication and default resolution (pure, no PortAudio)."""

from __future__ import annotations

from english_tutor.audio.devices import dedupe_input_devices, resolve_default

HOSTAPIS = [{"name": "MME"}, {"name": "Windows DirectSound"}, {"name": "Windows WASAPI"}]


def dev(name, hostapi, max_in=2, rate=48000.0):
    return {
        "name": name, "hostapi": hostapi, "max_input_channels": max_in,
        "max_output_channels": 0, "default_samplerate": rate,
    }


def test_wasapi_beats_directsound_and_mme():
    devices = [
        dev("Microphone (USB)", 0),
        dev("Microphone (USB)", 1),
        dev("Microphone (USB)", 2),
    ]
    result = dedupe_input_devices(devices, HOSTAPIS)
    assert len(result) == 1
    assert result[0].index == 2 and result[0].hostapi == "Windows WASAPI"
    assert result[0].priority == 3


def test_mme_truncated_name_merges_and_keeps_full_name():
    full = "Microphone (Realtek High Definition Audio)"
    assert len(full) > 31
    devices = [dev(full[:31], 0), dev(full, 2)]
    result = dedupe_input_devices(devices, HOSTAPIS)
    assert len(result) == 1
    assert result[0].name == full and result[0].index == 1


def test_output_only_devices_excluded():
    devices = [dev("Speakers", 2, max_in=0), dev("Mic", 2)]
    assert [d.name for d in dedupe_input_devices(devices, HOSTAPIS)] == ["Mic"]


def test_channels_capped_at_two_and_rate_int():
    result = dedupe_input_devices([dev("Array", 2, max_in=8, rate=44100.0)], HOSTAPIS)
    assert result[0].channels == 2 and result[0].default_samplerate == 44100


def test_sorted_by_name():
    devices = [dev("b mic", 2), dev("A mic", 2)]
    assert [d.name for d in dedupe_input_devices(devices, HOSTAPIS)] == ["A mic", "b mic"]


def test_unknown_api_has_lowest_priority():
    hostapis = HOSTAPIS + [{"name": "ASIO"}]
    devices = [dev("Mic", 3), dev("Mic", 0)]
    result = dedupe_input_devices(devices, hostapis)
    assert result[0].hostapi == "MME"


def test_resolve_default_maps_raw_index_to_deduped_device():
    raw = [dev("Mic (USB)", 0), dev("Mic (USB)", 2)]
    devices = dedupe_input_devices(raw, HOSTAPIS)
    assert resolve_default(devices, 0, raw).index == 1


def test_resolve_default_falls_back_to_first_device():
    raw = [dev("Mic", 2)]
    devices = dedupe_input_devices(raw, HOSTAPIS)
    assert resolve_default(devices, None, raw).name == "Mic"
    assert resolve_default(devices, 99, raw).name == "Mic"
    assert resolve_default([], None, raw) is None
