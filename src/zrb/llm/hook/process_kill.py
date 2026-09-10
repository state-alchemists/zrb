"""Killing a hook subprocess and everything it spawned.

The timeout and cancellation paths of `zrb.llm.hook.creator` are the only
callers. Nothing here raises: an error escaping onto those paths would be
swallowed by the creator's outer handler, turning a ``CancelledError`` that must
propagate into an ordinary failed HookResult.

The read side of the same problem lives in the sibling
`zrb.llm.hook.process_io`.
"""

import logging
import os
import signal
import subprocess

logger = logging.getLogger(__name__)


def read_process_group(process: subprocess.Popen) -> int | None:
    """The hook child's process group — derived from its pid, never queried.

    The caller always spawns with ``start_new_session=True``, which makes the
    child call ``setsid()`` before it execs — and POSIX guarantees a session
    leader's pgid equals its own pid. So the group is knowable without asking
    the OS at all.

    That matters because ``setsid()`` runs *in the child*, concurrently with
    the parent continuing past ``fork()`` — nothing orders it before the
    parent's next instruction. Querying ``os.getpgid(pid)`` right after spawn
    used to race that: under CPU contention the child can go unscheduled long
    enough for the parent to sample its *pre-setsid* pgid — still the
    parent's own, inherited one. That stale value then tripped
    ``_safe_tree_kill_group``'s self-kill guard (it looks like our own group),
    silently downgrading to the per-pid psutil fallback — which kills
    descendants one at a time rather than atomically, leaving a window where
    a killed ``sleep`` in ``sleep 5; touch x`` lets its parent shell run
    ``touch`` before its own kill lands. Deriving the value instead of
    sampling it closes that window entirely.
    """
    pid = getattr(process, "pid", None)
    if not isinstance(pid, int) or not hasattr(os, "getpgid"):
        return None
    return pid


def kill_process_tree(process: subprocess.Popen, pgid: int | None = None) -> None:
    """Kill a hook subprocess *and its descendants*.

    ``process.kill()`` alone only kills the shell spawned by ``shell=True``.
    A grandchild (``sh -c "sleep 30"`` where the shell forks rather than execs)
    survives it, and — because it inherited the stdout/stderr pipe write ends —
    keeps the reader blocked in its worker thread until the grandchild exits on
    its own. The hook returns its timeout result, but the thread stays pinned.

    POSIX: signal the process group. Elsewhere, or if the group is already gone,
    fall back to psutil's recursive child walk.

    *pgid* is derived from the child's pid by ``read_process_group`` rather
    than sampled via ``getpgid``, so it survives in the case that matters
    most: a shell that backgrounds a child and exits immediately
    (``cmd & disown``) is already gone by the timeout, and a live ``getpgid``
    would raise ESRCH — while the backgrounded descendant lives on holding the
    pipes. Only the group survives the leader, and the derived pgid is the one
    handle on it. ``_verify_process_group`` re-confirms the derived group
    against the OS at kill time (by then the child's own ``setsid()`` race is
    long past), refusing the group kill only on a genuine mismatch, and
    proceeds with the derived group when the pid is already reaped.

    Both tree kills are aimed by id, so both are catastrophic if handed one that
    is not a child's: ``killpg`` on our own group, or ``kill_pid`` on our own
    pid, SIGKILLs the running process. ``start_new_session=True`` on the Popen
    is what makes the group distinct — but this verifies it rather than trusting
    it, and skips any kill aimed at us.

    Never raises. This runs on the timeout and cancellation paths, where an
    escaping error would be swallowed by the outer handler — turning a
    ``CancelledError`` that must propagate into an ordinary failed HookResult.
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
            # lazy: heavy third-party — zrb.util.cmd.command imports psutil at
            # module level; deferring keeps it off the common (non-timeout)
            # path. Inside the try: an ImportError here would escape a
            # function documented never to raise, and the outer handler
            # would swallow the CancelledError that must propagate.
            from zrb.util.cmd.command import kill_pid

            kill_pid(pid, print_method=logger.debug)
        except Exception as e:
            logger.debug(f"Failed to kill hook process tree {pid}: {e}")
    # Always signal the direct child too: it is the only handle that exists on
    # Windows, and the last resort if both tree kills failed. Safe regardless of
    # the checks above — Popen.kill only ever targets its own child.
    try:
        process.kill()
    except Exception as e:
        logger.debug(f"Failed to kill hook process: {e}")


def _verify_process_group(process: subprocess.Popen, pgid: int | None) -> int | None:
    """Confirm *pgid* still matches the OS-reported group for *process*.

    Safe to query here (unlike at spawn time in ``read_process_group``): by
    the time ``kill_process_tree`` runs — a hook timeout or cancellation —
    the child's own ``setsid()`` has long since completed, so there is no
    race left to sample into. Catches a pid whose ``Popen`` was never
    actually started with ``start_new_session=True``.
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
        # Cannot determine the group (already reaped, or no getpgid): the
        # per-process fallback is still safe, the group kill is guarded
        # separately by _safe_tree_kill_group.
        logger.debug(f"could not read process group for hook pid {pid}: {e}")
    return pid


def _safe_tree_kill_group(pgid: int | None) -> int | None:
    """The process group to ``killpg``, or None when doing so would kill us.

    A group captured at spawn time is not self-evidently someone else's: if
    ``start_new_session`` ever stopped taking effect, the child would share our
    group and the group kill would SIGKILL zrb. Checked against our *current*
    group, which needs no lookup on the (possibly dead) child.
    """
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
        # Cannot read our own group: refuse rather than guess.
        logger.debug(f"could not read the current process group: {e}")
        return None
    return pgid
