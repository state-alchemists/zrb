from __future__ import annotations

from typing import Protocol

from zrb.llm.any_agent import AnyAgent
from zrb.llm.any_sub_agent_definition import AnySubAgentDefinition


class AnySubAgentManager(Protocol):
    def scan(self) -> list[AnySubAgentDefinition]: ...

    def get_agent_definition(self, name: str) -> AnySubAgentDefinition | None: ...

    def create_agent(self, name: str, ctx: object | None = None, yolo: bool | None = None) -> AnyAgent | None: ...
