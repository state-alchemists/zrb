"""Unit tests for resolve_factory_items."""

from zrb.llm.factory_resolver import resolve_factory_items


def test_static_items_only():
    assert resolve_factory_items(["a", "b"], [], ctx=None) == ["a", "b"]


def test_does_not_mutate_input_list():
    static = ["a"]
    resolve_factory_items(static, [lambda ctx: "b"], ctx=None)
    assert static == ["a"]


def test_factory_returning_single_item_is_appended():
    result = resolve_factory_items([], [lambda ctx: "x"], ctx=None)
    assert result == ["x"]


def test_factory_returning_list_is_flattened():
    result = resolve_factory_items([], [lambda ctx: ["x", "y"]], ctx=None)
    assert result == ["x", "y"]


def test_static_then_factories_order_preserved():
    factories = [lambda ctx: "c", lambda ctx: ["d", "e"]]
    result = resolve_factory_items(["a", "b"], factories, ctx=None)
    assert result == ["a", "b", "c", "d", "e"]


def test_ctx_is_passed_to_factories():
    seen = []
    resolve_factory_items([], [lambda ctx: seen.append(ctx) or "x"], ctx="CTX")
    assert seen == ["CTX"]
