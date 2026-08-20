from unittest.mock import MagicMock, patch

import pytest

from zrb.util.cmd.command import CmdResult
from zrb.util.git.commands import (
    add,
    commit,
    delete_branch,
    get_branches,
    get_current_branch,
    get_diff,
    get_repo_dir,
    is_branch_merged,
    pull,
    push,
)


@pytest.fixture
def mock_print():
    return MagicMock()


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
        "zrb.util.git.commands.run_command", new=MagicMock(side_effect=mock_run_command)
    ):
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
        "zrb.util.git.commands.run_command", new=MagicMock(side_effect=mock_run_command)
    ):
        result = await get_repo_dir()
        assert result == "/path/to/repo"


@pytest.mark.asyncio
async def test_get_current_branch():
    def mock_run_command(*args, **kwargs):
        async def _coro():
            return (CmdResult("main\n", "", ""), 0)

        return _coro()

    with patch(
        "zrb.util.git.commands.run_command", new=MagicMock(side_effect=mock_run_command)
    ):
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
        "zrb.util.git.commands.run_command", new=MagicMock(side_effect=mock_run_command)
    ):
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
        "zrb.util.git.commands.run_command", new=MagicMock(side_effect=mock_run_command)
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
        "zrb.util.git.commands.run_command", new=MagicMock(side_effect=mock_run_command)
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
        "zrb.util.git.commands.run_command", new=MagicMock(side_effect=mock_run_command)
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
        "zrb.util.git.commands.run_command", new=MagicMock(side_effect=mock_run_command)
    ):
        # Should not raise exception
        await commit("/repo", "message")


@pytest.mark.asyncio
async def test_pull():
    def mock_run_command(*args, **kwargs):
        async def _coro():
            return (CmdResult("Already up to date.", "", ""), 0)

        return _coro()

    with patch(
        "zrb.util.git.commands.run_command", new=MagicMock(side_effect=mock_run_command)
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
        "zrb.util.git.commands.run_command", new=MagicMock(side_effect=mock_run_command)
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
        "zrb.util.git.commands.run_command", new=MagicMock(side_effect=mock_run_command)
    ):
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


# --- Tests for is_branch_merged ---


async def _coro(val=None):
    return val


@pytest.mark.asyncio
async def test_is_branch_merged_returns_true_when_merged(mock_print):
    """Test is_branch_merged returns True when branch is in merged list."""
    merged_output = "  main\n* feature-a\n  feature-b\n"

    with patch(
        "zrb.util.git.commands.run_command",
        new=MagicMock(
            side_effect=lambda *a, **k: _coro(
                (CmdResult(output=merged_output, error="", display=""), 0)
            )
        ),
    ):
        result = await is_branch_merged(
            "/fake/repo", "feature-a", print_method=mock_print
        )
        assert result is True


@pytest.mark.asyncio
async def test_is_branch_merged_returns_false_when_not_merged(mock_print):
    """Test is_branch_merged returns False when branch is not in merged list."""
    merged_output = "  main\n* feature-a\n"

    with patch(
        "zrb.util.git.commands.run_command",
        new=MagicMock(
            side_effect=lambda *a, **k: _coro(
                (CmdResult(output=merged_output, error="", display=""), 0)
            )
        ),
    ):
        result = await is_branch_merged(
            "/fake/repo", "feature-b", print_method=mock_print
        )
        assert result is False


@pytest.mark.asyncio
async def test_is_branch_merged_uses_custom_target(mock_print):
    """Test is_branch_merged uses custom target when provided."""
    merged_output = "  main\n  feature-a\n"

    with patch(
        "zrb.util.git.commands.run_command",
        new=MagicMock(
            side_effect=lambda *a, **k: _coro(
                (CmdResult(output=merged_output, error="", display=""), 0)
            )
        ),
    ) as mock_run_command:
        await is_branch_merged(
            "/fake/repo", "feature-a", target="origin/main", print_method=mock_print
        )
        # Verify the command includes the custom target
        mock_run_command.assert_called_with(
            cmd=["git", "branch", "--merged", "origin/main"],
            cwd="/fake/repo",
            print_method=mock_print,
        )


@pytest.mark.asyncio
async def test_is_branch_merged_handles_empty_output(mock_print):
    """Test is_branch_merged handles empty output gracefully."""
    with patch(
        "zrb.util.git.commands.run_command",
        new=MagicMock(
            side_effect=lambda *a, **k: _coro(
                (CmdResult(output="", error="", display=""), 0)
            )
        ),
    ):
        result = await is_branch_merged(
            "/fake/repo", "any-branch", print_method=mock_print
        )
        assert result is False


@pytest.mark.asyncio
async def test_is_branch_merged_throws_on_non_zero_exit(mock_print):
    """Test is_branch_merged raises exception on non-zero exit code."""
    with patch(
        "zrb.util.git.commands.run_command",
        new=MagicMock(
            side_effect=lambda *a, **k: _coro(
                (CmdResult(output="", error="error", display=""), 1)
            )
        ),
    ):
        with pytest.raises(RuntimeError, match="Non zero exit code: 1"):
            await is_branch_merged("/fake/repo", "any-branch", print_method=mock_print)
