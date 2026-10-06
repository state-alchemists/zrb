'Safety guards for hook process-tree termination.'

import os
import signal
from unittest.mock import patch

import pytest

from zrb.llm.hook.process_kill import kill_process_tree, read_process_group


posix_process_groups_only = pytest.mark.skipif(
    os.name != "posix", reason="process groups (getpgid/killpg) are POSIX-only"
)




_DEAD_PID = 999999


class _KillRecordingProc:
    'A Popen stand-in that records whether the direct child kill ran.'

    returncode = None

    def __init__(self, pid=None):
        self.killed = False
        if pid is not None:
            self.pid = pid

    def kill(self):
        self.killed = True


def test_kill_process_tree_never_targets_zrbs_own_pid():
    'A tree kill aimed at our own pid must be refused.'
    process = _KillRecordingProc(os.getpid())

    with patch("zrb.util.cmd.command.kill_pid") as mock_kill_pid:


        kill_process_tree(process)

    mock_kill_pid.assert_not_called()
    assert process.killed, "fell back to no kill at all"


@posix_process_groups_only
def test_kill_process_tree_never_targets_zrbs_own_process_group():
    'A tree kill aimed at our process group must be refused.'
    process = _KillRecordingProc(_DEAD_PID)



    with (
        patch("os.getpgid", return_value=4242),
        patch("zrb.util.cmd.command.kill_pid") as mock_kill_pid,
    ):
        kill_process_tree(process, pgid=4242)

    mock_kill_pid.assert_not_called()
    assert process.killed, "fell back to no kill at all"


def test_kill_process_tree_tolerates_a_pidless_process():
    'Must not raise on the cancellation path when handed a mock without a pid.'
    killed = {"done": False}

    class _Proc:
        returncode = None

        def kill(self):
            killed["done"] = True

    kill_process_tree(_Proc())
    assert killed["done"]


def test_kill_process_tree_falls_back_to_psutil_when_killpg_fails():
    'A failed group kill must still reach the tree via the psutil child walk.'
    killed = {"direct": False}

    class _Proc:
        returncode = None
        pid = _DEAD_PID

        def kill(self):
            killed["direct"] = True

    with patch("zrb.util.cmd.command.kill_pid") as mock_kill_pid:
        kill_process_tree(_Proc(), pgid=_DEAD_PID)


    mock_kill_pid.assert_called_once()
    assert mock_kill_pid.call_args.args[0] == _DEAD_PID

    assert killed["direct"] is True


def test_kill_process_tree_survives_a_failing_psutil_walk():
    'An error out of the psutil walk is swallowed — this runs on the'
    killed = {"direct": False}

    class _Proc:
        returncode = None
        pid = _DEAD_PID

        def kill(self):
            killed["direct"] = True

    with patch("zrb.util.cmd.command.kill_pid", side_effect=RuntimeError("psutil")):
        kill_process_tree(_Proc(), pgid=_DEAD_PID)

    assert killed["direct"] is True


@posix_process_groups_only
def test_kill_process_tree_refuses_killpg_when_os_group_does_not_match():
    'A derived pgid that no longer matches the OS-reported group for the'
    process = _KillRecordingProc(_DEAD_PID)

    def fake_getpgid(pid):
        if pid == 0:
            return os.getpgid(0)
        return 5555

    with (
        patch("os.getpgid", side_effect=fake_getpgid),
        patch("os.killpg") as mock_killpg,
        patch("zrb.util.cmd.command.kill_pid") as mock_kill_pid,
    ):
        kill_process_tree(process, pgid=4242)

    mock_killpg.assert_not_called()
    mock_kill_pid.assert_called_once()
    assert mock_kill_pid.call_args.args[0] == _DEAD_PID
    assert process.killed


@posix_process_groups_only
def test_kill_process_tree_verify_group_skips_a_pidless_process():
    'With no pid to check the OS-reported group against, the derived pgid'
    process = _KillRecordingProc()

    with patch("os.killpg") as mock_killpg:
        kill_process_tree(process, pgid=4242)

    mock_killpg.assert_called_once_with(4242, signal.SIGKILL)


def test_read_process_group_returns_none_for_a_pidless_process():
    'A process object with no usable pid yields no group rather than raising.'
    assert read_process_group(_KillRecordingProc()) is None


@posix_process_groups_only
def test_read_process_group_returns_the_pid_even_for_an_already_dead_pid():
    'The group is derived from the pid, not queried — so it is available'
    assert read_process_group(_KillRecordingProc(_DEAD_PID)) == _DEAD_PID


@posix_process_groups_only
def test_read_process_group_ignores_a_stale_getpgid_answer():
    'Regression: the group must never come from a live ``getpgid`` call.'
    with patch("os.getpgid", return_value=os.getpgid(0)) as mock_getpgid:
        result = read_process_group(_KillRecordingProc(_DEAD_PID))

    mock_getpgid.assert_not_called()
    assert result == _DEAD_PID
