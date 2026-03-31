import asyncio
import json
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

    def _get_all_session_names(self) -> list[str]:
        if not CFG.LLM_HISTORY_DIR:
            return []
        import os

        history_dir = CFG.LLM_HISTORY_DIR
        history_dir = os.path.expanduser(history_dir)
        if not os.path.exists(history_dir):
            return []
        session_names = []
        for filename in os.listdir(history_dir):
            if filename.endswith(".json"):
                session_name = filename[:-5]
                session_names.append(session_name)
        return session_names

    def _get_sessions_with_timestamps(self) -> list[tuple[str, float]]:
        """Get all sessions with their file modification timestamps, newest first."""
        if not CFG.LLM_HISTORY_DIR:
            return []
        import os

        history_dir = CFG.LLM_HISTORY_DIR
        history_dir = os.path.expanduser(history_dir)
        if not os.path.exists(history_dir):
            return []
        sessions_with_times = []
        for filename in os.listdir(history_dir):
            if filename.endswith(".json"):
                file_path = os.path.join(history_dir, filename)
                mtime = os.path.getmtime(file_path)
                base_name = self._extract_base_name(filename[:-5])
                sessions_with_times.append((base_name, mtime))
        # Remove duplicates (keep newest), sort by mtime descending
        seen = set()
        result = []
        for base_name, mtime in sorted(
            sessions_with_times, key=lambda x: x[1], reverse=True
        ):
            if base_name not in seen:
                seen.add(base_name)
                result.append((base_name, mtime))
        return result

    def _extract_base_name(self, session_name: str) -> str:
        return _timestamp_pattern.sub("", session_name)

    def get_sessions_count(self) -> int:
        sessions_with_times = self._get_sessions_with_timestamps()
        base_names = {name for name, _ in sessions_with_times}
        active_ids = set(self._sessions.keys()) - base_names
        return len(base_names) + len(active_ids)

    def get_sessions(self, page: int = 1, limit: int = 20) -> list[dict[str, Any]]:
        sessions_with_times = self._get_sessions_with_timestamps()
        all_names = self._get_all_session_names()
        sessions = []
        seen_session_ids = set()

        for base_name, _ in sessions_with_times:
            matching_names = [
                n for n in all_names if self._extract_base_name(n) == base_name
            ]
            session_id = base_name
            seen_session_ids.add(session_id)
            is_active = session_id in self._sessions
            is_processing = (
                self._sessions[session_id].is_processing if is_active else False
            )
            sessions.append(
                {
                    "session_id": session_id,
                    "session_name": base_name,
                    "is_active": is_active,
                    "is_processing": is_processing,
                    "message_count": len(matching_names),
                }
            )

        # Add active sessions that aren't in history (new sessions without messages)
        for session_id, session in self._sessions.items():
            if session_id not in seen_session_ids:
                sessions.append(
                    {
                        "session_id": session_id,
                        "session_name": session.session_name,
                        "is_active": True,
                        "is_processing": session.is_processing,
                        "message_count": 0,
                    }
                )

        start = (page - 1) * limit
        end = start + limit
        return sessions[start:end]

    async def create_session(
        self,
        session_id: str | None = None,
        llm_chat_task: Any = None,
        chat_ui: Any = None,
        approval_channel: Any = None,
    ) -> ChatSession:
        async with self._lock:
            if session_id is None:
                session_id = get_random_name()
            if session_id in self._sessions:
                return self._sessions[session_id]
            session = ChatSession(
                session_id=session_id,
                session_name=session_id,
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
                        if isinstance(part.content, str):
                            content += part.content
                        else:
                            content += str(part.content)
                    elif hasattr(part, "content"):
                        content = str(part.content)
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
        self, session_id: str, response: str, is_json: bool = False
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
