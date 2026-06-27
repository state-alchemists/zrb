import os
from unittest import mock

import pytest

from zrb.builtin import changelog as changelog_module
from zrb.cmd.cmd_result import CmdResult
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


async def _coro(val=None):
    return val


@pytest.fixture
def mock_print():
    return mock.MagicMock()


@pytest.fixture
def session(mock_print):
    shared_ctx = SharedContext(print_fn=mock_print)
    return Session(shared_ctx=shared_ctx, state_logger=mock.MagicMock())


def _cmd_result(output):
    return CmdResult(output=output, error="", display=output)


def _run_command_factory(tag_output, tag_code=0, log_output="- a change"):
    """Dispatch run_command by subcommand: `git tag` vs `git log`."""

    async def fake_run_command(cmd, *args, **kwargs):
        if cmd[:2] == ["git", "tag"]:
            return _cmd_result(tag_output), tag_code
        if cmd[:2] == ["git", "log"]:
            if "-1" in cmd:  # date lookup
                return _cmd_result("2026-06-25\n"), 0
            return _cmd_result(log_output), 0
        return _cmd_result(""), 0

    return fake_run_command


def _agent_factory(captured, output="# Changelog\n"):
    """Mock create_agent; record tools and return an agent yielding `output`."""

    def fake_create_agent(tools=None, yolo=None, **kwargs):
        captured["tools"] = tools
        agent = mock.MagicMock()
        agent.run = mock.MagicMock(
            side_effect=lambda *a, **k: _coro(mock.Mock(output=output))
        )
        return agent

    return fake_create_agent


@pytest.mark.asyncio
async def test_generate_changelog_writes_files(session, mock_print, tmp_path):
    out_dir = str(tmp_path / "cl")
    captured = {}
    with (
        mock.patch(
            "zrb.builtin.changelog.get_repo_dir",
            new=lambda *a, **k: _coro("/fake/repo"),
        ),
        mock.patch(
            "zrb.builtin.changelog.run_command",
            new=_run_command_factory("v1.0.0\nv1.1.0\n"),
        ),
        mock.patch(
            "zrb.llm.agent.create_agent",
            new=_agent_factory(captured, output="# Notes\n"),
        ),
    ):
        result = await changelog_module.generate_changelog.async_run(
            session=session, kwargs={"dir": out_dir}
        )

    assert result == [
        os.path.join(out_dir, "v1.0.0.md"),
        os.path.join(out_dir, "v1.1.0.md"),
    ]
    for name in ("v1.0.0.md", "v1.1.0.md"):
        with open(os.path.join(out_dir, name)) as f:
            assert f.read() == "# Notes\n"


@pytest.mark.asyncio
async def test_generate_changelog_no_matching_tags(session, mock_print, tmp_path):
    with (
        mock.patch(
            "zrb.builtin.changelog.get_repo_dir",
            new=lambda *a, **k: _coro("/fake/repo"),
        ),
        mock.patch(
            "zrb.builtin.changelog.run_command",
            new=_run_command_factory("not-a-version\nrandom\n"),
        ),
    ):
        result = await changelog_module.generate_changelog.async_run(
            session=session, kwargs={"dir": str(tmp_path / "cl")}
        )

    assert result is None


@pytest.mark.asyncio
async def test_generate_changelog_skips_existing(session, mock_print, tmp_path):
    out_dir = tmp_path / "cl"
    out_dir.mkdir()
    (out_dir / "v1.0.0.md").write_text("existing")
    captured = {}
    with (
        mock.patch(
            "zrb.builtin.changelog.get_repo_dir",
            new=lambda *a, **k: _coro("/fake/repo"),
        ),
        mock.patch(
            "zrb.builtin.changelog.run_command",
            new=_run_command_factory("v1.0.0\n"),
        ),
        mock.patch(
            "zrb.llm.agent.create_agent",
            new=_agent_factory(captured),
        ),
    ):
        result = await changelog_module.generate_changelog.async_run(
            session=session, kwargs={"dir": str(out_dir)}
        )

    assert result == []
    assert (out_dir / "v1.0.0.md").read_text() == "existing"


@pytest.mark.asyncio
async def test_generate_changelog_raises_on_tag_failure(session, tmp_path):
    with (
        mock.patch(
            "zrb.builtin.changelog.get_repo_dir",
            new=lambda *a, **k: _coro("/fake/repo"),
        ),
        mock.patch(
            "zrb.builtin.changelog.run_command",
            new=_run_command_factory("", tag_code=1),
        ),
        pytest.raises(Exception, match="git tag failed"),
    ):
        await changelog_module.generate_changelog.async_run(
            session=session, kwargs={"dir": str(tmp_path / "cl")}
        )


@pytest.mark.asyncio
async def test_git_tool_allows_and_refuses(session, tmp_path):
    """The git tool passed to the agent allows read-only subcommands only."""
    captured = {}
    with (
        mock.patch(
            "zrb.builtin.changelog.get_repo_dir",
            new=lambda *a, **k: _coro("/fake/repo"),
        ),
        mock.patch(
            "zrb.builtin.changelog.run_command",
            new=_run_command_factory("v1.0.0\n", log_output="- x"),
        ),
        mock.patch(
            "zrb.llm.agent.create_agent",
            new=_agent_factory(captured),
        ),
    ):
        await changelog_module.generate_changelog.async_run(
            session=session, kwargs={"dir": str(tmp_path / "cl")}
        )

        git_tool = captured["tools"][0]
        # Allowed subcommand reaches run_command and returns its output.
        assert await git_tool(["log", "--stat"]) == "- x"
        # Refused: empty args, disallowed subcommand, and config injection.
        assert "Refused" in await git_tool([])
        assert "Refused" in await git_tool(["push"])
        assert "Refused" in await git_tool(["-c", "foo=bar", "log"])
