from zrb.llm.tool.registry import ToolRegistry


def my_tool():
    pass


def test_registry_basic():
    registry = ToolRegistry()
    registry.register(my_tool)
    assert registry.get("my_tool") == my_tool
    assert len(registry.get_all()) == 1


def test_registry_get_missing():
    registry = ToolRegistry()
    assert registry.get("non_existent") is None
