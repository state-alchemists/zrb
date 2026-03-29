from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from zrb.llm.approval.approval_channel import ApprovalContext, ApprovalResult


@dataclass
class PendingApproval:
    """Represents a pending tool approval request."""

    tool_call_id: str
    tool_name: str
    tool_args: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    future: asyncio.Future["ApprovalResult"] | None = None


@dataclass
class ChatSession:
    """Represents a single chat session."""

    session_id: str
    guest_id: str
    conversation_name: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    is_active: bool = True
    pending_approvals: dict[str, PendingApproval] = field(default_factory=dict)
    waiting_for_edit: str | None = None
    _pending_tool_call_id: str | None = None

    @property
    def pending_approval_list(self) -> list[dict[str, Any]]:
        """Get list of pending approvals for API response."""
        return [
            {
                "tool_call_id": pa.tool_call_id,
                "tool_name": pa.tool_name,
                "tool_args": pa.tool_args,
                "timestamp": pa.timestamp,
            }
            for pa in self.pending_approvals.values()
        ]


class ChatSessionManager:
    """Manages multiple chat sessions per guest.

    Each guest has their own isolated set of sessions.
    Sessions are stored in memory (can be extended to persist to disk/DB).
    """

    _instance: "ChatSessionManager | None" = None
    _lock = asyncio.Lock()

    def __init__(self):
        self._sessions: dict[str, ChatSession] = {}
        self._guest_sessions: dict[str, list[str]] = {}
        self._session_locks: dict[str, asyncio.Lock] = {}

    @classmethod
    def get_instance(cls) -> "ChatSessionManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def create_session(
        self,
        guest_id: str,
        conversation_name: str = "",
    ) -> ChatSession:
        """Create a new chat session for a guest."""
        import uuid

        async with self._lock:
            session_id = str(uuid.uuid4())[:8]
            if not conversation_name:
                conversation_name = self._generate_name()

            session = ChatSession(
                session_id=session_id,
                guest_id=guest_id,
                conversation_name=conversation_name,
            )
            self._sessions[session_id] = session
            self._session_locks[session_id] = asyncio.Lock()

            if guest_id not in self._guest_sessions:
                self._guest_sessions[guest_id] = []
            self._guest_sessions[guest_id].insert(0, session_id)

            return session

    async def get_session(self, session_id: str) -> ChatSession | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    async def get_guest_sessions(self, guest_id: str) -> list[ChatSession]:
        """Get all sessions for a guest."""
        session_ids = self._guest_sessions.get(guest_id, [])
        sessions = []
        for sid in session_ids:
            session = self._sessions.get(sid)
            if session and session.is_active:
                sessions.append(session)
        return sessions

    async def get_session_lock(self, session_id: str) -> asyncio.Lock | None:
        """Get the lock for a session."""
        return self._session_locks.get(session_id)

    async def add_pending_approval(
        self,
        session_id: str,
        context: "ApprovalContext",
    ) -> asyncio.Future["ApprovalResult"]:
        """Add a pending approval request to a session.

        Returns a Future that will be resolved when user responds.
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        future: asyncio.Future["ApprovalResult"] = (
            asyncio.get_event_loop().create_future()
        )
        pending = PendingApproval(
            tool_call_id=context.tool_call_id,
            tool_name=context.tool_name,
            tool_args=context.tool_args,
            future=future,
        )
        session.pending_approvals[context.tool_call_id] = pending
        session.updated_at = datetime.now().isoformat()
        return future

    async def get_pending_approval(
        self,
        session_id: str,
        tool_call_id: str,
    ) -> PendingApproval | None:
        """Get a pending approval by tool call ID."""
        session = self._sessions.get(session_id)
        if not session:
            return None
        return session.pending_approvals.get(tool_call_id)

    async def resolve_approval(
        self,
        session_id: str,
        tool_call_id: str,
        result: "ApprovalResult",
    ) -> bool:
        """Resolve a pending approval.

        Returns True if resolved, False if not found.
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        pending = session.pending_approvals.pop(tool_call_id, None)
        if pending and pending.future and not pending.future.done():
            pending.future.set_result(result)
            return True

        if pending and pending.future is None:
            return True

        return False

    async def set_waiting_for_edit(
        self,
        session_id: str,
        tool_call_id: str | None,
    ) -> None:
        """Set the session to wait for edit input."""
        session = self._sessions.get(session_id)
        if session:
            session.waiting_for_edit = tool_call_id

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            if not session:
                return False

            session_ids = self._guest_sessions.get(session.guest_id, [])
            if session_id in session_ids:
                session_ids.remove(session_id)

            self._session_locks.pop(session_id, None)
            return True

    async def rename_session(
        self,
        session_id: str,
        new_name: str,
    ) -> bool:
        """Rename a session."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        session.conversation_name = new_name
        session.updated_at = datetime.now().isoformat()
        return True

    def _generate_name(self) -> str:
        """Generate a random conversation name."""
        adjectives = [
            "calm",
            "happy",
            "bright",
            "swift",
            "wise",
            "gentle",
            "bold",
            "clear",
            "keen",
            "warm",
            "cool",
            "pure",
            "fine",
            "soft",
            "strong",
        ]
        nouns = [
            "river",
            "mountain",
            "forest",
            "ocean",
            "meadow",
            "valley",
            "canyon",
            "desert",
            "island",
            "plain",
            "sunset",
            "dawn",
            "star",
            "moon",
            "cloud",
        ]
        import random

        adj = random.choice(adjectives)
        noun = random.choice(nouns)
        return f"{adj}-{noun}"


chat_session_manager = ChatSessionManager.get_instance()
