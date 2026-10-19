"""PortAudio's view of the audio hardware, compared through a snapshot.

PortAudio has no portable callback for a device being plugged in, unplugged,
or made the default, so the portable signal for a change is what
`sd.query_devices()` and `sd.default.device` say now, next to what they said a
moment ago. `DeviceWatcher` snapshots when asked and says whether that changed.
"""

from __future__ import annotations

import time

# How often the snapshot is re-read at most, in `has_changed`.
DEFAULT_POLL_SECONDS = 2.0

# A snapshot read that does not come out as zrb expects (a fake, or a device
# entry missing its fields) says nothing, instead of ending the listening.
_SNAPSHOT_ERRORS = (AttributeError, IndexError, KeyError, TypeError, ValueError)


def _snapshot_errors(sd: object) -> "tuple[type[BaseException], ...]":
    """The errors above, plus the ones a device transition raises: while a
    device is unplugged or made default, PortAudio can fail for a moment to
    list the devices or name the default, where a read that says nothing
    keeps the listening going. `PortAudioError` is what the real
    *sounddevice* raises, when the *sd* at hand has one."""
    port_audio_error = getattr(sd, "PortAudioError", None)
    extra = (
        (port_audio_error,)
        if isinstance(port_audio_error, type)
        and issubclass(port_audio_error, BaseException)
        else ()
    )
    return (RuntimeError, OSError) + _SNAPSHOT_ERRORS + extra


def read_device_snapshot(
    sd: object,
) -> "tuple[tuple[tuple[int, str, int, int], ...], tuple[int, int]] | None":
    """PortAudio's devices and default device, as one value to compare, or
    ``None`` when the view cannot be read.

    A device reads as its index, name and the channels it can open, which make
    one out when it is plugged, unplugged or renamed. The defaults read as the
    *resolved* default microphone and speaker (`query_devices(kind="input")`
    and `"output"`) — what PortAudio opens without being asked for one, so
    the system default a change of setting has moved is seen — rather than
    `sd.default.device`, which carries at most what somebody set by hand.
    A read that raises (a fake, a device entry missing its fields, or a
    PortAudio failure during a device transition) is no snapshot.
    """
    try:
        query = getattr(sd, "query_devices")
        devices = tuple(
            (
                int(index),
                entry["name"],
                int(entry["max_input_channels"]),
                int(entry["max_output_channels"]),
            )
            for index, entry in enumerate(query())
        )
        default_input = int(query(kind="input")["index"])
        default_output = int(query(kind="output")["index"])
        return devices, (default_input, default_output)
    except _snapshot_errors(sd):
        return None


class DeviceWatcher:
    """Keeps PortAudio's device snapshot, re-reading it at most once every
    *poll_seconds*: `has_changed` says whether the devices or their default
    changed since the last ask."""

    def __init__(self, sd: object, poll_seconds: float = DEFAULT_POLL_SECONDS) -> None:
        self._sd = sd
        self._poll_seconds = poll_seconds
        self._snapshot = read_device_snapshot(sd)
        # The first ask is at once; after it, no more often than asked for.
        self._last_ask = 0.0

    def has_changed(self) -> bool:
        """Whether PortAudio's devices or their default changed since the
        last ask. A snapshot that does not read says nothing, and keeps the
        last one it could read, so a broken read in between does not wash a
        real change out."""
        now = time.monotonic()
        if now < self._last_ask + self._poll_seconds:
            return False
        self._last_ask = now
        snapshot = read_device_snapshot(self._sd)
        if snapshot is None:
            return False
        changed = self._snapshot is not None and snapshot != self._snapshot
        self._snapshot = snapshot
        return changed
