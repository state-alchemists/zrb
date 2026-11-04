"""Tests for the two approval registries: intrinsic and default (ADR-0062, 0139)."""

from __future__ import annotations

from zrb.llm.tool_call.always_approve import (
    is_always_auto_approve,
    is_default_auto_approve,
    register_always_auto_approve,
    register_default_auto_approve,
    register_default_auto_approve_if,
)


def test_unregistered_tool_is_not_auto_approved():
    assert is_always_auto_approve("SomeUnregisteredTool") is False


def test_register_then_query_round_trip():
    register_always_auto_approve("WidgetTool")
    assert is_always_auto_approve("WidgetTool") is True


def test_register_accepts_multiple_names():
    register_always_auto_approve("AlphaTool", "BetaTool")
    assert is_always_auto_approve("AlphaTool") is True
    assert is_always_auto_approve("BetaTool") is True


def test_ask_user_question_self_registers_on_import():
    # Importing the tool module must register its LLM-visible name.
    import zrb.llm.tool.ask  # noqa: F401

    assert is_always_auto_approve("AskUserQuestion") is True


def test_a_default_approved_tool_is_approved_for_every_call():
    register_default_auto_approve("ProbeDefaultTool")
    assert is_default_auto_approve("ProbeDefaultTool") is True
    assert is_default_auto_approve("ProbeDefaultTool", {"any": "args"}) is True


def test_an_argument_gated_default_is_approved_only_for_the_calls_it_accepts():
    """The rename dry run: the same tool, bounded by one argument."""
    register_default_auto_approve_if(
        "ProbeGatedTool", lambda args: args.get("dry_run") is True
    )
    assert is_default_auto_approve("ProbeGatedTool", {"dry_run": True}) is True
    assert is_default_auto_approve("ProbeGatedTool", {"dry_run": False}) is False
    assert is_default_auto_approve("ProbeGatedTool", {}) is False


def test_an_argument_gated_default_does_not_approve_unparseable_args():
    register_default_auto_approve_if("ProbeGatedTool2", lambda args: True)
    assert is_default_auto_approve("ProbeGatedTool2", None) is False


def test_an_unregistered_tool_is_not_default_approved():
    assert is_default_auto_approve("SomeUnregisteredTool") is False
    assert is_default_auto_approve("SomeUnregisteredTool", {"dry_run": True}) is False
