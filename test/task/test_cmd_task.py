from functools import partial
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.cmd.cmd_result import CmdResult
from zrb.cmd.cmd_val import AnyCmdVal
from zrb.context.any_context import AnyContext
from zrb.task.cmd_task import CmdTask
from zrb.xcom.xcom import Xcom


@pytest.mark.asyncio
async def test_cmd_task_exec_action_success():
    """Test _exec_action method for successful command execution."""
    mock_ctx = MagicMock(spec=AnyContext)
    mock_ctx.xcom = {}
    mock_ctx.render.side_effect = lambda x: x  # Simple render mock
    mock_ctx.env = {}

    mock_cmd_result = CmdResult(output="output", error="")
    mock_run_command = AsyncMock(return_value=(mock_cmd_result, 0))

    with patch("zrb.task.cmd_task.run_command", mock_run_command):
        task = CmdTask(name="test_cmd", cmd="echo hello")
        result = await task._exec_action(mock_ctx)

        mock_run_command.assert_called_once()
        assert result == mock_cmd_result
        mock_ctx.log_info.assert_any_call("Running script")
        mock_ctx.log_info.assert_any_call("Exit status: 0")
        assert "test_cmd-pid" in mock_ctx.xcom
        assert isinstance(mock_ctx.xcom["test_cmd-pid"], Xcom)


@pytest.mark.asyncio
async def test_cmd_task_exec_action_failure():
    """Test _exec_action method for command execution failure."""
    mock_ctx = MagicMock(spec=AnyContext)
    mock_ctx.xcom = {}
    mock_ctx.render.side_effect = lambda x: x
    mock_ctx.env = {}

    mock_cmd_result = CmdResult(output="", error="error")
    mock_run_command = AsyncMock(return_value=(mock_cmd_result, 1))

    with patch("zrb.task.cmd_task.run_command", mock_run_command):
        task = CmdTask(name="test_cmd_fail", cmd="exit 1")
        with pytest.raises(Exception, match="Process test_cmd_fail exited \\(1\\)"):
            await task._exec_action(mock_ctx)

        mock_run_command.assert_called_once()
        mock_ctx.log_info.assert_any_call("Running script")
        assert "test_cmd_fail-pid" in mock_ctx.xcom
        assert isinstance(mock_ctx.xcom["test_cmd_fail-pid"], Xcom)


@pytest.mark.asyncio
async def test_cmd_task_exec_action_plain_print():
    """Test _exec_action method with plain_print=True."""
    mock_ctx = MagicMock(spec=AnyContext)
    mock_ctx.xcom = {}
    mock_ctx.render.side_effect = lambda x: x
    mock_ctx.env = {}

    mock_cmd_result = CmdResult(output="output", error="")
    mock_run_command = AsyncMock(return_value=(mock_cmd_result, 0))

    with patch("zrb.task.cmd_task.run_command", mock_run_command):
        task = CmdTask(name="test_plain_print", cmd="echo plain", plain_print=True)
        await task._exec_action(mock_ctx)

        mock_run_command.assert_called_once()
        # Check if print_method passed to run_command is partial with plain=True
        call_args, call_kwargs = mock_run_command.call_args
        print_method = call_kwargs["print_method"]  # Access print_method from kwargs
        assert isinstance(print_method, partial)
        assert print_method.keywords.get("plain") is True


@pytest.mark.asyncio
async def test_cmd_task_exec_action_cwd():
    """Test _exec_action method with custom cwd."""
    mock_ctx = MagicMock(spec=AnyContext)
    mock_ctx.xcom = {}
    mock_ctx.render.side_effect = lambda x: x
    mock_ctx.env = {}

    mock_cmd_result = CmdResult(output="output", error="")
    mock_run_command = AsyncMock(return_value=(mock_cmd_result, 0))

    custom_cwd = "/tmp/custom_dir"
    with patch("zrb.task.cmd_task.run_command", mock_run_command), patch(
        "os.path.abspath", side_effect=lambda x: x
    ):  # Mock abspath for predictable test
        task = CmdTask(name="test_cwd", cmd="pwd", cwd=custom_cwd)
        await task._exec_action(mock_ctx)

        mock_run_command.assert_called_once()
        call_args, call_kwargs = mock_run_command.call_args
        assert call_kwargs["cwd"] == custom_cwd  # Access cwd from kwargs


@pytest.mark.asyncio
async def test_cmd_task_exec_action_env():
    """Test _exec_action method with custom environment variables."""
    mock_ctx = MagicMock(spec=AnyContext)
    mock_ctx.xcom = {}
    mock_ctx.render.side_effect = lambda x: x
    mock_ctx.env = {"MY_VAR": "my_value"}

    mock_cmd_result = CmdResult(output="output", error="")
    mock_run_command = AsyncMock(return_value=(mock_cmd_result, 0))

    with patch("zrb.task.cmd_task.run_command", mock_run_command):
        task = CmdTask(name="test_env", cmd="echo $MY_VAR")
        await task._exec_action(mock_ctx)

        mock_run_command.assert_called_once()
        call_args, call_kwargs = mock_run_command.call_args
        env_map = call_kwargs["env_map"]  # Access env_map from kwargs
        assert "MY_VAR" in env_map
        assert env_map["MY_VAR"] == "my_value"
        assert "_ZRB_SSH_PASSWORD" in env_map
        assert "PYTHONBUFFERED" in env_map
        assert env_map["PYTHONBUFFERED"] == "1"


@pytest.mark.asyncio
async def test_cmd_task_exec_action_remote():
    """Test _exec_action method for remote command execution."""
    mock_ctx = MagicMock(spec=AnyContext)
    mock_ctx.xcom = {}
    mock_ctx.render.side_effect = lambda x: x
    mock_ctx.env = {}

    mock_cmd_result = CmdResult(output="remote output", error="")
    mock_run_command = AsyncMock(return_value=(mock_cmd_result, 0))
    mock_get_remote_cmd_script = MagicMock(
        return_value="ssh user@host -p 22 'echo remote'"
    )

    with patch("zrb.task.cmd_task.run_command", mock_run_command), patch(
        "zrb.task.cmd_task.get_remote_cmd_script", mock_get_remote_cmd_script
    ):
        task = CmdTask(
            name="test_remote",
            cmd="echo remote",
            remote_host="host",
            remote_user="user",
        )
        await task._exec_action(mock_ctx)

        mock_get_remote_cmd_script.assert_called_once()
        mock_run_command.assert_called_once()
        call_args, call_kwargs = mock_run_command.call_args
        # The command passed to run_command should be the remote script
        assert call_kwargs["cmd"][2] == "ssh user@host -p 22 'echo remote'"


def test_cmd_task_get_should_warn_unrecommended_commands():
    """Test _get_should_warn_unrecommended_commands method."""
    # Test with default WARN_UNRECOMMENDED_COMMAND
    with patch("zrb.task.cmd_task.WARN_UNRECOMMENDED_COMMAND", True):
        task = CmdTask(
            name="test_warn_default_true", warn_unrecommended_command=None
        )  # Create new instance
        assert task._get_should_warn_unrecommended_commands() is True

    with patch("zrb.task.cmd_task.WARN_UNRECOMMENDED_COMMAND", False):
        task = CmdTask(
            name="test_warn_default_false", warn_unrecommended_command=None
        )  # Create new instance
        assert task._get_should_warn_unrecommended_commands() is False

    # Test with explicit warn_unrecommended_command=True
    task = CmdTask(name="test_warn_explicit_true", warn_unrecommended_command=True)
    assert task._get_should_warn_unrecommended_commands() is True

    # Test with explicit warn_unrecommended_command=False
    task = CmdTask(name="test_warn_explicit_false", warn_unrecommended_command=False)
    assert task._get_should_warn_unrecommended_commands() is False


def test_cmd_task_check_unrecommended_commands():
    """Test _check_unrecommended_commands method."""
    mock_ctx = MagicMock(spec=AnyContext)
    mock_check_unrecommended_commands = MagicMock(
        return_value={"rm": "Use zrb.util.file.remove instead"}
    )

    task = CmdTask(name="test_check_warn")

    # Test with bash shell and unrecommended commands
    with patch(
        "zrb.task.cmd_task.check_unrecommended_commands",
        mock_check_unrecommended_commands,
    ):
        task._check_unrecommended_commands(mock_ctx, "/bin/bash", "rm -rf /")
        mock_check_unrecommended_commands.assert_called_once_with("rm -rf /")
        mock_ctx.log_warning.assert_any_call(
            "The script contains unrecommended commands"
        )
        mock_ctx.log_warning.assert_any_call("- rm: Use zrb.util.file.remove instead")

    # Reset mocks
    mock_ctx.reset_mock()
    mock_check_unrecommended_commands.reset_mock()  # Reset mock after each scenario

    # Test with zsh shell and no unrecommended commands
    mock_check_unrecommended_commands.return_value = {}
    with patch(
        "zrb.task.cmd_task.check_unrecommended_commands",
        mock_check_unrecommended_commands,
    ):
        task._check_unrecommended_commands(mock_ctx, "/bin/zsh", "echo hello")
        mock_check_unrecommended_commands.assert_called_once_with("echo hello")
        mock_ctx.log_warning.assert_not_called()

    # Reset mocks
    mock_ctx.reset_mock()
    # Removed reset_known_calls as it might interfere
    mock_check_unrecommended_commands.reset_mock()  # Reset mock after each scenario

    # Test with non-bash/zsh shell
    with patch(
        "zrb.task.cmd_task.check_unrecommended_commands",
        mock_check_unrecommended_commands,
    ):
        task._check_unrecommended_commands(
            mock_ctx, "/usr/bin/python", "print('hello')"
        )
        mock_check_unrecommended_commands.assert_not_called()
        mock_ctx.log_warning.assert_not_called()


def test_cmd_task_get_shell_flag():
    """Test _get_shell_flag method."""
    mock_ctx = MagicMock(spec=AnyContext)
    mock_ctx.render.side_effect = lambda x: x

    # Test with default shell flag (-c)
    task = CmdTask(name="test_shell_flag_default")
    with patch.object(task, "_get_shell", return_value="/bin/sh"):
        assert task._get_shell_flag(mock_ctx) == "-c"

    # Test with specific shell flag (e.g., -e for node)
    task = CmdTask(name="test_shell_flag_node")
    with patch.object(
        task, "_get_shell", return_value="node"
    ):  # Mock _get_shell to return "node"
        assert task._get_shell_flag(mock_ctx) == "-e"

    # Test with explicit shell_flag attribute
    task = CmdTask(name="test_shell_flag_explicit", shell_flag="-x")
    with patch.object(task, "_get_shell", return_value="/bin/bash"):
        assert task._get_shell_flag(mock_ctx) == "-x"

    # Test with explicit shell_flag attribute and render_shell_flag=False
    task = CmdTask(
        name="test_shell_flag_no_render",
        shell_flag="{{ input.flag }}",
        render_shell_flag=False,
    )
    with patch.object(task, "_get_shell", return_value="/bin/bash"):
        assert task._get_shell_flag(mock_ctx) == "{{ input.flag }}"


def test_cmd_task_get_cwd():
    """Test _get_cwd method."""
    mock_ctx = MagicMock(spec=AnyContext)
    mock_ctx.render.side_effect = lambda x: x

    # Test with default cwd (os.getcwd())
    task = CmdTask(name="test_cwd_default")
    with patch("os.getcwd", return_value="/current/dir"), patch(
        "os.path.abspath", side_effect=lambda x: x
    ):
        assert task._get_cwd(mock_ctx) == "/current/dir"

    # Test with explicit cwd attribute
    task = CmdTask(name="test_cwd_explicit", cwd="/custom/dir")
    with patch("os.path.abspath", side_effect=lambda x: x):
        assert task._get_cwd(mock_ctx) == "/custom/dir"

    # Test with explicit cwd attribute and render_cwd=False
    task = CmdTask(name="test_cwd_no_render", cwd="{{ input.cwd }}", render_cwd=False)
    with patch("os.path.abspath", side_effect=lambda x: x):
        assert task._get_cwd(mock_ctx) == "{{ input.cwd }}"

    # Test with cwd attribute evaluating to None
    task = CmdTask(name="test_cwd_none", cwd=None)
    with patch("os.getcwd", return_value="/current/dir"), patch(
        "os.path.abspath", side_effect=lambda x: x
    ):
        assert task._get_cwd(mock_ctx) == "/current/dir"


def test_cmd_task_render_cmd_val():
    """Test _render_cmd_val method."""
    mock_ctx = MagicMock(spec=AnyContext)
    mock_ctx.render.side_effect = lambda x: x.replace("{{ input.name }}", "test_name")

    task = CmdTask(name="test_render")

    # Test with string cmd
    assert task._render_cmd_val(mock_ctx, "echo hello") == "echo hello"

    # Test with string cmd that needs rendering
    assert task._render_cmd_val(mock_ctx, "echo {{ input.name }}") == "echo test_name"

    # Test with list of strings
    cmd_list = ["echo 1", "echo 2"]
    assert task._render_cmd_val(mock_ctx, cmd_list) == "echo 1\necho 2"

    # Test with list of strings that need rendering
    cmd_list_render = ["echo {{ input.name }}", "echo 2"]
    assert task._render_cmd_val(mock_ctx, cmd_list_render) == "echo test_name\necho 2"

    # Test with callable cmd
    callable_cmd = MagicMock(return_value="echo from callable")
    assert task._render_cmd_val(mock_ctx, callable_cmd) == "echo from callable"
    callable_cmd.assert_called_once_with(mock_ctx)

    # Test with AnyCmdVal
    any_cmd_val = MagicMock(spec=AnyCmdVal)  # Mock AnyCmdVal instance
    any_cmd_val.to_str.return_value = "echo from anycmdval"
    # Assert that to_str is called and the return value is correct
    result = task._render_cmd_val(mock_ctx, any_cmd_val)
    any_cmd_val.to_str.assert_called_once_with(mock_ctx)
    assert result == "echo from anycmdval"
    any_cmd_val.to_str.assert_called_once_with(mock_ctx)

    # Test with mixed list
    # Re-create mocks for the mixed list test to avoid potential side effects
    callable_cmd_mixed = MagicMock(return_value="echo from callable")
    any_cmd_val_mixed = MagicMock(spec=AnyCmdVal)
    any_cmd_val_mixed.to_str.return_value = "echo from anycmdval"

    mixed_list = [
        "echo 1",
        callable_cmd_mixed,
        any_cmd_val_mixed,
        "echo {{ input.name }}",
    ]
    result_mixed = task._render_cmd_val(mock_ctx, mixed_list)

    # Assert calls for mocks within the list
    callable_cmd_mixed.assert_called_once_with(mock_ctx)
    any_cmd_val_mixed.to_str.assert_called_once_with(mock_ctx)

    assert (
        result_mixed
        == "echo 1\necho from callable\necho from anycmdval\necho test_name"
    )

    # Test with render_cmd=False
    task_no_render = CmdTask(name="test_no_render", render_cmd=False)
    assert (
        task_no_render._render_cmd_val(mock_ctx, "echo {{ input.name }}")
        == "echo {{ input.name }}"
    )
