from __future__ import annotations

from typing import Protocol

from zrb.llm.any_agent import AnyAgent


class AnyAgentRunner(Protocol):
    def create_agent(self, **kwargs: object) -> AnyAgent: ...

    async def run_agent(self, **kwargs: object) -> tuple[object, list[object]]: ...
