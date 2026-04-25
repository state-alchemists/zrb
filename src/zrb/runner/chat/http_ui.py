"""HTTP-backed UI used by the FastAPI chat session runner.

`HTTPUI` adapts `EventDrivenUI` so output is broadcast to SSE subscribers
and tool-call confirmations are routed through the per-session
`HTTPChatApprovalChannel`. The factory binds the session-specific
collaborators that `LLMChatTask` cannot know about up-front.
"""

from __future__ import annotations

import asyncio
from typing import Any

from zrb.runner.chat.chat_session_manager import ChatSessionManager
from zrb.runner.chat.http_chat import HTTPChatApprovalChannel


def create_http_ui_factory(
    session_manager: ChatSessionManager,
    session_id: str,
    session_name: str,
    approval_channel: HTTPChatApprovalChannel,
):
    """Build a UI factory closed over per-session HTTP collaborators."""
    from zrb.llm.approval.approval_channel import ApprovalContext
    from zrb.llm.ui import EventDrivenUI, UIConfig
    from zrb.util.cli.style import remove_style

    class HTTPUI(EventDrivenUI):
        def __init__(self, **kwargs):
            self._session_manager = session_manager
            self._session_id = session_id
            self._approval_channel = approval_channel
            super().__init__(**kwargs)
            self._input_queue: asyncio.Queue[str] = asyncio.Queue()
            self._streaming_started = False

        async def print(self, text: str, kind: str = "text") -> None:
            if kind == "streaming":
                self._streaming_started = True
            elif kind == "text":
                if self._streaming_started:
                    self._streaming_started = False
                    return
            clean = remove_style(text)
            if clean.strip():
                await self._session_manager.broadcast(
                    self._session_id, clean, kind=kind
                )

        async def get_input(self, prompt: str) -> str:
            if prompt:
                clean_prompt = remove_style(prompt).strip()
                if clean_prompt:
                    await self._session_manager.broadcast(
                        self._session_id, f"❓ {clean_prompt}"
                    )
            self._waiting_for_input = True
            try:
                return await self._input_queue.get()
            finally:
                self._waiting_for_input = False

        async def _confirm_tool_execution(self, call: Any) -> Any:
            context = ApprovalContext(
                tool_name=call.tool_name,
                tool_args=call.args if isinstance(call.args, dict) else {},
                tool_call_id=call.tool_call_id,
            )
            result = await self._approval_channel.request_approval(context)
            return result.to_pydantic_result()

        async def start_event_loop(self) -> None:
            # No-op: `_run_loop` is overridden directly.
            pass

        async def _run_loop(self) -> None:
            """Process one message then return; multi-turn handled by session runner."""
            # Block until every submitted user message has been task_done()'d.
            await self._message_queue.join()

        async def run_async(self) -> str:
            """Override so `CancelledError` propagates on server shutdown."""
            self._process_messages_task = asyncio.create_task(
                self._process_messages_loop()
            )
            if hasattr(self, "_background_tasks"):
                self._background_tasks.add(self._process_messages_task)

            if self._initial_message:
                self._submit_user_message(self._llm_task, self._initial_message)

            _was_cancelled = False
            try:
                await self._run_loop()
            except asyncio.CancelledError:
                _was_cancelled = True
            finally:
                self._process_messages_task.cancel()
                try:
                    await self._process_messages_task
                except asyncio.CancelledError:
                    pass
                finally:
                    if hasattr(self, "_background_tasks"):
                        self._background_tasks.discard(self._process_messages_task)

            if _was_cancelled:
                raise asyncio.CancelledError()
            return self.last_output

    def http_ui_factory(
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
        cfg.is_yolo = initial_yolo
        cfg.conversation_session_name = session_name

        return HTTPUI(
            ctx=ctx,
            llm_task=llm_task,
            history_manager=history_manager,
            config=cfg,
            initial_message=initial_message,
            initial_attachments=initial_attachments,
        )

    return http_ui_factory
