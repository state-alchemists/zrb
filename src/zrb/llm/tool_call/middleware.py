from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from zrb.llm.agent.types import ToolCallPart
    from zrb.llm.ui.any_agent_output import AnyAgentOutput


ResponseHandler = Callable[
    [
        "AnyAgentOutput",
        "ToolCallPart",
        str,
        Callable[["AnyAgentOutput", "ToolCallPart", str], Awaitable[Any]],
    ],
    Awaitable[Any],
]

ToolPolicy = Callable[
    [
        "AnyAgentOutput",
        "ToolCallPart",
        Callable[["AnyAgentOutput", "ToolCallPart"], Awaitable[Any]],
    ],
    Awaitable[Any],
]

ArgumentFormatter = Callable[
    ["AnyAgentOutput", "ToolCallPart", str], Awaitable[str | None]
]
