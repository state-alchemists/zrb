"""Killing a hook subprocess and everything it spawned.

Called on `zrb.llm.hook.creator`'s timeout and cancellation paths, so nothing
here raises: an escaping error would swallow a ``CancelledError`` that must
propagate.
"""

import logging
import os
import signal
import subprocess

logger = logging.getLogger(__name__)


def read_process_group(process: subprocess.Popen) -> int | None:
    """The hook child's process group, derived from its pid rather than queried.

    The child is spawned with ``start_new_session=True``, so its pgid equals its
    pid. Querying ``os.getpgid`` right after spawn races the child's
    ``setsid()`` and can return our own group, which would downgrade the kill to
    the non-atomic per-pid fallback.
    """
    pid = getattr(process, "pid", None)
    if not isinstance(pid, int) or not hasattr(os, "getpgid"):
        return None
    return pid


def kill_process_tree(process: subprocess.Popen, pgid: int | None = None) -> None:
    """Kill a hook subprocess *and its descendants*. Never raises.

    ``process.kill()`` alone leaves grandchildren alive holding the output pipes.
    On POSIX this signals the process group; otherwise, or if that fails, it
    falls back to psutil's recursive child walk. The group outlives a leader
    that already exited (``cmd & disown``), which is why *pgid* is passed in
    from spawn time. Any kill that would target this process is refused.
    """
    pid = _safe_tree_kill_pid(process)
    if pgid is None:
        pgid = read_process_group(process)
    pgid = _verify_process_group(process, pgid)
    group = _safe_tree_kill_group(pgid)
    group_killed = False
    if group is not None and hasattr(os, "killpg"):
        try:
            os.killpg(group, signal.SIGKILL)
            group_killed = True
        except Exception as e:
            logger.debug(f"killpg failed for hook group {group}: {e}")
    if pid is not None and not group_killed:
        try:
            # lazy: heavy third-party — zrb.cmd.command imports psutil;
            # inside the try so an ImportError cannot escape.
            from zrb.cmd.command import kill_pid

            kill_pid(pid, print_method=logger.debug)
        except Exception as e:
            logger.debug(f"Failed to kill hook process tree {pid}: {e}")
    # Always kill the direct child too: the only handle on Windows, and the
    # last resort if both tree kills failed.
    try:
        process.kill()
    except Exception as e:
        logger.debug(f"Failed to kill hook process: {e}")


def _verify_process_group(process: subprocess.Popen, pgid: int | None) -> int | None:
    """Return *pgid* unless the OS reports a different group for *process*.

    Safe to query here: the child's ``setsid()`` race is long past by kill time.
    """
    if pgid is None or not hasattr(os, "getpgid"):
        return pgid
    pid = getattr(process, "pid", None)
    if not isinstance(pid, int):
        return pgid
    try:
        if os.getpgid(pid) != pgid:
            logger.debug(
                f"refusing group kill: OS-reported group for pid {pid} does not "
                f"match derived group {pgid} — was start_new_session set on the "
                "hook Popen?"
            )
            return None
    except Exception as e:
        logger.debug(f"could not verify process group for pid {pid}: {e}")
    return pgid


def _safe_tree_kill_pid(process: subprocess.Popen) -> int | None:
    """The pid to aim the per-process (psutil) tree kill at, or None if unsafe.

    Returns None for a missing pid, our own pid, or a pid sharing our process
    group — each of which would make ``kill_pid`` SIGKILL this process.
    """
    pid = getattr(process, "pid", None)
    if not isinstance(pid, int):
        return None
    if pid == os.getpid():
        logger.debug(f"refusing tree kill: hook pid {pid} is the current process")
        return None
    try:
        if hasattr(os, "getpgid") and os.getpgid(pid) == os.getpgid(0):
            logger.debug(
                f"refusing tree kill: hook pid {pid} shares the current process "
                "group — is start_new_session still set on the hook Popen?"
            )
            return None
    except Exception as e:
        # Already reaped: the group kill is guarded by _safe_tree_kill_group.
        logger.debug(f"could not read process group for hook pid {pid}: {e}")
    return pid


def _safe_tree_kill_group(pgid: int | None) -> int | None:
    """The process group to ``killpg``, or None when it is our own group."""
    if pgid is None:
        return None
    if not hasattr(os, "getpgid"):
        return None
    try:
        if pgid == os.getpgid(0):
            logger.debug(
                f"refusing group kill: hook group {pgid} is the current process "
                "group — is start_new_session still set on the hook Popen?"
            )
            return None
    except Exception as e:
        logger.debug(f"could not read the current process group: {e}")
        return None
    return pgid
