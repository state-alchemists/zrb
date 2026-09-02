from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from zrb.llm.agent.types import ToolCallPart
    from zrb.llm.ui.any_ui import AnyUI


ResponseHandler = Callable[
    [
        "AnyUI",
        "ToolCallPart",
        str,
        Callable[["AnyUI", "ToolCallPart", str], Awaitable[Any]],
    ],
    Awaitable[Any],
]

ToolPolicy = Callable[
    [
        "AnyUI",
        "ToolCallPart",
        Callable[["AnyUI", "ToolCallPart"], Awaitable[Any]],
    ],
    Awaitable[Any],
]

ArgumentFormatter = Callable[["AnyUI", "ToolCallPart", str], Awaitable[str | None]]
