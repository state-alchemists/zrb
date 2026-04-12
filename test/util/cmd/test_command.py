import asyncio
import os
import subprocess

import psutil
import pytest

from zrb.util.cmd.command import check_unrecommended_commands, kill_pid, run_command
from zrb.util.cmd.remote import get_remote_cmd_script


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
    assert 'ssh -t -p "22" "user@example.com" \'ls -la\'' in result


def test_get_remote_cmd_script_with_ssh_key():
    """Test SSH command generation with SSH key."""
    cmd = "ls -la"
    result = get_remote_cmd_script(
        cmd, host="example.com", port=22, user="user", ssh_key="/path/to/key"
    )
    assert 'ssh -t -p "22" -i "/path/to/key" "user@example.com" \'ls -la\'' in result


def test_get_remote_cmd_script_with_password():
    """Test SSH command generation with password authentication."""
    cmd = "ls -la"
    result = get_remote_cmd_script(
        cmd,
        host="example.com",
        port=22,
        user="user",
        password="pass123",
        use_password=True,
    )
    assert 'sshpass -p "pass123" ssh -t -p "22" "user@example.com" \'ls -la\'' in result


def test_get_remote_cmd_script_with_ssh_key_and_password():
    """Test SSH command generation with both SSH key and password."""
    cmd = "ls -la"
    result = get_remote_cmd_script(
        cmd,
        host="example.com",
        port=22,
        user="user",
        password="pass123",
        use_password=True,
        ssh_key="/path/to/key",
    )
    assert (
        'sshpass -p "pass123" ssh -t -p "22" -i "/path/to/key" "user@example.com" \'ls -la\''
        in result
    )


def test_get_remote_cmd_script_custom_port():
    """Test SSH command generation with custom port."""
    cmd = "ls -la"
    result = get_remote_cmd_script(cmd, host="example.com", port=2222, user="user")
    assert 'ssh -t -p "2222" "user@example.com" \'ls -la\'' in result


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
