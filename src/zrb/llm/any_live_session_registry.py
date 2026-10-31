from __future__ import annotations

from typing import Protocol

from zrb.llm.any_live_sub_agent_session import AnyLiveSubAgentSession
from zrb.llm.any_sub_agent_manager import AnySubAgentManager


class AnyLiveSessionRegistry(Protocol):
    def add_session(
        self,
        session_id: str,
        agent_id: str,
        agent_name: str,
        sub_agent_manager: AnySubAgentManager,
        buffered_ui: object,
        yolo_override: bool | None = None,
    ) -> AnyLiveSubAgentSession: ...

    def mark_turn_finished(self, session_id: str, agent_id: str, history: list[object]) -> None: ...

    def has_message_budget(self, session_id: str, agent_id: str) -> bool: ...

    def describe_send_refusal(self, session_id: str, agent_id: str) -> str: ...

    def record_agent_message(self, session_id: str, agent_id: str) -> None: ...

    async def send_message(self, session_id: str, agent_id: str, text: str) -> object: ...
