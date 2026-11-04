"""Tests for builtin/llm/chat_tool_policy.py."""

import os
from unittest.mock import patch

import pytest

from zrb.builtin.llm.chat_tool_policy import (
    approve_if_mv_inside_notes_dir,
    approve_if_path_inside_cwd,
    approve_if_path_inside_notes_dir,
    approve_if_path_inside_parent,
    approve_if_path_inside_skill_or_plugin_dir,
    is_path_inside_notes_outside_memory,
    path_inside_any_parent,
    path_inside_parent,
)


class TestPathInsideParent:

    def test_path_inside_parent_returns_true(self, tmp_path):
        """Returns True when path is inside parent."""
        child = str(tmp_path / "subdir" / "file.txt")
        parent = str(tmp_path)
        assert path_inside_parent(child, parent) is True

    def test_path_is_parent_itself(self, tmp_path):
        """Returns True when path equals parent."""
        parent = str(tmp_path)
        assert path_inside_parent(parent, parent) is True

    def test_path_outside_parent_returns_false(self, tmp_path):
        """Returns False when path is outside parent."""
        other = str(tmp_path / ".." / "other_dir" / "file.txt")
        parent = str(tmp_path)
        assert path_inside_parent(other, parent) is False

    def test_path_exception_returns_false(self):
        """Returns False when path resolution fails."""
        with patch("os.path.abspath", side_effect=Exception("fail")):
            result = path_inside_parent("/some/path", "/parent")
        assert result is False


class TestApproveIfPathInsideParent:

    def test_with_path_key_inside(self, tmp_path):
        """Approves when 'path' is inside parent."""
        child = str(tmp_path / "file.txt")
        result = approve_if_path_inside_parent({"path": child}, str(tmp_path))
        assert result is True

    def test_with_path_key_outside(self, tmp_path):
        """Denies when 'path' is outside parent."""
        result = approve_if_path_inside_parent({"path": "/etc/passwd"}, str(tmp_path))
        assert result is False

    def test_with_no_path_key_returns_true(self):
        """Returns True when no 'path' key exists (tool args without a path are not gated)."""
        result = approve_if_path_inside_parent({"other_key": "value"}, "/parent")
        assert result is True


class TestApproveIfPathInsideCwd:

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


class TestApproveIfPathInsideNotesDir:

    def test_path_inside_notes_dir(self, tmp_path, monkeypatch):
        """Approves when path is inside the notes dir."""
        monkeypatch.setattr(
            "zrb.builtin.llm.chat_tool_policy.CFG",
            type("CFG", (), {"LLM_NOTES_DIR": str(tmp_path)})(),
        )
        child = str(tmp_path / "entry.md")
        result = approve_if_path_inside_notes_dir({"path": child})
        assert result is True


class TestApproveIfPathInsideNotesOutsideMemory:
    """The store lives inside the notes directory, and mutating it asks.

    Memory changes go through `Remember` and `Forget`, which enforce the id, the
    claim's length, the injection markers and the core's cap. A raw write to a
    fact or a delete of one is that same act with none of them.
    """

    def _patch_cfg(self, monkeypatch, notes_dir):
        monkeypatch.setattr(
            "zrb.builtin.llm.chat_tool_policy.CFG",
            type(
                "CFG",
                (),
                {
                    "LLM_NOTES_DIR": str(notes_dir),
                    "LLM_MEMORY_DIR": str(notes_dir / "memory-v1"),
                },
            )(),
        )

    def test_a_note_is_approved(self, tmp_path, monkeypatch):
        self._patch_cfg(monkeypatch, tmp_path)
        result = is_path_inside_notes_outside_memory(
            {"path": str(tmp_path / "user" / "identity.md")}
        )
        assert result is True

    def test_a_fact_file_is_not_approved(self, tmp_path, monkeypatch):
        self._patch_cfg(monkeypatch, tmp_path)
        result = is_path_inside_notes_outside_memory(
            {"path": str(tmp_path / "memory-v1" / "facts" / "x.md")}
        )
        assert result is False

    def test_the_generated_core_is_not_approved(self, tmp_path, monkeypatch):
        self._patch_cfg(monkeypatch, tmp_path)
        result = is_path_inside_notes_outside_memory(
            {"path": str(tmp_path / "memory-v1" / "core.md")}
        )
        assert result is False

    def test_a_path_outside_the_notes_dir_is_not_approved(self, tmp_path, monkeypatch):
        self._patch_cfg(monkeypatch, tmp_path)
        result = is_path_inside_notes_outside_memory({"path": "/etc/passwd"})
        assert result is False

    def test_a_sibling_named_like_the_store_is_still_approved(
        self, tmp_path, monkeypatch
    ):
        """`memory-v1-old` is a notes path, not the store — a prefix test would lie."""
        self._patch_cfg(monkeypatch, tmp_path)
        result = is_path_inside_notes_outside_memory(
            {"path": str(tmp_path / "memory-v1-old" / "note.md")}
        )
        assert result is True


class TestApproveIfMvInsideNotesDir:

    def _patch_cfg(self, monkeypatch, notes_dir):
        monkeypatch.setattr(
            "zrb.builtin.llm.chat_tool_policy.CFG",
            type(
                "CFG",
                (),
                {
                    "LLM_NOTES_DIR": str(notes_dir),
                    "LLM_MEMORY_DIR": str(notes_dir / "memory-v1"),
                },
            )(),
        )

    def test_both_paths_inside_notes_dir(self, tmp_path, monkeypatch):
        self._patch_cfg(monkeypatch, tmp_path)
        result = approve_if_mv_inside_notes_dir(
            {"src": str(tmp_path / "a.md"), "dst": str(tmp_path / "b.md")}
        )
        assert result is True

    def test_src_outside_returns_false(self, tmp_path, monkeypatch):
        self._patch_cfg(monkeypatch, tmp_path)
        result = approve_if_mv_inside_notes_dir(
            {"src": "/etc/passwd", "dst": str(tmp_path / "b.md")}
        )
        assert result is False

    def test_dst_outside_returns_false(self, tmp_path, monkeypatch):
        self._patch_cfg(monkeypatch, tmp_path)
        result = approve_if_mv_inside_notes_dir(
            {"src": str(tmp_path / "a.md"), "dst": "/etc/passwd"}
        )
        assert result is False

    def test_missing_src_returns_false(self, tmp_path, monkeypatch):
        self._patch_cfg(monkeypatch, tmp_path)
        result = approve_if_mv_inside_notes_dir({"dst": str(tmp_path / "b.md")})
        assert result is False

    def test_missing_dst_returns_false(self, tmp_path, monkeypatch):
        self._patch_cfg(monkeypatch, tmp_path)
        result = approve_if_mv_inside_notes_dir({"src": str(tmp_path / "a.md")})
        assert result is False


class TestPathInsideAnyParent:
    """Test path_inside_any_parent helper."""

    def test_path_inside_first_parent(self, tmp_path):
        """Returns True when path is inside the first parent."""
        child = str(tmp_path / "sub" / "file.txt")
        parents = [str(tmp_path), "/nonexistent"]
        assert path_inside_any_parent(child, parents) is True

    def test_path_inside_second_parent(self, tmp_path):
        """Returns True when path is inside a later parent."""
        child = str(tmp_path / "sub" / "file.txt")
        parents = ["/nonexistent", str(tmp_path)]
        assert path_inside_any_parent(child, parents) is True

    def test_path_not_inside_any(self, tmp_path):
        """Returns False when path is inside none of the parents."""
        child = str(tmp_path / "file.txt")
        parents = ["/other", "/another"]
        assert path_inside_any_parent(child, parents) is False

    def test_empty_parents_list(self, tmp_path):
        """Returns False when parents list is empty."""
        assert path_inside_any_parent(str(tmp_path / "file.txt"), []) is False


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
            mock_mgr.search_dirs = [str(skill_subdir)]
            result = approve_if_path_inside_skill_or_plugin_dir({"path": child})
        assert result is True

    def test_path_inside_plugin_dir(self, tmp_path):
        """Approves when path is inside a configured plugin directory."""
        plugin_dir = tmp_path / ".plugins"
        plugin_dir.mkdir()
        child = str(plugin_dir / "my-plugin" / "config.yml")

        with (
            patch("zrb.llm.skill.manager.skill_manager") as mock_mgr,
            patch("zrb.builtin.llm.chat_tool_policy.CFG") as mock_cfg,
        ):
            mock_mgr.search_dirs = []
            mock_cfg.LLM_PLUGIN_DIRS = [str(plugin_dir)]
            result = approve_if_path_inside_skill_or_plugin_dir({"path": child})
        assert result is True

    def test_path_outside_any(self, tmp_path):
        """Denies when path is outside all known dirs."""
        child = str(tmp_path / "random.txt")

        with (
            patch("zrb.llm.skill.manager.skill_manager") as mock_mgr,
            patch("zrb.builtin.llm.chat_tool_policy.CFG") as mock_cfg,
        ):
            mock_mgr.search_dirs = []
            mock_cfg.LLM_PLUGIN_DIRS = []
            result = approve_if_path_inside_skill_or_plugin_dir({"path": child})
        assert result is False


needs_symlinks = pytest.mark.skipif(
    os.name != "posix", reason="creating a symlink needs POSIX or a privilege"
)


@needs_symlinks
class TestASymlinkIsNotAPathAlias:
    """The answer is about the file touched, not the string that names it."""

    def _patch_cfg(self, monkeypatch, notes_dir):
        monkeypatch.setattr(
            "zrb.builtin.llm.chat_tool_policy.CFG",
            type(
                "CFG",
                (),
                {
                    "LLM_NOTES_DIR": str(notes_dir),
                    "LLM_MEMORY_DIR": str(notes_dir / "memory-v1"),
                },
            )(),
        )

    def test_a_symlinked_route_into_the_store_is_not_approved(
        self, tmp_path, monkeypatch
    ):
        """`memory-link` reads as a note and writes a fact; the lexical check missed it."""
        (tmp_path / "memory-v1").mkdir()
        (tmp_path / "memory-link").symlink_to(tmp_path / "memory-v1")
        self._patch_cfg(monkeypatch, tmp_path)
        result = is_path_inside_notes_outside_memory(
            {"path": str(tmp_path / "memory-link" / "facts" / "x.md")}
        )
        assert result is False

    def test_a_symlink_out_of_cwd_is_not_approved(self, tmp_path, monkeypatch):
        (tmp_path / "outside").mkdir()
        work = tmp_path / "work"
        work.mkdir()
        (work / "leak").symlink_to(tmp_path / "outside")
        monkeypatch.chdir(work)
        result = approve_if_path_inside_cwd({"path": str(work / "leak" / "secret.txt")})
        assert result is False

    def test_a_symlink_that_stays_inside_is_still_approved(self, tmp_path, monkeypatch):
        (tmp_path / "real").mkdir()
        (tmp_path / "alias").symlink_to(tmp_path / "real")
        self._patch_cfg(monkeypatch, tmp_path)
        result = is_path_inside_notes_outside_memory(
            {"path": str(tmp_path / "alias" / "note.md")}
        )
        assert result is True


def _chain(policy, next_handler):
    async def chained(ui, call):
        return await policy(ui, call, next_handler)

    return chained


class TestRegisteredChatPolicies:
    """What `zrb llm chat` approves, composed in the order it registered them.

    No test read this composition, which is how `Write`, `Edit` and `RM` came to
    be auto-approved for the memory store on the day the store moved inside the
    notes directory. These assert the outcome, not which policy produced it.
    """

    def _ask(self, verb, args, tmp_path, monkeypatch):
        """The composed policy chain for one call, and the human it may reach."""
        from unittest.mock import AsyncMock, MagicMock

        from zrb.builtin.llm.chat import llm_chat
        from zrb.config.config import CFG

        monkeypatch.setattr(CFG, "LLM_NOTES_DIR", str(tmp_path), raising=False)
        monkeypatch.setattr(
            CFG, "LLM_MEMORY_DIR", str(tmp_path / "memory-v1"), raising=False
        )
        call = MagicMock()
        call.tool_name = verb
        call.args = args
        asked = AsyncMock(return_value="asked")
        handler = asked
        # The task's own order: the first policy to decide wins.
        for policy in reversed(llm_chat.tool_policies):
            handler = _chain(policy, handler)
        return call, handler, asked

    @pytest.mark.asyncio
    @pytest.mark.parametrize("verb", ["Write", "Edit", "RM"])
    async def test_mutating_the_memory_store_reaches_the_human(
        self, verb, tmp_path, monkeypatch
    ):
        call, handler, asked = self._ask(
            verb,
            {"path": str(tmp_path / "memory-v1" / "core.md")},
            tmp_path,
            monkeypatch,
        )
        assert await handler(object(), call) == "asked"
        asked.assert_called_once()

    @pytest.mark.asyncio
    async def test_a_write_to_a_note_is_still_approved(self, tmp_path, monkeypatch):
        from pydantic_ai import ToolApproved

        call, handler, asked = self._ask(
            "Write",
            {"path": str(tmp_path / "user" / "identity.md")},
            tmp_path,
            monkeypatch,
        )
        assert isinstance(await handler(object(), call), ToolApproved)
        asked.assert_not_called()
