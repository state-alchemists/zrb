import asyncio
import json
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.llm.approval.approval_channel import (
    ApprovalChannel,
    ApprovalContext,
    ApprovalResult,
)

if TYPE_CHECKING:
    from zrb.runner.chat.chat_session_manager import ChatSessionManager


class HTTPChatApprovalChannel(ApprovalChannel):
    def __init__(self, session_manager: "ChatSessionManager", session_id: str):
        self.session_manager = session_manager
        self.session_id = session_id
        self._pending: dict[str, asyncio.Future[ApprovalResult]] = {}
        self._pending_context: dict[str, ApprovalContext] = {}
        self._waiting_for_edit_tool_call_id: str | None = None
        self._broadcast_tasks: set[asyncio.Task] = set()

    def is_waiting_for_edit(self) -> bool:
        return self._waiting_for_edit_tool_call_id is not None

    def get_editing_args(self) -> dict[str, Any] | None:
        if self._waiting_for_edit_tool_call_id is None:
            return None
        context = self._pending_context.get(self._waiting_for_edit_tool_call_id)
        if context is None:
            return None
        return context.tool_args

    def debug_state(self) -> dict:
        return {
            "waiting_for_edit_id": self._waiting_for_edit_tool_call_id,
            "pending_keys": list(self._pending.keys()),
            "pending_context_keys": list(self._pending_context.keys()),
            "broadcast_task_count": len(self._broadcast_tasks),
        }

    def has_pending_approvals(self) -> bool:
        return len(self._pending) > 0

    def get_pending_approvals(self) -> list[dict[str, Any]]:
        result = []
        for tool_call_id, ctx in self._pending_context.items():
            result.append(
                {
                    "tool_call_id": tool_call_id,
                    "tool_name": ctx.tool_name,
                    "tool_args": ctx.tool_args,
                }
            )
        return result

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[context.tool_call_id] = future
        self._pending_context[context.tool_call_id] = context

        args_json = json.dumps(context.tool_args, indent=2, default=str)
        message = (
            f"[TOOL CALL]\n"
            f"Tool: {context.tool_name}\n"
            f"Args:\n{args_json}\n"
            f"Approve? (y/n/e)"
        )
        await self.session_manager.broadcast(self.session_id, message)

        try:
            return await future
        except asyncio.CancelledError:
            self._pending.pop(context.tool_call_id, None)
            self._pending_context.pop(context.tool_call_id, None)
            # Edit mode must be released too. Leaving it set strands the
            # channel: is_waiting_for_edit() stays true forever, so the next
            # approval gets routed down the edit path and its answer is
            # swallowed against this now-dead tool call.
            if self._waiting_for_edit_tool_call_id == context.tool_call_id:
                self._waiting_for_edit_tool_call_id = None
            raise

    async def notify(
        self, message: str, context: ApprovalContext | None = None
    ) -> None:
        await self.session_manager.broadcast(self.session_id, message)

    def handle_response(self, response: str, tool_call_id: str | None = None) -> bool:
        if self._waiting_for_edit_tool_call_id:
            if self._handle_edit_response(response):
                return True
            # The edit slot was stale (its run was cancelled) and has now been
            # cleared. Fall through so this response can still answer whatever
            # approval is genuinely pending, instead of being dropped.
        if tool_call_id and tool_call_id in self._pending:
            self._apply_response(tool_call_id, response)
            return True
        if len(self._pending) == 1:
            only_tool_call_id = list(self._pending.keys())[0]
            self._apply_response(only_tool_call_id, response)
            return True
        return False

    def handle_edit_response(
        self, response: str, tool_call_id: str | None = None
    ) -> bool:
        """Resolve a pending edit with args parsed from ``response`` text.

        Returns True only when a pending tool call actually consumed the
        response, so callers never report success for a dropped answer.
        """
        claimed_id = self._claim_edit_tool_call_id(tool_call_id)
        if claimed_id is None:
            return False
        context = self._pending_context.pop(claimed_id)
        future = self._pending.pop(claimed_id)
        new_args = self._parse_edited_content(response)
        if new_args is not None:
            self._schedule_broadcast(f"[APPROVED with edited args] {context.tool_name}")
            future.set_result(ApprovalResult(approved=True, override_args=new_args))
        else:
            self._schedule_broadcast(f"[DENIED - invalid format] {context.tool_name}")
            future.set_result(
                ApprovalResult(approved=False, message="Invalid JSON/YAML format")
            )
        return True

    def handle_edit_response_obj(
        self, args: dict, tool_call_id: str | None = None
    ) -> bool:
        """Resolve a pending edit with already-decoded ``args``.

        Returns True only when a pending tool call actually consumed the args.
        """
        claimed_id = self._claim_edit_tool_call_id(tool_call_id)
        if claimed_id is None:
            return False
        context = self._pending_context.pop(claimed_id)
        future = self._pending.pop(claimed_id)
        self._schedule_broadcast(f"[APPROVED with edited args] {context.tool_name}")
        future.set_result(ApprovalResult(approved=True, override_args=args))
        return True

    def _claim_edit_tool_call_id(self, tool_call_id: str | None) -> str | None:
        """Take ownership of the awaiting edit slot, or return None.

        Edit mode is a single slot, so a response aimed at a different call is
        not an edit response and leaves the slot intact. A slot whose future is
        already gone (the run was cancelled underneath us) is stale: it gets
        cleared so the channel recovers, but None is still returned because
        nothing consumed the response.
        """
        waiting_id = self._waiting_for_edit_tool_call_id
        if waiting_id is None:
            return None
        if tool_call_id is not None and tool_call_id != waiting_id:
            return None
        if waiting_id not in self._pending or waiting_id not in self._pending_context:
            self._waiting_for_edit_tool_call_id = None
            return None
        self._waiting_for_edit_tool_call_id = None
        return waiting_id

    def _handle_edit_response(self, response: str) -> bool:
        return self.handle_edit_response(response)

    def _schedule_broadcast(self, message: str) -> None:
        """Fire a broadcast from a synchronous callback.

        The task is held in ``_broadcast_tasks`` until it finishes: with no
        strong reference the loop is free to garbage-collect it mid-flight and
        the client would silently never see the message. Failures are logged
        here rather than surfacing as "Task exception was never retrieved".
        """
        task = asyncio.create_task(
            self.session_manager.broadcast(self.session_id, message)
        )
        self._broadcast_tasks.add(task)
        task.add_done_callback(self._on_broadcast_done)

    def _on_broadcast_done(self, task: asyncio.Task) -> None:
        self._broadcast_tasks.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            CFG.LOGGER.warning(f"Failed to broadcast approval update: {error!r}")

    def _apply_response(self, tool_call_id: str, response: str) -> None:
        if tool_call_id not in self._pending:
            return
        if not isinstance(response, str):
            self._schedule_broadcast(
                f"[ERROR] Unexpected response type: {type(response).__name__}"
            )
            future = self._pending.pop(tool_call_id)
            del self._pending_context[tool_call_id]
            future.set_result(
                ApprovalResult(approved=False, message="Invalid response type")
            )
            return
        response_lower = response.lower().strip()
        future = self._pending.pop(tool_call_id)
        context = self._pending_context.pop(tool_call_id)
        if response_lower in ("y", "yes", "ok", "okay", ""):
            self._schedule_broadcast(f"[APPROVED] {context.tool_name}")
            future.set_result(ApprovalResult(approved=True))
        elif response_lower in ("n", "no", "deny", "cancel"):
            self._schedule_broadcast(f"[DENIED] {context.tool_name}")
            future.set_result(ApprovalResult(approved=False, message="User denied"))
        elif response_lower in ("e", "edit"):
            self._pending[tool_call_id] = future
            self._pending_context[tool_call_id] = context
            self._waiting_for_edit_tool_call_id = tool_call_id
            args_json = json.dumps(context.tool_args, indent=2, ensure_ascii=False)

            CFG.LOGGER.info(
                f"ENTERING EDIT MODE: tool_call_id={tool_call_id}, tool_args={context.tool_args}"
            )
            self._schedule_broadcast(f"[EDIT MODE] {context.tool_name}\n{args_json}")
        else:
            self._schedule_broadcast(f"[DENIED] {context.tool_name}: {response}")
            future.set_result(
                ApprovalResult(approved=False, message=f"User denied: {response}")
            )

    def _parse_edited_content(self, content: str) -> dict | None:
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        try:
            result = json.loads(content)
            if isinstance(result, dict):
                return result
            return None
        except json.JSONDecodeError:
            pass
        # lazy: heavy third-party
        import yaml

        try:
            result = yaml.safe_load(content)
            if isinstance(result, dict):
                return result
            return None
        except yaml.YAMLError:
            pass
        return None
