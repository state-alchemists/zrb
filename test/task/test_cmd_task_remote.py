import os

import pytest

from zrb.cmd.cmd_result import CmdResult
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session
from zrb.task.cmd_task import CmdTask


@pytest.fixture
def mock_session():
    return Session(shared_ctx=SharedContext(logging_level=20))


@pytest.mark.asyncio
async def test_cmd_task_remote_expands_tilde_in_ssh_key(mock_session):
    """The key path reaches ssh expanded, since quoting would hide a `~`."""
    import zrb.task.cmd_task

    commands = []

    def mock_run_command(*args, **kwargs):
        async def _coro():
            commands.append(kwargs["cmd"])
            return (CmdResult(output="", error="", display=""), 0)

        return _coro()

    original = zrb.task.cmd_task.run_command
    zrb.task.cmd_task.run_command = mock_run_command
    try:
        task = CmdTask(
            name="test_remote_key",
            cmd="true",
            remote_host="host",
            remote_user="user",
            remote_ssh_key="~/.ssh/id_ed25519",
        )
        mock_session.register_task(task)
        await task.exec(mock_session)
    finally:
        zrb.task.cmd_task.run_command = original

    script = commands[0][-1]
    assert os.path.expanduser("~/.ssh/id_ed25519") in script
    assert "'~" not in script
