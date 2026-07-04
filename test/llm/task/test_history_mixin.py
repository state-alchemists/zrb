"""Tests for HistoryMixin (conversation/history resolution + error recovery).

Exercised through the public ``LLMTask`` surface, which composes HistoryMixin.
Some helpers are invoked directly (mirroring the pre-existing convention for
``_save_cancelled_history`` / ``_handle_run_error``), since they are recovery
paths that are awkward to drive end-to-end.
"""

from unittest.mock import MagicMock

from zrb.llm.task.llm_task import LLMTask


class TestConversationAndHistoryLookup:
    def test_get_history_manager_returns_explicit(self):
        manager = MagicMock()
        task = LLMTask(name="t", history_manager=manager)
        assert task._get_history_manager(MagicMock()) is manager

    def test_get_history_manager_defaults_to_file_manager(self):
        from zrb.llm.history_manager.file_history_manager import FileHistoryManager

        task = LLMTask(name="t")
        assert isinstance(task._get_history_manager(MagicMock()), FileHistoryManager)

    def test_get_conversation_name_uses_explicit(self):
        task = LLMTask(
            name="t", conversation_name="my-convo", render_conversation_name=False
        )
        assert task._get_conversation_name(MagicMock()) == "my-convo"

    def test_get_conversation_name_random_when_blank(self):
        task = LLMTask(name="t")
        name = task._get_conversation_name(MagicMock())
        assert isinstance(name, str) and name.strip() != ""


class TestEffectivePrompt:
    def test_first_attempt_passes_message_through(self):
        task = LLMTask(name="t")
        ctx = MagicMock()
        ctx.attempt = 1
        msg, atts = task._get_effective_prompt(ctx, "hello", ["a"], [])
        assert msg == "hello"
        assert atts == ["a"]

    def test_retry_sends_notice_when_message_already_in_history(self):
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        task = LLMTask(name="t")
        ctx = MagicMock()
        ctx.attempt = 2
        history = [ModelRequest(parts=[UserPromptPart(content="hello")])]
        msg, atts = task._get_effective_prompt(ctx, "hello", ["keep"], history)
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
        msg, _ = task._get_effective_prompt(ctx, "continue", None, history)
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
        msg, _ = task._get_effective_prompt(ctx, "hello", None, history)
        assert "retry attempt 2" in msg


class TestContextLengthDetection:
    def test_detects_keyword(self):
        task = LLMTask(name="t")
        assert task._is_context_length_error(ValueError("prompt too long")) is True

    def test_ignores_unrelated_error(self):
        task = LLMTask(name="t")
        assert task._is_context_length_error(ValueError("boom")) is False

    def test_detects_status_400_with_keyword(self):
        task = LLMTask(name="t")
        err = ValueError("context window exceeded")
        err.status_code = 400
        assert task._is_context_length_error(err) is True


class TestPostProcessOutput:
    def test_strips_ansi_from_string(self):
        task = LLMTask(name="t")
        assert task._post_process_output("\x1b[31mhi\x1b[0m") == "hi"

    def test_passes_through_non_string(self):
        task = LLMTask(name="t")
        payload = {"k": "v"}
        assert task._post_process_output(payload) is payload


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
        task._save_cancelled_history(
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
        task._save_cancelled_history(
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
        task._save_cancelled_history(
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
        task._handle_run_error(
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
        task._handle_run_error(
            ctx, history_manager, "test-convo", error, partial_run=partial_run
        )

        # Context-length error saves the history as-is without growing it
        saved = history_manager.update.call_args[0][1]
        assert saved == []  # Not grown

    def test_no_op_when_error_has_no_history(self):
        error = ValueError("boom")  # no zrb_history attribute
        history_manager = MagicMock()
        task = LLMTask(name="test-task")
        task._handle_run_error(MagicMock(), history_manager, "test-convo", error)
        assert not history_manager.update.called
