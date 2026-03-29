from __future__ import annotations

import asyncio
import json
from typing import Any

from zrb.config.web_auth_config import WebAuthConfig
from zrb.config.config import CFG
from zrb.llm.chat import (
    ChatApprovalChannel,
    ChatSSEUI,
    ChatUIConfig,
    chat_approval_manager,
    chat_session_manager,
)
from zrb.llm.history_manager.file_history_manager import FileHistoryManager
from zrb.util.string.name import get_random_name

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

_approval_channel = ChatApprovalChannel()


@router.get("/sessions")
async def list_sessions(guest_id: str) -> JSONResponse:
    """List all sessions for a guest."""
    sessions = await chat_session_manager.get_guest_sessions(guest_id)
    return JSONResponse([
        {
            "session_id": s.session_id,
            "conversation_name": s.conversation_name,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
            "is_active": s.is_active,
        }
        for s in sessions
    ])


@router.post("/sessions")
async def create_session(request: Request) -> JSONResponse:
    """Create a new chat session."""
    body = await request.json()
    guest_id = body.get("guest_id")
    
    if not guest_id:
        raise HTTPException(status_code=400, detail="guest_id is required")
    
    conversation_name = body.get("conversation_name", get_random_name())
    session = await chat_session_manager.create_session(
        guest_id=guest_id,
        conversation_name=conversation_name,
    )
    
    return JSONResponse({
        "session_id": session.session_id,
        "conversation_name": session.conversation_name,
        "created_at": session.created_at,
    })


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> JSONResponse:
    """Get session info."""
    session = await chat_session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return JSONResponse({
        "session_id": session.session_id,
        "conversation_name": session.conversation_name,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "is_active": session.is_active,
    })


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> JSONResponse:
    """Delete a session."""
    success = await chat_session_manager.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return JSONResponse({"success": True})


@router.get("/sessions/{session_id}/stream")
async def stream(session_id: str, request: Request) -> StreamingResponse:
    """SSE stream for chat messages."""
    session = await chat_session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    async def event_generator():
        client_queue: asyncio.Queue[str] = asyncio.Queue()
        client_connected = True
        
        async def add_to_queue(message: str):
            print(f"[SSE DEBUG] add_to_queue called with: {message[:100]}...")
            await client_queue.put(message)
        
        sse_ui, llm_task = _create_sse_ui_and_task(session_id, session.guest_id, session.conversation_name, add_to_queue)
        _approval_channel.register_ui(session_id, sse_ui)
        ui_task = asyncio.create_task(sse_ui.run_async())
        
        print(f"[SSE DEBUG] Stream started for session {session_id}")
        yield f"data: {json.dumps({'type': 'status', 'data': {'connected': True, 'session_id': session_id}}, ensure_ascii=False)}\n\n"
        
        try:
            while client_connected:
                try:
                    message = await asyncio.wait_for(client_queue.get(), timeout=30)
                    print(f"[SSE DEBUG] Yielding message: {message[:100]}...")
                    yield f"data: {message}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"
                    
                if await request.is_disconnected():
                    print(f"[SSE DEBUG] Client disconnected")
                    client_connected = False
                    
        finally:
            print(f"[SSE DEBUG] Stream ending for session {session_id}")
            ui_task.cancel()
            _approval_channel.unregister_ui(session_id)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/sessions/{session_id}/messages")
async def send_message(session_id: str, request: Request) -> JSONResponse:
    """Send a message to the chat session."""
    session = await chat_session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    body = await request.json()
    message = body.get("message", "")
    
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    
    ui = _approval_channel.get_ui(session_id)
    if ui:
        ui.handle_incoming_message(message)
    else:
        raise HTTPException(
            status_code=400, 
            detail="No active SSE connection. Please connect to the stream first."
        )
    
    return JSONResponse({"success": True})


@router.get("/sessions/{session_id}/history")
async def get_history(session_id: str) -> JSONResponse:
    """Get chat history for a session."""
    session = await chat_session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    history_manager = FileHistoryManager(history_dir=CFG.LLM_HISTORY_DIR)
    try:
        history = history_manager.load(session.conversation_name)
        messages = []
        for item in history:
            if hasattr(item, 'parts'):
                for part in item.parts:
                    if hasattr(part, 'content') and part.content:
                        role = "user" if hasattr(item, 'role') and str(item.role) == "User" else "assistant"
                        messages.append({
                            "role": role,
                            "content": str(part.content),
                        })
        return JSONResponse({"messages": messages})
    except FileNotFoundError:
        return JSONResponse({"messages": []})


@router.get("/sessions/{session_id}/pending")
async def get_pending(session_id: str) -> JSONResponse:
    """Get pending approvals for a session."""
    session = await chat_session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return JSONResponse({
        "pending": session.pending_approval_list,
        "waiting_for_edit": session.waiting_for_edit,
    })


@router.post("/sessions/{session_id}/approve/{tool_call_id}")
async def approve_tool(session_id: str, tool_call_id: str) -> JSONResponse:
    """Approve a tool call."""
    result = await chat_approval_manager.approve(session_id, tool_call_id)
    return JSONResponse(result)


@router.post("/sessions/{session_id}/deny/{tool_call_id}")
async def deny_tool(
    session_id: str, 
    tool_call_id: str, 
    request: Request
) -> JSONResponse:
    """Deny a tool call."""
    body = await request.json()
    reason = body.get("reason", "")
    result = await chat_approval_manager.deny(session_id, tool_call_id, reason)
    return JSONResponse(result)


@router.post("/sessions/{session_id}/edit/{tool_call_id}")
async def edit_tool(
    session_id: str, 
    tool_call_id: str, 
    request: Request
) -> JSONResponse:
    """Submit edited tool arguments."""
    body = await request.json()
    new_args = body.get("args", {})
    result = await chat_approval_manager.submit_edit(session_id, tool_call_id, new_args)
    return JSONResponse(result)


def _create_sse_ui_and_task(
    session_id: str,
    guest_id: str,
    conversation_name: str,
    broadcast_fn,
):
    """Create a ChatSSEUI and LLMChatTask pair."""
    from zrb.llm.config.config import llm_config
    from zrb.llm.task.llm_chat_task import LLMChatTask
    
    history_manager = FileHistoryManager(history_dir=CFG.LLM_HISTORY_DIR)
    config = ChatUIConfig(
        assistant_name="Assistant",
        conversation_session_name=conversation_name,
    )
    
    llm_task = LLMChatTask(
        name="chat-session",
        description="Web chat session",
        llm_config=llm_config,
    )
    llm_task.append_approval_channel(_approval_channel)
    
    ui = ChatSSEUI(
        session_id=session_id,
        ctx=None,
        llm_task=llm_task,
        history_manager=history_manager,
        config=config,
        initial_message="",
        broadcast_fn=broadcast_fn,
    )
    
    def print_fn(*args, **kwargs):
        text = kwargs.pop("sep", " ").join(str(v) for v in args) + kwargs.pop("end", "\n")
        ui.append_to_output(text)
    
    llm_task._print_fn = print_fn
    llm_task.append_ui(ui)
    
    return ui, llm_task
