"""Tests for llm/prompt/system_context.py."""

from unittest.mock import MagicMock, patch

import pytest

from zrb.context.any_context import AnyContext
from zrb.llm.prompt.system_context import system_context
from zrb.llm.tool.plan import get_current_context_session, set_current_session


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
        assert "Time:" in enriched
        assert "OS:" in enriched
        assert "CWD:" in enriched

    def test_system_context_includes_tools(self):
        """system_context should include installed tools."""
        ctx = MagicMock(spec=AnyContext)
        received = []

        def next_handler(ctx, prompt):
            received.append(prompt)
            return "ok"

        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/python"
            with patch("subprocess.run") as mock_run:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = "Python 3.14.0"
                mock_run.return_value = mock_result
                system_context(ctx, "test", next_handler)

        enriched = received[0]
        assert "Tools:" in enriched

    def test_system_context_includes_git_when_in_repo(self):
        """system_context should include git info when inside a git repo."""
        ctx = MagicMock(spec=AnyContext)
        received = []

        def next_handler(ctx, prompt):
            received.append(prompt)
            return "ok"

        with patch(
            "zrb.llm.prompt.system_context.is_inside_git_dir", return_value=True
        ):
            with patch("subprocess.run") as mock_run:

                def side_effect(args, **kwargs):
                    result = MagicMock()
                    if "branch" in args:
                        result.stdout = "main\n"
                    elif "status" in args:
                        result.stdout = ""
                    return result

                mock_run.side_effect = side_effect
                system_context(ctx, "test", next_handler)

        enriched = received[0]
        assert "Git:" in enriched

    def test_system_context_includes_project_markers(self):
        """system_context should include detected project types."""
        ctx = MagicMock(spec=AnyContext)
        received = []

        def next_handler(ctx, prompt):
            received.append(prompt)
            return "ok"

        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = True
            system_context(ctx, "test", next_handler)

        enriched = received[0]
        assert "Project:" in enriched

    def test_system_context_wires_session_from_ctx(self):
        """system_context should call set_current_session with ctx.input.session value."""
        ctx = MagicMock()
        ctx.input.session = "my-special-session"

        system_context(ctx, "", lambda c, p: "ok")

        assert get_current_context_session() == "my-special-session"

    def test_system_context_injects_pending_todos(self):
        """system_context should include pending and in_progress todos in the prompt."""
        ctx = MagicMock()
        ctx.input.session = "todo-inject-session"
        received = []

        fake_todos = {
            "total": 3,
            "completed": 1,
            "todos": [
                {"id": "1", "content": "Done task", "status": "completed"},
                {"id": "2", "content": "Pending task", "status": "pending"},
                {"id": "3", "content": "Active task", "status": "in_progress"},
            ],
        }

        with patch("zrb.llm.tool.plan.todo_manager") as mock_tm:
            mock_tm.get_todos.return_value = fake_todos
            system_context(ctx, "", lambda c, p: received.append(p) or "ok")

        enriched = received[0]
        assert "Todos" in enriched
        assert "Pending task" in enriched
        assert "Active task" in enriched
        assert "Done task" not in enriched  # completed items omitted

    def test_system_context_omits_todos_when_all_complete(self):
        """system_context should not inject todos when no pending/in_progress items exist."""
        ctx = MagicMock()
        ctx.input.session = "all-done-session"
        received = []

        fake_todos = {
            "total": 2,
            "completed": 2,
            "todos": [
                {"id": "1", "content": "Done 1", "status": "completed"},
                {"id": "2", "content": "Done 2", "status": "completed"},
            ],
        }

        with patch("zrb.llm.tool.plan.todo_manager") as mock_tm:
            mock_tm.get_todos.return_value = fake_todos
            system_context(ctx, "", lambda c, p: received.append(p) or "ok")

        assert "Todos" not in received[0]

    def test_system_context_omits_todos_when_none_exist(self):
        """system_context should not add a Todos section when get_todos returns None."""
        ctx = MagicMock()
        ctx.input.session = "no-todos-session"
        received = []

        with patch("zrb.llm.tool.plan.todo_manager") as mock_tm:
            mock_tm.get_todos.return_value = None
            system_context(ctx, "", lambda c, p: received.append(p) or "ok")

        assert "Todos" not in received[0]
