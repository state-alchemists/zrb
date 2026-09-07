"""Fitness function: slash-command dispatch must go through the UI facade.

`BaseUI` publishes a `handle_<x>_command` method for every slash command, and
`BaseUI` is the documented Level-3 extension point — a user subclasses it and
overrides one of those to customise a command.

That only works if `command_table()` binds the handler to the **UI instance**.
Binding it to the sub-part that owns the code (`self._conversation.handle_save_command`)
resolves the method once, at table-build time, off an object the subclass is
not in the MRO of — so the override is silently skipped and the built-in runs
instead. No error, no warning; the customisation just does nothing.

This is a real regression that shipped: see the 3.0.0b7 changelog entry.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.ui import SimpleUI, UIConfig


class _ProbeUI(SimpleUI):
    """Minimal concrete UI, plus an override of one command handler."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.overridden_with = []

    async def print(self, text: str, kind: str = "text") -> None: ...

    async def get_input(self, prompt: str) -> str:
        return ""

    def handle_save_command(self, text: str) -> bool:
        self.overridden_with.append(text)
        return True


@pytest.fixture
def ui():
    return _ProbeUI(
        ctx=Context(SharedContext(), "probe", 0, ""),
        llm_task=MagicMock(),
        history_manager=MagicMock(),
        config=UIConfig.default(),
    )


def test_every_command_handler_is_bound_to_the_ui_instance(ui):
    misbound = [
        f"{handler.__qualname__} is bound to "
        f"{type(getattr(handler, '__self__', None)).__name__}"
        for handler, *_ in ui.commands.command_table()
        if getattr(handler, "__self__", None) is not ui
    ]
    assert not misbound, (
        "Command handler(s) bound to something other than the UI instance. A "
        "subclass override of the same-named BaseUI method will be silently "
        "ignored. Bind to `base_ui.handle_x_command`, not "
        f"`self._part.handle_x_command`:\n  " + "\n  ".join(misbound)
    )


def test_a_subclass_override_actually_runs_when_the_command_is_typed(ui):
    """The behaviour the binding rule exists to protect."""
    ui.save_commands = ["/save"]
    asyncio.run(ui.dispatch_command("/save my-session"))
    assert ui.overridden_with == ["/save my-session"]
