"""`DeviceWatcher`: PortAudio's devices compared through snapshots, and the
pacing of how often they are re-read."""

import time
import types

from zrb.llm.util.audio_devices import DeviceWatcher, read_device_snapshot


class _PortAudioError(Exception):
    """A stand-in for `sounddevice.PortAudioError`."""


class FakeSoundDevice:
    """A `sounddevice`: *devices* is its view of the hardware, and
    *default_in*/*default_out* are the indices `query_devices(kind=...)`
    resolves — what a stream with no *device* named would open. With none
    available, the view answers PortAudio's own way, `PortAudioError`."""

    PortAudioError = _PortAudioError

    def __init__(self, devices, default_in=0, default_out=0):
        self.devices = list(devices)
        self.default_in = default_in
        self.default_out = default_out
        self.is_readable = True
        self.read_error = KeyError("no view of the devices")

    def query_devices(self, device=None, kind=None):
        if not self.is_readable:
            raise self.read_error
        if device is None and kind is not None:
            index = self.default_in if kind == "input" else self.default_out
            if not isinstance(index, int) or index < 0 or index >= len(self.devices):
                raise self.PortAudioError(f"Error querying device {index}")
            return self.device_at(index)
        return [self.device_at(index) for index in range(len(self.devices))]

    def device_at(self, index):
        return {**self.devices[index], "index": index}


def _builtin():
    return {"name": "BuiltIn", "max_input_channels": 2, "max_output_channels": 0}


def _airpods():
    return {"name": "AirPods", "max_input_channels": 2, "max_output_channels": 2}


def _speakers():
    return {
        "name": "Monitor Speakers",
        "max_input_channels": 0,
        "max_output_channels": 2,
    }


def test_a_device_snapshot_reads_devices_and_their_defaults():
    snapshot = read_device_snapshot(
        FakeSoundDevice([_builtin(), _airpods()], default_in=0, default_out=1)
    )

    assert snapshot == (
        ((0, "BuiltIn", 2, 0), (1, "AirPods", 2, 2)),
        (0, 1),
    )


def test_the_defaults_are_what_portaudio_would_open():
    """The pair is the resolved default microphone and speaker index, as
    `query_devices(kind=...)` answers it — a hand-set preference in
    `sd.default.device` of some older shape is not what the snapshot says."""
    fake = FakeSoundDevice([_builtin(), _airpods()], default_in=1, default_out=0)

    assert read_device_snapshot(fake)[1] == (1, 0)


def test_an_operating_system_default_change_is_a_change():
    """The OS default microphone moved to a device that was there all along:
    the device list says the same, the resolved default does not, and that
    is what the watch is for."""
    devices = FakeSoundDevice([_builtin(), _airpods()], default_in=0, default_out=1)
    watcher = DeviceWatcher(devices, poll_seconds=0.0)
    assert watcher.has_changed() is False

    devices.default_in = 1
    assert watcher.has_changed() is True
    assert watcher.has_changed() is False


def test_an_unreadable_view_says_nothing():
    """A `sounddevice` without its usual fields (a mock) gives no snapshot,
    and so never says changed."""
    assert read_device_snapshot(types.SimpleNamespace()) is None
    watcher = DeviceWatcher(types.SimpleNamespace(), poll_seconds=0.0)
    assert watcher.has_changed() is False


def test_a_device_that_is_not_there_resolved_to_nothing():
    """`query_devices(kind=...)` of a kind with no device raises — PortAudio
    answers `Error querying device -1` for its `paNoDevice` — and a default
    of nothing is no readable snapshot."""
    devices = FakeSoundDevice([_built_in_with_output()], default_in=0, default_out=-1)
    assert read_device_snapshot(devices) is None


def _built_in_with_output():
    return {
        "name": "BuiltIn",
        "max_input_channels": 2,
        "max_output_channels": 2,
    }


def test_a_portaudio_failure_during_a_transition_says_nothing():
    """Unplugging a device while the snapshot is taken can leave PortAudio
    unable to list the hardware for a moment: the read says nothing, and the
    listening is not ended with it."""
    devices = FakeSoundDevice([_builtin()])
    devices.is_readable = False
    devices.read_error = RuntimeError("PortAudio could not enumerate devices")
    assert read_device_snapshot(devices) is None


def test_a_portaudio_error_says_nothing():
    """`sounddevice.PortAudioError` — what a failed query raises on the real
    `sounddevice` — is treated like any other unreadable snapshot."""
    devices = FakeSoundDevice([_builtin()])
    devices.is_readable = False
    devices.read_error = devices.PortAudioError("hardware hiccup")
    assert read_device_snapshot(devices) is None


def test_a_device_transition_keeps_the_last_readable_snapshot():
    """A failure in between does not end the listening, and does not wash a
    change out: the watcher keeps the last snapshot it could read, and the
    change a later readable view carries is still said."""
    devices = FakeSoundDevice([_builtin()])
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
    devices = FakeSoundDevice([_builtin()])
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
    # A generous poll window: a tight one can itself elapse between the two
    # calls below under a slow/contended CI runner, making the "sooner than
    # asked for" check falsely see the poll as due.
    poll_seconds = 2.0
    devices = FakeSoundDevice([_builtin()])
    watcher = DeviceWatcher(devices, poll_seconds=poll_seconds)
    assert watcher.has_changed() is False

    devices.devices.append(_airpods())
    assert watcher.has_changed() is False  # sooner than asked for

    time.sleep(poll_seconds)  # the wait, and the change is seen
    assert watcher.has_changed() is True
