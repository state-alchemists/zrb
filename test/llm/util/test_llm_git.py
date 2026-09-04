"""Tests for llm/util/git.py - Git utility functions."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _clear_git_cache():
    """Clear the lru_cache on check_git_dir before each test."""
    from zrb.llm.util.git import check_git_dir

    check_git_dir.cache_clear()
    yield
    check_git_dir.cache_clear()


class TestIsInsideGitDir:
    """Test is_inside_git_dir function."""

    def test_inside_git_dir(self):
        """Test is_inside_git_dir returns True when inside a git directory."""
        from zrb.llm.util.git import is_inside_git_dir

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = is_inside_git_dir()
            assert result is True

    def test_not_inside_git_dir(self):
        """Test is_inside_git_dir returns False when not inside a git directory."""
        from zrb.llm.util.git import is_inside_git_dir

        mock_result = MagicMock()
        mock_result.returncode = 1  # Non-zero return code

        with patch("subprocess.run", return_value=mock_result):
            result = is_inside_git_dir()
            assert result is False

    def test_exception_returns_false(self):
        """Test is_inside_git_dir returns False on exception."""
        from zrb.llm.util.git import is_inside_git_dir

        with patch("subprocess.run", side_effect=Exception("Test error")):
            result = is_inside_git_dir()
            assert result is False

    def test_calls_git_command(self):
        """Test is_inside_git_dir calls correct git command."""
        from zrb.llm.util.git import is_inside_git_dir

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            is_inside_git_dir()
            mock_run.assert_called_once_with(
                ["git", "rev-parse", "--is-inside-work-tree"],
                capture_output=True,
                text=True,
                timeout=5.0,
            )

    def test_probe_is_bounded_by_the_configured_timeout(self, monkeypatch):
        """The probe must be bounded, and by ZRB_LLM_GIT_CMD_TIMEOUT.

        Regression: it ran with no timeout at all while the knob that documents
        this cap was never read, so a git that blocks (credential prompt,
        index.lock contention) stalled every prompt compose behind it.
        """
        from zrb.llm.util.git import is_inside_git_dir

        monkeypatch.setenv("ZRB_LLM_GIT_CMD_TIMEOUT", "2500")
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            is_inside_git_dir()

        assert mock_run.call_args.kwargs["timeout"] == 2.5

    def test_probe_timeout_reads_as_not_a_git_dir(self):
        """A timeout is the same safe answer as any other failure."""
        from zrb.llm.util.git import is_inside_git_dir

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 5.0)):
            assert is_inside_git_dir() is False

    def test_filenot_found_returns_false(self):
        """Test is_inside_git_dir handles FileNotFoundError."""
        from zrb.llm.util.git import is_inside_git_dir

        with patch("subprocess.run", side_effect=FileNotFoundError("git not found")):
            result = is_inside_git_dir()
            assert result is False

    def test_permission_error_returns_false(self):
        """Test is_inside_git_dir handles PermissionError."""
        from zrb.llm.util.git import is_inside_git_dir

        with patch("subprocess.run", side_effect=PermissionError("Permission denied")):
            result = is_inside_git_dir()
            assert result is False

    def test_actually_inside_git_repo(self, monkeypatch):
        """Test is_inside_git_dir in actual git repo (integration test)."""
        from pathlib import Path

        from zrb.llm.util.git import is_inside_git_dir

        # monkeypatch.chdir, not a bare os.chdir in try/finally: pytest
        # restores the cwd even when the body dies in a way `finally` cannot
        # catch, so a failure here can't leave every later test in this
        # xdist worker running from the wrong directory.
        monkeypatch.chdir(Path(__file__).resolve().parent.parent.parent)
        assert is_inside_git_dir() is True

    def test_probe_timeout_is_not_memoized(self):
        """A transient stall must not stick as "not a git dir" for the process.

        Regression: the probe is `lru_cache`d, so once a timeout was answered as
        False it was cached — one cold-cache stall (credential prompt,
        index.lock contention) silently disabled the live-context git block and
        the worktree tools for the rest of the run.
        """
        from zrb.llm.util.git import is_inside_git_dir

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 5.0)):
            assert is_inside_git_dir() is False

        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            assert is_inside_git_dir() is True
            mock_run.assert_called_once()

    def test_non_timeout_failure_is_still_memoized(self):
        """Only the transient case is retried; a real answer stays cached."""
        from zrb.llm.util.git import is_inside_git_dir

        with patch("subprocess.run", side_effect=FileNotFoundError("no git")):
            assert is_inside_git_dir() is False

        with patch("subprocess.run") as mock_run:
            assert is_inside_git_dir() is False
            mock_run.assert_not_called()
