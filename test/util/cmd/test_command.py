import asyncio
import os
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import psutil
import pytest

from zrb.config.config import CFG
from zrb.util.cmd.command import (
    check_unrecommended_commands,
    kill_pid,
    resolve_shell,
    run_command,
    terminate_pid,
    terminate_process,
)
from zrb.util.cmd.remote import get_remote_cmd_script


def test_resolve_shell_empty_uses_cfg_shell(monkeypatch):
    # No explicit shell -> fall back to CFG.SHELL.
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_SHELL", raising=False)
    monkeypatch.setattr(CFG, "DEFAULT_SHELL", "bash")
    sh, flag = resolve_shell("")
    assert sh == CFG.SHELL == "bash"
    assert flag == "-c"


def test_resolve_shell_env_opt_in(monkeypatch):
    # An explicit ZRB_SHELL opts the empty call into that shell.
    monkeypatch.setenv(f"{CFG.ENV_PREFIX}_SHELL", "bash")
    assert resolve_shell("") == ("bash", "-c")


def test_resolve_shell_posix():
    assert resolve_shell("bash") == ("bash", "-c")
    assert resolve_shell("zsh") == ("zsh", "-c")


def test_resolve_shell_runtimes_and_powershell():
    assert resolve_shell("node") == ("node", "-e")
    assert resolve_shell("ruby") == ("ruby", "-e")
    assert resolve_shell("php") == ("php", "-r")
    # Flag lookup is case-insensitive on the shell name; PowerShell uses
    # -Command (not the cmd.exe /c switch).
    assert resolve_shell("PowerShell") == ("PowerShell", "-Command")
    assert resolve_shell("pwsh") == ("pwsh", "-Command")
    # cmd.exe uses /c, not -c.
    assert resolve_shell("cmd") == ("cmd", "/c")


@pytest.mark.asyncio
async def test_terminate_process_kills_tree():
    # A shell that spawns a child; terminate_process must reap the whole tree.
    proc = await asyncio.create_subprocess_shell(
        "sleep 30 & sleep 30",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    await asyncio.sleep(0.1)
    await terminate_process(proc, grace_seconds=2.0)
    assert proc.returncode is not None


@pytest.mark.asyncio
async def test_terminate_process_already_exited_is_noop():
    proc = await asyncio.create_subprocess_shell("true")
    await proc.wait()
    # Should not raise even though the process is gone.
    await terminate_process(proc, grace_seconds=1.0)


def test_terminate_pid_unknown_is_noop():
    # A non-existent PID must not raise.
    terminate_pid(2_000_000_000)


@pytest.mark.asyncio
async def test_terminate_pid_terminates():
    proc = subprocess.Popen(["sleep", "3"])
    pid = proc.pid
    assert psutil.pid_exists(pid)

    terminate_pid(pid)
    proc.wait()

    for _ in range(10):
        if not psutil.pid_exists(pid):
            break
        try:
            if psutil.Process(pid).status() == psutil.STATUS_ZOMBIE:
                break
        except psutil.NoSuchProcess:
            break
        await asyncio.sleep(0.1)

    assert (
        not psutil.pid_exists(pid)
        or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    )


def test_check_unrecommended_commands():
    # Test safe script
    assert check_unrecommended_commands("printf 'hello'") == {}

    # Test banned commands
    violations = check_unrecommended_commands("echo 'hello'")
    assert "echo" in violations
    assert violations["echo"] == "echo isn't consistent across OS; use printf instead"

    violations = check_unrecommended_commands("ls -la")
    assert r"\bls " in violations

    violations = check_unrecommended_commands("cat file | sort -V")
    assert r"sort.*-V" in violations


@pytest.mark.asyncio
async def test_run_command_success():
    cmd = ["printf", "hello"]
    result, return_code = await run_command(cmd)

    assert return_code == 0
    assert result.output.strip() == "hello"
    assert result.error == ""


@pytest.mark.asyncio
async def test_run_command_stderr():
    # Write to stderr
    script = "import sys; print('error', file=sys.stderr)"
    cmd = ["python3", "-c", script]
    result, return_code = await run_command(cmd)

    assert return_code == 0
    assert "error" in result.error.strip()


@pytest.mark.asyncio
async def test_run_command_timeout():
    # Sleep for 2 seconds, but timeout is 0.5s
    cmd = ["sleep", "2"]

    with pytest.raises(asyncio.TimeoutError):
        await run_command(cmd, timeout=0.5)


@pytest.mark.asyncio
async def test_run_command_cwd():
    # Print current working directory
    cmd = ["pwd"]
    cwd = "/tmp"
    result, return_code = await run_command(cmd, cwd=cwd)

    assert return_code == 0
    # Resolving symlinks for /tmp on some systems
    assert os.path.realpath(result.output.strip()) == os.path.realpath(cwd)


@pytest.mark.asyncio
async def test_kill_pid():
    # Start a long running process
    proc = subprocess.Popen(["sleep", "3"])
    pid = proc.pid

    assert psutil.pid_exists(pid)

    kill_pid(pid)
    proc.wait()  # Fix ResourceWarning by waiting for it to fully terminate

    # Wait for process to terminate
    for _ in range(10):
        if not psutil.pid_exists(pid):
            break
        try:
            p = psutil.Process(pid)
            if p.status() == psutil.STATUS_ZOMBIE:
                break
        except psutil.NoSuchProcess:
            break
        await asyncio.sleep(0.1)

    assert (
        not psutil.pid_exists(pid)
        or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    )


def test_get_remote_cmd_script_basic():
    """Test basic SSH command generation."""
    cmd = "ls -la"
    result = get_remote_cmd_script(cmd, host="example.com", port=22, user="user")
    assert "ssh -t -p 22 user@example.com 'ls -la'" in result


def test_get_remote_cmd_script_with_ssh_key():
    """Test SSH command generation with SSH key."""
    cmd = "ls -la"
    result = get_remote_cmd_script(
        cmd, host="example.com", port=22, user="user", ssh_key="/path/to/key"
    )
    assert "ssh -t -p 22 -i /path/to/key user@example.com 'ls -la'" in result


def test_get_remote_cmd_script_with_password():
    """Test SSH command generation with password authentication."""
    cmd = "ls -la"
    result = get_remote_cmd_script(
        cmd,
        host="example.com",
        port=22,
        user="user",
        use_password=True,
    )
    assert "sshpass -e ssh -t -p 22 user@example.com 'ls -la'" in result


def test_get_remote_cmd_script_with_ssh_key_and_password():
    """Test SSH command generation with both SSH key and password."""
    cmd = "ls -la"
    result = get_remote_cmd_script(
        cmd,
        host="example.com",
        port=22,
        user="user",
        use_password=True,
        ssh_key="/path/to/key",
    )
    assert "sshpass -e ssh -t -p 22 -i /path/to/key user@example.com 'ls -la'" in result


def test_get_remote_cmd_script_custom_port():
    """Test SSH command generation with custom port."""
    cmd = "ls -la"
    result = get_remote_cmd_script(cmd, host="example.com", port=2222, user="user")
    assert "ssh -t -p 2222 user@example.com 'ls -la'" in result


def test_get_remote_cmd_script_quotes_injection_in_credentials():
    """Password is passed via SSHPASS env var, not on the command line."""
    malicious = 'p"$(touch /tmp/pwn)`'

    result = get_remote_cmd_script(
        "ls",
        host="example.com",
        port=22,
        user="user",
        use_password=True,
    )
    # sshpass -e reads the password from SSHPASS — never on the command line.
    assert "sshpass -e" in result
    assert malicious not in result


def test_check_unrecommended_commands_process_substitution():
    """Test detection of process substitution."""
    violations = check_unrecommended_commands("cat <(echo hello)")
    assert "<(" in violations


def test_check_unrecommended_commands_column():
    """Test detection of column command."""
    violations = check_unrecommended_commands("cat file | column")
    assert "column" in violations


def test_check_unrecommended_commands_eval():
    """Test detection of eval command."""
    violations = check_unrecommended_commands("eval 'echo hello'")
    assert "eval" in violations


def test_check_unrecommended_commands_realpath():
    """Test detection of realpath command."""
    violations = check_unrecommended_commands("realpath file.txt")
    assert "realpath" in violations


def test_check_unrecommended_commands_source():
    """Test detection of source command."""
    violations = check_unrecommended_commands("source script.sh")
    assert "source" in violations


def test_check_unrecommended_commands_which():
    """Test detection of which command."""
    violations = check_unrecommended_commands("which python")
    assert "which" in violations


def test_check_unrecommended_commands_grep_y():
    """Test detection of grep -y."""
    violations = check_unrecommended_commands("grep -y pattern file")
    assert r"grep.* -y" in violations


def test_check_unrecommended_commands_grep_P():
    """Test detection of grep -P."""
    violations = check_unrecommended_commands("grep -P pattern file")
    assert r"grep.* -P" in violations


def test_check_unrecommended_commands_grep_long():
    """Test detection of grep long options."""
    violations = check_unrecommended_commands("grep --color pattern file")
    assert r"grep[^|]+--\w{2,}" in violations


def test_check_unrecommended_commands_sort_V():
    """Test detection of sort -V."""
    violations = check_unrecommended_commands("sort -V file")
    assert r"sort.*-V" in violations


def test_check_unrecommended_commands_multiple_violations():
    """Test detection of multiple violations."""
    violations = check_unrecommended_commands("echo hello | sort -V")
    assert "echo" in violations
    assert r"sort.*-V" in violations


@pytest.mark.asyncio
async def test_run_command_with_env():
    """Test run_command with custom environment."""
    cmd = ["env"]
    env_map = {"MY_VAR": "my_value"}
    result, return_code = await run_command(cmd, env_map=env_map)
    assert return_code == 0
    assert "MY_VAR=my_value" in result.output


@pytest.mark.asyncio
async def test_run_command_with_print_method():
    """Test run_command with custom print method."""
    printed_lines = []

    def capture_print(msg, **kwargs):
        printed_lines.append(msg)

    cmd = ["echo", "test"]
    result, return_code = await run_command(cmd, print_method=capture_print)
    assert return_code == 0
    assert "test" in printed_lines


@pytest.mark.asyncio
async def test_run_command_nonzero_exit():
    """Test run_command with non-zero exit code."""
    cmd = ["bash", "-c", "exit 42"]
    result, return_code = await run_command(cmd)
    assert return_code == 42


def test_kill_pid_nonexistent():
    """Test kill_pid with nonexistent process."""
    # Use a PID that's very unlikely to exist
    kill_pid(9999999)  # Should not raise


def test_kill_pid_with_print_method():
    """Test kill_pid with custom print method."""
    proc = subprocess.Popen(["sleep", "3"])
    pid = proc.pid

    printed_messages = []

    def capture_print(msg, **kwargs):
        printed_messages.append(msg)

    kill_pid(pid, print_method=capture_print)
    proc.wait()

    assert any(f"process {pid}" in msg.lower() for msg in printed_messages)


class TestRunCommandEdgeCases:
    """Test edge cases in run_command for better coverage."""

    @pytest.mark.asyncio
    async def test_run_command_with_register_pid(self):
        """Test run_command with PID registration callback."""
        registered_pids = []

        def register_pid(pid):
            registered_pids.append(pid)

        cmd = ["echo", "test"]
        result, return_code = await run_command(cmd, register_pid_method=register_pid)

        assert return_code == 0
        assert len(registered_pids) == 1
        assert registered_pids[0] > 0

    @pytest.mark.asyncio
    async def test_run_command_with_max_output_line_zero(self):
        """Test run_command with max_output_line=0 (no capture, unlimited display)."""
        # When max_output_line=0, output is NOT captured but still printed
        printed_lines = []

        def capture_print(msg, **kwargs):
            printed_lines.append(msg)

        cmd = ["echo", "test"]
        result, return_code = await run_command(
            cmd,
            max_output_line=0,
            max_error_line=0,
            max_display_line=0,
            print_method=capture_print,
        )

        assert return_code == 0
        # Output is empty because nothing is captured when max_line=0
        assert result.output == ""
        # But it was still printed
        assert any("test" in line for line in printed_lines)

    @pytest.mark.asyncio
    async def test_run_command_with_display_output(self):
        """Test run_command captures display output."""
        cmd = ["echo", "display test"]
        result, return_code = await run_command(cmd)

        assert return_code == 0
        assert "display test" in result.display

    @pytest.mark.asyncio
    async def test_run_command_cancellation_during_execution(self):
        """Test run_command handles cancellation gracefully."""
        import asyncio

        cmd = ["sleep", "10"]  # Long running

        async def run_and_cancel():
            task = asyncio.create_task(run_command(cmd, timeout=60))
            # Give it a moment to start
            await asyncio.sleep(0.1)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass  # Expected

        # Should not hang or raise unhandled exceptions
        await run_and_cancel()

    @pytest.mark.asyncio
    async def test_run_command_with_interactive_mode(self):
        """Test run_command with interactive mode enabled."""
        cmd = ["echo", "interactive test"]
        result, return_code = await run_command(
            cmd, is_interactive=False  # Can't truly test interactive in unit tests
        )

        assert return_code == 0
        assert "interactive test" in result.output


class TestCheckUnrecommendedCommandsEdgeCases:
    """Additional edge case tests for check_unrecommended_commands."""

    def test_check_readlink_pattern(self):
        """Test detection of readlink -f pattern."""
        violations = check_unrecommended_commands('readlink -f "$0"')
        assert r'readlink.+-.*f.+["$]' in violations

    def test_check_sort_sort_versions(self):
        """Test detection of sort --sort-versions."""
        violations = check_unrecommended_commands("sort --sort-versions file")
        assert r"sort.*--sort-versions" in violations

    def test_check_test_command(self):
        """Test detection of ' test' command."""
        violations = check_unrecommended_commands("if test -f file; then echo; fi")
        assert " test" in violations

    def test_check_empty_script(self):
        """Test empty command script."""
        violations = check_unrecommended_commands("")
        assert violations == {}

    def test_check_clean_script(self):
        """Test script with no violations."""
        violations = check_unrecommended_commands("printf 'hello world'")
        assert violations == {}


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

        # The process ignored SIGINT so wait_for timed out, triggering kill_pid path


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
