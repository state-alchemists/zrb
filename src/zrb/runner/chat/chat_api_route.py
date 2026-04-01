import asyncio
import json
from typing import Any

from zrb.config.config import CFG
from zrb.config.web_auth_config import WebAuthConfig
from zrb.group.any_group import AnyGroup
from zrb.llm.approval.approval_channel import (
    ApprovalChannel,
    ApprovalContext,
    ApprovalResult,
)
from zrb.llm.approval.multiplex_approval_channel import MultiplexApprovalChannel
from zrb.runner.chat.chat_session_manager import ChatSession, ChatSessionManager
from zrb.runner.chat.http_chat import HTTPChatApprovalChannel
from zrb.runner.web_util.user import get_user_from_request
from zrb.util.group import NodeNotFoundError, extract_node_from_args

from .sse_stream import SSEStreamResponse

DEFAULT_LLM_TIMEOUT = 300


async def _get_llm_chat_task(root_group: AnyGroup) -> Any:
    try:
        task, _, _ = extract_node_from_args(root_group, ["llm", "chat"])
        return task
    except NodeNotFoundError:
        return None


def serve_chat_api(
    app: Any,
    root_group: AnyGroup,
    web_auth_config: WebAuthConfig,
) -> None:
    from fastapi import Request
    from fastapi.responses import JSONResponse

    session_manager = ChatSessionManager.get_instance_sync()

    @app.get("/api/v1/chat/sessions")
    async def list_chat_sessions(
        request: Request,
        page: int = 1,
        limit: int = 20,
    ) -> JSONResponse:
        await get_user_from_request(web_auth_config, request)
        sessions = session_manager.get_sessions(page=page, limit=limit)
        total = session_manager.get_sessions_count()
        return JSONResponse(
            content={
                "sessions": sessions,
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit if total > 0 else 1,
            }
        )

    @app.post("/api/v1/chat/sessions")
    async def create_chat_session(request: Request) -> JSONResponse:
        await get_user_from_request(web_auth_config, request)
        data = await request.json() if request.method == "POST" else {}
        session_id = data.get("session_id")
        session_name = data.get("session_name")
        session = await session_manager.create_session(
            session_id=session_id, session_name=session_name
        )
        return JSONResponse(
            content={
                "session_id": session.session_id,
                "session_name": session.session_name,
            }
        )

    @app.delete("/api/v1/chat/sessions/{session_id}")
    async def delete_chat_session(
        session_id: str,
        request: Request,
    ) -> JSONResponse:
        await get_user_from_request(web_auth_config, request)
        removed = await session_manager.remove_session(session_id)
        if removed:
            return JSONResponse(content={"success": True})
        return JSONResponse(content={"error": "Session not found"}, status_code=404)

    @app.get("/api/v1/chat/sessions/{session_id}/messages")
    async def get_chat_messages(
        session_id: str,
        request: Request,
    ) -> JSONResponse:
        await get_user_from_request(web_auth_config, request)
        messages = session_manager.get_messages(session_id)
        serializable_messages = []
        for msg in messages:
            msg_dict = {
                "role": msg.get("role", "unknown"),
                "content": msg.get("content", ""),
            }
            if "timestamp" in msg and msg["timestamp"]:
                msg_dict["timestamp"] = str(msg["timestamp"])
            serializable_messages.append(msg_dict)
        return JSONResponse(content={"messages": serializable_messages})

    @app.post("/api/v1/chat/sessions/{session_id}/messages")
    async def post_chat_message(
        session_id: str,
        request: Request,
    ) -> JSONResponse:
        await get_user_from_request(web_auth_config, request)
        data = await request.json()
        message = data.get("message", "")
        is_approval_action = data.get("isApprovalAction", False)
        is_json = isinstance(message, dict)

        CFG.LOGGER.info(
            f"POST message: is_approval_action={is_approval_action}, is_json={is_json}, message={str(message)[:100]}"
        )

        session = session_manager.get_session(session_id)
        if session is None:
            session = await session_manager.create_session(session_id=session_id)

        # Handle approval actions (y/n/edit button clicks)
        if is_approval_action:
            is_waiting_edit = session_manager.is_waiting_for_edit(session_id)

            # Handle edit response with JSON args
            if is_json and is_waiting_edit:
                approval_result = session_manager.handle_approval_response(
                    session_id, message, is_json=True
                )
                if approval_result.get("handled"):
                    return JSONResponse(
                        content={
                            "status": "approval_handled",
                            "type": approval_result.get("type"),
                        }
                    )

            # Handle regular approval responses (y, n, e/edit commands)
            approval_result = session_manager.handle_approval_response(
                session_id, message, is_json=False
            )
            if approval_result.get("handled"):
                return JSONResponse(
                    content={
                        "status": "approval_handled",
                        "type": approval_result.get("type"),
                    }
                )

            # If we're waiting for edit but message isn't JSON, return error
            if is_waiting_edit:
                return JSONResponse(
                    content={"error": "Waiting for edit response, send JSON args"},
                    status_code=400,
                )

            # If there are pending approvals but response wasn't handled
            if session_manager.has_pending_approvals(session_id):
                return JSONResponse(
                    content={"error": "Pending tool approval, use y/n/e"},
                    status_code=400,
                )

        # Regular user message (not an approval action)
        # Convert message to string for sending to LLM
        if isinstance(message, dict):
            message = json.dumps(message)
        CFG.LOGGER.info(f"Sending to input queue: {message[:100]}")
        await session_manager.send_input(session_id, message)
        return JSONResponse(content={"status": "sent"})

    @app.get("/api/v1/chat/sessions/{session_id}/approval")
    async def get_pending_approval(
        session_id: str,
        request: Request,
    ) -> JSONResponse:
        await get_user_from_request(web_auth_config, request)
        pending = session_manager.get_pending_approvals(session_id)
        is_waiting_edit = session_manager.is_waiting_for_edit(session_id)
        editing_args = None
        if is_waiting_edit:
            editing_args = session_manager.get_editing_args(session_id)
        result = {
            "pending_approvals": pending,
            "is_waiting_for_edit": is_waiting_edit,
            "editing_args": editing_args,
        }
        CFG.LOGGER.info(
            f"GET /approval: is_waiting_edit={is_waiting_edit}, editing_args={editing_args}"
        )
        return JSONResponse(content=result)

    @app.get("/api/v1/chat/sessions/{session_id}/streaming")
    async def stream_chat(
        session_id: str,
        request: Request,
    ) -> SSEStreamResponse:
        await get_user_from_request(web_auth_config, request)
        session = session_manager.get_session(session_id)
        if session is None:
            session = await session_manager.create_session(session_id=session_id)

        if session.task_coroutine is None or session.task_coroutine.done():
            llm_chat = await _get_llm_chat_task(root_group)
            if llm_chat is None:
                await session_manager.broadcast(
                    session_id,
                    "[ERROR] LLM chat task not found. Please ensure 'zrb llm chat' is registered.",
                )
            else:
                approval_channel = HTTPChatApprovalChannel(
                    session_manager=session_manager,
                    session_id=session_id,
                )
                session.approval_channel = approval_channel
                session.task_coroutine = asyncio.create_task(
                    _run_chat_session(session, llm_chat, session_manager)
                )

        return SSEStreamResponse(
            session_id=session_id,
            session_manager=session_manager,
        )

    @app.get("/api/v1/chat/sessions/{session_id}/status")
    async def get_session_status(
        session_id: str,
        request: Request,
    ) -> JSONResponse:
        await get_user_from_request(web_auth_config, request)
        session = session_manager.get_session(session_id)
        if session is None:
            return JSONResponse(content={"exists": False})
        return JSONResponse(
            content={
                "exists": True,
                "is_processing": session.is_processing,
                "has_pending_approvals": session_manager.has_pending_approvals(
                    session_id
                ),
            }
        )


async def _run_chat_session(
    session: ChatSession,
    llm_chat_task: Any,
    session_manager: ChatSessionManager,
) -> None:
    current_task = asyncio.current_task()

    async def run_llm_message(session_obj: Any, timeout: float) -> None:
        try:
            async with asyncio.timeout(timeout):
                await llm_chat_task.async_run(session=session_obj)
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            await session_manager.broadcast(
                session.session_id, "[TIMEOUT] LLM request timed out"
            )
            raise
        except Exception as e:
            import traceback as tb_lib

            error_details = tb_lib.format_exc()
            await session_manager.broadcast(
                session.session_id, f"[ERROR] {error_details}"
            )
            raise

    try:
        from zrb.context.shared_context import SharedContext
        from zrb.session.session import Session

        saved_ui_factories = list(llm_chat_task._ui_factories)
        saved_approval_channels = list(llm_chat_task._approval_channels)
        saved_history_manager = llm_chat_task._history_manager
        saved_include_default_ui = llm_chat_task._include_default_ui

        try:
            llm_chat_task.set_history_manager(session_manager._history_manager)

            approval_channel = session.approval_channel

            http_ui_factory = _create_http_ui_factory(
                session_manager,
                session.session_id,
                session.session_name,
                approval_channel,
            )
            llm_chat_task._ui_factories = [http_ui_factory]
            llm_chat_task._approval_channels = [approval_channel]
            llm_chat_task._include_default_ui = False

            session_manager.set_processing(session.session_id, False)

            while True:
                llm_task: asyncio.Task | None = None
                try:
                    message = await asyncio.wait_for(
                        session.input_queue.get(), timeout=0.5
                    )
                except asyncio.CancelledError:
                    if llm_task and not llm_task.done():
                        llm_task.cancel()
                    raise
                except asyncio.TimeoutError:
                    if current_task.cancelling() > 0:
                        if llm_task and not llm_task.done():
                            llm_task.cancel()
                        raise
                    continue
                session_manager.set_processing(session.session_id, True)
                CFG.LOGGER.info(f"Processing message: {message[:100]}")
                await session_manager.broadcast(session.session_id, f"[USER] {message}")

                shared_ctx = SharedContext(
                    input={
                        "message": message,
                        "session": session.session_name,
                        "yolo": "false",
                        "attachments": "",
                        "model": "",
                    }
                )
                session_obj = Session(shared_ctx=shared_ctx)
                llm_task = asyncio.create_task(
                    run_llm_message(session_obj, DEFAULT_LLM_TIMEOUT)
                )
                try:
                    await llm_task
                    CFG.LOGGER.info("LLM task completed")
                except asyncio.CancelledError:
                    session_manager.set_processing(session.session_id, False)
                    raise
                except Exception as e:
                    CFG.LOGGER.error(f"LLM task error: {e}")
                    raise
                session_manager.set_processing(session.session_id, False)
        finally:
            llm_chat_task._ui_factories = saved_ui_factories
            llm_chat_task._approval_channels = saved_approval_channels
            llm_chat_task._history_manager = saved_history_manager
            llm_chat_task._include_default_ui = saved_include_default_ui
    except asyncio.CancelledError:
        raise
    except Exception as e:
        import traceback

        error_msg = f"[ERROR] {str(e)}\n{traceback.format_exc()}"
        await session_manager.broadcast(session.session_id, error_msg)
    finally:
        session_manager.set_processing(session.session_id, False)


def _create_http_ui_factory(
    session_manager: ChatSessionManager,
    session_id: str,
    session_name: str,
    approval_channel: HTTPChatApprovalChannel,
):
    from zrb.llm.approval.approval_channel import ApprovalContext
    from zrb.llm.ui.simple_ui import (
        EventDrivenUI,
        UIConfig,
    )
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
            # No-op: _run_loop is overridden directly
            pass

        async def _run_loop(self) -> None:
            """Process one message then return (enables multi-turn via session runner)."""
            # Wait for the submitted message to be fully processed by the LLM.
            # _message_queue.join() blocks until task_done() is called for every
            # item that was put() into the queue.
            await self._message_queue.join()

        async def run_async(self) -> str:
            """Override to re-raise CancelledError so server shutdown propagates."""
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

        ui = HTTPUI(
            ctx=ctx,
            llm_task=llm_task,
            history_manager=history_manager,
            config=cfg,
            initial_message=initial_message,
            initial_attachments=initial_attachments,
        )
        return ui

    return http_ui_factory
