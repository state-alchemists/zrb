"""`_spawn` must treat an explicit env_map as the child's whole environment.

The bug was `(env_map or os.environ)`: an empty mapping is falsy, so a caller
that meant "this child inherits nothing" silently got the parent's whole
environment instead.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.cmd.command import run_command


def _empty_stream() -> MagicMock:
    stream = MagicMock()
    stream.read = AsyncMock(return_value=b"")
    return stream


@pytest.mark.asyncio
async def test_an_explicit_empty_env_map_is_not_replaced_by_the_parent_environment():
    process = MagicMock()
    process.pid = 999
    process.returncode = 0
    process.stdout = _empty_stream()
    process.stderr = _empty_stream()
    process.wait = AsyncMock(return_value=0)
    spawn = AsyncMock(return_value=process)

    with patch("zrb.cmd.command.asyncio.create_subprocess_exec", new=spawn):
        await run_command(["irrelevant"], env_map={}, print_method=lambda *_: None)

    child_env = spawn.call_args.kwargs["env"]
    assert child_env == {"TERM": "xterm-256color"}
    assert "PATH" not in child_env
