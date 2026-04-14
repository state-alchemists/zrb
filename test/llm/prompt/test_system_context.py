"""Tests for llm/prompt/system_context.py."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from zrb.context.any_context import AnyContext
from zrb.llm.prompt.system_context import (
    _get_git_info,
    _get_project_files,
    _get_runtime_info,
    _get_tool_version,
    system_context,
)


class TestSystemContext:
    """Test system_context function."""

    def test_system_context_calls_next_handler(self):
        """system_context should call next_handler with enriched prompt."""
        ctx = MagicMock(spec=AnyContext)
        received_prompts = []

        def next_handler(ctx, prompt):
            received_prompts.append(prompt)
            return "result"

        result = system_context(ctx, "original prompt", next_handler)

        assert result == "result"
        assert len(received_prompts) == 1
        # Prompt should be enriched with system context
        enriched = received_prompts[0]
        assert "original prompt" in enriched
        assert "System Context" in enriched

    def test_system_context_includes_time_and_os(self):
        """system_context enriched prompt should include time and OS info."""
        ctx = MagicMock(spec=AnyContext)
        received = []

        def next_handler(ctx, prompt):
            received.append(prompt)
            return "ok"

        system_context(ctx, "test", next_handler)

        enriched = received[0]
        assert "Current Time" in enriched
        assert "Operating System" in enriched
        assert "Current Directory" in enriched


class TestGetProjectFiles:
    """Test _get_project_files function."""

    def test_returns_empty_when_no_files(self, tmp_path, monkeypatch):
        """Returns empty string when no project files exist."""
        monkeypatch.chdir(tmp_path)
        result = _get_project_files()
        assert result == ""

    def test_returns_found_files(self, tmp_path, monkeypatch):
        """Returns found project files in categories."""
        monkeypatch.chdir(tmp_path)
        # Create a known project file
        (tmp_path / "README.md").write_text("# Test")

        result = _get_project_files()
        assert "README.md" in result
        assert "Documentation" in result


class TestGetRuntimeInfo:
    """Test _get_runtime_info function."""

    def test_returns_string(self):
        """_get_runtime_info returns a string (may be empty if no tools installed)."""
        result = _get_runtime_info()
        assert isinstance(result, str)

    def test_includes_installed_tools(self, monkeypatch):
        """Known installed tools appear in runtime info."""
        # Mock shutil.which to pretend python is available
        import shutil

        original_which = shutil.which

        def mock_which(cmd):
            if cmd == "python":
                return "/usr/bin/python"
            return None

        with patch("shutil.which", side_effect=mock_which):
            with patch("subprocess.run") as mock_run:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = "Python 3.14.0"
                mock_result.stderr = ""
                mock_run.return_value = mock_result

                result = _get_runtime_info()

        assert "Python" in result


class TestGetToolVersion:
    """Test _get_tool_version function."""

    def test_returns_empty_when_tool_not_found(self):
        """Returns empty string when command not in PATH."""
        with patch("shutil.which", return_value=None):
            result = _get_tool_version("nonexistent_cmd", ["--version"])
        assert result == ""

    def test_returns_version_string(self):
        """Returns first line of output when command succeeds."""
        with patch("shutil.which", return_value="/usr/bin/fake"):
            with patch("subprocess.run") as mock_run:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = "fake 1.2.3\nExtra line"
                mock_result.stderr = ""
                mock_run.return_value = mock_result

                result = _get_tool_version("fake", ["--version"])

        assert result == "fake 1.2.3"

    def test_returns_empty_on_nonzero_exit(self):
        """Returns empty string when command exits with non-zero code."""
        with patch("shutil.which", return_value="/usr/bin/fake"):
            with patch("subprocess.run") as mock_run:
                mock_result = MagicMock()
                mock_result.returncode = 1
                mock_result.stdout = "error output"
                mock_result.stderr = "error"
                mock_run.return_value = mock_result

                result = _get_tool_version("fake", ["--version"])

        assert result == ""

    def test_returns_empty_on_exception(self):
        """Returns empty string when subprocess raises exception."""
        with patch("shutil.which", return_value="/usr/bin/fake"):
            with patch("subprocess.run", side_effect=Exception("timeout")):
                result = _get_tool_version("fake", ["--version"])

        assert result == ""

    def test_uses_stderr_when_stdout_empty(self):
        """Falls back to stderr when stdout is empty."""
        with patch("shutil.which", return_value="/usr/bin/java"):
            with patch("subprocess.run") as mock_run:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = ""
                mock_result.stderr = "java version 11.0.1"
                mock_run.return_value = mock_result

                result = _get_tool_version("java", ["-version"])

        assert result == "java version 11.0.1"


class TestGetGitInfo:
    """Test _get_git_info function."""

    def test_returns_empty_when_not_git_repo(self):
        """Returns empty string when not inside a git repository."""
        with patch(
            "zrb.llm.prompt.system_context.is_inside_git_dir", return_value=False
        ):
            result = _get_git_info()
        assert result == ""

    def test_returns_branch_and_status_in_git_repo(self):
        """Returns branch and status when in a git repository."""
        with patch(
            "zrb.llm.prompt.system_context.is_inside_git_dir", return_value=True
        ):
            with patch("subprocess.run") as mock_run:

                def side_effect(args, **kwargs):
                    result = MagicMock()
                    if "branch" in args:
                        result.stdout = "main\n"
                    elif "status" in args:
                        result.stdout = ""  # Clean
                    return result

                mock_run.side_effect = side_effect
                result = _get_git_info()

        assert "main" in result
        assert "Clean" in result

    def test_returns_dirty_when_uncommitted_changes(self):
        """Reports 'Dirty' when there are uncommitted changes."""
        with patch(
            "zrb.llm.prompt.system_context.is_inside_git_dir", return_value=True
        ):
            with patch("subprocess.run") as mock_run:

                def side_effect(args, **kwargs):
                    result = MagicMock()
                    if "branch" in args:
                        result.stdout = "feature-branch\n"
                    elif "status" in args:
                        result.stdout = "M modified_file.py\n"
                    return result

                mock_run.side_effect = side_effect
                result = _get_git_info()

        assert "Dirty" in result

    def test_returns_empty_on_exception(self):
        """Returns empty string when an exception occurs."""
        with patch(
            "zrb.llm.prompt.system_context.is_inside_git_dir",
            side_effect=Exception("git error"),
        ):
            result = _get_git_info()
        assert result == ""
