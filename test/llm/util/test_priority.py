"""`zrb.llm.util.priority`: the scheduling ask speech's threads make."""

import os
import types

import zrb.llm.util.priority as priority
from zrb.llm.util.priority import raise_priority


class _FakeLib:
    """A ctypes library whose `pthread_set_qos_class_self_np` is a stub."""

    def __init__(self, result: int | Exception) -> None:
        self._result = result
        self.asked: tuple[int, int, int] | None = None

        # A plain function, not a bound method: production writes `restype`
        # and `argtypes` onto what ctypes hands back.
        def stub(qos: int, relative: int) -> int:
            self.asked = (qos, relative, os.getpid())
            if isinstance(self._result, Exception):
                raise self._result
            return self._result

        self.pthread_set_qos_class_self_np = stub


class _FakeCtypes:
    """A ctypes whose `CDLL` answers the stub, whatever library is asked."""

    c_int = int
    c_uint32 = int

    def __init__(self, lib: _FakeLib) -> None:
        self._lib = lib

    def CDLL(self, _: str) -> _FakeLib:
        return self._lib


def fake_os(set_priority, current_nice: int = 0):
    """An `os` the POSIX ask reads, so no real attribute is needed."""
    return types.SimpleNamespace(
        setpriority=set_priority,
        getpriority=lambda *_: current_nice,
        PRIO_PROCESS=0,
    )


def run_darwin(monkeypatch, lib: _FakeLib) -> "int | None":
    return run_as(monkeypatch, "darwin", ctypes_lib=lib)


def run_as(
    monkeypatch, platform: str, ctypes_lib: _FakeLib | None = None
) -> "int | None":
    monkeypatch.setattr(priority.sys, "platform", platform)
    if ctypes_lib is not None:
        monkeypatch.setattr(priority, "ctypes", _FakeCtypes(ctypes_lib))
    return raise_priority()


def test_the_ask_answers_what_was_granted_and_nothing_escapes():
    granted = raise_priority()
    assert granted is None or isinstance(granted, int)


def test_a_declined_posix_ask_is_none(monkeypatch):
    monkeypatch.setattr(priority, "os", fake_os(None))
    assert run_as(monkeypatch, "linux") is None


def test_a_granted_posix_ask_lowers_the_nice_by_five(monkeypatch):
    asks: list[tuple[int, int, int]] = []

    def record(who_from: int, who: int, value: int) -> object:
        asks.append((who_from, who, value))
        return 0

    monkeypatch.setattr(priority, "os", fake_os(record))
    assert run_as(monkeypatch, "linux") == -5
    assert asks == [(0, 0, -5)]


def test_an_already_higher_priority_is_left_alone(monkeypatch):
    asks: list[int] = []
    monkeypatch.setattr(priority, "os", fake_os(lambda *a: asks.append(a), -10))
    assert run_as(monkeypatch, "linux") == -10
    assert asks == []


def test_a_posix_without_getpriority_still_asks(monkeypatch):
    asks: list[tuple[int, int, int]] = []
    stub = types.SimpleNamespace(setpriority=lambda *a: asks.append(a), PRIO_PROCESS=0)
    monkeypatch.setattr(priority, "os", stub)
    assert run_as(monkeypatch, "linux") == -5
    assert asks == [(0, 0, -5)]


def test_a_granted_macos_ask_is_user_initiated(monkeypatch):
    fake = _FakeLib(0)
    assert run_darwin(monkeypatch, fake) == 0x19
    assert fake.asked == (0x19, 0, os.getpid())


def test_a_refused_macos_ask_is_none_silent(monkeypatch):
    assert run_darwin(monkeypatch, _FakeLib(-1)) is None


def test_a_broken_macos_ask_is_none_silent(monkeypatch):
    assert run_darwin(monkeypatch, _FakeLib(OSError("no library"))) is None


def test_a_platform_with_no_ask_is_declined(monkeypatch):
    monkeypatch.setattr(priority, "os", types.SimpleNamespace())
    assert run_as(monkeypatch, "win32") is None


def test_an_unloadable_library_is_none_silent(monkeypatch):
    class _BrokenCtypes:
        c_int = int
        c_uint32 = int

        @staticmethod
        def CDLL(_: str) -> object:
            raise OSError("library not found")

    monkeypatch.setattr(priority, "ctypes", _BrokenCtypes)
    assert run_as(monkeypatch, "darwin") is None
