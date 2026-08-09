"""Tests for llm/prompt/system_context.py.

The module is split into a stable half (``system_context`` — session-invariant
facts rendered into the cached system prompt) and a volatile half
(``render_live_context`` — per-turn state injected into the user turn). The two
test classes below mirror that split; the cross-cutting guards assert the
volatile content stays *out* of the system prompt (so the cacheable prefix
survives) and the stable content stays *out* of the live block.
"""

from unittest.mock import MagicMock, patch

from zrb.context.any_context import AnyContext
from zrb.llm.prompt.live_context import render_live_context
from zrb.llm.prompt.system_context import system_context
from zrb.llm.sandbox import SandboxPolicy, set_current_sandbox_policy
from zrb.llm.tool.plan import get_current_context_session


class TestSystemContext:
    """Test the stable ``system_context`` middleware (cached system prompt)."""

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

    def test_system_context_includes_os_and_cwd(self):
        """system_context enriched prompt should include OS and CWD info."""
        ctx = MagicMock(spec=AnyContext)
        received = []

        def next_handler(ctx, prompt):
            received.append(prompt)
            return "ok"

        system_context(ctx, "test", next_handler)

        enriched = received[0]
        assert "OS:" in enriched
        assert "CWD:" in enriched

    def test_system_context_states_that_tool_calls_reach_the_real_machine(self):
        """The unsandboxed default must be stated, not left for the model to guess.

        Priority Order rank 1 says to confirm anything destructive or
        irreversible. ``LLM_SANDBOX_ENABLED`` defaults to False, so by default
        that is literally true — and nothing else in the composed prompt says
        so. A rule whose stakes are invisible is a rule that gets under-applied.
        """
        ctx = MagicMock(spec=AnyContext)
        received = []

        set_current_sandbox_policy(SandboxPolicy(enabled=False))
        try:
            system_context(ctx, "test", lambda c, p: received.append(p) or "ok")
        finally:
            set_current_sandbox_policy(None)

        assert "Sandbox: none" in received[0]

    def test_system_context_claims_no_containment_when_sandboxed(self):
        """Silence when contained — never a licence to relax.

        The affirmative branch is deliberately absent: a "you are sandboxed"
        line would relax rank 1 on the strength of a config the model cannot
        verify. Saying nothing leaves the unconditional rule in force, which is
        the safe way to be wrong.
        """
        ctx = MagicMock(spec=AnyContext)
        received = []

        set_current_sandbox_policy(SandboxPolicy(enabled=True))
        try:
            system_context(ctx, "test", lambda c, p: received.append(p) or "ok")
        finally:
            set_current_sandbox_policy(None)

        assert "Sandbox" not in received[0]

    def test_system_context_excludes_volatile_state(self):
        """Volatile per-turn state must NOT live in the cached system prompt.

        Time/git/todos/worktree change between turns; emitting them here would
        invalidate the cacheable prefix on every request. They belong to
        render_live_context instead.
        """
        ctx = MagicMock(spec=AnyContext)
        received = []
        system_context(ctx, "test", lambda c, p: received.append(p) or "ok")
        enriched = received[0]
        assert "Time:" not in enriched
        assert "Git:" not in enriched
        assert "Todos" not in enriched
        assert "Interactive:" not in enriched

    def test_system_context_anchors_live_context_contract(self):
        """The system prompt must explain the <live-context> block to the model."""
        ctx = MagicMock(spec=AnyContext)
        received = []
        system_context(ctx, "test", lambda c, p: received.append(p) or "ok")
        enriched = received[0]
        assert "<live-context>" in enriched
        assert "authoritative" in enriched

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

    def test_deny_listed_model_gets_the_batching_override(self):
        """The only parallel-tool-call line that renders is the withdrawal.

        Batching is the prompt's unconditional default (ADR-0038); this line is
        how a model known to malform parallel calls opts back out.
        """
        ctx = MagicMock(spec=AnyContext)
        received = []
        system_context(
            ctx,
            "",
            lambda c, p: received.append(p) or "ok",
            model="ollama:minimax-m2.7:cloud",
        )
        rendered = received[0]
        assert "NOT supported by this model" in rendered
        assert "one tool call per response" in rendered

    def test_the_override_outranks_the_tool_descriptions_too(self):
        """Batching is now urged in two places the override has to beat.

        `workflow`'s Tool usage rule and `read_file`'s docstring both tell the
        model to batch. For a deny-listed model the request-level
        `parallel_tool_calls=False` is documented as defence-in-depth only —
        Ollama-cloud ignores it — so this line is the mechanism that actually
        works, and it has to name what it overrides.
        """
        ctx = MagicMock(spec=AnyContext)
        received = []
        system_context(
            ctx,
            "",
            lambda c, p: received.append(p) or "ok",
            model="ollama:glm-4.7:cloud",
        )
        rendered = received[0]
        assert "overrides every batching instruction" in rendered
        assert "tool description" in rendered

    def test_read_file_defers_to_the_system_context_override(self):
        """The docstring must not contradict the line that overrides it.

        A tool description is static, so it cannot be withheld per model. It can
        only name its own exception — otherwise a deny-listed model reads "call
        this in parallel" and "issue exactly one tool call" in the same request.
        """
        from zrb.llm.tool.file_read import read_file

        doc = " ".join((read_file.__doc__ or "").split())

        assert "in parallel" in doc
        assert "unless System Context says this model cannot batch" in doc

    def test_no_model_is_told_that_batching_is_supported(self):
        """Regression: the affirmative branch was unreachable and gated the rule.

        ``supports_parallel_tool_calls`` resolves to True for no built-in model,
        so an affirmative line could never render — yet ``workflow.md`` made
        batching conditional on it appearing. Every model read the rule as
        unsatisfied. The affirmative branch is gone; nothing may reintroduce it.
        """
        ctx = MagicMock(spec=AnyContext)
        for name in ("openai:gpt-4o-mini", "google:gemini-2.5-flash", None):
            received = []
            system_context(ctx, "", lambda c, p: received.append(p) or "ok", model=name)
            assert "Parallel tool calls: supported" not in received[0]

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


class TestRenderLiveContext:
    """Test the volatile ``render_live_context`` renderer (injected user turn)."""

    def test_render_live_context_includes_time(self):
        """The live block carries the per-turn timestamp."""
        ctx = MagicMock(spec=AnyContext)
        rendered = render_live_context(ctx)
        assert "Time:" in rendered

    def test_render_live_context_excludes_stable_facts(self):
        """Stable facts stay in the system prompt, not the per-turn block."""
        ctx = MagicMock(spec=AnyContext)
        rendered = render_live_context(ctx)
        assert "OS:" not in rendered
        assert "CWD:" not in rendered
        assert "Project:" not in rendered

    def test_render_live_context_includes_git_when_in_repo(self):
        """render_live_context should include git info when inside a git repo."""
        ctx = MagicMock(spec=AnyContext)

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
                rendered = render_live_context(ctx)

        assert "Git:" in rendered

    def test_live_context_git_calls_honour_the_configured_timeout(self, monkeypatch):
        """Every live-context git call is bounded by ZRB_LLM_GIT_CMD_TIMEOUT.

        Regression: the timeout was hardcoded to 5s while the knob documenting
        this cap was never read by anything, so raising or lowering it did
        nothing.
        """
        ctx = MagicMock(spec=AnyContext)
        monkeypatch.setenv("ZRB_LLM_GIT_CMD_TIMEOUT", "3000")

        with patch("zrb.llm.util.git.is_inside_git_dir", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="")
                render_live_context(ctx)

        git_calls = [
            c for c in mock_run.call_args_list if c.args and "git" in c.args[0]
        ]
        assert git_calls, "no git commands ran"
        assert all(c.kwargs.get("timeout") == 3.0 for c in git_calls), [
            c.kwargs.get("timeout") for c in git_calls
        ]

    def test_render_live_context_wires_session_from_ctx(self):
        """render_live_context should set the tool session from ctx.input.session."""
        ctx = MagicMock()
        ctx.input.session = "my-special-session"

        render_live_context(ctx)

        assert get_current_context_session() == "my-special-session"

    def test_render_live_context_injects_pending_todos(self):
        """render_live_context should include pending and in_progress todos."""
        ctx = MagicMock()
        ctx.input.session = "todo-inject-session"

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
            rendered = render_live_context(ctx)

        assert "Todos" in rendered
        assert "Pending task" in rendered
        assert "Active task" in rendered
        assert "Done task" not in rendered  # completed items omitted

    def test_render_live_context_omits_todos_when_all_complete(self):
        """No Todos section when no pending/in_progress items exist."""
        ctx = MagicMock()
        ctx.input.session = "all-done-session"

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
            rendered = render_live_context(ctx)

        assert "Todos" not in rendered

    def test_render_live_context_omits_todos_when_none_exist(self):
        """No Todos section when get_todos returns None."""
        ctx = MagicMock()
        ctx.input.session = "no-todos-session"

        with patch("zrb.llm.tool.plan.todo_manager") as mock_tm:
            mock_tm.get_todos.return_value = None
            rendered = render_live_context(ctx)

        assert "Todos" not in rendered

    def test_render_live_context_renders_interactive_yes_by_default(self):
        """Without ctx.input.interactive set, default is interactive=True."""
        ctx = MagicMock(spec=AnyContext)
        rendered = render_live_context(ctx)
        assert "Interactive: yes" in rendered
        # Negative guard rail must not appear in interactive mode
        assert "do not call AskUserQuestion" not in rendered

    def test_render_live_context_renders_interactive_no_when_input_false(self):
        """ctx.input.interactive=False renders the non-interactive guard line.

        The line no longer names the tools it used to forbid: AskUserQuestion,
        EnterPlanMode and ExitPlanMode are registered only in interactive
        sessions, so this branch warned against three tools that were already
        absent from it. What it must still carry is the instruction that
        replaces waiting — proceed rather than block.
        """
        ctx = MagicMock()
        ctx.input.session = "noninteractive-session"
        ctx.input.interactive = False
        rendered = render_live_context(ctx)
        assert "Interactive: no" in rendered
        assert "do not wait on user input" in rendered
        assert "AskUserQuestion" not in rendered

    def test_render_live_context_sets_interactive_mode_contextvar(self):
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
            render_live_context(ctx)
            assert get_interactive_mode() is False
        finally:
            set_interactive_mode(True)

    def test_render_live_context_omits_mode_line_in_default_mode(self):
        """No 'Active mode' line unless plan mode is explicitly entered."""
        ctx = MagicMock(spec=AnyContext)
        rendered = render_live_context(ctx)
        assert "Active mode" not in rendered

    def test_render_live_context_includes_plan_mode_line(self):
        """Entering plan mode surfaces a read-only mode line in the block."""
        from zrb.llm.permission.state import (
            AgentMode,
            AgentModeState,
            current_agent_mode,
        )

        ctx = MagicMock(spec=AnyContext)
        token = current_agent_mode.set(AgentModeState(mode=AgentMode.PLAN))
        try:
            rendered = render_live_context(ctx)
        finally:
            current_agent_mode.reset(token)
        assert "Active mode: PLAN" in rendered
