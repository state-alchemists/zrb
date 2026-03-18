"""Tests for llm/util/git.py - Git utility functions."""

import subprocess
from unittest.mock import patch, MagicMock

import pytest


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
            )

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

    def test_actually_inside_git_repo(self):
        """Test is_inside_git_dir in actual git repo (integration test)."""
        from zrb.llm.util.git import is_inside_git_dir
        import os

        # This test runs in the actual repo directory
        # It should return True since we're inside a git repo
        original_cwd = os.getcwd()
        try:
            # Just make sure we're in the repo root
            os.chdir("/home/gofrendi/zrb")
            # The function should detect we're in a git repo
            result = is_inside_git_dir()
            # Since we're running tests in a git repo, should be True
            assert result is True
        finally:
            os.chdir(original_cwd)