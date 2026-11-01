from unittest.mock import MagicMock, mock_open, patch

import pytest

from zrb.builtin.searxng.start import copy_searxng_setting, start_searxng
from zrb.cmd.cmd_result import CmdResult
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


def _action(task):
    """`task.action` narrowed to the callable `@make_task` always sets."""
    action = task.action
    assert callable(action)
    return action


def test_copy_searxng_setting(tmp_path):
    ctx = MagicMock()
    mock_home = str(tmp_path / "home")
    fake_content = '"ultrasecretkey"'

    with (
        patch("os.path.expanduser", return_value=mock_home),
        patch("os.path.isfile", return_value=False),
        patch("os.makedirs"),
        patch(
            "zrb.builtin.searxng.start.open", mock_open(read_data=fake_content)
        ) as mock_file,
        patch("shutil.copy") as mock_copy,
    ):

        _action(copy_searxng_setting)(ctx)

        assert ctx.print.called
        mock_file.assert_called()
        mock_copy.assert_called_once()


@pytest.mark.asyncio
async def test_start_searxng_gives_the_image_no_arguments(monkeypatch):
    """The image ends the command: the container takes no options, so a
    trailing flag is ignored by it and means nothing to `docker run`."""
    seen: dict[str, list[str]] = {}

    async def fake_run_command(*, cmd, **_kwargs):
        seen["cmd"] = cmd
        return CmdResult(output="", error="", display=""), 0

    monkeypatch.setattr("zrb.task.cmd_task.run_command", fake_run_command)
    session = Session(shared_ctx=SharedContext(input={"port": 8080}, logging_level=20))
    session.register_task(start_searxng)

    await start_searxng.exec_action(start_searxng.get_ctx(session))

    script = seen["cmd"][-1]
    assert script.split()[-1].startswith("docker.io/searxng/searxng:")
