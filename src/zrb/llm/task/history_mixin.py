"""History / conversation lookup + error & cancellation recovery for `LLMTask`.

These helpers resolve the conversation name and history manager, decide what to
re-send on a retry, and persist a meaningful history when a run errors or is
cancelled. They are kept out of `llm_task.py` so the host stays focused on the
constructor and the execution core. None of these methods call ``run_agent`` /
``create_agent`` / ``summarize_history`` (those seams stay in the host).

State assumed to exist on the host class (set in `LLMTask.__init__`):
- `_history_manager`, `_conversation_name`, `_render_conversation_name`
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.llm.history_manager.file_history_manager import FileHistoryManager
from zrb.util.attr import get_attr
from zrb.util.cli.style import remove_style
from zrb.util.string.name import get_random_name

if TYPE_CHECKING:
    from zrb.attr.type import StrAttr
    from zrb.context.any_context import AnyContext
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager


class HistoryMixin:
    """Conversation/history resolution and error/cancellation recovery."""

    if TYPE_CHECKING:
        # Attributes supplied by the host class (set in LLMTask.__init__).
        _history_manager: AnyHistoryManager | None
        _conversation_name: StrAttr | None
        _render_conversation_name: bool

    def _get_history_manager(self, ctx: AnyContext) -> AnyHistoryManager:
        if self._history_manager is not None:
            return self._history_manager
        return FileHistoryManager(history_dir=CFG.LLM_HISTORY_DIR)

    def _get_conversation_name(self, ctx: AnyContext) -> str:
        conversation_name = str(
            get_attr(ctx, self._conversation_name, "", self._render_conversation_name)
        )
        if conversation_name.strip() == "":
            conversation_name = get_random_name()
        return conversation_name

    def _get_effective_prompt(
        self,
        ctx: AnyContext,
        user_message: str,
        user_attachments: list[Any] | None,
        message_history: list[Any],
    ) -> tuple[str, list[Any] | None]:
        # Detect retry and avoid duplicating the initial message if it's already in history
        # Also, if it's a retry, we might want to inform the LLM about the previous failure.
        if ctx.attempt > 1 and len(message_history) > 0:
            # lazy: heavy third-party
            from pydantic_ai.messages import ModelRequest, UserPromptPart

            # Compare ONLY the most recent real user turn. Scanning the whole
            # history means a recurring message (e.g. "continue") matches some
            # old turn and the user's current message gets replaced by the
            # generic retry notice. "[SYSTEM]"-prefixed turns are bookkeeping
            # appended by error/cancel recovery — skipped, not user turns.
            found_user_message = False
            str_user_message = str(user_message)
            for msg in reversed(message_history):
                if not isinstance(msg, ModelRequest):
                    continue
                part_texts = [
                    _user_part_text(part)
                    for part in msg.parts
                    if isinstance(part, UserPromptPart)
                ]
                if not part_texts:
                    continue  # tool-return-only request
                if all(text.startswith("[SYSTEM]") for text in part_texts):
                    continue
                found_user_message = str_user_message in part_texts
                break

            if found_user_message:
                # User message is already in history, so we don't need to send it again.
                # Instead, we send a retry notice.
                # IMPORTANT: Preserve attachments on retry - they may still be needed
                ctx.log_info("Initial message found in history, sending retry notice.")
                return (
                    f"[SYSTEM] This is retry attempt {ctx.attempt}. "
                    "The previous attempt failed. Please review the history and continue.",
                    user_attachments,  # Preserve attachments on retry
                )
        return user_message, user_attachments

    def _is_context_length_error(self, error: Exception) -> bool:
        """Return True when the error is a model context-length / prompt-too-long rejection."""
        err_str = str(error).lower()
        context_keywords = [
            "prompt too long",
            "context length",
            "context window",
            "max tokens",
            "token limit",
            "input too long",
            "maximum context",
        ]
        if any(kw in err_str for kw in context_keywords):
            return True
        # pydantic_ai ModelHTTPError with status 400 and context-related body
        status_code = getattr(error, "status_code", None)
        if status_code == 400 and any(kw in err_str for kw in context_keywords):
            return True
        return False

    def _handle_run_error(
        self,
        ctx: AnyContext,
        history_manager: AnyHistoryManager,
        conversation_name: str,
        error: Exception,
        partial_run: Any = None,
    ):
        # lazy: heavy third-party
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            ToolCallPart,
            ToolReturnPart,
            UserPromptPart,
        )

        new_history = getattr(error, "zrb_history", None)
        if new_history is None:
            return
        # Do not append error info when the history is already too long — appending
        # would make the next retry even longer and guarantee repeated failures.
        if self._is_context_length_error(error):
            ctx.log_warning(
                "Context-length error detected; not growing history for retry."
            )
            history_manager.update(conversation_name, new_history)
            history_manager.save(conversation_name)
            return
        # Append error information to history so it's available on next retry
        # 1. Handle dangling tool calls if necessary
        if len(new_history) > 0:
            last_msg = new_history[-1]
            if isinstance(last_msg, ModelResponse):
                tool_returns = []
                for part in last_msg.parts:
                    if isinstance(part, ToolCallPart):
                        tool_returns.append(
                            ToolReturnPart(
                                tool_name=part.tool_name,
                                content=f"Error: {str(error)}",
                                tool_call_id=part.tool_call_id,
                            )
                        )
                if tool_returns:
                    new_history.append(ModelRequest(parts=tool_returns))

        # 2. Append general error information
        error_msg = f"[SYSTEM] Error occurred: {str(error)}"
        new_history.append(ModelRequest(parts=[UserPromptPart(content=error_msg)]))
        # 3. Append partial run summary if available and meaningful
        if partial_run is not None and partial_run.completed_tools:
            summary = partial_run.build_summary()
            new_history.append(ModelRequest(parts=[UserPromptPart(content=summary)]))
        history_manager.update(conversation_name, new_history)
        history_manager.save(conversation_name)

    def _save_cancelled_history(
        self,
        history_manager: AnyHistoryManager,
        conversation_name: str,
        message_history: list[Any],
        user_message: Any,
        partial_run: Any = None,
    ) -> None:
        """Save partial history when a run is cancelled by the user (e.g. Escape).

        Constructs a synthetic history containing the original history, the
        user's message, and a cancellation marker so the next turn can build
        on context rather than starting fresh.  Best-effort: a failure must not
        crash the interrupt path, but it is logged so silent history loss is
        diagnosable.
        """
        try:
            # lazy: heavy third-party
            from pydantic_ai.messages import (
                ModelRequest,
                ModelResponse,
                TextPart,
                UserPromptPart,
            )

            partial_history = list(message_history)
            partial_history.append(
                ModelRequest(parts=[UserPromptPart(content=str(user_message))])
            )
            partial_history.append(
                ModelResponse(
                    parts=[
                        TextPart(content="[SYSTEM: Response was interrupted by user]")
                    ]
                )
            )
            if partial_run is not None and partial_run.completed_tools:
                summary = partial_run.build_summary()
                partial_history.append(
                    ModelRequest(parts=[UserPromptPart(content=summary)])
                )
            history_manager.update(conversation_name, partial_history)
            history_manager.save(conversation_name)
        except Exception as e:
            CFG.LOGGER.warning(f"Failed to save cancelled history: {e}")

    def _post_process_output(self, output: Any) -> Any:
        if isinstance(output, str):
            # Remove ANSI escape codes first to ensure regex patterns work correctly
            output = remove_style(output)
        return output


def _user_part_text(part: Any) -> str:
    """Extract the text of a UserPromptPart (text-only or multimodal content)."""
    if isinstance(part.content, str):
        return part.content
    if isinstance(part.content, list):
        # Multimodal: content is [text, BinaryContent(...)]
        for item in part.content:
            if isinstance(item, str):
                return item
    return ""
