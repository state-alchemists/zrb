"""Tests for LLMTaskHistory (conversation/history resolution + error recovery).

Driven through ``LLMTask``, which composes LLMTaskHistory. These methods are
part of that host's surface — it calls them by name and a subclass overrides
them to change where history lives — so calling them directly is exercising the
public API rather than reaching past it.
"""

from unittest.mock import MagicMock

from zrb.llm.task.llm_task import LLMTask


class TestConversationAndHistoryLookup:
    def test_get_history_manager_returns_explicit(self):
        manager = MagicMock()
        task = LLMTask(name="t", history_manager=manager)
        assert task.get_history_manager(MagicMock()) is manager

    def test_get_history_manager_defaults_to_file_manager(self):
        from zrb.llm.history_manager.file_history_manager import FileHistoryManager

        task = LLMTask(name="t")
        assert isinstance(task.get_history_manager(MagicMock()), FileHistoryManager)

    def test_get_conversation_name_uses_explicit(self):
        task = LLMTask(
            name="t", conversation_name="my-convo", render_conversation_name=False
        )
        assert task.get_conversation_name(MagicMock()) == "my-convo"

    def test_get_conversation_name_random_when_blank(self):
        task = LLMTask(name="t")
        name = task.get_conversation_name(MagicMock())
        assert isinstance(name, str) and name.strip() != ""


class TestHistoryConfig:
    """`LLMTask.history_config` groups the same three knobs — see
    `HistoryConfig`'s own docstring for why chat/execution.py's wrap boundary
    forwards this as one unit."""

    def test_reflects_constructor_values(self):
        manager = MagicMock()
        task = LLMTask(
            name="t",
            history_manager=manager,
            conversation_name="my-convo",
            render_conversation_name=False,
        )
        config = task.history_config
        assert config.history_manager is manager
        assert config.conversation_name == "my-convo"
        assert config.render_conversation_name is False

    def test_reflects_history_manager_setter_immediately(self):
        """`history_manager` has a public setter — `history_config` must not
        be a value cached at construction, or the setter's documented
        "visible immediately" contract (see `history.py`'s module docstring)
        would silently stop holding for this read path."""
        task = LLMTask(name="t")
        new_manager = MagicMock()
        task.history_manager = new_manager
        assert task.history_config.history_manager is new_manager


class TestEffectivePrompt:
    def test_first_attempt_passes_message_through(self):
        task = LLMTask(name="t")
        ctx = MagicMock()
        ctx.attempt = 1
        msg, atts = task.get_effective_prompt(ctx, "hello", ["a"], [])
        assert msg == "hello"
        assert atts == ["a"]

    def test_retry_sends_notice_when_message_already_in_history(self):
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        task = LLMTask(name="t")
        ctx = MagicMock()
        ctx.attempt = 2
        history = [ModelRequest(parts=[UserPromptPart(content="hello")])]
        msg, atts = task.get_effective_prompt(ctx, "hello", ["keep"], history)
        assert "retry attempt 2" in msg
        # Attachments are preserved on retry.
        assert atts == ["keep"]

    def test_retry_resends_when_last_user_turn_differs(self):
        # Only the MOST RECENT user turn counts: a recurring message (e.g.
        # "continue") matching an OLD turn must not suppress resending.
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            TextPart,
            UserPromptPart,
        )

        task = LLMTask(name="t")
        ctx = MagicMock()
        ctx.attempt = 2
        history = [
            ModelRequest(parts=[UserPromptPart(content="continue")]),
            ModelResponse(parts=[TextPart(content="done")]),
            ModelRequest(parts=[UserPromptPart(content="something else")]),
        ]
        msg, _ = task.get_effective_prompt(ctx, "continue", None, history)
        assert msg == "continue"

    def test_retry_skips_system_bookkeeping_and_tool_return_turns(self):
        # "[SYSTEM]" turns appended by error recovery and tool-return-only
        # requests are not user turns — the real user turn behind them is
        # the one compared against.
        from pydantic_ai.messages import (
            ModelRequest,
            ToolReturnPart,
            UserPromptPart,
        )

        task = LLMTask(name="t")
        ctx = MagicMock()
        ctx.attempt = 2
        history = [
            ModelRequest(parts=[UserPromptPart(content="hello")]),
            ModelRequest(
                parts=[ToolReturnPart(tool_name="t", content="x", tool_call_id="id1")]
            ),
            ModelRequest(
                parts=[UserPromptPart(content="[SYSTEM] Error occurred: boom")]
            ),
        ]
        msg, _ = task.get_effective_prompt(ctx, "hello", None, history)
        assert "retry attempt 2" in msg


class TestContextLengthDetection:
    def test_detects_keyword(self):
        task = LLMTask(name="t")
        assert task.is_context_length_error(ValueError("prompt too long")) is True

    def test_ignores_unrelated_error(self):
        task = LLMTask(name="t")
        assert task.is_context_length_error(ValueError("boom")) is False

    def test_detects_status_400_with_keyword(self):
        task = LLMTask(name="t")
        err = ValueError("context window exceeded")
        err.status_code = 400
        assert task.is_context_length_error(err) is True


class TestPostProcessOutput:
    def test_strips_ansi_from_string(self):
        task = LLMTask(name="t")
        assert task.post_process_output("\x1b[31mhi\x1b[0m") == "hi"

    def test_passes_through_non_string(self):
        task = LLMTask(name="t")
        payload = {"k": "v"}
        assert task.post_process_output(payload) is payload


class TestSaveCancelledHistory:
    def test_with_partial_run(self):
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        from zrb.llm.agent.run.partial_run import PartialRunAccumulator

        partial_run = PartialRunAccumulator()
        partial_run.completed_tools.append(
            ("search_files", '{"query": "main.py"}', "Found main.py")
        )

        history_manager = MagicMock()
        task = LLMTask(name="test-task")
        task.save_cancelled_history(
            history_manager,
            "test-convo",
            [],
            "hello",
            partial_run=partial_run,
        )

        assert history_manager.update.called
        assert history_manager.save.called
        saved = history_manager.update.call_args[0][1]
        assert len(saved) == 3  # user msg + cancelled marker + partial summary
        assert isinstance(saved[-1], ModelRequest)
        assert isinstance(saved[-1].parts[0], UserPromptPart)
        assert "search_files" in saved[-1].parts[0].content
        assert "Found main.py" in saved[-1].parts[0].content

    def test_without_partial_run(self):
        history_manager = MagicMock()
        task = LLMTask(name="test-task")
        task.save_cancelled_history(
            history_manager,
            "test-convo",
            [],
            "hello",
        )

        saved = history_manager.update.call_args[0][1]
        assert len(saved) == 2  # user msg + cancelled marker only

    def test_skips_summary_when_no_tools(self):
        from zrb.llm.agent.run.partial_run import PartialRunAccumulator

        partial_run = PartialRunAccumulator()
        partial_run.is_interrupted = True

        history_manager = MagicMock()
        task = LLMTask(name="test-task")
        task.save_cancelled_history(
            history_manager,
            "test-convo",
            [],
            "hello",
            partial_run=partial_run,
        )

        saved = history_manager.update.call_args[0][1]
        assert (
            len(saved) == 2
        )  # user msg + cancelled marker only — no tools to summarize

    def test_uses_live_history_over_pre_turn_baseline(self):
        """When the interrupted run captured live progress (real tool calls
        made this turn), that's used as the base instead of the stale
        pre-turn `message_history` — and the user's message is not
        duplicated, since the live history already includes it."""
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            TextPart,
            ToolCallPart,
            ToolReturnPart,
            UserPromptPart,
        )

        from zrb.llm.agent.run.partial_run import PartialRunAccumulator

        partial_run = PartialRunAccumulator()
        partial_run.latest_history = [
            ModelRequest(parts=[UserPromptPart(content="hello")]),
            ModelResponse(
                parts=[ToolCallPart(tool_name="t", args="{}", tool_call_id="c1")]
            ),
            ModelRequest(
                parts=[ToolReturnPart(tool_name="t", content="ok", tool_call_id="c1")]
            ),
        ]

        history_manager = MagicMock()
        task = LLMTask(name="test-task")
        # Stale pre-turn baseline — must NOT be used since live history exists.
        task.save_cancelled_history(
            history_manager,
            "test-convo",
            ["stale-pre-turn-placeholder"],
            "hello",
            partial_run=partial_run,
        )

        saved = history_manager.update.call_args[0][1]
        assert "stale-pre-turn-placeholder" not in saved
        # 3 live messages + the cancellation marker; user message not duplicated.
        assert len(saved) == 4
        assert isinstance(saved[-1], ModelResponse)
        assert isinstance(saved[-1].parts[0], TextPart)
        assert "interrupted by user" in saved[-1].parts[0].content

    def test_closes_dangling_tool_call_from_live_history(self):
        """A live history ending in a ModelResponse with an unresolved tool
        call gets a synthetic ToolReturnPart before the cancellation marker —
        otherwise most providers reject the resumed history outright."""
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            ToolCallPart,
            ToolReturnPart,
            UserPromptPart,
        )

        from zrb.llm.agent.run.partial_run import PartialRunAccumulator

        partial_run = PartialRunAccumulator()
        partial_run.latest_history = [
            ModelRequest(parts=[UserPromptPart(content="hello")]),
            ModelResponse(
                parts=[ToolCallPart(tool_name="t", args="{}", tool_call_id="c1")]
            ),
        ]

        history_manager = MagicMock()
        task = LLMTask(name="test-task")
        task.save_cancelled_history(
            history_manager, "test-convo", [], "hello", partial_run=partial_run
        )

        saved = history_manager.update.call_args[0][1]
        # dangling-call closure + cancellation marker, on top of the 2 live msgs
        assert len(saved) == 4
        closing = saved[2]
        assert isinstance(closing, ModelRequest)
        assert isinstance(closing.parts[0], ToolReturnPart)
        assert closing.parts[0].tool_call_id == "c1"


class TestHandleRunError:
    def test_appends_partial_summary(self):
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        from zrb.llm.agent.run.partial_run import PartialRunAccumulator

        partial_run = PartialRunAccumulator()
        partial_run.completed_tools.append(("search", "{}", "Found foo.py"))

        error = ValueError("API error")
        error.zrb_history = [
            ModelRequest(parts=[UserPromptPart(content="user msg")]),
        ]

        history_manager = MagicMock()
        ctx = MagicMock()
        task = LLMTask(name="test-task")
        task.handle_run_error(
            ctx, history_manager, "test-convo", error, partial_run=partial_run
        )

        saved = history_manager.update.call_args[0][1]
        assert len(saved) == 3  # original + error + partial summary

        # Last message should be the partial summary
        last = saved[-1]
        assert isinstance(last, ModelRequest)
        content = last.parts[0].content
        assert "search" in content
        assert "Found foo.py" in content

    def test_skips_partial_summary_on_context_length(self):
        from zrb.llm.agent.run.partial_run import PartialRunAccumulator

        partial_run = PartialRunAccumulator()
        partial_run.completed_tools.append(("search", "{}", "Found foo.py"))

        error = ValueError("prompt too long")
        error.zrb_history = []

        history_manager = MagicMock()
        ctx = MagicMock()
        task = LLMTask(name="test-task")
        task.handle_run_error(
            ctx, history_manager, "test-convo", error, partial_run=partial_run
        )

        # Context-length error saves the history as-is without growing it
        saved = history_manager.update.call_args[0][1]
        assert saved == []  # Not grown

    def test_no_op_when_error_has_no_history(self):
        error = ValueError("boom")  # no zrb_history attribute
        history_manager = MagicMock()
        task = LLMTask(name="test-task")
        task.handle_run_error(MagicMock(), history_manager, "test-convo", error)
        assert not history_manager.update.called

    def test_closes_dangling_tool_call_before_error_notice(self):
        """A `zrb_history` ending in a ModelResponse with an unresolved tool
        call gets a synthetic error ToolReturnPart closing it, before the
        `[SYSTEM] Error occurred` notice is appended."""
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            ToolCallPart,
            ToolReturnPart,
            UserPromptPart,
        )

        error = ValueError("connection reset")
        error.zrb_history = [
            ModelRequest(parts=[UserPromptPart(content="hello")]),
            ModelResponse(
                parts=[ToolCallPart(tool_name="t", args="{}", tool_call_id="c1")]
            ),
        ]

        history_manager = MagicMock()
        ctx = MagicMock()
        task = LLMTask(name="test-task")
        task.handle_run_error(ctx, history_manager, "test-convo", error)

        saved = history_manager.update.call_args[0][1]
        # dangling-call closure + the error notice, on top of the 2 original msgs
        assert len(saved) == 4
        closing = saved[2]
        assert isinstance(closing, ModelRequest)
        assert isinstance(closing.parts[0], ToolReturnPart)
        assert closing.parts[0].tool_call_id == "c1"
        assert "connection reset" in closing.parts[0].content
        assert isinstance(saved[-1], ModelRequest)
        assert "Error occurred" in saved[-1].parts[0].content
