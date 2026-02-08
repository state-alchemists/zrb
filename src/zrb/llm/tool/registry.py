from collections.abc import Callable


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Callable] = {}

    def register(
        self,
        tool: Callable,
        name: str | None = None,
        aliases: list[str] | None = None,
    ):
        """
        Register a tool with an optional name and aliases.
        """
        tool_name = name or getattr(tool, "__name__", str(tool))
        self._tools[tool_name] = tool
        if aliases:
            for alias in aliases:
                self._tools[alias] = tool

    def get(self, name: str) -> Callable | None:
        """
        Get a tool by name or alias.
        """
        return self._tools.get(name)

    def get_all(self) -> dict[str, Callable]:
        """
        Get all registered tools (including aliases).
        """
        return self._tools.copy()


tool_registry = ToolRegistry()
