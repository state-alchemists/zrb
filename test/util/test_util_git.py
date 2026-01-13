from unittest.mock import MagicMock, patch

import pytest

from zrb.cmd.cmd_result import CmdResult
from zrb.util.git import (
    add,
    commit,
    delete_branch,
    get_branches,
    get_current_branch,
    get_diff,
    get_repo_dir,
    pull,
    push,
)


@pytest.mark.asyncio
async def test_get_diff():
    # MagicMock run_command output for diff
    # /dev/null lines are ignored by the parser, resulting in correct state
    diff_output = """--- /dev/null
+++ b/new.txt
@@ -0,0 +1 @@
+New file content
--- a/deleted.txt
+++ /dev/null
@@ -1 +0,0 @@
-Deleted content
--- a/modified.txt
+++ b/modified.txt
@@ -1 +1 @@
-Old content
+New content
"""

    def mock_run_command(*args, **kwargs):
        async def _coro():
            return (CmdResult(diff_output, "", ""), 0)

        return _coro()

    with patch(
        "zrb.util.git.run_command", new=MagicMock(side_effect=mock_run_command)
    ) as mock_run:
        result = await get_diff("/repo", "HEAD~1", "HEAD")

        assert "new.txt" in result.created
        assert "deleted.txt" in result.removed
        assert "modified.txt" in result.updated


@pytest.mark.asyncio
async def test_get_repo_dir():
    def mock_run_command(*args, **kwargs):
        async def _coro():
            return (CmdResult("/path/to/repo\n", "", ""), 0)

        return _coro()

    with patch(
        "zrb.util.git.run_command", new=MagicMock(side_effect=mock_run_command)
    ) as mock_run:
        result = await get_repo_dir()
        assert result == "/path/to/repo"


@pytest.mark.asyncio
async def test_get_current_branch():
    def mock_run_command(*args, **kwargs):
        async def _coro():
            return (CmdResult("main\n", "", ""), 0)

        return _coro()

    with patch(
        "zrb.util.git.run_command", new=MagicMock(side_effect=mock_run_command)
    ) as mock_run:
        result = await get_current_branch("/repo")
        assert result == "main"


@pytest.mark.asyncio
async def test_get_branches():
    output = "  main\n* develop\n  feature"

    def mock_run_command(*args, **kwargs):
        async def _coro():
            return (CmdResult(output, "", ""), 0)

        return _coro()

    with patch(
        "zrb.util.git.run_command", new=MagicMock(side_effect=mock_run_command)
    ) as mock_run:
        result = await get_branches("/repo")
        assert "main" in result
        assert "develop" in result
        assert "feature" in result


@pytest.mark.asyncio
async def test_delete_branch():
    def mock_run_command(*args, **kwargs):
        async def _coro():
            return (CmdResult("Deleted branch foo", "", ""), 0)

        return _coro()

    with patch(
        "zrb.util.git.run_command", new=MagicMock(side_effect=mock_run_command)
    ) as mock_run:
        await delete_branch("/repo", "foo")
        mock_run.assert_called_with(
            cmd=["git", "branch", "-d", "foo"], cwd="/repo", print_method=print
        )


@pytest.mark.asyncio
async def test_add():
    def mock_run_command(*args, **kwargs):
        async def _coro():
            return (CmdResult("", "", ""), 0)

        return _coro()

    with patch(
        "zrb.util.git.run_command", new=MagicMock(side_effect=mock_run_command)
    ) as mock_run:
        await add("/repo")
        mock_run.assert_called()


@pytest.mark.asyncio
async def test_commit():
    def mock_run_command(*args, **kwargs):
        async def _coro():
            return (CmdResult("[main 123456] message", "", ""), 0)

        return _coro()

    with patch(
        "zrb.util.git.run_command", new=MagicMock(side_effect=mock_run_command)
    ) as mock_run:
        await commit("/repo", "message")
        mock_run.assert_called()


@pytest.mark.asyncio
async def test_commit_nothing_to_commit():
    # Simulate exit code 1 but "nothing to commit" in output
    def mock_run_command(*args, **kwargs):
        async def _coro():
            return (
                CmdResult("nothing to commit, working tree clean", "", ""),
                1,
            )

        return _coro()

    with patch(
        "zrb.util.git.run_command", new=MagicMock(side_effect=mock_run_command)
    ) as mock_run:
        # Should not raise exception
        await commit("/repo", "message")


@pytest.mark.asyncio
async def test_pull():
    def mock_run_command(*args, **kwargs):
        async def _coro():
            return (CmdResult("Already up to date.", "", ""), 0)

        return _coro()

    with patch(
        "zrb.util.git.run_command", new=MagicMock(side_effect=mock_run_command)
    ) as mock_run:
        await pull("/repo", "origin", "main")
        mock_run.assert_called()


@pytest.mark.asyncio
async def test_push():
    def mock_run_command(*args, **kwargs):
        async def _coro():
            return (CmdResult("Everything up-to-date", "", ""), 0)

        return _coro()

    with patch(
        "zrb.util.git.run_command", new=MagicMock(side_effect=mock_run_command)
    ) as mock_run:
        await push("/repo", "origin", "main")
        mock_run.assert_called()


@pytest.mark.asyncio
async def test_git_errors():
    # Test error raising for all functions
    def mock_run_command(*args, **kwargs):
        async def _coro():
            return (CmdResult("", "Error", "Error"), 1)

        return _coro()

    with patch(
        "zrb.util.git.run_command", new=MagicMock(side_effect=mock_run_command)
    ) as mock_run:
        with pytest.raises(Exception):
            await get_diff("/repo", "HEAD", "HEAD")

        with pytest.raises(Exception):
            await get_repo_dir()

        with pytest.raises(Exception):
            await get_current_branch("/repo")

        with pytest.raises(Exception):
            await get_branches("/repo")

        with pytest.raises(Exception):
            await delete_branch("/repo", "branch")

        with pytest.raises(Exception):
            await add("/repo")

        with pytest.raises(Exception):
            await commit("/repo", "msg")

        with pytest.raises(Exception):
            await pull("/repo", "origin", "main")

        with pytest.raises(Exception):
            await push("/repo", "origin", "main")
