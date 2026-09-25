"""History / conversation lookup + error & cancellation recovery for `LLMTask`.

Resolves the conversation name and history manager, decides what to re-send on
a retry, and persists a meaningful history when a run errors or is cancelled.

Composed into `LLMTask` as `self._history`; reads the owner's public
`history_manager` on every access because it has a public setter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.llm.agent.run.history_utils import close_dangling_tool_calls
from zrb.llm.history_manager.file_history_manager import default_history_manager
from zrb.llm.task.shared_getters import resolve_conversation_name
from zrb.util.cli.style import remove_style

if TYPE_CHECKING:
    from zrb.context.any_context import AnyContext
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.task.llm_task import LLMTask


class LLMTaskHistory:
    """Conversation/history resolution and error/cancellation recovery.

    Every method here is part of the host's surface rather than an internal
    detail: the host calls them by name, and a subclass overrides them to change
    where history lives or what a failed run leaves behind.
    """

    def __init__(self, llm_task: "LLMTask") -> None:
        self._llm_task = llm_task

    def get_history_manager(self, ctx: AnyContext) -> AnyHistoryManager:
        """The configured history manager, or a default file-backed one."""
        if self._llm_task.history_manager is not None:
            return self._llm_task.history_manager
        return default_history_manager()

    def get_conversation_name(self, ctx: AnyContext) -> str:
        """The configured conversation name, or a fresh random one when blank."""
        return resolve_conversation_name(ctx, self._llm_task.conversation_name_attr)

    def get_effective_prompt(
        self,
        ctx: AnyContext,
        user_message: str,
        user_attachments: list[Any] | None,
        message_history: list[Any],
    ) -> tuple[str, list[Any] | None]:
        """The message to send this attempt, plus the attachments to send with it.

        On a retry whose message is already the last user turn in history,
        re-sending it would duplicate the turn, so a retry notice goes instead.
        """
        if ctx.attempt <= 1 or not message_history:
            return user_message, user_attachments
        if not _is_last_user_turn(str(user_message), message_history):
            return user_message, user_attachments
        ctx.log_info("Initial message found in history, sending retry notice.")
        # Attachments are kept: the retry may still need them.
        return (
            f"[SYSTEM] This is retry attempt {ctx.attempt}. "
            "The previous attempt failed. Please review the history and continue.",
            user_attachments,
        )

    def is_context_length_error(self, error: Exception) -> bool:
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
        return any(kw in err_str for kw in context_keywords)

    def handle_run_error(
        self,
        ctx: AnyContext,
        history_manager: AnyHistoryManager,
        conversation_name: str,
        error: Exception,
        partial_run: Any = None,
    ):
        """Persist what a failed run leaves behind, so the next retry sees it.

        No-op unless the error carries a ``zrb_history``. A context-length
        failure saves the history unchanged — appending to it would make the
        next attempt longer and guarantee the same failure.
        """
        # lazy: zrb internal (heavy via transitive)
        from zrb.llm.agent.types import ModelRequest, UserPromptPart

        new_history = getattr(error, "zrb_history", None)
        if new_history is None:
            return
        if self.is_context_length_error(error):
            ctx.log_warning(
                "Context-length error detected; not growing history for retry."
            )
            history_manager.update(conversation_name, new_history)
            history_manager.save(conversation_name)
            return
        new_history = close_dangling_tool_calls(new_history, reason=f"Error: {error}")

        error_msg = f"[SYSTEM] Error occurred: {str(error)}"
        new_history.append(ModelRequest(parts=[UserPromptPart(content=error_msg)]))
        if partial_run is not None and partial_run.completed_tools:
            summary = partial_run.build_summary()
            new_history.append(ModelRequest(parts=[UserPromptPart(content=summary)]))
        history_manager.update(conversation_name, new_history)
        history_manager.save(conversation_name)

    def save_cancelled_history(
        self,
        history_manager: AnyHistoryManager,
        conversation_name: str,
        message_history: list[Any],
        user_message: Any,
        partial_run: Any = None,
    ) -> None:
        """Save partial history when a run is cancelled by the user (e.g. Escape).

        Records everything the interrupted turn actually did plus a
        cancellation marker, so the next turn builds on real context.
        Best-effort: a failure is logged, never raised into the interrupt path.
        """
        try:
            # lazy: zrb internal (heavy via transitive)
            from zrb.llm.agent.types import (
                ModelRequest,
                ModelResponse,
                TextPart,
                UserPromptPart,
            )

            latest_history = getattr(partial_run, "latest_history", None)
            if latest_history is not None:
                # The live run's messages: the user turn plus completed tools.
                partial_history = list(latest_history)
            else:
                # Cancelled before the run reached the model.
                partial_history = list(message_history)
                partial_history.append(
                    ModelRequest(parts=[UserPromptPart(content=str(user_message))])
                )
            partial_history = close_dangling_tool_calls(
                partial_history,
                reason="[SYSTEM] Cancelled by user before this tool call's "
                "result was recorded.",
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

    def post_process_output(self, output: Any) -> Any:
        """Strip terminal styling from a string result; pass anything else through."""
        if isinstance(output, str):
            return remove_style(output)
        return output


def _is_last_user_turn(user_message: str, message_history: list[Any]) -> bool:
    """Whether *user_message* is the most recent real user turn in history.

    Only the latest turn is compared, so a recurring message ("continue") does
    not match an old one. "[SYSTEM]" turns are recovery bookkeeping, skipped.
    """
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import ModelRequest, UserPromptPart

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
        return user_message in part_texts
    return False


def _user_part_text(part: Any) -> str:
    """Extract the text of a UserPromptPart (text-only or multimodal content)."""
    if isinstance(part.content, str):
        return part.content
    if isinstance(part.content, list):
        for item in part.content:
            if isinstance(item, str):
                return item
    return ""
