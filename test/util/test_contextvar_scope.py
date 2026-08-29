"""Tests for the `scoped()` ContextVar RAII primitive."""

from contextvars import ContextVar

import pytest

from zrb.util.contextvar_scope import scoped

_var: ContextVar[str] = ContextVar("_test_contextvar_scope_var", default="default")


def test_scoped_sets_value_inside_the_block():
    with scoped(_var, "inside"):
        assert _var.get() == "inside"


def test_scoped_resets_after_the_block():
    with scoped(_var, "inside"):
        pass
    assert _var.get() == "default"


def test_scoped_resets_on_exception():
    with pytest.raises(RuntimeError):
        with scoped(_var, "inside"):
            assert _var.get() == "inside"
            raise RuntimeError("boom")
    assert _var.get() == "default"


def test_scoped_restores_prior_non_default_value():
    token = _var.set("outer")
    try:
        with scoped(_var, "inner"):
            assert _var.get() == "inner"
        assert _var.get() == "outer"
    finally:
        _var.reset(token)
