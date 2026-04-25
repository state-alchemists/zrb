"""Tests for agent runtime-state wrappers (zrb.llm.agent.runtime_state)."""

from __future__ import annotations

import asyncio

import pytest

from zrb.llm.agent.runtime_state import (
    current_approval_channel,
    current_tool_confirmation,
    current_ui,
    current_yolo,
    get_current_approval_channel,
    get_current_tool_confirmation,
    get_current_ui,
    get_current_yolo,
)


def test_default_values_are_safe():
    # Each ContextVar declares a sensible default; the wrappers must reflect it.
    assert get_current_ui() is None
    assert get_current_yolo() is False
    assert get_current_tool_confirmation() is None
    assert get_current_approval_channel() is None


def test_wrapper_reads_value_set_via_underlying_contextvar():
    sentinel_ui = object()
    token = current_ui.set(sentinel_ui)
    try:
        assert get_current_ui() is sentinel_ui
    finally:
        current_ui.reset(token)
    assert get_current_ui() is None


def test_yolo_wrapper_reads_underlying_var():
    token = current_yolo.set(True)
    try:
        assert get_current_yolo() is True
    finally:
        current_yolo.reset(token)
    assert get_current_yolo() is False


def test_tool_confirmation_wrapper_reads_underlying_var():
    def fake_confirmation(_call):
        return None

    token = current_tool_confirmation.set(fake_confirmation)
    try:
        assert get_current_tool_confirmation() is fake_confirmation
    finally:
        current_tool_confirmation.reset(token)
    assert get_current_tool_confirmation() is None


def test_approval_channel_wrapper_reads_underlying_var():
    sentinel_channel = object()
    token = current_approval_channel.set(sentinel_channel)
    try:
        assert get_current_approval_channel() is sentinel_channel
    finally:
        current_approval_channel.reset(token)
    assert get_current_approval_channel() is None


def test_wrappers_are_isolated_per_task():
    """Each asyncio task gets its own copy of the ContextVar."""
    sentinel_a = object()
    sentinel_b = object()
    captured: dict[str, object | None] = {}

    async def task_a():
        token = current_ui.set(sentinel_a)
        try:
            await asyncio.sleep(0.01)
            captured["a"] = get_current_ui()
        finally:
            current_ui.reset(token)

    async def task_b():
        token = current_ui.set(sentinel_b)
        try:
            await asyncio.sleep(0.01)
            captured["b"] = get_current_ui()
        finally:
            current_ui.reset(token)

    async def runner():
        await asyncio.gather(task_a(), task_b())

    asyncio.run(runner())
    assert captured["a"] is sentinel_a
    assert captured["b"] is sentinel_b


@pytest.mark.parametrize(
    "wrapper, var, value",
    [
        (get_current_ui, current_ui, "ui-marker"),
        (get_current_yolo, current_yolo, True),
        (get_current_tool_confirmation, current_tool_confirmation, lambda c: None),
        (get_current_approval_channel, current_approval_channel, "chan-marker"),
    ],
)
def test_wrapper_matches_underlying_get(wrapper, var, value):
    token = var.set(value)
    try:
        assert wrapper() == var.get()
    finally:
        var.reset(token)
