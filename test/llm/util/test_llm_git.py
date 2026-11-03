"Tests for llm/util/git.py - Git utility functions."

import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _clear_git_cache():
    "Clear the lru_cache on check_git_dir before each test."
    from zrb.llm.util.git import check_git_dir

    check_git_dir.cache_clear()
    yield
    check_git_dir.cache_clear()


class TestIsInsideGitDir:
    "Test is_inside_git_dir function."

    def test_inside_git_dir(self):
        "Test is_inside_git_dir returns True when inside a git directory."
        from zrb.llm.util.git import is_inside_git_dir

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = is_inside_git_dir()
            assert result is True

    def test_not_inside_git_dir(self):
        "Test is_inside_git_dir returns False when not inside a git directory."
        from zrb.llm.util.git import is_inside_git_dir

        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = is_inside_git_dir()
            assert result is False

    def test_exception_returns_false(self):
        "Test is_inside_git_dir returns False on exception."
        from zrb.llm.util.git import is_inside_git_dir

        with patch("subprocess.run", side_effect=Exception("Test error")):
            result = is_inside_git_dir()
            assert result is False

    def test_calls_git_command(self):
        "Test is_inside_git_dir calls correct git command."
        from zrb.llm.util.git import is_inside_git_dir

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            is_inside_git_dir()
            mock_run.assert_called_once_with(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=os.getcwd(),
                capture_output=True,
                text=True,
                timeout=5.0,
            )

    def test_probe_is_bounded_by_the_configured_timeout(self, monkeypatch):
        "The probe uses ``ZRB_LLM_GIT_CMD_TIMEOUT``."
        from zrb.llm.util.git import is_inside_git_dir

        monkeypatch.setenv("ZRB_LLM_GIT_CMD_TIMEOUT", "2500")
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            is_inside_git_dir()

        assert mock_run.call_args.kwargs["timeout"] == 2.5

    def test_probe_timeout_reads_as_not_a_git_dir(self):
        "A timeout is the same safe answer as any other failure."
        from zrb.llm.util.git import is_inside_git_dir

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 5.0)):
            assert is_inside_git_dir() is False

    def test_filenot_found_returns_false(self):
        "Test is_inside_git_dir handles FileNotFoundError."
        from zrb.llm.util.git import is_inside_git_dir

        with patch("subprocess.run", side_effect=FileNotFoundError("git not found")):
            result = is_inside_git_dir()
            assert result is False

    def test_permission_error_returns_false(self):
        "Test is_inside_git_dir handles PermissionError."
        from zrb.llm.util.git import is_inside_git_dir

        with patch("subprocess.run", side_effect=PermissionError("Permission denied")):
            result = is_inside_git_dir()
            assert result is False

    def test_actually_inside_git_repo(self, monkeypatch):
        "Test is_inside_git_dir in actual git repo (integration test)."
        from pathlib import Path

        from zrb.llm.util.git import is_inside_git_dir

        monkeypatch.chdir(Path(__file__).resolve().parent.parent.parent)
        assert is_inside_git_dir() is True

    def test_probe_timeout_is_not_memoized(self):
        "A timeout result is not memoized."
        from zrb.llm.util.git import is_inside_git_dir

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 5.0)):
            assert is_inside_git_dir() is False

        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            assert is_inside_git_dir() is True
            mock_run.assert_called_once()

    def test_non_timeout_failure_is_still_memoized(self):
        "Only the transient case is retried; a real answer stays cached."
        from zrb.llm.util.git import is_inside_git_dir

        with patch("subprocess.run", side_effect=FileNotFoundError("no git")):
            assert is_inside_git_dir() is False

        with patch("subprocess.run") as mock_run:
            assert is_inside_git_dir() is False
            mock_run.assert_not_called()


class TestRepositoryRoot:
    "Test repository_root, which names the repository a checkout belongs to."

    def test_a_relative_common_dir_is_resolved_where_git_ran(self, tmp_path):
        """Git answers `.git` at a repository's top and `../../.git` from a
        subdirectory.

        `--path-format=absolute` would do that resolving, but it needs Git 2.31,
        and an empty answer reads as "outside any checkout" — which turns the
        journal's scoping off silently. The plain command answers the same thing
        on every version, so the resolution happens here instead."""
        from zrb.llm.util.git import repository_root

        repo = tmp_path / "soda"
        deep = repo / "src" / "deep"
        deep.mkdir(parents=True)
        answer = MagicMock(returncode=0, stdout="../../.git\n")

        with patch("subprocess.run", return_value=answer) as run:
            assert repository_root(str(deep)) == str(repo)

        assert "--path-format=absolute" not in run.call_args.args[0]

    def test_an_absolute_common_dir_is_kept(self, tmp_path):
        "A linked worktree already answers absolutely; resolving must not move it."
        from zrb.llm.util.git import repository_root

        common = tmp_path / "soda" / ".git"
        answer = MagicMock(returncode=0, stdout=f"{common}\n")

        with patch("subprocess.run", return_value=answer):
            assert repository_root(str(tmp_path / "soda-wt")) == str(tmp_path / "soda")
