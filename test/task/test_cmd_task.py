from functools import partial
from unittest.mock import Mock, patch

import pytest

from zrb.cmd.cmd_result import CmdResult
from zrb.context.any_context import AnyContext
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session
from zrb.task.cmd_task import CmdTask


@pytest.fixture
def mock_session():
    shared_ctx = SharedContext(logging_level=20)
    session = Session(shared_ctx=shared_ctx)
    return session


@pytest.mark.asyncio
async def test_cmd_task_exec_success(mock_session):
    """Test successful command execution via exec."""
    mock_cmd_result = CmdResult(output="output", error="", display="output")

    # Create a simple async function instead of AsyncMock
    async def mock_run_command(*args, **kwargs):
        return (mock_cmd_result, 0)
    
    with patch(
        "zrb.task.cmd_task.run_command", new=Mock(side_effect=mock_run_command)
    ):
        task = CmdTask(name="test_cmd", cmd="echo hello")
        mock_session.register_task(task)

        ctx = mock_session.get_ctx(task)
        result = await task.exec(mock_session)

        # We can't use assert_called_once() with side_effect
        # but the test will fail if run_command isn't called
        assert result == mock_cmd_result


@pytest.mark.asyncio
async def test_cmd_task_exec_failure(mock_session):
    """Test command execution failure via exec."""
    mock_cmd_result = CmdResult(output="", error="error", display="")

    # Create a simple async function instead of AsyncMock
    async def mock_run_command(*args, **kwargs):
        return (mock_cmd_result, 1)
    
    with patch(
        "zrb.task.cmd_task.run_command", new=Mock(side_effect=mock_run_command)
    ):
        task = CmdTask(name="test_cmd_fail", cmd="exit 1")
        mock_session.register_task(task)

        ctx = mock_session.get_ctx(task)
        with pytest.raises(Exception, match="Process test_cmd_fail exited \\(1\\)"):
            await task.exec(mock_session)


@pytest.mark.asyncio
async def test_cmd_task_exec_plain_print(mock_session):
    """Test plain_print=True via exec."""
    mock_cmd_result = CmdResult(output="output", error="", display="output")
    
    # Track call arguments
    call_args_list = []
    
    # Create a simple async function instead of AsyncMock
    async def mock_run_command(*args, **kwargs):
        call_args_list.append((args, kwargs))
        return (mock_cmd_result, 0)
    
    with patch(
        "zrb.task.cmd_task.run_command", new=Mock(side_effect=mock_run_command)
    ):
        task = CmdTask(name="test_plain_print", cmd="echo plain", plain_print=True)
        mock_session.register_task(task)

        ctx = mock_session.get_ctx(task)
        await task.exec(mock_session)

        # Check that run_command was called
        assert len(call_args_list) == 1
        call_kwargs = call_args_list[0][1]
        print_method = call_kwargs["print_method"]
        assert isinstance(print_method, partial)
        assert print_method.keywords.get("plain") is True


@pytest.mark.asyncio
async def test_cmd_task_exec_cwd(mock_session):
    """Test custom cwd via exec."""
    mock_cmd_result = CmdResult(output="output", error="", display="output")
    custom_cwd = "/tmp/custom_dir"
    
    # Track call arguments
    call_args_list = []
    
    # Create a simple async function instead of AsyncMock
    async def mock_run_command(*args, **kwargs):
        call_args_list.append((args, kwargs))
        return (mock_cmd_result, 0)
    
    with patch(
        "zrb.task.cmd_task.run_command", new=Mock(side_effect=mock_run_command)
    ), patch("os.path.abspath", side_effect=lambda x: x):
        task = CmdTask(name="test_cwd", cmd="pwd", cwd=custom_cwd)
        mock_session.register_task(task)

        ctx = mock_session.get_ctx(task)
        await task.exec(mock_session)

        # Check that run_command was called
        assert len(call_args_list) == 1
        call_kwargs = call_args_list[0][1]
        assert call_kwargs["cwd"] == custom_cwd


@pytest.mark.asyncio
async def test_cmd_task_exec_env(mock_session):
    """Test custom environment variables via exec."""
    mock_cmd_result = CmdResult(output="output", error="", display="output")
    
    # Track call arguments
    call_args_list = []
    
    # Create a simple async function instead of AsyncMock
    async def mock_run_command(*args, **kwargs):
        call_args_list.append((args, kwargs))
        return (mock_cmd_result, 0)
    
    with patch(
        "zrb.task.cmd_task.run_command", new=Mock(side_effect=mock_run_command)
    ):
        mock_session.shared_ctx.env["MY_VAR"] = "my_value"
        task = CmdTask(name="test_env", cmd="echo $MY_VAR")
        mock_session.register_task(task)

        ctx = mock_session.get_ctx(task)
        await task.exec(mock_session)

        # Check that run_command was called
        assert len(call_args_list) == 1
        call_kwargs = call_args_list[0][1]
        env_map = call_kwargs["env_map"]
        assert env_map["MY_VAR"] == "my_value"


@pytest.mark.asyncio
async def test_cmd_task_exec_remote(mock_session):
    """Test remote command execution via exec."""
    mock_cmd_result = CmdResult(
        output="remote output", error="", display="remote output"
    )

    async def mock_run_command(*args, **kwargs):
        return (mock_cmd_result, 0)
    
    with patch(
        "zrb.task.cmd_task.run_command", new=Mock(side_effect=mock_run_command)
    ) as mock_run_command_patch, patch(
        "zrb.task.cmd_task.get_remote_cmd_script", return_value="ssh-script"
    ) as mock_get_remote:
        mock_run_command_patch.side_effect = mock_run_command
        task = CmdTask(
            name="test_remote",
            cmd="echo remote",
            remote_host="host",
            remote_user="user",
        )
        mock_session.register_task(task)

        ctx = mock_session.get_ctx(task)
        await task.exec(mock_session)

        mock_get_remote.assert_called_once()
        call_kwargs = mock_run_command_patch.call_args.kwargs
        assert call_kwargs["cmd"][2] == "ssh-script"