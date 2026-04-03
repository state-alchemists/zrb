from unittest import mock

import pytest

from zrb.util import git as git_util
from zrb.util.cmd.command import CmdResult


async def _coro(val=None):
    return val


@pytest.fixture
def mock_print():
    return mock.MagicMock()


# --- Tests for is_branch_merged ---


@pytest.mark.asyncio
async def test_is_branch_merged_returns_true_when_merged(mock_print):
    """Test is_branch_merged returns True when branch is in merged list."""
    merged_output = "  main\n* feature-a\n  feature-b\n"

    with mock.patch(
        "zrb.util.git.run_command",
        new=mock.MagicMock(
            side_effect=lambda *a, **k: _coro(
                (CmdResult(output=merged_output, error="", display=""), 0)
            )
        ),
    ):
        result = await git_util.is_branch_merged(
            "/fake/repo", "feature-a", print_method=mock_print
        )
        assert result is True


@pytest.mark.asyncio
async def test_is_branch_merged_returns_false_when_not_merged(mock_print):
    """Test is_branch_merged returns False when branch is not in merged list."""
    merged_output = "  main\n* feature-a\n"

    with mock.patch(
        "zrb.util.git.run_command",
        new=mock.MagicMock(
            side_effect=lambda *a, **k: _coro(
                (CmdResult(output=merged_output, error="", display=""), 0)
            )
        ),
    ):
        result = await git_util.is_branch_merged(
            "/fake/repo", "feature-b", print_method=mock_print
        )
        assert result is False


@pytest.mark.asyncio
async def test_is_branch_merged_uses_custom_target(mock_print):
    """Test is_branch_merged uses custom target when provided."""
    merged_output = "  main\n  feature-a\n"

    with mock.patch(
        "zrb.util.git.run_command",
        new=mock.MagicMock(
            side_effect=lambda *a, **k: _coro(
                (CmdResult(output=merged_output, error="", display=""), 0)
            )
        ),
    ) as mock_run_command:
        await git_util.is_branch_merged(
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
    with mock.patch(
        "zrb.util.git.run_command",
        new=mock.MagicMock(
            side_effect=lambda *a, **k: _coro(
                (CmdResult(output="", error="", display=""), 0)
            )
        ),
    ):
        result = await git_util.is_branch_merged(
            "/fake/repo", "any-branch", print_method=mock_print
        )
        assert result is False


@pytest.mark.asyncio
async def test_is_branch_merged_throws_on_non_zero_exit(mock_print):
    """Test is_branch_merged raises exception on non-zero exit code."""
    with mock.patch(
        "zrb.util.git.run_command",
        new=mock.MagicMock(
            side_effect=lambda *a, **k: _coro(
                (CmdResult(output="", error="error", display=""), 1)
            )
        ),
    ):
        with pytest.raises(Exception, match="Non zero exit code: 1"):
            await git_util.is_branch_merged(
                "/fake/repo", "any-branch", print_method=mock_print
            )