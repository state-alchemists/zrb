"""Tests for the intrinsic always-auto-approve registry (ADR-0062)."""

from __future__ import annotations

from zrb.llm.tool_call.always_approve import (
    is_always_auto_approve,
    register_always_auto_approve,
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
