"""Tests for builtin/llm/chat_tool_policy.py."""

import os
from unittest.mock import patch

import pytest

from zrb.builtin.llm.chat_tool_policy import (
    _approve_if_path_inside_parent,
    _path_inside_parent,
    approve_if_path_inside_cwd,
    approve_if_path_inside_journal_dir,
)


class TestPathInsideParent:
    """Test _path_inside_parent helper."""

    def test_path_inside_parent_returns_true(self, tmp_path):
        """Returns True when path is inside parent."""
        child = str(tmp_path / "subdir" / "file.txt")
        parent = str(tmp_path)
        assert _path_inside_parent(child, parent) is True

    def test_path_is_parent_itself(self, tmp_path):
        """Returns True when path equals parent."""
        parent = str(tmp_path)
        assert _path_inside_parent(parent, parent) is True

    def test_path_outside_parent_returns_false(self, tmp_path):
        """Returns False when path is outside parent."""
        other = str(tmp_path / ".." / "other_dir" / "file.txt")
        parent = str(tmp_path)
        assert _path_inside_parent(other, parent) is False

    def test_path_exception_returns_false(self):
        """Returns False when path resolution fails."""
        with patch("os.path.abspath", side_effect=Exception("fail")):
            result = _path_inside_parent("/some/path", "/parent")
        assert result is False


class TestApproveIfPathInsideParent:
    """Test _approve_if_path_inside_parent helper."""

    def test_with_path_key_inside(self, tmp_path):
        """Approves when 'path' is inside parent."""
        child = str(tmp_path / "file.txt")
        result = _approve_if_path_inside_parent({"path": child}, str(tmp_path))
        assert result is True

    def test_with_path_key_outside(self, tmp_path):
        """Denies when 'path' is outside parent."""
        result = _approve_if_path_inside_parent({"path": "/etc/passwd"}, str(tmp_path))
        assert result is False

    def test_with_paths_list_all_inside(self, tmp_path):
        """Approves when all 'paths' are inside parent."""
        paths = [str(tmp_path / "a.txt"), str(tmp_path / "b.txt")]
        result = _approve_if_path_inside_parent({"paths": paths}, str(tmp_path))
        assert result is True

    def test_with_paths_list_some_outside(self, tmp_path):
        """Denies when any path in 'paths' is outside parent."""
        paths = [str(tmp_path / "a.txt"), "/etc/passwd"]
        result = _approve_if_path_inside_parent({"paths": paths}, str(tmp_path))
        assert result is False

    def test_with_paths_not_a_list(self, tmp_path):
        """Denies when 'paths' is not a list."""
        result = _approve_if_path_inside_parent({"paths": "not_a_list"}, str(tmp_path))
        assert result is False

    def test_with_files_list_all_inside(self, tmp_path):
        """Approves when all 'files' paths are inside parent."""
        files = [
            {"path": str(tmp_path / "a.txt")},
            {"path": str(tmp_path / "b.txt")},
        ]
        result = _approve_if_path_inside_parent({"files": files}, str(tmp_path))
        assert result is True

    def test_with_files_list_some_outside(self, tmp_path):
        """Denies when any file path is outside parent."""
        files = [
            {"path": str(tmp_path / "a.txt")},
            {"path": "/etc/passwd"},
        ]
        result = _approve_if_path_inside_parent({"files": files}, str(tmp_path))
        assert result is False

    def test_with_files_not_a_list(self, tmp_path):
        """Denies when 'files' is not a list."""
        result = _approve_if_path_inside_parent({"files": "not_a_list"}, str(tmp_path))
        assert result is False

    def test_with_no_path_keys_returns_true(self):
        """Returns True when no path/paths/files keys exist."""
        result = _approve_if_path_inside_parent({"other_key": "value"}, "/parent")
        assert result is True


class TestApproveIfPathInsideCwd:
    """Test approve_if_path_inside_cwd function."""

    def test_path_inside_cwd(self, tmp_path, monkeypatch):
        """Approves when path is inside cwd."""
        monkeypatch.chdir(tmp_path)
        child = str(tmp_path / "file.txt")
        result = approve_if_path_inside_cwd({"path": child})
        assert result is True

    def test_path_outside_cwd(self, tmp_path, monkeypatch):
        """Denies when path is outside cwd."""
        monkeypatch.chdir(tmp_path)
        result = approve_if_path_inside_cwd({"path": "/etc/passwd"})
        assert result is False


class TestApproveIfPathInsideJournalDir:
    """Test approve_if_path_inside_journal_dir function."""

    def test_path_inside_journal_dir(self, tmp_path, monkeypatch):
        """Approves when path is inside journal dir."""
        monkeypatch.setattr(
            "zrb.builtin.llm.chat_tool_policy.CFG",
            type("CFG", (), {"LLM_JOURNAL_DIR": str(tmp_path)})(),
        )
        child = str(tmp_path / "entry.md")
        result = approve_if_path_inside_journal_dir({"path": child})
        assert result is True
