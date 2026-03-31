import asyncio
import json
from typing import TYPE_CHECKING, Any

from zrb.llm.approval.approval_channel import (
    ApprovalChannel,
    ApprovalContext,
    ApprovalResult,
)
from zrb.llm.ui.simple_ui import BufferedOutputMixin, EventDrivenUI, UIConfig
from zrb.util.cli.style import remove_style

if TYPE_CHECKING:
    from zrb.runner.chat.chat_session_manager import ChatSessionManager


class HTTPChatApprovalChannel(ApprovalChannel):
    def __init__(self, session_manager: "ChatSessionManager", session_id: str):
        self.session_manager = session_manager
        self.session_id = session_id
        self._pending: dict[str, asyncio.Future[ApprovalResult]] = {}
        self._pending_context: dict[str, ApprovalContext] = {}
        self._waiting_for_edit_tool_call_id: str | None = None

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
            if context.tool_call_id in self._pending:
                del self._pending[context.tool_call_id]
            if context.tool_call_id in self._pending_context:
                del self._pending_context[context.tool_call_id]
            raise

    async def notify(
        self, message: str, context: ApprovalContext | None = None
    ) -> None:
        await self.session_manager.broadcast(self.session_id, message)

    def handle_response(self, response: str, tool_call_id: str | None = None) -> bool:
        if self._waiting_for_edit_tool_call_id:
            self._handle_edit_response(response)
            return True
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
    ) -> None:
        if not self._waiting_for_edit_tool_call_id:
            return
        tool_call_id = tool_call_id or self._waiting_for_edit_tool_call_id
        self._waiting_for_edit_tool_call_id = None
        if tool_call_id not in self._pending:
            return
        context = self._pending_context.get(tool_call_id)
        new_args = self._parse_edited_content(response)
        future = self._pending.pop(tool_call_id)
        del self._pending_context[tool_call_id]
        if new_args is not None:
            asyncio.create_task(
                self.session_manager.broadcast(
                    self.session_id,
                    f"[APPROVED with edited args] {context.tool_name}",
                )
            )
            future.set_result(ApprovalResult(approved=True, override_args=new_args))
        else:
            asyncio.create_task(
                self.session_manager.broadcast(
                    self.session_id,
                    f"[DENIED - invalid format] {context.tool_name}",
                )
            )
            future.set_result(
                ApprovalResult(approved=False, message="Invalid JSON/YAML format")
            )

    def handle_edit_response_obj(
        self, args: dict, tool_call_id: str | None = None
    ) -> None:
        if not self._waiting_for_edit_tool_call_id:
            return
        tool_call_id = tool_call_id or self._waiting_for_edit_tool_call_id
        self._waiting_for_edit_tool_call_id = None
        if tool_call_id not in self._pending:
            return
        context = self._pending_context.get(tool_call_id)
        future = self._pending.pop(tool_call_id)
        del self._pending_context[tool_call_id]
        asyncio.create_task(
            self.session_manager.broadcast(
                self.session_id,
                f"[APPROVED with edited args] {context.tool_name}",
            )
        )
        future.set_result(ApprovalResult(approved=True, override_args=args))

    def _handle_edit_response(self, response: str) -> None:
        self.handle_edit_response(response)

    def _apply_response(self, tool_call_id: str, response: str) -> None:
        if tool_call_id not in self._pending:
            return
        if not isinstance(response, str):
            asyncio.create_task(
                self.session_manager.broadcast(
                    self.session_id,
                    f"[ERROR] Unexpected response type: {type(response).__name__}",
                )
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
            asyncio.create_task(
                self.session_manager.broadcast(
                    self.session_id,
                    f"[APPROVED] {context.tool_name}",
                )
            )
            future.set_result(ApprovalResult(approved=True))
        elif response_lower in ("n", "no", "deny", "cancel"):
            asyncio.create_task(
                self.session_manager.broadcast(
                    self.session_id,
                    f"[DENIED] {context.tool_name}",
                )
            )
            future.set_result(ApprovalResult(approved=False, message="User denied"))
        elif response_lower in ("e", "edit"):
            self._pending[tool_call_id] = future
            self._pending_context[tool_call_id] = context
            self._waiting_for_edit_tool_call_id = tool_call_id
            args_json = json.dumps(context.tool_args, indent=2, ensure_ascii=False)
            from zrb.config.config import CFG

            CFG.LOGGER.info(
                f"ENTERING EDIT MODE: tool_call_id={tool_call_id}, tool_args={context.tool_args}"
            )
            asyncio.create_task(
                self.session_manager.broadcast(
                    self.session_id,
                    f"[EDIT MODE] {context.tool_name}\n{args_json}",
                )
            )
        else:
            asyncio.create_task(
                self.session_manager.broadcast(
                    self.session_id,
                    f"[DENIED] {context.tool_name}: {response}",
                )
            )
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
        try:
            import yaml

            result = yaml.safe_load(content)
            if isinstance(result, dict):
                return result
            return None
        except yaml.YAMLError:
            pass
        return None


class HTTPChatUI(EventDrivenUI, BufferedOutputMixin):
    def __init__(
        self,
        session_manager: "ChatSessionManager",
        session_id: str,
        approval_channel: "HTTPChatApprovalChannel | None" = None,
        **kwargs,
    ):
        self.session_manager = session_manager
        self.session_id = session_id
        self._approval_channel = approval_channel
        super().__init__(**kwargs)
        BufferedOutputMixin.__init__(self, flush_interval=0.3, max_buffer_size=3000)
        self._waiting_for_input = False
        self._input_queue: asyncio.Queue[str] = asyncio.Queue()

    @property
    def conversation_session_name(self) -> str:
        return self.session_id

    async def _send_buffered(self, text: str) -> None:
        clean = remove_style(text).strip()
        if not clean:
            return
        await self.session_manager.broadcast(self.session_id, clean)

    async def print(self, text: str) -> None:
        self.buffer_output(text)

    def handle_incoming_message(self, text: str):
        if self._waiting_for_input:
            self._input_queue.put_nowait(text)
        else:
            self._submit_user_message(self._llm_task, text)

    async def get_input(self, prompt: str) -> str:
        if prompt:
            clean_prompt = remove_style(prompt).strip()
            if clean_prompt:
                await self.session_manager.broadcast(
                    self.session_id, f"❓ {clean_prompt}"
                )
        self._waiting_for_input = True
        self.session_manager.set_processing(self.session_id, True)
        try:
            return await self._input_queue.get()
        finally:
            self._waiting_for_input = False
            self.session_manager.set_processing(self.session_id, False)

    async def _confirm_tool_execution(self, call: Any) -> Any:
        """Handle tool execution confirmation using approval channel."""
        if self._approval_channel is None:
            raise RuntimeError("No approval channel configured for HTTP chat")
        context = ApprovalContext(
            tool_name=call.tool_name,
            tool_args=call.args if isinstance(call.args, dict) else {},
            tool_call_id=call.tool_call_id,
        )
        result = await self._approval_channel.request_approval(context)
        return result.to_pydantic_result()

    async def start_event_loop(self) -> None:
        await self.start_flush_loop()
        while True:
            await asyncio.sleep(3600)


def create_http_chat_ui_factory(
    session_manager: "ChatSessionManager",
    session_id: str,
):
    def http_chat_ui_factory(
        ctx,
        llm_task,
        history_manager,
        ui_commands,
        initial_message,
        initial_conversation_name,
        initial_yolo,
        initial_attachments,
    ):
        cfg = UIConfig.default()
        if ui_commands:
            cfg = cfg.merge_commands(ui_commands)
        cfg.yolo = initial_yolo
        cfg.conversation_session_name = session_id

        ui = HTTPChatUI(
            ctx=ctx,
            llm_task=llm_task,
            history_manager=history_manager,
            config=cfg,
            initial_message=initial_message,
            initial_attachments=initial_attachments,
            session_manager=session_manager,
            session_id=session_id,
        )
        return ui

    return http_chat_ui_factory
