import asyncio
import os
import re
from dataclasses import dataclass, field
from typing import Any

from zrb.config.config import CFG
from zrb.llm.agent.activity import agent_activity_registry
from zrb.llm.history_manager.file_history_manager import (
    FileHistoryManager,
    default_history_manager,
)
from zrb.llm.input_source import WEB_INPUT, InputProvenance
from zrb.llm.prompt.live_context import split_live_context
from zrb.llm.util.feature_config import close_feature_sessions

# Re-exported for chat_api_route.py and tests.
from zrb.llm.util.subagent_session_naming import (
    parse_delegated_session,
    subagent_history_directories,
)
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
        self._history_manager = default_history_manager()
        self._init_coros: list[asyncio.Task] = []
        # All SSE sessions share one LLMChatTask whose UI/approval/history config
        # is read at run time; held per message so one session cannot clobber
        # another's in-flight run.
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

    @classmethod
    def reset_instance(cls) -> None:
        """Drop the singleton so the next `get_instance*()` builds a fresh one (test seam)."""
        cls._instance = None

    @property
    def task_lock(self) -> asyncio.Lock:
        """Lock serializing drives of the shared LLMChatTask (see __init__)."""
        return self._task_lock

    @property
    def history_manager(self) -> FileHistoryManager:
        return self._history_manager

    def set_history_manager(self, history_manager: FileHistoryManager):
        self._history_manager = history_manager

    def has_session(self, session_id: str) -> bool:
        return session_id in self._sessions

    @property
    def sessions(self) -> dict[str, ChatSession]:
        return self._sessions

    def get_active_tasks(self) -> list[asyncio.Task]:
        tasks = []
        for session in self._sessions.values():
            if session.task_coroutine is not None and not session.task_coroutine.done():
                tasks.append(session.task_coroutine)
        return tasks

    async def cancel_all_sessions(self) -> None:
        for session in self._sessions.values():
            if session.task_coroutine is not None and not session.task_coroutine.done():
                session.task_coroutine.cancel()
                try:
                    await session.task_coroutine
                except asyncio.CancelledError:
                    pass

    def _extract_base_name(self, session_name: str) -> str:
        return _timestamp_pattern.sub("", session_name)

    def scan_sessions(self) -> list[tuple[str, float, int]]:
        """Group history files by base session name.

        Returns ``(base_name, newest_mtime, file_count)`` tuples, newest first.
        Also scans delegated sub-agent transcripts under ``subagent/{agent_type}/``.
        """
        if not CFG.LLM_HISTORY_DIR:
            return []
        history_dir = os.path.expanduser(CFG.LLM_HISTORY_DIR)
        if not os.path.isdir(history_dir):
            return []
        grouped: dict[str, list] = {}  # base -> [max_mtime, count]
        for directory in subagent_history_directories(history_dir):
            try:
                entries = os.scandir(directory)
            except OSError:
                continue
            with entries:
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
        for base_name, _mtime, file_count in self.scan_sessions():
            seen.add(base_name)
            is_active = base_name in self._sessions
            # An active session is always a root session, even if its name
            # matches the delegated-session shape.
            delegated = None if is_active else parse_delegated_session(base_name)
            listing.append(
                {
                    "session_id": base_name,
                    "session_name": base_name,
                    "is_active": is_active,
                    "is_processing": (
                        self._sessions[base_name].is_processing if is_active else False
                    ),
                    "message_count": file_count,
                    "parent_session_id": delegated[0] if delegated else None,
                    "agent_name": delegated[1] if delegated else None,
                }
            )
        # Active sessions with no history file yet are the newest.
        extras = [
            {
                "session_id": session_id,
                "session_name": session.session_name,
                "is_active": True,
                "is_processing": session.is_processing,
                "message_count": 0,
                "parent_session_id": None,
                "agent_name": None,
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
            agent_activity_registry.clear(session_id=session_id)
            close_feature_sessions(session_id)
            # lazy: transitively heavy via internal — live_session.py imports
            # run_agent, which pulls in pydantic_ai.
            from zrb.llm.agent.subagent.live_session import (
                live_subagent_session_registry,
            )

            live_subagent_session_registry.clear(session_id=session_id)
            # Background shells outlive a message; this is their only cleanup.
            # Keyed by session_id: session_name is not unique.
            # lazy: transitively heavy via internal — shell_background.py stays off load path
            from zrb.llm.tool.shell_background import get_shell_background_registry

            await get_shell_background_registry().cancel_for_session(session_id)
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
            live_context = None
            if role == "user":
                content, live_context = split_live_context(content)
            result.append(
                {
                    "role": role,
                    "content": content,
                    "live_context": live_context,
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

    async def send_input(
        self,
        session_id: str,
        text: str,
        attachments: "list[str] | None" = None,
        source: InputProvenance | None = WEB_INPUT,
    ) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        session.input_queue.put_nowait(
            {"message": text, "attachments": attachments or [], "source": source}
        )
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
                handled = approval_channel.handle_edit_response_obj(response)
            else:
                handled = approval_channel.handle_edit_response(response)
            if handled:
                return {"handled": True, "type": "edit"}
            if is_json:
                # No edit slot consumed the args; handle_response cannot parse a
                # dict and would deny the pending approval.
                return {"handled": False, "error": "No pending edit request"}
        if approval_channel.has_pending_approvals():
            handled = approval_channel.handle_response(response)
            return {"handled": handled, "type": "approval"}
        return {"handled": False, "error": "No pending approvals"}
