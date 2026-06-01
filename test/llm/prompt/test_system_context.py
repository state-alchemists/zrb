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

        with patch("zrb.llm.util.git.is_inside_git_dir", return_value=True):
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

    def test_system_context_omits_model_line_when_model_is_none(self):
        """Default callers (no model bound) get no Model line — back-compat."""
        ctx = MagicMock(spec=AnyContext)
        received = []
        system_context(ctx, "", lambda c, p: received.append(p) or "ok")
        assert "Model:" not in received[0]

    def test_system_context_shows_plain_model_line_for_unknown_caps_model(self):
        """When the registry has no parallel-tool-call knowledge, only the identifier shows — no guidance."""
        ctx = MagicMock(spec=AnyContext)
        received = []
        system_context(
            ctx,
            "",
            lambda c, p: received.append(p) or "ok",
            model="openai:gpt-4o",
        )
        rendered = received[0]
        assert "- Model: openai:gpt-4o" in rendered
        # Neither encouragement nor warning when tristate is None
        assert "CRITICAL" not in rendered
        assert "supports parallel tool calls" not in rendered.lower()

    def test_system_context_only_shows_model_line_no_capability_warning(self):
        """Capability-driven guidance moved to Tool Usage Guide — system context is identity-only."""
        ctx = MagicMock(spec=AnyContext)
        received = []
        system_context(
            ctx,
            "",
            lambda c, p: received.append(p) or "ok",
            model="ollama:minimax-m2.7:cloud",
        )
        rendered = received[0]
        assert "- Model: ollama:minimax-m2.7:cloud" in rendered
        # The CRITICAL warning is no longer emitted from system_context —
        # it lives in the Tool Usage Guide section (see test_tool_guidance.py).
        assert "CRITICAL" not in rendered
        assert "`ReadReadRead`" not in rendered

    def test_system_context_omits_model_line_when_model_unrecognisable(self):
        """A MagicMock with no real ``model_name`` is treated as unknown."""
        ctx = MagicMock(spec=AnyContext)
        received = []
        opaque_model = MagicMock()  # .model_name returns another MagicMock
        system_context(
            ctx,
            "",
            lambda c, p: received.append(p) or "ok",
            model=opaque_model,
        )
        assert "Model:" not in received[0]

    def test_system_context_renders_interactive_yes_by_default(self):
        """Without ctx.input.interactive set, default is interactive=True."""
        ctx = MagicMock(spec=AnyContext)
        received = []
        system_context(ctx, "", lambda c, p: received.append(p) or "ok")
        rendered = received[0]
        assert "Interactive: yes" in rendered
        # Negative guard rail must not appear in interactive mode
        assert "do not call AskUserQuestion" not in rendered

    def test_system_context_renders_interactive_no_when_input_false(self):
        """ctx.input.interactive=False renders the non-interactive guard line."""
        ctx = MagicMock()
        ctx.input.session = "noninteractive-session"
        ctx.input.interactive = False
        received = []
        system_context(ctx, "", lambda c, p: received.append(p) or "ok")
        rendered = received[0]
        assert "Interactive: no" in rendered
        assert "do not call AskUserQuestion" in rendered

    def test_system_context_sets_interactive_mode_contextvar(self):
        """The ContextVar must be updated so the tool can read it later."""
        from zrb.llm.tool.ambient_state import (
            get_interactive_mode,
            set_interactive_mode,
        )

        # Start from a known state different from the value we'll set
        set_interactive_mode(True)
        try:
            ctx = MagicMock()
            ctx.input.session = "ctxvar-session"
            ctx.input.interactive = False
            system_context(ctx, "", lambda c, p: "ok")
            assert get_interactive_mode() is False
        finally:
            set_interactive_mode(True)

    def test_system_context_omits_mode_line_in_default_mode(self):
        """No 'Active mode' line unless plan mode is explicitly entered."""
        received = []
        ctx = MagicMock(spec=AnyContext)
        system_context(ctx, "test", lambda c, p: received.append(p))
        assert "Active mode" not in received[0]

    def test_system_context_includes_plan_mode_line(self):
        """Entering plan mode surfaces a read-only mode line in the prompt."""
        from zrb.llm.permission.state import AgentMode, current_agent_mode

        received = []
        ctx = MagicMock(spec=AnyContext)
        token = current_agent_mode.set(AgentMode.PLAN)
        try:
            system_context(ctx, "test", lambda c, p: received.append(p))
        finally:
            current_agent_mode.reset(token)
        assert "Active mode: PLAN" in received[0]
