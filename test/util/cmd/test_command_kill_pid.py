import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import psutil
import pytest

from zrb.config.config import CFG
from zrb.util.cmd.command import kill_pid, run_command, terminate_pid, terminate_process


class TestKillPidWithChildren:
    """Tests for kill_pid with child processes to cover lines 210-211."""

    def test_kill_pid_with_child_processes(self):
        """Test kill_pid on a process that has child processes."""
        import subprocess

        # Start a shell that spawns a child process
        proc = subprocess.Popen(["bash", "-c", "sleep 60 & sleep 60"])
        pid = proc.pid

        printed_messages = []

        def capture_print(msg, **kwargs):
            printed_messages.append(msg)

        import time

        time.sleep(0.1)  # Let child processes start
        kill_pid(pid, print_method=capture_print)
        proc.wait()

        # Verify that some "Killing" messages were printed
        assert any("illing" in msg for msg in printed_messages)


class TestRunCommandGracefulKill:
    """Tests for run_command timeout/cancellation that hit the graceful kill path."""

    @pytest.mark.asyncio
    async def test_run_command_timeout_triggers_graceful_kill(self):
        """Test that a timeout on a stubborn process triggers forceful kill path (lines 132-139)."""
        # Use a script that ignores SIGINT to force the graceful kill timeout
        # The process catches SIGINT but doesn't exit, causing TimeoutError in wait_for
        cmd = [
            "python3",
            "-c",
            (
                "import signal, time\n"
                "signal.signal(signal.SIGINT, signal.SIG_IGN)\n"
                "time.sleep(10)\n"
            ),
        ]
        printed_messages = []

        def capture_print(msg, **kwargs):
            printed_messages.append(msg)

        with pytest.raises(asyncio.TimeoutError):
            await run_command(cmd, print_method=capture_print, timeout=0.5)


class TestReadStreamPrintFallback:
    """Tests for the print fallback path in __read_stream (lines 188-189)."""

    @pytest.mark.asyncio
    async def test_run_command_with_print_method_no_end_kwarg(self):
        """Test run_command where print method doesn't accept 'end' keyword (line 188-189)."""

        def print_no_kwargs(msg):
            # Does not accept keyword arguments - triggers the except branch
            pass

        cmd = ["printf", "hello\\nworld"]
        # This should not raise even if print_method doesn't accept end=
        result, return_code = await run_command(cmd, print_method=print_no_kwargs)
        assert return_code == 0


class TestTerminateProcessTree:
    """Cover terminate_process branches that depend on psutil/process state."""

    @pytest.mark.asyncio
    async def test_terminate_process_pid_snapshot_no_such_process(self):
        """If the process vanishes before snapshot, _process_tree_pids falls back to [pid]."""
        proc = MagicMock()
        proc.returncode = None
        proc.pid = 4321
        proc.wait = AsyncMock(return_value=0)

        printed = []
        with (
            patch(
                "zrb.util.cmd.command.psutil.Process",
                side_effect=psutil.NoSuchProcess(4321),
            ),
            patch("zrb.util.cmd.command.psutil.pid_exists", return_value=False),
            patch("zrb.util.cmd.command.terminate_pid") as term,
        ):
            await terminate_process(
                proc, grace_seconds=0.1, print_method=printed.append
            )
        # terminate_pid was still attempted on the snapshotted single pid.
        term.assert_called_once()

    @pytest.mark.asyncio
    async def test_terminate_process_grace_timeout_then_force_kills_survivors(self):
        """A process that won't exit within grace is force-killed via kill_pid (lines 119-123)."""
        proc = MagicMock()
        proc.returncode = None
        proc.pid = 5555

        async def never_returns():
            await asyncio.sleep(10)

        # wait() never completes within the grace window -> real wait_for times out.
        proc.wait = never_returns

        fake_parent = MagicMock()
        fake_parent.children.return_value = []

        with (
            patch("zrb.util.cmd.command.psutil.Process", return_value=fake_parent),
            patch("zrb.util.cmd.command.psutil.pid_exists", return_value=True),
            patch("zrb.util.cmd.command.terminate_pid"),
            patch("zrb.util.cmd.command.kill_pid") as kill,
        ):
            await terminate_process(proc, grace_seconds=0.01)
        # The snapshotted pid was still alive after grace, so kill_pid ran.
        kill.assert_called_once()


class TestTerminatePidErrors:
    """Cover the generic-exception branch in terminate_pid (lines 145-148)."""

    def test_terminate_pid_reports_unexpected_termination_error(self):
        """A non-NoSuchProcess error while terminating a child is reported, not raised."""
        child = MagicMock()
        child.pid = 777
        child.terminate.side_effect = RuntimeError("permission denied")

        parent = MagicMock()
        parent.children.return_value = [child]
        parent.terminate.return_value = None

        printed = []
        with patch("zrb.util.cmd.command.psutil.Process", return_value=parent):
            terminate_pid(123, print_method=printed.append)

        assert any("Failed to terminate process 777" in m for m in printed)

    def test_terminate_pid_child_already_gone_is_ignored(self):
        """A child that disappears mid-terminate (NoSuchProcess) is silently skipped (line 146)."""
        child = MagicMock()
        child.pid = 888
        child.terminate.side_effect = psutil.NoSuchProcess(888)

        parent = MagicMock()
        parent.children.return_value = [child]
        parent.terminate.return_value = None

        printed = []
        with patch("zrb.util.cmd.command.psutil.Process", return_value=parent):
            terminate_pid(123, print_method=printed.append)

        # No "Failed to terminate" message for a vanished child.
        assert not any("Failed to terminate" in m for m in printed)


class TestRunCommandKillFallbacks:
    """Cover run_command cleanup branches (lines 230-237)."""

    @pytest.mark.asyncio
    async def test_timeout_killpg_then_force_kill(self):
        """On timeout, a process that ignores SIGINT is force-killed via kill_pid."""
        printed = []
        # killpg succeeds, but wait_for on cleanup times out -> kill_pid path.
        with (
            patch("zrb.util.cmd.command.os.killpg") as killpg,
            patch("zrb.util.cmd.command.kill_pid") as kill,
        ):
            # Patch only the cleanup wait_for, not the whole loop, by failing the
            # graceful wait. Easiest reliable trigger: a real stubborn process.
            cmd = [
                "python3",
                "-c",
                (
                    "import signal, time\n"
                    "signal.signal(signal.SIGINT, signal.SIG_IGN)\n"
                    "time.sleep(10)\n"
                ),
            ]
            with pytest.raises(asyncio.TimeoutError):
                await run_command(cmd, print_method=printed.append, timeout=0.3)
        assert killpg.called
        # The stubborn process forced the kill_pid fallback.
        assert kill.called

    @pytest.mark.asyncio
    async def test_timeout_killpg_raises_is_swallowed(self):
        """If os.killpg itself raises (e.g. process already gone), it is swallowed (line 236-237)."""
        printed = []
        with patch("zrb.util.cmd.command.os.killpg", side_effect=ProcessLookupError()):
            cmd = ["sleep", "5"]
            with pytest.raises(asyncio.TimeoutError):
                await run_command(cmd, print_method=printed.append, timeout=0.3)


class TestGetCmdStdinInteractive:
    """Cover the interactive-stdin branch (line 247) via run_command."""

    @pytest.mark.asyncio
    async def test_interactive_uses_real_stdin_when_tty(self):
        """When interactive and stdin is a tty, the child shares the real stdin."""
        captured = {}

        real_create = asyncio.create_subprocess_exec

        async def fake_create(*args, **kwargs):
            captured["stdin"] = kwargs.get("stdin")
            return await real_create(*args, **kwargs)

        with (
            patch("zrb.util.cmd.command.sys.stdin") as fake_stdin,
            patch(
                "zrb.util.cmd.command.asyncio.create_subprocess_exec",
                side_effect=fake_create,
            ),
        ):
            fake_stdin.isatty.return_value = True
            result, return_code = await run_command(
                ["printf", "hi"], is_interactive=True
            )

        assert return_code == 0
        # Interactive + tty resolves to the real sys.stdin object, not DEVNULL.
        assert captured["stdin"] is fake_stdin


class TestReadStreamErrorBranches:
    """Cover __read_stream's carriage-return-live and generic exception branches."""

    @pytest.mark.asyncio
    async def test_read_stream_shows_carriage_return_progress_without_newline(self):
        """`\\r`-driven progress output (no trailing `\\n`) is still captured/printed."""
        stream = MagicMock()
        # No trailing "\n" at all -- mimics a progress bar that only uses "\r",
        # plus a final chunk once the stream closes (empty bytes == EOF).
        stream.read = AsyncMock(
            side_effect=[b"10%\r50%\r100% done", b""],
        )

        fake_proc = MagicMock()
        fake_proc.pid = 999
        fake_proc.returncode = 0
        fake_proc.stdout = stream
        fake_proc.stderr = stream
        fake_proc.wait = AsyncMock(return_value=0)

        printed = []
        with patch(
            "zrb.util.cmd.command.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=fake_proc),
        ):
            result, return_code = await run_command(
                ["irrelevant"], print_method=printed.append
            )

        # All three progress segments were printed live, not dropped/batched.
        assert any("10%" in m for m in printed)
        assert any("50%" in m for m in printed)
        assert any("100% done" in m for m in printed)
        assert "100% done" in result.output

    @pytest.mark.asyncio
    async def test_read_stream_generic_exception_breaks_cleanly(self):
        """A stream read exception breaks the read loop without crashing."""
        stream = MagicMock()
        stream.read = AsyncMock(side_effect=RuntimeError("boom"))

        fake_proc = MagicMock()
        fake_proc.pid = 999
        fake_proc.returncode = 0
        fake_proc.stdout = stream
        fake_proc.stderr = stream
        fake_proc.wait = AsyncMock(return_value=0)

        with patch(
            "zrb.util.cmd.command.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=fake_proc),
        ):
            result, return_code = await run_command(["irrelevant"])

        # The read loop swallowed the RuntimeError and produced empty output.
        assert return_code == 0
        assert result.output == ""

    @pytest.mark.asyncio
    async def test_run_command_does_not_force_no_color(self):
        """NO_COLOR must not be set on the child env: per convention any
        non-empty value (even "0") disables color, so setting it can only
        strip color, never allow it."""
        captured = {}

        real_create = asyncio.create_subprocess_exec

        async def fake_create(*args, **kwargs):
            captured["env"] = kwargs.get("env")
            return await real_create(*args, **kwargs)

        with patch(
            "zrb.util.cmd.command.asyncio.create_subprocess_exec",
            side_effect=fake_create,
        ):
            await run_command(["true"])

        assert "NO_COLOR" not in captured["env"]
        assert captured["env"]["TERM"] == "xterm-256color"

    @pytest.mark.asyncio
    async def test_read_stream_force_flushes_line_exceeding_buffer_limit(
        self, monkeypatch
    ):
        """A line with no `\\r`/`\\n` is force-flushed once it exceeds
        CFG.CMD_BUFFER_LIMIT, instead of growing the buffer without bound."""
        monkeypatch.setattr(CFG, "CMD_BUFFER_LIMIT", 10)
        stream = MagicMock()
        long_line = b"a" * 20
        # No "\r"/"\n" anywhere -- the only way this gets flushed is the
        # buffer-size safety valve. Followed by EOF for both streams.
        stream.read = AsyncMock(side_effect=[long_line, b"", b""])

        fake_proc = MagicMock()
        fake_proc.pid = 999
        fake_proc.returncode = 0
        fake_proc.stdout = stream
        fake_proc.stderr = stream
        fake_proc.wait = AsyncMock(return_value=0)

        printed = []
        with patch(
            "zrb.util.cmd.command.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=fake_proc),
        ):
            result, return_code = await run_command(
                ["irrelevant"], print_method=printed.append
            )

        assert any("a" * 20 in m for m in printed)
        assert "a" * 20 in result.output
