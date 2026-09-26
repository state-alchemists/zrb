import os
import shutil
import sys
from typing import Any, NamedTuple


class TerminalSize(NamedTuple):
    columns: int
    lines: int


def is_real_console(stream: Any) -> bool:
    """Confirm *stream* is backed by an actual console, not just any
    character-special device.

    Windows' `isatty()` (the C runtime's `_isatty`) returns True for any
    character device, which includes the NUL device — so stdin redirected
    from NUL (`< NUL`, `subprocess.DEVNULL`) is misreported as interactive,
    unlike POSIX where `isatty()` already makes this distinction correctly.
    `GetConsoleMode` only succeeds against a genuine console handle, so it
    disambiguates where `isatty()` alone cannot. POSIX needs no such check.
    """
    if os.name != "nt":
        return True
    try:
        # lazy: platform-only — `msvcrt` does not exist off Windows, so this
        # cannot hoist; and `ctypes` costs ~14ms every POSIX start for a
        # branch POSIX returns above without reaching.
        import ctypes
        import msvcrt

        handle = msvcrt.get_osfhandle(stream.fileno())
        mode = ctypes.c_uint32()
        return bool(ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)))
    except Exception:
        return False


def get_terminal_size(fallback: tuple[int, int] = (80, 24)) -> TerminalSize:
    """
    Get the terminal size in a robust way, even when stdout is redirected.
    """
    for stream in (sys.__stdout__, sys.__stderr__, sys.__stdin__):
        if stream is not None:
            try:
                size = os.get_terminal_size(stream.fileno())
                return TerminalSize(columns=size.columns, lines=size.lines)
            except (AttributeError, ValueError, OSError):
                continue

    # Windows: CONOUT$ still reaches the console when stdout/stderr are redirected.
    if os.name == "nt":
        try:
            fd = os.open("CONOUT$", os.O_RDONLY)
            try:
                size = os.get_terminal_size(fd)
                return TerminalSize(columns=size.columns, lines=size.lines)
            finally:
                os.close(fd)
        except Exception:
            pass

    # Honors COLUMNS/LINES, then *fallback*.
    try:
        size = shutil.get_terminal_size(fallback=fallback)
        return TerminalSize(columns=size.columns, lines=size.lines)
    except Exception:
        return TerminalSize(columns=fallback[0], lines=fallback[1])
