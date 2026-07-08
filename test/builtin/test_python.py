import subprocess
import sys
from unittest import mock

import pytest

from zrb.builtin.python import format_python_code
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


def get_session():
    return Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock())


def make_completed_process(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


@pytest.mark.asyncio
async def test_format_python_code_runs_tools_via_current_interpreter():
    with mock.patch(
        "zrb.builtin.python.subprocess.run",
        return_value=make_completed_process(stdout="reformatted"),
    ) as mock_run:
        res = await format_python_code.async_run(session=get_session())
    assert res == "ok"
    commands = [call.args[0] for call in mock_run.call_args_list]
    assert commands == [
        [
            sys.executable,
            "-m",
            "isort",
            ".",
            "--profile",
            "black",
            "--force-grid-wrap",
            "0",
        ],
        [sys.executable, "-m", "black", "."],
    ]


@pytest.mark.asyncio
async def test_format_python_code_fails_when_tools_missing():
    with (
        mock.patch("zrb.builtin.python.importlib.util.find_spec", return_value=None),
        mock.patch("zrb.builtin.python.subprocess.run") as mock_run,
    ):
        with pytest.raises(Exception) as exc_info:
            await format_python_code.async_run(session=get_session())
    assert "isort and black not found" in str(exc_info.value)
    assert "--include-apps" in str(exc_info.value)
    mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_format_python_code_fails_on_nonzero_exit():
    with mock.patch(
        "zrb.builtin.python.subprocess.run",
        return_value=make_completed_process(returncode=1, stderr="boom"),
    ):
        with pytest.raises(Exception) as exc_info:
            await format_python_code.async_run(session=get_session())
    assert "failed (exit 1)" in str(exc_info.value)
