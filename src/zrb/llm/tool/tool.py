from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from pydantic_ai import Tool as PydanticTool


def Tool(
    function: Callable[..., Any],
    name: str | None = None,
    description: str | None = None,
    *args,
    **kwargs,
) -> "PydanticTool":
    from pydantic_ai import Tool as PydanticTool

    return PydanticTool(function, name=name, description=description, *args, **kwargs)
