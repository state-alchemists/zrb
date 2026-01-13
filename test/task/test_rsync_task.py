from unittest.mock import MagicMock, patch

import pytest

from zrb.context.shared_context import SharedContext
from zrb.session.session import Session
from zrb.task.rsync_task import RsyncTask


@pytest.fixture
def mock_session():
    shared_ctx = SharedContext()
    session = Session(shared_ctx=shared_ctx)
    return session


@pytest.mark.asyncio
async def test_rsync_task_local_to_remote(mock_session):
    rsync_task = RsyncTask(
        name="test_rsync",
        local_source_path="/local/path",
        remote_destination_path="/remote/path",
        remote_host="remote-host",
        remote_user="remote-user",
    )
    mock_session.register_task(rsync_task)

    # Track call arguments
    call_args_list = []

    # Create a simple function that returns a coroutine instead of an async function
    def mock_run_command(*args, **kwargs):
        async def _coro():
            call_args_list.append((args, kwargs))
            return (None, 0)

        return _coro()

    with patch(
        "zrb.task.cmd_task.run_command", new=MagicMock(side_effect=mock_run_command)
    ):
        await rsync_task.exec(mock_session)

        # Check that run_command was called
        assert len(call_args_list) == 1
        call_kwargs = call_args_list[0][1]
        cmd_script = call_kwargs["cmd"][2]
        assert "rsync" in cmd_script
        assert "/local/path" in cmd_script
        assert "remote-user@remote-host:/remote/path" in cmd_script


@pytest.mark.asyncio
async def test_rsync_task_remote_to_local(mock_session):
    rsync_task = RsyncTask(
        name="test_rsync",
        remote_source_path="/remote/path",
        local_destination_path="/local/path",
        remote_host="remote-host",
        remote_user="remote-user",
    )
    mock_session.register_task(rsync_task)

    # Track call arguments
    call_args_list = []

    # Create a simple function that returns a coroutine instead of an async function
    def mock_run_command(*args, **kwargs):
        async def _coro():
            call_args_list.append((args, kwargs))
            return (None, 0)

        return _coro()

    with patch(
        "zrb.task.cmd_task.run_command", new=MagicMock(side_effect=mock_run_command)
    ):
        await rsync_task.exec(mock_session)

        # Check that run_command was called
        assert len(call_args_list) == 1
        call_kwargs = call_args_list[0][1]
        cmd_script = call_kwargs["cmd"][2]
        assert "rsync" in cmd_script
        assert "remote-user@remote-host:/remote/path" in cmd_script
        assert "/local/path" in cmd_script


@pytest.mark.asyncio
async def test_rsync_task_with_key(mock_session):
    rsync_task = RsyncTask(
        name="test_rsync",
        local_source_path="/local/path",
        remote_destination_path="/remote/path",
        remote_host="remote-host",
        remote_user="remote-user",
        remote_ssh_key="/path/to/key",
    )
    mock_session.register_task(rsync_task)

    # Track call arguments
    call_args_list = []

    # Create a simple function that returns a coroutine instead of an async function
    def mock_run_command(*args, **kwargs):
        async def _coro():
            call_args_list.append((args, kwargs))
            return (None, 0)

        return _coro()

    with patch(
        "zrb.task.cmd_task.run_command", new=MagicMock(side_effect=mock_run_command)
    ):
        await rsync_task.exec(mock_session)

        # Check that run_command was called
        assert len(call_args_list) == 1
        call_kwargs = call_args_list[0][1]
        cmd_script = call_kwargs["cmd"][2]
        assert "-i /path/to/key" in cmd_script


@pytest.mark.asyncio
async def test_rsync_task_with_password(mock_session):
    rsync_task = RsyncTask(
        name="test_rsync",
        local_source_path="/local/path",
        remote_destination_path="/remote/path",
        remote_host="remote-host",
        remote_user="remote-user",
        remote_password="password",
    )
    mock_session.register_task(rsync_task)

    # Track call arguments
    call_args_list = []

    # Create a simple function that returns a coroutine instead of an async function
    def mock_run_command(*args, **kwargs):
        async def _coro():
            call_args_list.append((args, kwargs))
            return (None, 0)

        return _coro()

    with patch(
        "zrb.task.cmd_task.run_command", new=MagicMock(side_effect=mock_run_command)
    ):
        await rsync_task.exec(mock_session)

        # Check that run_command was called
        assert len(call_args_list) == 1
        call_kwargs = call_args_list[0][1]
        cmd_script = call_kwargs["cmd"][2]
        assert "sshpass" in cmd_script


@pytest.mark.asyncio
async def test_rsync_task_with_key_and_password(mock_session):
    rsync_task = RsyncTask(
        name="test_rsync",
        local_source_path="/local/path",
        remote_destination_path="/remote/path",
        remote_host="remote-host",
        remote_user="remote-user",
        remote_ssh_key="/path/to/key",
        remote_password="password",
    )
    mock_session.register_task(rsync_task)

    # Track call arguments
    call_args_list = []

    # Create a simple function that returns a coroutine instead of an async function
    def mock_run_command(*args, **kwargs):
        async def _coro():
            call_args_list.append((args, kwargs))
            return (None, 0)

        return _coro()

    with patch(
        "zrb.task.cmd_task.run_command", new=MagicMock(side_effect=mock_run_command)
    ):
        await rsync_task.exec(mock_session)

        # Check that run_command was called
        assert len(call_args_list) == 1
        call_kwargs = call_args_list[0][1]
        cmd_script = call_kwargs["cmd"][2]
        assert "sshpass" in cmd_script
        assert "-i /path/to/key" in cmd_script
