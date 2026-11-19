"""PortAudio's view of the audio hardware, and the machine's own default
output beside it.

PortAudio has no portable callback for a device being plugged in, unplugged,
or made the default, so the portable signal for a change is what it says now
next to what it said a moment ago; `DeviceWatcher` snapshots that. It reaches
only as far as PortAudio reads the devices again at all, which on macOS it does
not: PortAudio 19.7 listed the one device it had found when it was started for
four minutes, while a headset was plugged in and made the default. So the
machine's own default output is read from CoreAudio
(`read_system_default_output`), which is what moves on a plug or an unplug.
"""

from __future__ import annotations

import ctypes
import functools
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


def read_portaudio_default_output(sd: object) -> "str | None":
    """The name of the output PortAudio plays on without being asked for a
    device, or ``None`` when it cannot be read. What it answers is from when it
    was started, so this is the output a stream would use now, not necessarily
    the one the machine is set to play on."""
    try:
        return str(getattr(sd, "query_devices")(kind="output")["name"])
    except _snapshot_errors(sd):
        return None


def read_system_default_output(sd: object) -> "str | None":
    """The name of the output the machine itself is set to play on, or ``None``
    when it cannot be told.

    On macOS this is asked of CoreAudio, which moves when a device is plugged
    in or made the default; PortAudio is no help there, since it keeps the
    devices, and the default among them, that it read when it was started.
    Anywhere else PortAudio's own word on the default is all there is, which
    makes this agree with `read_portaudio_default_output` by construction."""
    name = _read_the_system_default_output()
    if name is not None:
        return name
    return read_portaudio_default_output(sd)


# CoreAudio's system object, and the four-character selectors its properties
# are addressed by, on the global scope and the main element.
_SYSTEM_OBJECT = 1
_GLOBAL_SCOPE = 0x676C6F62  # 'glob'
_MAIN_ELEMENT = 0
_DEFAULT_OUTPUT = 0x644F7574  # 'dOut'
_OBJECT_NAME = 0x6C6E616D  # 'lnam'
_DEVICE_ID_BYTES = 4
_UTF8 = 0x08000100
_CORE_AUDIO_PATH = "/System/Library/Frameworks/CoreAudio.framework/CoreAudio"
_CORE_FOUNDATION_PATH = (
    "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
)


class _PropertyAddress(ctypes.Structure):
    _fields_ = [
        ("selector", ctypes.c_uint32),
        ("scope", ctypes.c_uint32),
        ("element", ctypes.c_uint32),
    ]


@functools.cache
def _core_audio() -> "tuple[ctypes.CDLL, ctypes.CDLL] | None":
    """CoreAudio and CoreFoundation with the calls used here typed, or ``None``
    where they are not there (anything but macOS). Read once: a machine's
    frameworks do not change under the process.

    The calls are typed rather than left to ctypes' guesses, because a wrong
    guess about the arguments of a C function that returns a pointer reads a
    register that was never written."""
    try:
        core_audio = ctypes.CDLL(_CORE_AUDIO_PATH)
        core_foundation = ctypes.CDLL(_CORE_FOUNDATION_PATH)
        get_property = core_audio.AudioObjectGetPropertyData
        get_property.restype = ctypes.c_int32
        get_property.argtypes = [
            ctypes.c_uint32,
            ctypes.POINTER(_PropertyAddress),
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.c_void_p,
        ]
        get_name = core_foundation.CFStringGetCString
        get_name.restype = ctypes.c_bool
        get_name.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_long,
            ctypes.c_uint32,
        ]
        get_length = core_foundation.CFStringGetLength
        get_length.restype = ctypes.c_long
        get_length.argtypes = [ctypes.c_void_p]
    except (AttributeError, OSError):
        return None
    return core_audio, core_foundation


def _read_property(owner: int, selector: int, size: int) -> "bytes | None":
    """One CoreAudio property of *owner*, *size* bytes of it, or ``None`` when
    it does not read as that."""
    libraries = _core_audio()
    if libraries is None:
        return None
    core_audio, _ = libraries
    address = _PropertyAddress(selector, _GLOBAL_SCOPE, _MAIN_ELEMENT)
    data = ctypes.create_string_buffer(size)
    size_read = ctypes.c_uint32(size)
    status = core_audio.AudioObjectGetPropertyData(
        owner, ctypes.byref(address), 0, None, ctypes.byref(size_read), data
    )
    if status != 0 or size_read.value != size:
        return None
    return data.raw


def _read_the_system_default_output() -> "str | None":
    """The name of the output the machine plays on, read from CoreAudio, or
    ``None`` where CoreAudio cannot be asked. The name is the device's own, in
    UTF-8; the reference it comes as belongs to the system and is not freed."""
    raw = _read_property(_SYSTEM_OBJECT, _DEFAULT_OUTPUT, _DEVICE_ID_BYTES)
    if raw is None:
        return None
    device = int.from_bytes(raw, "little")
    libraries = _core_audio()
    if not device or libraries is None:
        return None
    _, core_foundation = libraries
    raw = _read_property(device, _OBJECT_NAME, ctypes.sizeof(ctypes.c_void_p))
    if raw is None:
        return None
    reference = int.from_bytes(raw, "little")
    if not reference:
        return None
    length = core_foundation.CFStringGetLength(ctypes.c_void_p(reference))
    name = ctypes.create_string_buffer(length * 4 + 1)
    is_read = core_foundation.CFStringGetCString(
        ctypes.c_void_p(reference), name, len(name), _UTF8
    )
    return name.value.decode(errors="replace") if is_read else None
