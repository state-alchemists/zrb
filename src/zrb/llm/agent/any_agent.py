from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from zrb.llm.agent.any_agent_result import AnyAgentResult


class AnyAgent(Protocol):
    async def run(self, message: object, **kwargs: object) -> AnyAgentResult: ...
