"""Raising a thread's scheduling priority, best-effort."""

from __future__ import annotations

import ctypes
import logging
import os
import sys

logger = logging.getLogger(__name__)

# Above the default and background QoS classes, below the interactive one a
# UI holds: synthesis is work the listener is waiting on, not a redraw.
_QOS_CLASS_USER_INITIATED = 0x19
_NICE_ASK = -5


def raise_priority() -> "int | None":
    """Ask for a higher scheduling priority on the calling thread.

    Answers what the machine granted — the QoS class on macOS, the nice value
    on POSIX — or None when it declined. Never raises: speech keeps speaking
    at the priority a busy machine would have it keep anyway.
    """
    try:
        if sys.platform == "darwin":
            if _is_macos_priority_raise_granted():
                return _QOS_CLASS_USER_INITIATED
            return None
        if _is_posix_priority_raise_granted():
            return _NICE_ASK
        return None
    except (OSError, AttributeError, ValueError) as exc:
        logger.debug(f"Scheduling priority not raised here: {exc}")
        return None


def _is_macos_priority_raise_granted() -> bool:
    """Raise this thread's macOS QoS class to user-initiated."""
    pthread = ctypes.CDLL("libpthread.dylib")
    set_qos = pthread.pthread_set_qos_class_self_np
    set_qos.restype = ctypes.c_int
    set_qos.argtypes = (ctypes.c_uint32, ctypes.c_int)
    return set_qos(_QOS_CLASS_USER_INITIATED, 0) == 0


def _is_posix_priority_raise_granted() -> bool:
    """Lower this thread's nice value; only an rlimit lets the raise through."""
    set_priority = getattr(os, "setpriority", None)
    if set_priority is None:
        return False
    try:
        set_priority(os.PRIO_PROCESS, 0, _NICE_ASK)
    except OSError:
        return False
    return True
