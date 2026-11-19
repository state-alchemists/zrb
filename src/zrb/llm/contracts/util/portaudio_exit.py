"""Keeping PortAudio's exit handler from holding the process.

sounddevice terminates PortAudio from an `atexit` handler, which stops every
stream still open. On macOS that call can block for good when CoreAudio has
deadlocked, and the process then ignores Ctrl+C: quitting is what runs it.

Shared by both voice features, so neither imports the other.
"""

from __future__ import annotations

import atexit
import logging
import threading

logger = logging.getLogger(__name__)

_EXIT_TIMEOUT_SECONDS = 2.0
_GUARDED_MARK = "zrb_exit_guarded"


def guard_portaudio_exit(sd: object, timeout: float = _EXIT_TIMEOUT_SECONDS) -> None:
    """Replace sounddevice's exit handler with one that gives up after
    *timeout* seconds, so a stuck audio service cannot keep the process from
    ending. Once per process; the device is released when the process is gone."""
    handler = getattr(sd, "_exit_handler", None)
    if handler is None or getattr(sd, _GUARDED_MARK, False):
        return
    setattr(sd, _GUARDED_MARK, True)
    atexit.unregister(handler)

    def guarded() -> None:
        finished = threading.Event()

        def run() -> None:
            try:
                handler()
            finally:
                finished.set()

        threading.Thread(target=run, name="zrb-portaudio-exit", daemon=True).start()
        if not finished.wait(timeout):
            logger.warning(f"PortAudio did not stop in {timeout} seconds; exiting")

    atexit.register(guarded)
