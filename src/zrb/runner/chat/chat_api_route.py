import asyncio
import json
from typing import Any

from zrb.config.config import CFG
from zrb.config.web_auth_config import WebAuthConfig
from zrb.group.any_group import AnyGroup
from zrb.runner.chat.chat_session_manager import ChatSessionManager
from zrb.runner.chat.chat_session_runner import run_chat_session as _run_chat_session
from zrb.runner.chat.http_chat import HTTPChatApprovalChannel
from zrb.runner.web_util.user import get_user_from_request
from zrb.util.group import NodeNotFoundError, extract_node_from_args

from .sse_stream import SSEStreamResponse


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
        limit: int | None = None,
    ) -> JSONResponse:
        if limit is None:
            limit = CFG.WEB_API_PAGE_SIZE
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
            f"POST message: is_approval_action={is_approval_action}, "
            f"is_json={is_json}, message={str(message)[:100]}"
        )

        session = session_manager.get_session(session_id)
        if session is None:
            session = await session_manager.create_session(session_id=session_id)

        if is_approval_action:
            is_waiting_edit = session_manager.is_waiting_for_edit(session_id)

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

            if is_waiting_edit:
                return JSONResponse(
                    content={"error": "Waiting for edit response, send JSON args"},
                    status_code=400,
                )

            if session_manager.has_pending_approvals(session_id):
                return JSONResponse(
                    content={"error": "Pending tool approval, use y/n/e"},
                    status_code=400,
                )

        # Regular user message (not an approval action)
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
        editing_args = (
            session_manager.get_editing_args(session_id) if is_waiting_edit else None
        )
        result = {
            "pending_approvals": pending,
            "is_waiting_for_edit": is_waiting_edit,
            "editing_args": editing_args,
        }
        CFG.LOGGER.info(
            f"GET /approval: is_waiting_edit={is_waiting_edit}, "
            f"editing_args={editing_args}"
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
                    "[ERROR] LLM chat task not found. "
                    "Please ensure 'zrb llm chat' is registered.",
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
