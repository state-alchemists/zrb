"""Tests for `Tpl`, the explicit opt-in to template rendering."""

from zrb.attr.tpl import Tpl
from zrb.context.shared_context import SharedContext
from zrb.util.attr import get_bool_attr, get_int_attr, get_str_attr


def test_tpl_renders_against_the_context():
    ctx = SharedContext(input={"who": "world"})
    assert Tpl("hello {ctx.input.who}")(ctx) == "hello world"


def test_tpl_exposes_its_unrendered_template():
    assert Tpl("{ctx.input.x}").template == "{ctx.input.x}"


def test_tpl_repr_shows_the_template():
    assert repr(Tpl("{ctx.input.x}")) == "Tpl('{ctx.input.x}')"


def test_tpl_equality_is_by_template():
    assert Tpl("a") == Tpl("a")
    assert Tpl("a") != Tpl("b")
    assert Tpl("a") != "a"
    assert len({Tpl("a"), Tpl("a"), Tpl("b")}) == 2


def test_a_bare_string_attr_is_a_literal():
    """The whole point: braces in a plain string reach the consumer untouched."""
    ctx = SharedContext(input={"who": "world"})
    assert get_str_attr(ctx, "hello {ctx.input.who}") == "hello {ctx.input.who}"


def test_a_tpl_attr_is_rendered():
    ctx = SharedContext(input={"who": "world"})
    assert get_str_attr(ctx, Tpl("hello {ctx.input.who}")) == "hello world"


def test_tpl_feeds_the_typed_getters():
    """`Tpl` renders to text, which the typed getters then coerce."""
    ctx = SharedContext(input={"flag": "true", "count": "7"})
    assert get_bool_attr(ctx, Tpl("{ctx.input.flag}")) is True
    assert get_int_attr(ctx, Tpl("{ctx.input.count}")) == 7


def test_tpl_binds_loop_values_eagerly():
    """A `Tpl` built from an f-string captures the loop variable's *value*,
    where a closure would capture the variable and yield the last one."""
    ctx = SharedContext()
    tpls = [Tpl(f"item-{n}") for n in range(3)]
    lambdas = [lambda c: f"item-{n}" for n in range(3)]

    assert [t(ctx) for t in tpls] == ["item-0", "item-1", "item-2"]
    assert [f(ctx) for f in lambdas] == ["item-2", "item-2", "item-2"]
