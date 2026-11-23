import shlex
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

        assert len(call_args_list) == 1
        call_kwargs = call_args_list[0][1]
        cmd_script = call_kwargs["cmd"][2]
        assert "sshpass" in cmd_script
        assert "-i /path/to/key" in cmd_script


@pytest.mark.asyncio
async def test_rsync_task_brackets_an_ipv6_host(mock_session):
    rsync_task = RsyncTask(
        name="test_rsync_v6",
        local_source_path="/local/path",
        remote_destination_path="/remote/path",
        remote_host="2001:db8::1",
        remote_user="remote-user",
    )
    mock_session.register_task(rsync_task)
    scripts = []

    def mock_run_command(*args, **kwargs):
        async def _coro():
            scripts.append(kwargs["cmd"][2])
            return (None, 0)

        return _coro()

    with patch(
        "zrb.task.cmd_task.run_command", new=MagicMock(side_effect=mock_run_command)
    ):
        await rsync_task.exec(mock_session)

    assert "remote-user@[2001:db8::1]:/remote/path" in scripts[0]


def _script(task: RsyncTask) -> str:
    return task._get_cmd_script(SharedContext())


def test_remote_path_omits_an_empty_user():
    task = RsyncTask(
        name="test_rsync",
        local_source_path="/local/path",
        remote_destination_path="/remote/path",
        remote_host="remote-host",
    )

    script = _script(task)

    assert "remote-host:/remote/path" in script
    assert "@remote-host" not in script


def test_paths_with_spaces_stay_single_arguments():
    task = RsyncTask(
        name="test_rsync",
        local_source_path="/local/with space",
        remote_destination_path="/remote/with space",
        remote_host="remote-host",
        remote_user="remote-user",
    )

    tokens = shlex.split(_script(task))

    assert "/local/with space" in tokens
    assert "remote-user@remote-host:/remote/with space" in tokens


def test_paths_with_a_single_quote_are_escaped():
    path = "/local/it's here"

    task = RsyncTask(
        name="test_rsync",
        local_source_path=path,
        remote_destination_path="/remote/path",
        remote_host="remote-host",
        remote_user="remote-user",
    )

    assert path in shlex.split(_script(task))


def test_paths_with_shell_syntax_are_quoted():
    path = "/local/$(touch /tmp/pwned) `id`; rm -rf /"

    task = RsyncTask(
        name="test_rsync",
        local_source_path=path,
        remote_destination_path="/remote/path",
        remote_host="remote-host",
        remote_user="remote-user",
    )

    assert path in shlex.split(_script(task))


def test_ssh_key_is_quoted_for_the_remote_shell():
    key = "/keys/it's a key"

    task = RsyncTask(
        name="test_rsync",
        local_source_path="/local/path",
        remote_destination_path="/remote/path",
        remote_host="remote-host",
        remote_user="remote-user",
        remote_ssh_key=key,
    )

    tokens = shlex.split(_script(task))
    ssh_command = shlex.split(tokens[tokens.index("-e") + 1])

    assert ssh_command == ["ssh", "-i", key, "-p", "22"]


def test_exclude_from_with_a_quote_stays_one_argument():
    exclude = "/ignore/it's here"

    task = RsyncTask(
        name="test_rsync",
        local_source_path="/local/path",
        remote_destination_path="/remote/path",
        remote_host="remote-host",
        remote_user="remote-user",
        exclude_from=exclude,
    )

    assert f"--exclude-from={exclude}" in shlex.split(_script(task))


def test_password_auth_preserves_sshpass_e():
    task = RsyncTask(
        name="test_rsync",
        local_source_path="/local/path",
        remote_destination_path="/remote/path",
        remote_host="remote-host",
        remote_user="remote-user",
        remote_password="s3cret",
    )

    script = _script(task)

    assert script.startswith("sshpass -e rsync ")
    assert "s3cret" not in script


def test_a_remote_path_requires_a_host():
    task = RsyncTask(
        name="test_rsync",
        local_source_path="/local/path",
        remote_destination_path="/remote/path",
    )

    with pytest.raises(ValueError, match="remote_host"):
        _script(task)


def test_two_remote_sides_are_refused():
    task = RsyncTask(
        name="test_rsync",
        remote_source_path="/remote/source",
        remote_destination_path="/remote/destination",
        remote_host="remote-host",
        remote_user="remote-user",
    )

    with pytest.raises(ValueError, match="remote-to-remote"):
        _script(task)


def test_two_local_sides_are_refused():
    task = RsyncTask(
        name="test_rsync",
        local_source_path="/local/source",
        local_destination_path="/local/destination",
    )

    with pytest.raises(ValueError, match="local-to-local"):
        _script(task)


def test_a_side_with_both_local_and_remote_paths_is_refused():
    task = RsyncTask(
        name="test_rsync",
        local_source_path="/local/source",
        remote_source_path="/remote/source",
        local_destination_path="/local/destination",
        remote_host="remote-host",
    )

    with pytest.raises(
        ValueError, match="both local_source_path and remote_source_path"
    ):
        _script(task)


def test_a_missing_side_is_refused():
    task = RsyncTask(
        name="test_rsync",
        remote_destination_path="/remote/destination",
        remote_host="remote-host",
    )

    with pytest.raises(ValueError, match="local_source_path or remote_source_path"):
        _script(task)
