"""Safety guards on the hook tree kill.

The happy paths (a real timed-out hook, a descendant of an exited shell) are
driven end-to-end from `test_creator_subprocess.py`; what is left here is the
one thing that cannot be tested that way, because getting it wrong takes the
test runner down with it.
"""

import os
from unittest.mock import patch

from zrb.llm.hook.process_kill import kill_process_tree, read_process_group

# A pid/group high enough that no live process owns it, so getpgid and killpg
# both raise ProcessLookupError — the "already gone" shape the fallbacks exist
# for. Not our own pid or group, so the safety guards let the kill through.
_DEAD_PID = 999999


class _KillRecordingProc:
    """A Popen stand-in that records whether the direct child kill ran."""

    returncode = None

    def __init__(self, pid=None):
        self.killed = False
        if pid is not None:
            self.pid = pid

    def kill(self):
        self.killed = True


def test_kill_process_tree_never_targets_zrbs_own_pid():
    """A tree kill aimed at our own pid must be refused.

    `kill_pid` (psutil, recursive) on our pid SIGKILLs the running zrb.
    `start_new_session=True` on the hook Popen is what keeps the child distinct,
    but this verifies rather than trusts it.

    Regression: an earlier guard blocked only the killpg vector and then fell
    through to kill_pid with the same pid — which killed the test runner
    outright (exit 137).
    """
    process = _KillRecordingProc(os.getpid())

    with patch("zrb.util.cmd.command.kill_pid") as mock_kill_pid:
        # Surviving this call at all is half the assertion: a self-targeted tree
        # kill terminates the process instead of returning.
        kill_process_tree(process)

    mock_kill_pid.assert_not_called()
    assert process.killed, "fell back to no kill at all"


def test_kill_process_tree_never_targets_zrbs_own_process_group():
    """A tree kill aimed at a pid sharing our process group must be refused.

    `killpg` on our group SIGKILLs the running zrb along with the hook. The pid
    here is not ours, so only the group check can catch it — which is what makes
    this distinct from the own-pid case above.
    """
    process = _KillRecordingProc(_DEAD_PID)

    # Every getpgid answer is our group, so the hook's pid looks like a group
    # member: both the per-pid and the group vector must back off.
    with (
        patch("os.getpgid", return_value=4242),
        patch("zrb.util.cmd.command.kill_pid") as mock_kill_pid,
    ):
        kill_process_tree(process, pgid=4242)

    mock_kill_pid.assert_not_called()
    assert process.killed, "fell back to no kill at all"


def test_kill_process_tree_tolerates_a_pidless_process():
    """Must not raise on the cancellation path when handed a mock without a pid."""
    killed = {"done": False}

    class _Proc:
        returncode = None

        def kill(self):
            killed["done"] = True

    kill_process_tree(_Proc())
    assert killed["done"]


def test_kill_process_tree_falls_back_to_psutil_when_killpg_fails():
    """A failed group kill must still reach the tree via the psutil child walk.

    The group is the primary handle, but it is gone the moment nothing in it is
    alive — and a hook whose shell exited while a descendant lingers is exactly
    the case the fallback exists for.
    """
    killed = {"direct": False}

    class _Proc:
        returncode = None
        pid = _DEAD_PID

        def kill(self):
            killed["direct"] = True

    with patch("zrb.util.cmd.command.kill_pid") as mock_kill_pid:
        kill_process_tree(_Proc(), pgid=_DEAD_PID)

    # killpg raised (no such group), so the per-pid walk had to carry the kill.
    mock_kill_pid.assert_called_once()
    assert mock_kill_pid.call_args.args[0] == _DEAD_PID
    # The direct child kill always runs as the last resort.
    assert killed["direct"] is True


def test_kill_process_tree_survives_a_failing_psutil_walk():
    """An error out of the psutil walk is swallowed — this runs on the
    cancellation path, where an escaping error would turn a CancelledError that
    must propagate into an ordinary failed HookResult."""
    killed = {"direct": False}

    class _Proc:
        returncode = None
        pid = _DEAD_PID

        def kill(self):
            killed["direct"] = True

    with patch("zrb.util.cmd.command.kill_pid", side_effect=RuntimeError("psutil")):
        kill_process_tree(_Proc(), pgid=_DEAD_PID)

    assert killed["direct"] is True


def test_read_process_group_returns_none_for_a_pidless_process():
    """A process object with no usable pid yields no group rather than raising."""
    assert read_process_group(_KillRecordingProc()) is None


def test_read_process_group_returns_the_pid_even_for_an_already_dead_pid():
    """The group is derived from the pid, not queried — so it is available
    even once the child is reaped, when a live ``getpgid`` would ESRCH."""
    assert read_process_group(_KillRecordingProc(_DEAD_PID)) == _DEAD_PID


def test_read_process_group_ignores_a_stale_getpgid_answer():
    """Regression: the group must never come from a live ``getpgid`` call.

    ``start_new_session=True`` makes the child call ``setsid()`` before it
    execs, which runs *in the child* concurrently with the parent continuing
    past ``fork()`` — nothing orders it before the parent's next instruction.
    Under CPU contention the child can still be unscheduled (pre-``setsid()``,
    still in our own group) when the parent samples it, so a real
    ``os.getpgid(pid)`` call here would occasionally read our own pgid instead
    of the child's — tripping the self-kill guard in
    ``_safe_tree_kill_group`` and downgrading to the non-atomic per-pid
    fallback. Proven by making ``getpgid`` lie and asserting it is never
    consulted.
    """
    with patch("os.getpgid", return_value=os.getpgid(0)) as mock_getpgid:
        result = read_process_group(_KillRecordingProc(_DEAD_PID))

    mock_getpgid.assert_not_called()
    assert result == _DEAD_PID
