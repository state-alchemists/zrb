from functools import partial

import pytest

from zrb.cmd.cmd_result import CmdResult
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

    # Create a simple function that returns a coroutine instead of an async function
    def mock_run_command(*args, **kwargs):
        async def _coro():
            return (mock_cmd_result, 0)

        return _coro()

    import zrb.task.cmd_task

    original_run_command = zrb.task.cmd_task.run_command
    zrb.task.cmd_task.run_command = mock_run_command
    try:
        task = CmdTask(name="test_cmd", cmd="echo hello")
        mock_session.register_task(task)

        result = await task.exec(mock_session)

        # We can't use assert_called_once() with side_effect
        # but the test will fail if run_command isn't called
        assert result == mock_cmd_result
    finally:
        zrb.task.cmd_task.run_command = original_run_command


@pytest.mark.asyncio
async def test_cmd_task_exec_failure(mock_session):
    """Test command execution failure via exec."""
    mock_cmd_result = CmdResult(output="", error="error", display="")

    # Create a simple function that returns a coroutine instead of an async function
    def mock_run_command(*args, **kwargs):
        async def _coro():
            return (mock_cmd_result, 1)

        return _coro()

    import zrb.task.cmd_task

    original_run_command = zrb.task.cmd_task.run_command
    zrb.task.cmd_task.run_command = mock_run_command
    try:
        task = CmdTask(name="test_cmd_fail", cmd="exit 1")
        mock_session.register_task(task)

        with pytest.raises(Exception, match="Process test_cmd_fail exited \\(1\\)"):
            await task.exec(mock_session)
    finally:
        zrb.task.cmd_task.run_command = original_run_command


@pytest.mark.asyncio
async def test_cmd_task_exec_plain_print(mock_session):
    """Test plain_print=True via exec."""
    mock_cmd_result = CmdResult(output="output", error="", display="output")

    # Track call arguments
    call_args_list = []

    # Create a simple function that returns a coroutine instead of an async function
    def mock_run_command(*args, **kwargs):
        async def _coro():
            call_args_list.append((args, kwargs))
            return (mock_cmd_result, 0)

        return _coro()

    import zrb.task.cmd_task

    original_run_command = zrb.task.cmd_task.run_command
    zrb.task.cmd_task.run_command = mock_run_command
    try:
        task = CmdTask(name="test_plain_print", cmd="echo plain", plain_print=True)
        mock_session.register_task(task)

        await task.exec(mock_session)

        # Check that run_command was called
        assert len(call_args_list) == 1
        call_kwargs = call_args_list[0][1]
        print_method = call_kwargs["print_method"]
        assert isinstance(print_method, partial)
        assert print_method.keywords.get("plain") is True
    finally:
        zrb.task.cmd_task.run_command = original_run_command


@pytest.mark.asyncio
async def test_cmd_task_exec_cwd(mock_session):
    """Test custom cwd via exec."""
    mock_cmd_result = CmdResult(output="output", error="", display="output")
    custom_cwd = "/tmp/custom_dir"

    # Track call arguments
    call_args_list = []

    # Create a simple function that returns a coroutine instead of an async function
    def mock_run_command(*args, **kwargs):
        async def _coro():
            call_args_list.append((args, kwargs))
            return (mock_cmd_result, 0)

        return _coro()

    import zrb.task.cmd_task

    original_run_command = zrb.task.cmd_task.run_command
    zrb.task.cmd_task.run_command = mock_run_command
    import os

    original_abspath = os.path.abspath
    os.path.abspath = lambda x: x
    try:
        task = CmdTask(name="test_cwd", cmd="pwd", cwd=custom_cwd)
        mock_session.register_task(task)

        await task.exec(mock_session)

        # Check that run_command was called
        assert len(call_args_list) == 1
        call_kwargs = call_args_list[0][1]
        assert call_kwargs["cwd"] == custom_cwd
    finally:
        zrb.task.cmd_task.run_command = original_run_command
        os.path.abspath = original_abspath


@pytest.mark.asyncio
async def test_cmd_task_exec_env(mock_session):
    """Test custom environment variables via exec."""
    mock_cmd_result = CmdResult(output="output", error="", display="output")

    # Track call arguments
    call_args_list = []

    # Create a simple function that returns a coroutine instead of an async function
    def mock_run_command(*args, **kwargs):
        async def _coro():
            call_args_list.append((args, kwargs))
            return (mock_cmd_result, 0)

        return _coro()

    import zrb.task.cmd_task

    original_run_command = zrb.task.cmd_task.run_command
    zrb.task.cmd_task.run_command = mock_run_command
    try:
        mock_session.shared_ctx.env["MY_VAR"] = "my_value"
        task = CmdTask(name="test_env", cmd="echo $MY_VAR")
        mock_session.register_task(task)

        await task.exec(mock_session)

        # Check that run_command was called
        assert len(call_args_list) == 1
        call_kwargs = call_args_list[0][1]
        env_map = call_kwargs["env_map"]
        assert env_map["MY_VAR"] == "my_value"
    finally:
        zrb.task.cmd_task.run_command = original_run_command


@pytest.mark.asyncio
async def test_cmd_task_exec_remote(mock_session):
    """Test remote command execution via exec."""
    mock_cmd_result = CmdResult(
        output="remote output", error="", display="remote output"
    )

    # Track call arguments
    call_args_list = []

    def mock_run_command(*args, **kwargs):
        async def _coro():
            call_args_list.append((args, kwargs))
            return (mock_cmd_result, 0)

        return _coro()

    import zrb.task.cmd_task

    original_run_command = zrb.task.cmd_task.run_command
    zrb.task.cmd_task.run_command = mock_run_command
    original_get_remote_cmd_script = zrb.task.cmd_task.get_remote_cmd_script
    zrb.task.cmd_task.get_remote_cmd_script = lambda *a, **k: "ssh-script"
    try:
        task = CmdTask(
            name="test_remote",
            cmd="echo remote",
            remote_host="host",
            remote_user="user",
        )
        mock_session.register_task(task)

        await task.exec(mock_session)

        assert len(call_args_list) == 1
        call_kwargs = call_args_list[0][1]
        assert call_kwargs["cmd"][2] == "ssh-script"
    finally:
        zrb.task.cmd_task.run_command = original_run_command
        zrb.task.cmd_task.get_remote_cmd_script = original_get_remote_cmd_script
