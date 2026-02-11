from collections.abc import Callable


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Callable] = {}

    def register(
        self,
        tool: Callable,
    ):
        """
        Register a tool.
        """
        tool_name = getattr(tool, "__name__", str(tool))
        self._tools[tool_name] = tool

    def get(self, name: str) -> Callable | None:
        """
        Get a tool by name.
        """
        return self._tools.get(name)

    def get_all(self) -> dict[str, Callable]:
        """
        Get all registered tools.
        """
        return self._tools.copy()


tool_registry = ToolRegistry()
