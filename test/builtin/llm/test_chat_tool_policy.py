"""Tests for builtin/llm/chat_tool_policy.py."""

import os
from unittest.mock import MagicMock, patch

import pytest

from zrb.builtin.llm.chat_tool_policy import (
    _approve_if_path_inside_parent,
    _path_inside_any_parent,
    _path_inside_parent,
    approve_if_mv_inside_journal_dir,
    approve_if_path_inside_cwd,
    approve_if_path_inside_journal_dir,
    approve_if_path_inside_skill_or_plugin_dir,
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

    def test_with_no_path_key_returns_true(self):
        """Returns True when no 'path' key exists (tool args without a path are not gated)."""
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


class TestApproveIfMvInsideJournalDir:
    """Test approve_if_mv_inside_journal_dir — both src and dst must be inside."""

    def _patch_cfg(self, monkeypatch, journal_dir):
        monkeypatch.setattr(
            "zrb.builtin.llm.chat_tool_policy.CFG",
            type("CFG", (), {"LLM_JOURNAL_DIR": str(journal_dir)})(),
        )

    def test_both_paths_inside_journal_dir(self, tmp_path, monkeypatch):
        self._patch_cfg(monkeypatch, tmp_path)
        result = approve_if_mv_inside_journal_dir(
            {"src": str(tmp_path / "a.md"), "dst": str(tmp_path / "b.md")}
        )
        assert result is True

    def test_src_outside_returns_false(self, tmp_path, monkeypatch):
        self._patch_cfg(monkeypatch, tmp_path)
        result = approve_if_mv_inside_journal_dir(
            {"src": "/etc/passwd", "dst": str(tmp_path / "b.md")}
        )
        assert result is False

    def test_dst_outside_returns_false(self, tmp_path, monkeypatch):
        self._patch_cfg(monkeypatch, tmp_path)
        result = approve_if_mv_inside_journal_dir(
            {"src": str(tmp_path / "a.md"), "dst": "/etc/passwd"}
        )
        assert result is False

    def test_missing_src_returns_false(self, tmp_path, monkeypatch):
        self._patch_cfg(monkeypatch, tmp_path)
        result = approve_if_mv_inside_journal_dir({"dst": str(tmp_path / "b.md")})
        assert result is False

    def test_missing_dst_returns_false(self, tmp_path, monkeypatch):
        self._patch_cfg(monkeypatch, tmp_path)
        result = approve_if_mv_inside_journal_dir({"src": str(tmp_path / "a.md")})
        assert result is False


class TestPathInsideAnyParent:
    """Test _path_inside_any_parent helper."""

    def test_path_inside_first_parent(self, tmp_path):
        """Returns True when path is inside the first parent."""
        child = str(tmp_path / "sub" / "file.txt")
        parents = [str(tmp_path), "/nonexistent"]
        assert _path_inside_any_parent(child, parents) is True

    def test_path_inside_second_parent(self, tmp_path):
        """Returns True when path is inside a later parent."""
        child = str(tmp_path / "sub" / "file.txt")
        parents = ["/nonexistent", str(tmp_path)]
        assert _path_inside_any_parent(child, parents) is True

    def test_path_not_inside_any(self, tmp_path):
        """Returns False when path is inside none of the parents."""
        child = str(tmp_path / "file.txt")
        parents = ["/other", "/another"]
        assert _path_inside_any_parent(child, parents) is False

    def test_empty_parents_list(self, tmp_path):
        """Returns False when parents list is empty."""
        assert _path_inside_any_parent(str(tmp_path / "file.txt"), []) is False


class TestApproveIfPathInsideSkillOrPluginDir:
    """Test approve_if_path_inside_skill_or_plugin_dir."""

    def test_no_path_key_returns_true(self):
        """Returns True when no 'path' key exists."""
        result = approve_if_path_inside_skill_or_plugin_dir({"other": "value"})
        assert result is True

    def test_path_inside_skill_dir(self, tmp_path):
        """Approves when path is inside a skill search directory."""
        skill_subdir = tmp_path / ".skills"
        skill_subdir.mkdir()
        child = str(skill_subdir / "my-skill.py")

        with patch("zrb.llm.skill.manager.skill_manager") as mock_mgr:
            mock_mgr.get_search_directories.return_value = [str(skill_subdir)]
            result = approve_if_path_inside_skill_or_plugin_dir({"path": child})
        assert result is True

    def test_path_inside_plugin_dir(self, tmp_path):
        """Approves when path is inside a configured plugin directory."""
        plugin_dir = tmp_path / ".plugins"
        plugin_dir.mkdir()
        child = str(plugin_dir / "my-plugin" / "config.yml")

        with patch("zrb.llm.skill.manager.skill_manager") as mock_mgr, patch(
            "zrb.builtin.llm.chat_tool_policy.CFG"
        ) as mock_cfg:
            mock_mgr.get_search_directories.return_value = []
            mock_cfg.LLM_PLUGIN_DIRS = [str(plugin_dir)]
            result = approve_if_path_inside_skill_or_plugin_dir({"path": child})
        assert result is True

    def test_path_outside_any(self, tmp_path):
        """Denies when path is outside all known dirs."""
        child = str(tmp_path / "random.txt")

        with patch("zrb.llm.skill.manager.skill_manager") as mock_mgr, patch(
            "zrb.builtin.llm.chat_tool_policy.CFG"
        ) as mock_cfg:
            mock_mgr.get_search_directories.return_value = []
            mock_cfg.LLM_PLUGIN_DIRS = []
            result = approve_if_path_inside_skill_or_plugin_dir({"path": child})
        assert result is False
