"""`DeviceWatcher`: PortAudio's devices compared through snapshots, and the
pacing of how often they are re-read."""

import time
import types

from zrb.llm.util.audio_devices import DeviceWatcher, read_device_snapshot


class _PortAudioError(Exception):
    """A stand-in for `sounddevice.PortAudioError`."""


class FakeSoundDevice:
    """A `sounddevice`: *devices* is its view of the hardware and *default*
    its default device pair (an index, or an ``(input, output)`` pair)."""

    PortAudioError = _PortAudioError

    def __init__(self, devices, default=-1):
        self.devices = list(devices)
        self.default = types.SimpleNamespace(device=default)
        self.is_readable = True
        self.read_error = KeyError("no view of the devices")

    def query_devices(self):
        if not self.is_readable:
            raise self.read_error
        return [dict(device) for device in self.devices]


def _builtin():
    return {"name": "BuiltIn", "max_input_channels": 2, "max_output_channels": 0}


def _airpods():
    return {"name": "AirPods", "max_input_channels": 2, "max_output_channels": 2}


def test_a_device_snapshot_reads_devices_and_their_default():
    snapshot = read_device_snapshot(FakeSoundDevice([_builtin()], default=2))

    assert snapshot == (
        ((0, "BuiltIn", 2, 0),),
        (2, 2),
    )


def test_a_default_pair_is_read_as_an_input_and_an_output():
    """The pair can be two devices, when the microphone and the speakers are
    not one device."""
    snapshot = read_device_snapshot(FakeSoundDevice([_builtin()], default=(1, 2)))

    assert snapshot == (((0, "BuiltIn", 2, 0),), (1, 2))


def test_an_unreadable_view_says_nothing():
    """A `sounddevice` without its usual fields (a mock) gives no snapshot,
    and so never says changed."""
    assert read_device_snapshot(types.SimpleNamespace()) is None
    watcher = DeviceWatcher(types.SimpleNamespace(), poll_seconds=0.0)
    assert watcher.has_changed() is False


def test_a_portaudio_failure_during_a_transition_says_nothing():
    """Unplugging a device while the snapshot is taken can leave PortAudio
    unable to list the hardware for a moment: the read says nothing, and the
    listening is not ended with it."""
    devices = FakeSoundDevice([_builtin()], default=-1)
    devices.is_readable = False
    devices.read_error = RuntimeError("PortAudio could not enumerate devices")
    assert read_device_snapshot(devices) is None


def test_a_portaudio_error_says_nothing():
    """`sounddevice.PortAudioError` — what a failed query raises on the real
    `sounddevice` — is treated like any other unreadable snapshot."""
    devices = FakeSoundDevice([_builtin()], default=-1)
    devices.is_readable = False
    devices.read_error = devices.PortAudioError("hardware hiccup")
    assert read_device_snapshot(devices) is None


def test_a_device_transition_keeps_the_last_readable_snapshot():
    """A failure in between does not end the listening, and does not wash a
    change out: the watcher keeps the last snapshot it could read, and the
    change a later readable view carries is still said."""
    devices = FakeSoundDevice([_builtin()], default=-1)
    watcher = DeviceWatcher(devices, poll_seconds=0.0)
    assert watcher.has_changed() is False

    devices.read_error = devices.PortAudioError("hardware hiccup")
    assert watcher.has_changed() is False

    devices.devices.append(_airpods())
    assert watcher.has_changed() is True


def test_a_plugged_or_unplugged_device_is_a_change():
    devices = FakeSoundDevice([_builtin()])
    watcher = DeviceWatcher(devices, poll_seconds=0.0)
    assert watcher.has_changed() is False

    devices.devices.append(_airpods())
    assert watcher.has_changed() is True

    assert watcher.has_changed() is False


def test_a_new_default_device_is_a_change():
    devices = FakeSoundDevice([_builtin(), _airpods()], default=-1)
    watcher = DeviceWatcher(devices, poll_seconds=0.0)
    assert watcher.has_changed() is False

    devices.default.device = 1
    assert watcher.has_changed() is True


def test_a_snapshot_that_does_not_read_keeps_the_last_one():
    """A read that fails in between does not wash a real change out, nor
    does it claim one: the watcher keeps the last snapshot it could read."""
    devices = FakeSoundDevice([_builtin()])
    watcher = DeviceWatcher(devices, poll_seconds=0.0)
    assert watcher.has_changed() is False

    devices.is_readable = False
    assert watcher.has_changed() is False

    devices.is_readable = True
    assert watcher.has_changed() is False


def test_a_break_reads_no_snapshot_when_there_never_was_one():
    """Nothing read at all — and a fresh view never produced a change from
    a first read that failed either."""
    devices = FakeSoundDevice([_builtin()], default=-1)
    devices.is_readable = False
    watcher = DeviceWatcher(devices, poll_seconds=0.0)
    assert watcher.has_changed() is False

    devices.is_readable = True
    devices.devices.append(_airpods())
    # The first snapshot there ever was is the one now: no change to report.
    assert watcher.has_changed() is False


def test_it_is_not_read_more_often_than_asked_for():
    """`has_changed` asks for a fresh view at most once per *poll_seconds*:
    a change within the wait is not seen, and one to it, once it is due, is."""
    devices = FakeSoundDevice([_builtin()], default=-1)
    watcher = DeviceWatcher(devices, poll_seconds=0.05)
    assert watcher.has_changed() is False

    devices.devices.append(_airpods())
    assert watcher.has_changed() is False  # sooner than asked for

    time.sleep(0.05)  # the wait, and the change is seen
    assert watcher.has_changed() is True
