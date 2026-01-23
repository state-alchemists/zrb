from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable

from zrb.llm.tool_call.ui_protocol import UIProtocol

if TYPE_CHECKING:
    from pydantic_ai import ToolCallPart


ResponseHandler = Callable[
    [
        UIProtocol,
        "ToolCallPart",
        str,
        Callable[[UIProtocol, "ToolCallPart", str], Awaitable[Any]],
    ],
    Awaitable[Any],
]

ToolPolicy = Callable[
    [
        "ToolCallPart",
        Callable[["ToolCallPart"], Awaitable[Any]],
    ],
    Awaitable[Any],
]

ArgumentFormatter = Callable[[UIProtocol, "ToolCallPart", str], Awaitable[str | None]]
