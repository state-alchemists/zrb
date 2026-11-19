from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from zrb.llm.engine.agent.any_agent import AnyAgent
    from zrb.llm.orchestration.subagent.any_sub_agent_definition import (
        AnySubAgentDefinition,
    )


class AnySubAgentManager(Protocol):
    def scan(self) -> list[AnySubAgentDefinition]: ...

    def get_agent_definition(self, name: str) -> AnySubAgentDefinition | None: ...

    def create_agent(
        self, name: str, ctx: object | None = None, yolo: bool | None = None
    ) -> AnyAgent | None: ...

    # A host may register tools on the manager itself (`append_tool`,
    # `append_tool_factory`), and those are as much a part of what delegation
    # offers as the agents are — an agent hook names them in its `tools:` list.
    # Declared loosely on purpose: the manager returns pydantic-ai `Tool`
    # objects, and a contract may not import what it does not need to name.
    def get_tool_registry(self) -> Mapping[str, object]: ...

    def get_tool_factories(self) -> Sequence[Callable[..., object]]: ...
