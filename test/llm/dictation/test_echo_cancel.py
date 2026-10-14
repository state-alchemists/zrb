"""Tests for the echo-cancelled microphone (macOS voice processing)."""

import asyncio
import sys
from unittest.mock import MagicMock, call, patch

import pytest

from zrb.llm.dictation.echo_cancel import (
    EchoCancelledMicrophone,
    Rechunker,
    Resampler,
    get_unavailable_reason,
)

np = pytest.importorskip("numpy")


def _tone(rate, seconds, hz=440.0):
    t = np.arange(int(rate * seconds)) / rate
    return (0.5 * np.sin(2 * np.pi * hz * t)).astype(np.float32)


def _peak_hz(signal, rate):
    spectrum = np.abs(np.fft.rfft(signal))
    return np.fft.rfftfreq(len(signal), 1 / rate)[np.argmax(spectrum)]


def test_resampler_downsamples_and_keeps_the_pitch():
    resampler = Resampler(np, 48000, 16000)

    out = resampler.convert(_tone(48000, 1.0))

    assert abs(len(out) - 16000) <= 1
    assert out.dtype == np.float32
    assert abs(_peak_hz(out, 16000) - 440) < 2


def test_resampler_leaves_no_seam_between_blocks():
    signal = _tone(48000, 0.5)
    whole = Resampler(np, 48000, 16000).convert(signal)
    split = Resampler(np, 48000, 16000)

    pieces = [split.convert(signal[i : i + 1234]) for i in range(0, len(signal), 1234)]

    assert np.allclose(np.concatenate(pieces), whole, atol=1e-5)


def test_resampler_handles_a_fractional_ratio():
    out = Resampler(np, 44100, 16000).convert(_tone(44100, 1.0))

    assert abs(len(out) - 16000) <= 1
    assert abs(_peak_hz(out, 16000) - 440) < 2


def test_resampler_filters_out_what_would_fold_back():
    # 12 kHz is over 16 kHz audio's 8 kHz Nyquist: unfiltered it would fold
    # back to 4 kHz, into the band the transcriber hears.
    out = Resampler(np, 48000, 16000).convert(_tone(48000, 1.0, hz=12000))

    assert np.sqrt(np.mean(out[100:] ** 2)) < 0.01


def test_resampler_at_the_same_rate_passes_audio_through():
    signal = _tone(16000, 0.1)

    assert np.allclose(Resampler(np, 16000, 16000).convert(signal), signal)


def test_rechunker_emits_whole_blocks_and_keeps_the_rest():
    emitted = []
    rechunker = Rechunker(np, 4, emitted.append)

    rechunker.append(np.arange(6, dtype=np.float32))
    rechunker.append(np.arange(6, 9, dtype=np.float32))

    assert [block.tolist() for block in emitted] == [[0, 1, 2, 3], [4, 5, 6, 7]]


def test_unavailable_off_macos(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")

    assert "echo-cancel module" in get_unavailable_reason(None)


def test_unavailable_with_a_named_device(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")

    assert "LLM_DICTATION_DEVICE" in get_unavailable_reason("2")


def test_unavailable_without_pyobjc(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    with patch("importlib.util.find_spec", return_value=None):
        assert "pyobjc-framework-AVFoundation" in get_unavailable_reason(None)


def test_available_on_macos_with_pyobjc(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    with patch("importlib.util.find_spec", return_value=object()):
        assert get_unavailable_reason(None) is None


class _FakeBuffer:
    def __init__(self, samples):
        self._samples = samples

    def frameLength(self):
        return len(self._samples)

    def floatChannelData(self):
        channel = MagicMock()
        channel.as_buffer.side_effect = lambda n: self._samples[:n].tobytes()
        return [channel]


def _fake_avfoundation(rate=48000.0, enabled=(True, None), started=(True, None)):
    avf = MagicMock()
    engine = avf.AVAudioEngine.alloc.return_value.init.return_value
    node = engine.inputNode.return_value
    node.setVoiceProcessingEnabled_error_.return_value = enabled
    node.outputFormatForBus_.return_value.sampleRate.return_value = rate
    engine.startAndReturnError_.return_value = started
    engine.isRunning.return_value = True
    return avf, engine, node


def _start(avf, blocksize=1600):
    blocks = []
    microphone = EchoCancelledMicrophone(
        np, lambda data, frames, t, s: blocks.append(data), 16000, blocksize
    )
    with patch("zrb.llm.dictation.echo_cancel.import_avfoundation", return_value=avf):
        microphone.start()
    return microphone, blocks


def test_microphone_builds_the_output_side_before_voice_processing():
    avf, engine, _ = _fake_avfoundation()

    _start(avf)

    calls = engine.mock_calls
    assert calls.index(call.outputNode()) < calls.index(
        call.inputNode().setVoiceProcessingEnabled_error_(True, None)
    )


def test_microphone_hands_on_blocks_at_the_transcriber_rate():
    avf, _, node = _fake_avfoundation()
    microphone, blocks = _start(avf)
    tap = node.installTapOnBus_bufferSize_format_block_.call_args.args[3]

    for _ in range(3):
        tap(_FakeBuffer(_tone(48000, 0.1)), None)

    assert node.installTapOnBus_bufferSize_format_block_.call_args.args[1] == 4800
    assert len(blocks) >= 2
    assert all(block.shape == (1600, 1) for block in blocks)
    assert microphone.active


def test_microphone_asks_for_the_least_ducking():
    avf, _, node = _fake_avfoundation()

    _start(avf)

    node.setVoiceProcessingOtherAudioDuckingConfiguration_.assert_called_once_with(
        (False, avf.AVAudioVoiceProcessingOtherAudioDuckingLevelMin)
    )


def test_microphone_skips_ducking_where_macos_has_no_setting():
    avf, engine, _ = _fake_avfoundation()
    old_node = MagicMock(
        spec=[
            "setVoiceProcessingEnabled_error_",
            "outputFormatForBus_",
            "installTapOnBus_bufferSize_format_block_",
            "removeTapOnBus_",
        ]
    )
    old_node.setVoiceProcessingEnabled_error_.return_value = (True, None)
    old_node.outputFormatForBus_.return_value.sampleRate.return_value = 48000.0
    engine.inputNode.return_value = old_node

    microphone, _ = _start(avf)

    assert microphone.active


def _assert_released(engine, node):
    """The tap is off, the engine stopped, and voice processing off again."""
    node.removeTapOnBus_.assert_called_once_with(0)
    engine.stop.assert_called_once_with()
    node.setVoiceProcessingEnabled_error_.assert_called_with(False, None)


def test_microphone_raises_and_releases_when_voice_processing_will_not_switch_on():
    avf, engine, node = _fake_avfoundation(enabled=(False, "no"))

    with pytest.raises(RuntimeError, match="would not switch on"):
        _start(avf)
    _assert_released(engine, node)


def test_microphone_raises_and_releases_when_the_engine_will_not_start():
    avf, engine, node = _fake_avfoundation(started=(False, "-10875"))

    with pytest.raises(RuntimeError, match="would not start"):
        _start(avf)
    _assert_released(engine, node)


@pytest.mark.parametrize("step", ["prepare", "startAndReturnError_"])
def test_microphone_releases_the_engine_when_cocoa_raises(step):
    avf, engine, node = _fake_avfoundation()
    getattr(engine, step).side_effect = ValueError("NSInternalInconsistencyException")

    with pytest.raises(RuntimeError, match="NSInternalInconsistencyException"):
        _start(avf)
    _assert_released(engine, node)


def test_microphone_release_runs_every_step_when_one_fails():
    avf, engine, node = _fake_avfoundation()
    engine.prepare.side_effect = ValueError("route lost")
    node.removeTapOnBus_.side_effect = ValueError("no tap")

    with pytest.raises(RuntimeError) as raised:
        _start(avf)

    engine.stop.assert_called_once_with()
    node.setVoiceProcessingEnabled_error_.assert_called_with(False, None)
    # The release failure is what surfaces; the startup failure is kept
    # as its context, so neither is lost.
    assert "no tap" in str(raised.value)
    assert "route lost" in str(raised.value.__cause__.__context__)


def test_microphone_close_releases_the_engine_once():
    avf, engine, node = _fake_avfoundation()
    microphone, _ = _start(avf)

    microphone.close()
    microphone.close()

    _assert_released(engine, node)
    assert not microphone.active


def test_microphone_close_stops_the_engine_even_when_the_tap_will_not_come_off():
    avf, engine, node = _fake_avfoundation()
    microphone, _ = _start(avf)
    node.removeTapOnBus_.side_effect = ValueError("no tap")

    with pytest.raises(ValueError, match="no tap"):
        microphone.close()

    engine.stop.assert_called_once_with()
    assert not microphone.active


def test_microphone_is_inactive_once_macos_stops_the_engine():
    avf, engine, _ = _fake_avfoundation()
    microphone, _ = _start(avf)

    engine.isRunning.return_value = False

    assert not microphone.active


@pytest.mark.asyncio
async def test_microphone_confirms_audio_once_a_block_arrives():
    avf, _, node = _fake_avfoundation()
    microphone, _ = _start(avf)
    tap = node.installTapOnBus_bufferSize_format_block_.call_args.args[3]
    tap(_FakeBuffer(_tone(48000, 0.1)), None)

    await microphone.confirm_audio(timeout=1.0)


@pytest.mark.asyncio
async def test_microphone_confirm_fails_at_once_when_macos_stops_the_engine():
    # A Bluetooth headset: voice processing starts, then macOS stops it.
    avf, engine, _ = _fake_avfoundation()
    microphone, _ = _start(avf)
    engine.isRunning.return_value = False

    with pytest.raises(RuntimeError, match="heard nothing"):
        await asyncio.wait_for(microphone.confirm_audio(timeout=60), timeout=1)


@pytest.mark.asyncio
async def test_microphone_confirm_fails_when_no_audio_arrives_in_time():
    avf, _, _ = _fake_avfoundation()
    microphone, _ = _start(avf)

    with pytest.raises(RuntimeError, match="heard nothing"):
        await microphone.confirm_audio(timeout=0.1)
