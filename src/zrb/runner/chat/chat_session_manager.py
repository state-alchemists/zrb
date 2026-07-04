import asyncio
import os
import re
from dataclasses import dataclass, field
from typing import Any

from zrb.config.config import CFG
from zrb.llm.history_manager.file_history_manager import FileHistoryManager
from zrb.util.string.name import get_random_name

_timestamp_pattern = re.compile(r"-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}(?:-\d{2})?$")


@dataclass
class ChatSession:
    session_id: str
    session_name: str
    llm_chat_task: Any = field(default=None, repr=False)
    chat_ui: Any = field(default=None, repr=False)
    approval_channel: Any = field(default=None, repr=False)
    task_coroutine: asyncio.Task | None = field(default=None, repr=False)
    output_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    input_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    is_processing: bool = False


class ChatSessionManager:
    _instance: "ChatSessionManager | None" = None
    _lock = asyncio.Lock()

    def __init__(self):
        self._sessions: dict[str, ChatSession] = {}
        self._history_manager = FileHistoryManager(history_dir=CFG.LLM_HISTORY_DIR)
        self._init_coros: list[asyncio.Task] = []
        # Serializes drives of the single shared LLMChatTask. Multiple SSE sessions
        # share one task instance whose ui_factories/approval_channels/history_manager
        # are read at run time; without this, a second session's config would clobber
        # an in-flight run. Held per message (not per session) so sessions still
        # coexist — they just don't drive the shared task simultaneously.
        self._task_lock = asyncio.Lock()

    @classmethod
    async def get_instance(cls) -> "ChatSessionManager":
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def get_instance_sync(cls) -> "ChatSessionManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def task_lock(self) -> asyncio.Lock:
        """Lock serializing drives of the shared LLMChatTask (see __init__)."""
        return self._task_lock

    @property
    def history_manager(self) -> FileHistoryManager:
        """Get the history manager."""
        return self._history_manager

    def set_history_manager(self, history_manager: FileHistoryManager):
        """Set the history manager."""
        self._history_manager = history_manager

    def has_session(self, session_id: str) -> bool:
        """Check if a session exists."""
        return session_id in self._sessions

    @property
    def sessions(self) -> dict[str, ChatSession]:
        """Get the active sessions."""
        return self._sessions

    def get_active_tasks(self) -> list[asyncio.Task]:
        """Get all active task coroutines for cleanup."""
        tasks = []
        for session in self._sessions.values():
            if session.task_coroutine is not None and not session.task_coroutine.done():
                tasks.append(session.task_coroutine)
        return tasks

    async def cancel_all_sessions(self) -> None:
        """Cancel all active session tasks."""
        for session in self._sessions.values():
            if session.task_coroutine is not None and not session.task_coroutine.done():
                session.task_coroutine.cancel()
                try:
                    await session.task_coroutine
                except asyncio.CancelledError:
                    pass

    def _extract_base_name(self, session_name: str) -> str:
        return _timestamp_pattern.sub("", session_name)

    def _scan_sessions(self) -> list[tuple[str, float, int]]:
        """Group history files by base session name in one directory scan.

        Returns ``(base_name, newest_mtime, file_count)`` tuples, newest first.
        The history dir holds a main file per session plus every timestamped
        backup, so it grows fast — a single ``scandir`` pass with O(n) grouping
        replaces the old three-listdir + per-file ``getmtime`` + O(n²) name
        matching that made listing heavy.
        """
        if not CFG.LLM_HISTORY_DIR:
            return []
        history_dir = os.path.expanduser(CFG.LLM_HISTORY_DIR)
        if not os.path.isdir(history_dir):
            return []
        grouped: dict[str, list] = {}  # base -> [max_mtime, count]
        with os.scandir(history_dir) as entries:
            for entry in entries:
                if not entry.name.endswith(".json"):
                    continue
                base_name = self._extract_base_name(entry.name[:-5])
                try:
                    mtime = entry.stat().st_mtime
                except OSError:
                    continue
                slot = grouped.get(base_name)
                if slot is None:
                    grouped[base_name] = [mtime, 1]
                else:
                    if mtime > slot[0]:
                        slot[0] = mtime
                    slot[1] += 1
        ranked = [(base, mt, count) for base, (mt, count) in grouped.items()]
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked

    def _session_listing(self) -> list[dict[str, Any]]:
        """History + active sessions as display dicts, most recent first."""
        listing: list[dict[str, Any]] = []
        seen: set[str] = set()
        for base_name, _mtime, file_count in self._scan_sessions():
            seen.add(base_name)
            is_active = base_name in self._sessions
            listing.append(
                {
                    "session_id": base_name,
                    "session_name": base_name,
                    "is_active": is_active,
                    "is_processing": (
                        self._sessions[base_name].is_processing if is_active else False
                    ),
                    "message_count": file_count,
                }
            )
        # Active sessions with no history file yet are the newest → put on top.
        extras = [
            {
                "session_id": session_id,
                "session_name": session.session_name,
                "is_active": True,
                "is_processing": session.is_processing,
                "message_count": 0,
            }
            for session_id, session in self._sessions.items()
            if session_id not in seen
        ]
        return extras + listing

    def get_sessions_count(self) -> int:
        return len(self._session_listing())

    def get_sessions(
        self, page: int = 1, limit: int | None = None
    ) -> list[dict[str, Any]]:
        if limit is None:
            limit = CFG.WEB_SESSION_PAGE_SIZE
        listing = self._session_listing()
        start = (page - 1) * limit
        return listing[start : start + limit]

    async def create_session(
        self,
        session_id: str | None = None,
        session_name: str | None = None,
        llm_chat_task: Any = None,
        chat_ui: Any = None,
        approval_channel: Any = None,
    ) -> ChatSession:
        async with self._lock:
            if session_id is None:
                session_id = get_random_name()
            if session_id in self._sessions:
                return self._sessions[session_id]
            final_name = session_name if session_name else session_id
            session = ChatSession(
                session_id=session_id,
                session_name=final_name,
                llm_chat_task=llm_chat_task,
                chat_ui=chat_ui,
                approval_channel=approval_channel,
            )
            self._sessions[session_id] = session
            return session

    def get_session(self, session_id: str) -> ChatSession | None:
        return self._sessions.get(session_id)

    async def remove_session(self, session_id: str) -> bool:
        async with self._lock:
            if session_id not in self._sessions:
                return False
            session = self._sessions[session_id]
            if session.task_coroutine and not session.task_coroutine.done():
                session.task_coroutine.cancel()
                try:
                    await session.task_coroutine
                except asyncio.CancelledError:
                    pass
            del self._sessions[session_id]
            return True

    def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        session = self._sessions.get(session_id)
        session_name = session.session_name if session else session_id
        messages = self._history_manager.load(session_name)
        result = []
        for msg in messages:
            if hasattr(msg, "kind"):
                role = "user" if msg.kind == "request" else "assistant"
            else:
                role = "unknown"
            content = ""
            if hasattr(msg, "parts"):
                for part in msg.parts:
                    if hasattr(part, "content"):
                        part_content = getattr(part, "content")
                        if isinstance(part_content, str):
                            content += part_content
                        else:
                            content += str(part_content)
            result.append(
                {
                    "role": role,
                    "content": content,
                    "timestamp": getattr(msg, "timestamp", None),
                }
            )
        return result

    async def broadcast(self, session_id: str, text: str, kind: str = "text") -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        await session.output_queue.put({"text": text, "kind": kind})
        return True

    async def send_input(self, session_id: str, text: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        session.input_queue.put_nowait(text)
        return True

    def set_processing(self, session_id: str, is_processing: bool) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        session.is_processing = is_processing
        return True

    def has_pending_approvals(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None or session.approval_channel is None:
            return False
        return session.approval_channel.has_pending_approvals()

    def get_pending_approvals(self, session_id: str) -> list[dict[str, Any]]:
        session = self._sessions.get(session_id)
        if session is None or session.approval_channel is None:
            return []
        return session.approval_channel.get_pending_approvals()

    def is_waiting_for_edit(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None or session.approval_channel is None:
            return False
        return session.approval_channel.is_waiting_for_edit()

    def get_editing_args(self, session_id: str) -> dict[str, Any] | None:
        session = self._sessions.get(session_id)
        if session is None or session.approval_channel is None:
            return None
        return session.approval_channel.get_editing_args()

    def handle_approval_response(
        self, session_id: str, response: Any, is_json: bool = False
    ) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if session is None or session.approval_channel is None:
            return {"handled": False, "error": "Session or approval channel not found"}
        approval_channel = session.approval_channel
        if is_json or approval_channel.is_waiting_for_edit():
            if is_json:
                approval_channel.handle_edit_response_obj(response)
            else:
                approval_channel.handle_edit_response(response)
            return {"handled": True, "type": "edit"}
        if approval_channel.has_pending_approvals():
            handled = approval_channel.handle_response(response)
            return {"handled": handled, "type": "approval"}
        return {"handled": False, "error": "No pending approvals"}
