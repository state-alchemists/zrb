from __future__ import annotations

from typing import Protocol

from zrb.llm.any_agent_result import AnyAgentResult


class AnyAgent(Protocol):
    async def run(self, message: object, **kwargs: object) -> AnyAgentResult: ...
