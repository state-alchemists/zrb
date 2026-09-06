"""`UIDefaultsMixin` — the inert half of the `AnyUI` contract.

Driven through a minimal host that implements only `AnyUI`'s six behavioral
methods, which is exactly the shape the mixin exists for.
"""

import asyncio

import pytest

from zrb.llm.ui.any_ui import AnyUI
from zrb.llm.ui.defaults import UIDefaultsMixin


class _MinimalUI(UIDefaultsMixin, AnyUI):
    """A UI that implements the behavioral half and nothing else."""

    async def ask_user(self, prompt, output_to_parent="", agent_id=None) -> str:
        return ""

    async def ask_user_choice(self, spec, agent_id=None) -> str:
        return ""

    def append_to_output(self, *values, **kwargs):
        pass

    def stream_to_parent(self, *values, **kwargs):
        pass

    async def run_interactive_command(self, cmd, shell=False):
        return None

    async def run_async(self):
        return None


def test_a_ui_implementing_only_the_behavioral_half_is_instantiable():
    """The point of the mixin: `AnyUI`'s state members stop being six more
    methods every custom UI has to write."""
    assert isinstance(_MinimalUI(), AnyUI)


def test_defaults_report_absence_rather_than_a_fake_value():
    ui = _MinimalUI()
    assert ui.is_thinking is False
    assert ui.llm_task is None
    assert ui.model is None
    assert ui.multi_ui_parent is None
    assert ui.tool_call_handler is None
    assert ui.yolo is False


def test_the_writable_members_round_trip():
    ui = _MinimalUI()
    ui.is_thinking = True
    ui.llm_task = "task"
    ui.model = "openai:gpt-5.6-luna"
    ui.multi_ui_parent = "parent"
    assert (ui.is_thinking, ui.llm_task, ui.model, ui.multi_ui_parent) == (
        True,
        "task",
        "openai:gpt-5.6-luna",
        "parent",
    )


def test_writes_do_not_leak_between_instances():
    """The class-level defaults are shadowed per instance, not shared."""
    first, second = _MinimalUI(), _MinimalUI()
    first.is_thinking = True
    first.model = "a-model"
    assert second.is_thinking is False
    assert second.model is None


@pytest.mark.asyncio
async def test_background_tasks_is_one_mutable_set_per_instance():
    """Callers `.add()`/`.discard()` on the returned set (see
    `default/lifecycle.py::_track_background`), so handing back a fresh set
    each call would silently drop every task registered on it."""
    ui = _MinimalUI()
    task = asyncio.create_task(asyncio.sleep(0))

    ui.background_tasks.add(task)
    assert task in ui.background_tasks  # same set, not a copy

    ui.background_tasks.discard(task)
    assert task not in ui.background_tasks
    await task

    # ...and not shared with the next instance.
    assert _MinimalUI().background_tasks == set()


def test_the_side_effect_hooks_are_silent_no_ops():
    """A UI with no live surface, no buffer and no pending confirmation has
    nothing to do for any of these — that is the answer, not an error."""
    ui = _MinimalUI()
    assert ui.invalidate_ui() is None
    assert ui.flush_to_parent() is None
    assert ui.cancel_pending_confirmations() is None
    assert ui.cancel_pending_confirmations(flush=False) is None


def test_a_host_implementing_a_member_for_real_wins_over_the_default():
    """MRO order matters: `BaseUI` and `MultiUI` mix this in for the members
    they do not track, while their own definitions take precedence."""

    class _RealThinking(_MinimalUI):
        @property
        def is_thinking(self) -> bool:
            return True

    assert _RealThinking().is_thinking is True
