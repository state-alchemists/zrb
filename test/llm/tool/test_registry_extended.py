from zrb.llm.tool.registry import ToolRegistry


def my_tool():
    pass


def test_registry_basic():
    registry = ToolRegistry()
    registry.register(my_tool)
    assert registry.get("my_tool") == my_tool
    assert len(registry.get_all()) == 1


def test_registry_alias():
    registry = ToolRegistry()
    registry.register(my_tool, aliases=["alias1", "alias2"])
    assert registry.get("my_tool") == my_tool
    assert registry.get("alias1") == my_tool
    assert registry.get("alias2") == my_tool
    assert len(registry.get_all()) == 3


def test_registry_custom_name():
    registry = ToolRegistry()
    registry.register(my_tool, name="custom_name")
    assert registry.get("custom_name") == my_tool
    assert registry.get("my_tool") is None


def test_registry_get_missing():
    registry = ToolRegistry()
    assert registry.get("non_existent") is None
