import asyncio
import json
import os
import stat
import tempfile
import uuid
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.config.web_auth_config import WebAuthConfig
from zrb.group.any_group import AnyGroup, NodeNotFoundError
from zrb.llm.subagent.manager import sub_agent_manager
from zrb.llm.util.attachment import check_attachment_bytes, get_media_type
from zrb.runner.chat.chat_session_manager import (
    ChatSessionManager,
    parse_delegated_session,
)
from zrb.runner.chat.chat_session_runner import run_chat_session
from zrb.runner.chat.http_chat import HTTPChatApprovalChannel
from zrb.runner.web_util.user import get_user_from_request
from zrb.util.string.conversion import to_safe_filename

from .sse_stream import SSEStreamResponse

if TYPE_CHECKING:
    from fastapi.responses import JSONResponse


def _ensure_private_dir(path: str) -> None:
    """Create *path* 0700, refusing a symlink or a directory another user owns.

    The upload root has a fixed name under the shared temp dir, so another
    local user could pre-create it as a symlink. Mirrors
    `llm/agent/spill.py::_ensure_root`.
    """
    os.makedirs(path, mode=0o700, exist_ok=True)
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or os.path.islink(path):
        raise PermissionError(f"Upload dir must be a directory, not a symlink: {path}")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise PermissionError(f"Upload dir must be owned by the current user: {path}")
    os.chmod(path, 0o700)


def save_uploaded_attachment(session_id: str, filename: str, data: bytes) -> str:
    """Persist an uploaded attachment to a per-session temp dir, return its path.

    Uploads are never cleaned up. Add a retention sweep if the temp
    dir's growth becomes a real problem.
    """
    upload_root = os.path.join(tempfile.gettempdir(), "zrb_web_chat_uploads")
    _ensure_private_dir(upload_root)
    # `session_id` is untrusted: `..` would chmod the shared temp dir.
    safe_session = to_safe_filename(session_id)
    if not safe_session:
        raise ValueError(f"Invalid session id: {session_id!r}")
    upload_dir = os.path.join(upload_root, safe_session)
    # Assert containment rather than rely on `to_safe_filename`'s behavior.
    if os.path.dirname(os.path.abspath(upload_dir)) != os.path.abspath(upload_root):
        raise ValueError(f"Invalid session id: {session_id!r}")
    _ensure_private_dir(upload_dir)
    # The client filename contributes only its (already sniff-checked) extension.
    extension = os.path.splitext(os.path.basename(filename))[1][:16]
    if not extension.isascii() or any(c in extension for c in '\\/:*?"<>|\0'):
        extension = ""
    entry = f"{uuid.uuid4().hex}{extension}"
    _write_into_dir(upload_dir, entry, data)
    return os.path.join(upload_dir, entry)


def _write_into_dir(directory: str, entry: str, data: bytes) -> None:
    """Write *data* to *entry* inside *directory*, resolving the name once.

    Writing through a held directory descriptor closes the check-then-open
    race where the directory is swapped for a symlink; `O_EXCL | O_NOFOLLOW`
    refuses a planted entry. Windows lacks `dir_fd`/`O_NOFOLLOW` and falls
    back to `O_EXCL` alone.
    """
    binary = getattr(os, "O_BINARY", 0)
    if os.open not in os.supports_dir_fd or not hasattr(os, "O_NOFOLLOW"):
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | binary
        fd = os.open(os.path.join(directory, entry), flags, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        return
    dir_fd = os.open(directory, os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY)
    try:
        info = os.fstat(dir_fd)
        if hasattr(os, "getuid") and info.st_uid != os.getuid():
            raise PermissionError(
                f"Upload dir must be owned by the current user: {directory}"
            )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | binary
        fd = os.open(entry, flags, 0o600, dir_fd=dir_fd)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
    finally:
        os.close(dir_fd)


async def get_llm_chat_task(root_group: AnyGroup) -> Any:
    try:
        task, _, _ = root_group.extract_node(["llm", "chat"])
        return task
    except NodeNotFoundError:
        return None


async def resolve_llm_chat_task_for_session(
    session_id: str, root_group: AnyGroup
) -> "tuple[Any, str]":
    """Return the task to drive *session_id*, and the message to broadcast if none.

    A delegated sub-agent session id (`{parent}-sub-{agent_name}-{agent_id}`)
    resumes with that sub-agent's own task instead of the shared `llm chat`.
    """
    delegated = parse_delegated_session(session_id)
    if delegated is not None:
        agent_name = delegated[1]
        llm_chat = sub_agent_manager.create_llm_chat_task(agent_name)
        not_found_msg = (
            f"[ERROR] Cannot resume sub-agent '{agent_name}' — its definition "
            "no longer exists, or it was built from a pre-built agent "
            "instance that cannot be resumed this way."
        )
        return llm_chat, not_found_msg
    llm_chat = await get_llm_chat_task(root_group)
    not_found_msg = (
        "[ERROR] LLM chat task not found. "
        f"Please ensure '{CFG.ROOT_GROUP_NAME} llm chat' is registered."
    )
    return llm_chat, not_found_msg


async def _require_auth(
    web_auth_config: WebAuthConfig,
    root_group: AnyGroup,
    request: Any,
) -> "JSONResponse | None":
    """Return a 403 response unless the requester may access ``llm chat``.

    Returns ``None`` when allowed, or when no chat task is registered.
    """
    # lazy: heavy third-party
    from fastapi.responses import JSONResponse

    user = await get_user_from_request(web_auth_config, request)
    llm_chat = await get_llm_chat_task(root_group)
    if llm_chat is not None and not user.can_access_task(llm_chat):
        return JSONResponse(content={"detail": "Forbidden"}, status_code=403)
    return None


async def _read_json_body(request: Any) -> dict:
    """Parse the request body as a JSON object; an empty or malformed body yields ``{}``."""
    try:
        data = await request.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


async def _handle_list_chat_sessions(
    session_manager: ChatSessionManager,
    page: int,
    limit: int | None,
) -> "JSONResponse":
    # lazy: heavy third-party
    from fastapi.responses import JSONResponse

    if limit is None:
        limit = CFG.WEB_API_PAGE_SIZE
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


async def _handle_create_chat_session(
    session_manager: ChatSessionManager,
    request: Any,
) -> "JSONResponse":
    # lazy: heavy third-party
    from fastapi.responses import JSONResponse

    data = await _read_json_body(request)
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


async def _handle_delete_chat_session(
    session_manager: ChatSessionManager,
    session_id: str,
) -> "JSONResponse":
    # lazy: heavy third-party
    from fastapi.responses import JSONResponse

    removed = await session_manager.remove_session(session_id)
    if removed:
        return JSONResponse(content={"success": True})
    return JSONResponse(content={"error": "Session not found"}, status_code=404)


async def _handle_get_chat_messages(
    session_manager: ChatSessionManager,
    session_id: str,
) -> "JSONResponse":
    # lazy: heavy third-party
    from fastapi.responses import JSONResponse

    messages = session_manager.get_messages(session_id)
    serializable_messages = []
    for msg in messages:
        msg_dict = {
            "role": msg.get("role", "unknown"),
            "content": msg.get("content", ""),
        }
        if msg.get("live_context"):
            msg_dict["live_context"] = msg["live_context"]
        if "timestamp" in msg and msg["timestamp"]:
            msg_dict["timestamp"] = str(msg["timestamp"])
        serializable_messages.append(msg_dict)
    return JSONResponse(content={"messages": serializable_messages})


async def _handle_upload_chat_attachment(
    session_manager: ChatSessionManager,
    session_id: str,
    file: Any,
) -> "JSONResponse":
    # lazy: heavy third-party
    from fastapi.responses import JSONResponse

    filename = file.filename or "attachment"
    media_type = get_media_type(filename)
    if not media_type:
        return JSONResponse(
            content={"error": f"Unsupported file type: {filename}"},
            status_code=400,
        )
    # Read one byte past the cap so an oversized upload is never read in full.
    limit = CFG.LLM_MAX_ATTACHMENT_BYTES
    if limit > 0:
        data = await file.read(limit + 1)
        if len(data) > limit:
            return JSONResponse(
                content={"error": f"File too large (limit {limit} bytes)"},
                status_code=400,
            )
    else:
        data = await file.read()
    rejection = check_attachment_bytes(data, media_type)
    if rejection:
        return JSONResponse(content={"error": f"File {rejection}"}, status_code=400)
    try:
        path = save_uploaded_attachment(session_id, filename, data)
    except ValueError as invalid:
        return JSONResponse(content={"error": str(invalid)}, status_code=400)
    except OSError as failure:
        CFG.LOGGER.warning(f"Attachment store failed: {failure}")
        return JSONResponse(
            content={"error": "Could not store attachment"}, status_code=507
        )
    display_name = os.path.basename(filename)[:255] or "attachment"
    return JSONResponse(content={"path": path, "name": display_name})


async def _handle_post_chat_message(
    session_manager: ChatSessionManager,
    session_id: str,
    request: Any,
) -> "JSONResponse":
    # lazy: heavy third-party
    from fastapi.responses import JSONResponse

    data = await _read_json_body(request)
    message = data.get("message", "")
    if not isinstance(message, (str, dict)):
        return JSONResponse(
            content={"error": "Field 'message' must be a string or an object"},
            status_code=400,
        )
    attachments = data.get("attachments") or []
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
        elif not is_json:
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
        # A dict never retries as is_json=False: handle_response would deny
        # the pending approval.
        # Re-read: an unhandled claim above may have cleared a stale edit slot.
        is_waiting_edit = session_manager.is_waiting_for_edit(session_id)
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

    if isinstance(message, dict):
        message = json.dumps(message)
    CFG.LOGGER.info(f"Sending to input queue: {message[:100]}")
    await session_manager.send_input(session_id, message, attachments=attachments)
    return JSONResponse(content={"status": "sent"})


async def _handle_get_pending_approval(
    session_manager: ChatSessionManager,
    session_id: str,
) -> "JSONResponse":
    # lazy: heavy third-party
    from fastapi.responses import JSONResponse

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


async def _handle_stream_chat(
    session_manager: ChatSessionManager,
    root_group: AnyGroup,
    session_id: str,
) -> "SSEStreamResponse":
    session = session_manager.get_session(session_id)
    if session is None:
        session = await session_manager.create_session(session_id=session_id)

    if session.task_coroutine is None or session.task_coroutine.done():
        llm_chat, not_found_msg = await resolve_llm_chat_task_for_session(
            session_id, root_group
        )
        if llm_chat is None:
            await session_manager.broadcast(session_id, not_found_msg)
        else:
            approval_channel = HTTPChatApprovalChannel(
                session_manager=session_manager,
                session_id=session_id,
            )
            session.approval_channel = approval_channel
            session.task_coroutine = asyncio.create_task(
                run_chat_session(session, llm_chat, session_manager)
            )

    return SSEStreamResponse(
        session_id=session_id,
        session_manager=session_manager,
    )


async def _handle_get_session_status(
    session_manager: ChatSessionManager,
    session_id: str,
) -> "JSONResponse":
    # lazy: heavy third-party
    from fastapi.responses import JSONResponse

    session = session_manager.get_session(session_id)
    if session is None:
        return JSONResponse(content={"exists": False})
    return JSONResponse(
        content={
            "exists": True,
            "is_processing": session.is_processing,
            "has_pending_approvals": session_manager.has_pending_approvals(session_id),
        }
    )


def serve_chat_api(  # noqa: C901 -- registration/factory fn; mccabe sums the one-line route closures into this line, radon scores each separately (near-trivial on its own)
    app: Any,
    root_group: AnyGroup,
    web_auth_config: WebAuthConfig,
) -> None:
    # lazy: heavy third-party
    from fastapi import File, Request, UploadFile

    session_manager = ChatSessionManager.get_instance_sync()

    @app.get("/api/v1/chat/sessions")
    async def list_chat_sessions(
        request: Request,
        page: int = 1,
        limit: int | None = None,
    ) -> "JSONResponse":
        if (
            forbidden := await _require_auth(web_auth_config, root_group, request)
        ) is not None:
            return forbidden
        return await _handle_list_chat_sessions(session_manager, page, limit)

    @app.post("/api/v1/chat/sessions")
    async def create_chat_session(request: Request) -> "JSONResponse":
        if (
            forbidden := await _require_auth(web_auth_config, root_group, request)
        ) is not None:
            return forbidden
        return await _handle_create_chat_session(session_manager, request)

    @app.delete("/api/v1/chat/sessions/{session_id}")
    async def delete_chat_session(
        session_id: str,
        request: Request,
    ) -> "JSONResponse":
        if (
            forbidden := await _require_auth(web_auth_config, root_group, request)
        ) is not None:
            return forbidden
        return await _handle_delete_chat_session(session_manager, session_id)

    @app.get("/api/v1/chat/sessions/{session_id}/messages")
    async def get_chat_messages(
        session_id: str,
        request: Request,
    ) -> "JSONResponse":
        if (
            forbidden := await _require_auth(web_auth_config, root_group, request)
        ) is not None:
            return forbidden
        return await _handle_get_chat_messages(session_manager, session_id)

    @app.post("/api/v1/chat/sessions/{session_id}/attachments")
    async def upload_chat_attachment(
        session_id: str,
        request: Request,
        file: UploadFile = File(...),
    ) -> "JSONResponse":
        if (
            forbidden := await _require_auth(web_auth_config, root_group, request)
        ) is not None:
            return forbidden
        return await _handle_upload_chat_attachment(session_manager, session_id, file)

    @app.post("/api/v1/chat/sessions/{session_id}/messages")
    async def post_chat_message(
        session_id: str,
        request: Request,
    ) -> "JSONResponse":
        if (
            forbidden := await _require_auth(web_auth_config, root_group, request)
        ) is not None:
            return forbidden
        return await _handle_post_chat_message(session_manager, session_id, request)

    @app.get("/api/v1/chat/sessions/{session_id}/approval")
    async def get_pending_approval(
        session_id: str,
        request: Request,
    ) -> "JSONResponse":
        if (
            forbidden := await _require_auth(web_auth_config, root_group, request)
        ) is not None:
            return forbidden
        return await _handle_get_pending_approval(session_manager, session_id)

    @app.get("/api/v1/chat/sessions/{session_id}/streaming")
    async def stream_chat(
        session_id: str,
        request: Request,
    ) -> "SSEStreamResponse":
        if (
            forbidden := await _require_auth(web_auth_config, root_group, request)
        ) is not None:
            return forbidden  # pyright: ignore[reportReturnType]
        return await _handle_stream_chat(session_manager, root_group, session_id)

    @app.get("/api/v1/chat/sessions/{session_id}/status")
    async def get_session_status(
        session_id: str,
        request: Request,
    ) -> "JSONResponse":
        if (
            forbidden := await _require_auth(web_auth_config, root_group, request)
        ) is not None:
            return forbidden
        return await _handle_get_session_status(session_manager, session_id)
