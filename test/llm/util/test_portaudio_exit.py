"""`guard_portaudio_exit`: a stuck PortAudio must not keep the process alive."""

import threading
import time
import types

from zrb.llm.util import portaudio_exit


def _guard(monkeypatch, handler, timeout):
    registered: list = []
    monkeypatch.setattr(portaudio_exit.atexit, "register", registered.append)
    monkeypatch.setattr(portaudio_exit.atexit, "unregister", lambda fn: None)
    sd = types.SimpleNamespace()
    setattr(sd, "_exit_handler", handler)
    portaudio_exit.guard_portaudio_exit(sd, timeout)
    return registered


def test_a_handler_that_never_returns_is_given_up_on(monkeypatch):
    release = threading.Event()
    [guarded] = _guard(monkeypatch, lambda: release.wait(5), timeout=0.05)

    started = time.monotonic()
    guarded()
    elapsed = time.monotonic() - started
    release.set()

    assert elapsed < 1


def test_a_handler_that_returns_is_run(monkeypatch):
    ran = threading.Event()
    [guarded] = _guard(monkeypatch, ran.set, timeout=2)

    guarded()

    assert ran.is_set()
